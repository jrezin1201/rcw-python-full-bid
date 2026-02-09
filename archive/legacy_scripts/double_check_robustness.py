#!/usr/bin/env venv/bin/python
"""
DOUBLE CHECK: Comprehensive robustness verification.
This creates multiple test files with KNOWN values and verifies
that they are extracted EXACTLY correctly.
"""
import pandas as pd
import numpy as np
import requests
import json
import time
import os

API_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY", "test-api-key")

def create_test_file_1():
    """Create test file 1 with specific known values."""
    print("\nCreating Test File 1: Different quantities...")

    # Read original structure
    orig = pd.read_excel('baycrest_new.xlsx', sheet_name='1 Bldg')
    df = orig.copy()

    # Set SPECIFIC KNOWN VALUES we'll verify later
    test_values = {
        2: ('Studio Unit Count', 25),      # Row 2, Column B, Value 25
        3: ('1 Bed Room Count', 400),      # Row 3, Column B, Value 400
        4: ('2 Bedroom Count', 250),       # Row 4, Column B, Value 250
        5: ('3 Bed Room Count', 50),       # Row 5, Column B, Value 50
        7: ('Total SF', 525000),           # Row 7, Column B, Value 525000
        17: ('Cor. Door Count', 500),      # Corridor doors
        20: ('Storage Count', 30),         # Storage count
        54: ('Unit Doors', 3000),          # Unit doors
        56: ('Wardrobes', 200),            # Wardrobes
        57: ('W/D', 600),                  # Washer/Dryer
        60: ('Windows', 1200),             # Windows
        104: ('Garage Storage Count', 55), # Garage storage
    }

    for row, (item_name, value) in test_values.items():
        df.iloc[row-1, 2] = value  # Column C (index 2)

    # Save
    with pd.ExcelWriter('test_file_1.xlsx', engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='1 Bldg', index=False)
        # Copy other sheets
        for sheet in pd.ExcelFile('baycrest_new.xlsx').sheet_names:
            if sheet != '1 Bldg':
                pd.read_excel('baycrest_new.xlsx', sheet_name=sheet).to_excel(
                    writer, sheet_name=sheet, index=False)

    return 'test_file_1.xlsx', test_values

def create_test_file_2():
    """Create test file 2 with extreme values and extra items."""
    print("\nCreating Test File 2: Extreme values + extra items...")

    orig = pd.read_excel('baycrest_new.xlsx', sheet_name='1 Bldg')
    df = orig.copy()

    # Set EXTREME VALUES to test boundaries
    test_values = {
        2: ('Studio Unit Count', 0),         # Zero value
        3: ('1 Bed Room Count', 9999),       # Very large
        4: ('2 Bedroom Count', 1),           # Single unit
        7: ('Total SF', 10000000),           # 10 million SF
        17: ('Cor. Door Count', 1),          # Minimal
        54: ('Unit Doors', 10000),           # Very large
        104: ('Garage Storage Count', 999),  # Large
    }

    for row, (item_name, value) in test_values.items():
        df.iloc[row-1, 2] = value

    # Add completely new items (should go to unmapped)
    new_rows = pd.DataFrame([
        [None, 'Smart Home Systems', 450, None, None],
        [None, 'EV Charging Stations', 75, None, None],
        [None, 'Rooftop Garden SF', 8500.50, None, None],
    ], columns=df.columns)

    df = pd.concat([df.iloc[:30], new_rows, df.iloc[30:]], ignore_index=True)

    with pd.ExcelWriter('test_file_2.xlsx', engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='1 Bldg', index=False)
        for sheet in pd.ExcelFile('baycrest_new.xlsx').sheet_names:
            if sheet != '1 Bldg':
                pd.read_excel('baycrest_new.xlsx', sheet_name=sheet).to_excel(
                    writer, sheet_name=sheet, index=False)

    return 'test_file_2.xlsx', test_values

def create_test_file_3():
    """Create test file 3 with decimal values."""
    print("\nCreating Test File 3: Decimal/fractional values...")

    orig = pd.read_excel('baycrest_new.xlsx', sheet_name='1 Bldg')
    df = orig.copy()

    # Set DECIMAL VALUES to test precision
    test_values = {
        3: ('1 Bed Room Count', 333.5),      # Fractional units (should round)
        4: ('2 Bedroom Count', 134.75),      # Fractional units (should round)
        7: ('Total SF', 410064.123),         # Decimal SF
        17: ('Cor. Door Count', 367.9),      # Fractional doors (should round)
        31: ('Parapet LF', 315.6789),        # Precise LF
    }

    for row, (item_name, value) in test_values.items():
        df.iloc[row-1, 2] = value

    with pd.ExcelWriter('test_file_3.xlsx', engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='1 Bldg', index=False)
        for sheet in pd.ExcelFile('baycrest_new.xlsx').sheet_names:
            if sheet != '1 Bldg':
                pd.read_excel('baycrest_new.xlsx', sheet_name=sheet).to_excel(
                    writer, sheet_name=sheet, index=False)

    return 'test_file_3.xlsx', test_values

def test_extraction(file_name, expected_values):
    """Test a file and verify exact value extraction."""

    print(f"\n{'='*60}")
    print(f"Testing: {file_name}")
    print('='*60)

    # Submit job
    with open(file_name, "rb") as f:
        response = requests.post(
            f"{API_URL}/api/v1/jobs/",
            headers={"X-API-Key": API_KEY},
            files={"file": (file_name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"template": "baycrest_v1"}
        )

    if response.status_code not in [200, 201]:
        print(f"❌ FAILED to submit: {response.status_code}")
        return False

    job_id = response.json()["job_id"]

    # Wait for completion
    for _ in range(30):
        response = requests.get(
            f"{API_URL}/api/v1/jobs/{job_id}",
            headers={"X-API-Key": API_KEY}
        )
        if response.json()["status"] in ["SUCCEEDED", "FAILED"]:
            break
        time.sleep(1)

    result = response.json()

    if result["status"] != "SUCCEEDED":
        print(f"❌ Job FAILED: {result.get('error')}")
        return False

    # Build mapping of what was extracted
    extracted = {}
    for section in result["result"]["sections"]:
        for item in section["items"]:
            extracted[item["key"]] = item["qty_raw"]

    # VERIFY EXACT VALUES
    print("\nVERIFYING EXACT VALUES:")
    print("-" * 40)

    # Map row items to expected keys
    value_map = {
        'Studio Unit Count': 'Unit Count',  # Maps to Unit Count
        '1 Bed Room Count': '1 Bedroom Count',
        '2 Bedroom Count': '2 Bedroom Count',
        '3 Bed Room Count': '3 Bedroom Count',
        'Total SF': 'Gross Building SF',
        'Cor. Door Count': 'Corridor Doors',
        'Storage Count': 'Storage Count',
        'Unit Doors': 'Unit Doors',
        'Wardrobes': 'Wardrobes',
        'W/D': 'Washer/Dryer',
        'Windows': 'Windows Count',
        'Garage Storage Count': 'Garage Storage Count',
        'Parapet LF': 'Parapet LF',
    }

    all_correct = True
    for row, (item_name, expected) in expected_values.items():
        mapped_name = value_map.get(item_name, item_name)

        if mapped_name in extracted:
            actual = extracted[mapped_name]

            # For EA items, they should be rounded
            if mapped_name in ['1 Bedroom Count', '2 Bedroom Count', '3 Bedroom Count',
                              'Corridor Doors', 'Unit Count']:
                expected_compare = round(expected) if isinstance(expected, float) else expected
                actual_compare = round(actual) if isinstance(actual, float) else actual
            else:
                expected_compare = expected
                actual_compare = actual

            if abs(expected_compare - actual_compare) < 0.01:
                print(f"  ✅ {item_name}: {actual:,.2f} (expected {expected:,.2f})")
            else:
                print(f"  ❌ {item_name}: {actual:,.2f} (expected {expected:,.2f}) WRONG!")
                all_correct = False
        else:
            print(f"  ⚠️ {item_name}: NOT FOUND in results")
            all_correct = False

    # Check unmapped items
    unmapped = result["result"].get("unmapped", [])
    if unmapped:
        print(f"\n📋 Unmapped items: {len(unmapped)}")
        for item in unmapped[:3]:
            print(f"  • {item['classification']}")

    return all_correct

def main():
    print("="*60)
    print("DOUBLE CHECK: COMPREHENSIVE ROBUSTNESS VERIFICATION")
    print("="*60)
    print("\nThis test creates files with KNOWN values and verifies")
    print("they are extracted EXACTLY correctly.")

    # Create and test multiple files
    test_files = [
        create_test_file_1(),
        create_test_file_2(),
        create_test_file_3(),
    ]

    results = []
    for file_name, expected_values in test_files:
        success = test_extraction(file_name, expected_values)
        results.append((file_name, success))

    # Summary
    print("\n" + "="*60)
    print("DOUBLE CHECK SUMMARY")
    print("="*60)

    all_passed = all(r[1] for r in results)

    for file_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{file_name}: {status}")

    if all_passed:
        print("\n✅ ✅ ✅ ALL TESTS PASSED! ✅ ✅ ✅")
        print("\nCONCLUSION: The solution is ROBUST and ACCURATE")
        print("• Handles different values correctly")
        print("• Maintains exact precision for bidding")
        print("• Properly handles edge cases")
        print("• Safe for production use")
    else:
        print("\n❌ SOME TESTS FAILED!")
        print("Need to investigate failures before production use")

    print("\n" + "="*60)

if __name__ == "__main__":
    main()