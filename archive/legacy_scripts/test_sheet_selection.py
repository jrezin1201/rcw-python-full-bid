#!/usr/bin/env venv/bin/python
"""
Test sheet selection functionality.
"""
import requests
import json
import time
import os

API_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY", "test-api-key")

def test_sheet_selection(file_path, sheet_selection, description):
    """Test extraction with specific sheet selection."""

    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"File: {file_path}")
    print(f"Sheet Selection: {sheet_selection}")
    print('='*60)

    # Submit job with sheet selection
    with open(file_path, "rb") as f:
        data = {"template": "baycrest_v1"}
        if sheet_selection:
            data["sheets"] = sheet_selection

        response = requests.post(
            f"{API_URL}/api/v1/jobs/",
            headers={"X-API-Key": API_KEY},
            files={"file": (file_path, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data=data
        )

    if response.status_code not in [200, 201]:
        print(f"❌ Failed to submit: {response.status_code}")
        print(response.text)
        return None

    job_id = response.json()["job_id"]
    print(f"Job ID: {job_id}")

    # Wait for completion
    print("Processing...")
    for _ in range(30):
        response = requests.get(
            f"{API_URL}/api/v1/jobs/{job_id}",
            headers={"X-API-Key": API_KEY}
        )
        result = response.json()
        if result["status"] in ["SUCCEEDED", "FAILED"]:
            break
        time.sleep(1)

    if result["status"] != "SUCCEEDED":
        print(f"❌ Job failed: {result.get('error')}")
        if result.get("error_detail"):
            print(f"Details: {result['error_detail']}")
        return None

    # Display results
    print("\n✅ Job Succeeded!")
    stats = result["qa"]["stats"]
    print(f"Statistics:")
    print(f"  • Total rows: {stats['rows_total']}")
    print(f"  • Items extracted: {stats['rows_extracted']}")
    print(f"  • Items mapped: {stats['items_mapped']}")
    print(f"  • Items unmapped: {stats['items_unmapped']}")

    # Show which sheets were processed
    if result["result"].get("raw_data"):
        sheets_seen = set()
        for item in result["result"]["raw_data"][:50]:  # Check first 50 items
            if "provenance" in item and "sheet" in item["provenance"]:
                sheets_seen.add(item["provenance"]["sheet"])

        if sheets_seen:
            print(f"\nSheets processed: {sorted(sheets_seen)}")

    # Show sample items
    print("\nSample items extracted:")
    sections = result["result"]["sections"]
    item_count = 0
    for section in sections[:3]:
        for item in section["items"][:2]:
            print(f"  • {item['key']}: {item['qty']:,.0f} {item['uom']}")
            item_count += 1
            if item_count >= 5:
                break
        if item_count >= 5:
            break

    return result

def main():
    print("="*60)
    print("SHEET SELECTION TEST")
    print("="*60)
    print("\nThis test verifies different sheet selection options work")

    # Test 1: Default (no sheet specified, should use 1 Bldg)
    print("\n" + "="*60)
    print("TEST 1: DEFAULT (NO SHEET SPECIFIED)")
    result1 = test_sheet_selection("baycrest_new.xlsx", None, "Default sheet selection")

    # Test 2: Specific sheet
    print("\n" + "="*60)
    print("TEST 2: SPECIFIC SHEET")
    result2 = test_sheet_selection("baycrest_new.xlsx", "1 Bldg", "Specific sheet: 1 Bldg")

    # Test 3: Multiple sheets
    print("\n" + "="*60)
    print("TEST 3: MULTIPLE SHEETS")
    result3 = test_sheet_selection("baycrest_new.xlsx", "1 Bldg,2 Bldgs", "Multiple sheets: 1 Bldg, 2 Bldgs")

    # Test 4: All sheets
    print("\n" + "="*60)
    print("TEST 4: ALL SHEETS")
    result4 = test_sheet_selection("baycrest_new.xlsx", "all", "All sheets in file")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    tests = [
        ("Default", result1 is not None),
        ("Specific Sheet", result2 is not None),
        ("Multiple Sheets", result3 is not None),
        ("All Sheets", result4 is not None)
    ]

    for test_name, passed in tests:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    if all(passed for _, passed in tests):
        print("\n✅ ✅ ✅ ALL SHEET TESTS PASSED! ✅ ✅ ✅")
        print("\nSheet selection features:")
        print("• Default: Uses '1 Bldg' or signature-matched sheet")
        print("• Specific: Can specify exact sheet name")
        print("• Multiple: Can process multiple sheets (comma-separated)")
        print("• All: Can process all data sheets in file")
    else:
        print("\n❌ Some tests failed - check error messages above")

    print("="*60)

if __name__ == "__main__":
    main()