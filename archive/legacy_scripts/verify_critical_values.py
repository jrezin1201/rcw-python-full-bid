#!/usr/bin/env venv/bin/python
"""
Verify critical values are correctly mapped after the fix.
This is essential for construction bidding accuracy.
"""
import json
import requests
import time
import os

API_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY", "test-api-key")

# Critical values to verify (from the actual Excel data)
EXPECTED_VALUES = {
    "1 Bedroom Count": 333,
    "2 Bedroom Count": 134,  # NOT 333!
    "3 Bedroom Count": 0,    # NOT 333!
    "Washer/Dryer": 467,     # NOT 1449!
    "Unit Doors": 2393,
    "Windows Count": 928,
    "Garage Storage Count": 40,  # NOT mixed with general storage (19)
    "Storage Count": 19,
    "Gross Building SF": 410064,  # Maps from "Total SF"
}

def verify_baycrest_extraction():
    """Test and verify critical values are correctly extracted."""

    print("=" * 60)
    print("CRITICAL VALUE VERIFICATION TEST")
    print("=" * 60)

    # 1. Submit job
    print("\n1. Submitting job with baycrest_v1 template...")
    with open("baycrest_new.xlsx", "rb") as f:
        response = requests.post(
            f"{API_URL}/api/v1/jobs/",
            headers={"X-API-Key": API_KEY},
            files={"file": ("baycrest_new.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"template": "baycrest_v1"}
        )

    if response.status_code not in [200, 201]:
        print(f"Error submitting job: {response.status_code}")
        return

    job_data = response.json()
    job_id = job_data["job_id"]
    print(f"Job submitted: {job_id}")

    # 2. Wait for completion
    print("\n2. Waiting for job to complete...")
    for i in range(30):
        response = requests.get(
            f"{API_URL}/api/v1/jobs/{job_id}",
            headers={"X-API-Key": API_KEY}
        )

        job_status = response.json()
        status = job_status["status"]

        if status in ["SUCCEEDED", "FAILED"]:
            break
        time.sleep(1)

    # 3. Verify critical values
    print("\n3. VERIFYING CRITICAL VALUES:")
    print("-" * 40)

    if job_status['status'] != 'SUCCEEDED':
        print(f"ERROR: Job failed with status {job_status['status']}")
        return

    result = job_status.get('result', {})
    sections = result.get('sections', [])

    # Build a flat dictionary of all mapped items
    mapped_values = {}
    for section in sections:
        for item in section.get('items', []):
            key = item['key']
            qty = item['qty_raw']  # Use raw value for exact comparison
            source = item.get('source_classification', '')
            mapped_values[key] = {
                'qty': qty,
                'source': source
            }

    # Check critical values
    errors = []
    for item_name, expected_value in EXPECTED_VALUES.items():
        if item_name in mapped_values:
            actual_value = mapped_values[item_name]['qty']
            source = mapped_values[item_name]['source']

            if abs(actual_value - expected_value) > 0.01:  # Allow tiny float differences
                errors.append({
                    'item': item_name,
                    'expected': expected_value,
                    'actual': actual_value,
                    'source': source,
                    'difference': actual_value - expected_value
                })
                print(f"❌ {item_name}: WRONG VALUE!")
                print(f"   Expected: {expected_value}")
                print(f"   Got: {actual_value} (from '{source}')")
                print(f"   Difference: ${(actual_value - expected_value):,.0f} error in bid!")
            else:
                print(f"✅ {item_name}: {actual_value:,.0f} (correct)")
        else:
            print(f"⚠️ {item_name}: NOT FOUND in mapped items")
            errors.append({
                'item': item_name,
                'expected': expected_value,
                'actual': None,
                'source': 'NOT MAPPED'
            })

    # 4. Summary
    print("\n" + "=" * 60)
    if errors:
        print("❌ CRITICAL ERRORS FOUND!")
        print("-" * 40)
        total_error = 0
        for err in errors:
            if err['actual'] is not None:
                # Calculate potential cost impact (example: $100/SF or $1000/unit)
                if 'SF' in err['item']:
                    cost_impact = abs(err['difference']) * 100  # $100/SF
                    print(f"• {err['item']}: ${cost_impact:,.0f} potential error")
                else:
                    cost_impact = abs(err['difference']) * 1000  # $1000/unit
                    print(f"• {err['item']}: ${cost_impact:,.0f} potential error")
                total_error += cost_impact

        print(f"\nTOTAL POTENTIAL BID ERROR: ${total_error:,.0f}")
        print("THIS COULD COST HUNDREDS OF THOUSANDS IN MISBIDS!")
    else:
        print("✅ ALL CRITICAL VALUES VERIFIED CORRECTLY!")
        print("Safe to use for bidding.")

    print("=" * 60)

if __name__ == "__main__":
    verify_baycrest_extraction()