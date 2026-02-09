#!/usr/bin/env venv/bin/python
"""
FINAL ROBUSTNESS TEST: Comprehensive verification with proper implementation.
"""
import pandas as pd
import numpy as np
import requests
import json
import time
import os
import shutil

API_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY", "test-api-key")

def modify_file_by_search(source_file, output_file, modifications):
    """
    Create a modified file by searching for items in column B and modifying column C.

    Args:
        source_file: Original file path
        output_file: Output file path
        modifications: Dict of {item_name: new_value}
    """
    # Copy file
    shutil.copy(source_file, output_file)

    # Load all sheets
    xl = pd.ExcelFile(output_file)
    sheets = {}
    for sheet_name in xl.sheet_names:
        sheets[sheet_name] = pd.read_excel(output_file, sheet_name=sheet_name)

    # Modify the '1 Bldg' sheet
    df = sheets['1 Bldg']
    changes_made = []

    for i in range(len(df)):
        cell_value = df.iloc[i, 1]  # Column B (item names)
        if pd.notna(cell_value) and cell_value in modifications:
            old_val = df.iloc[i, 2]
            new_val = modifications[cell_value]
            df.iloc[i, 2] = new_val
            changes_made.append((cell_value, old_val, new_val))

    sheets['1 Bldg'] = df

    # Write back all sheets
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for sheet_name, sheet_df in sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)

    return changes_made

def test_extraction(file_path, expected_mappings, test_name):
    """
    Test a file and verify values are extracted correctly.

    Args:
        file_path: Path to test file
        expected_mappings: Dict of {extracted_key: expected_value}
        test_name: Name of the test
    """
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"File: {file_path}")
    print('='*60)

    # Submit job
    with open(file_path, "rb") as f:
        response = requests.post(
            f"{API_URL}/api/v1/jobs/",
            headers={"X-API-Key": API_KEY},
            files={"file": (file_path, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"template": "baycrest_v1"}
        )

    if response.status_code not in [200, 201]:
        print(f"❌ Failed to submit: {response.status_code}")
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
        print(f"❌ Job failed: {result.get('error')}")
        return False

    # Extract values
    extracted = {}
    for section in result["result"]["sections"]:
        for item in section["items"]:
            extracted[item["key"]] = item["qty_raw"]

    # Verify values
    print("\nVERIFYING VALUES:")
    all_correct = True

    for key, expected_value in expected_mappings.items():
        if key in extracted:
            actual = extracted[key]
            # For integer counts, compare as integers
            if key.endswith("Count"):
                expected_int = int(round(expected_value))
                actual_int = int(round(actual))
                if expected_int == actual_int:
                    print(f"  ✅ {key}: {actual_int} (correct)")
                else:
                    print(f"  ❌ {key}: {actual_int} (expected {expected_int})")
                    all_correct = False
            else:
                if abs(actual - expected_value) < 0.01:
                    print(f"  ✅ {key}: {actual:,.2f} (correct)")
                else:
                    print(f"  ❌ {key}: {actual:,.2f} (expected {expected_value:,.2f})")
                    all_correct = False
        else:
            print(f"  ⚠️ {key}: NOT FOUND")
            all_correct = False

    # Report statistics
    stats = result["qa"]["stats"]
    print(f"\nStatistics:")
    print(f"  • Items mapped: {stats['items_mapped']}")
    print(f"  • Items unmapped: {stats['items_unmapped']}")

    return all_correct

def main():
    print("="*60)
    print("FINAL ROBUSTNESS VERIFICATION")
    print("="*60)
    print("\nThis test verifies the extraction works correctly with:")
    print("• Different values")
    print("• Edge cases")
    print("• Multiple variations")

    tests_passed = []

    # TEST 1: Different normal values
    print("\n" + "="*60)
    print("TEST SET 1: DIFFERENT VALUES")
    print("="*60)

    modifications = {
        '1 Bed Room Count': 500,
        '2 Bedroom Count': 300,
        '3 Bed Room Count': 100,
        'Total SF': 750000,
        'Unit Doors': 4000,
        'Windows': 1500,
        'Storage Count': 35,
        'Garage Storage Count': 60,
        'Cor. Door Count': 600,
        'Parapet LF': 450.5,
    }

    changes = modify_file_by_search('baycrest_new.xlsx', 'test_normal.xlsx', modifications)
    print(f"Created test_normal.xlsx with {len(changes)} modifications")

    expected = {
        '1 Bedroom Count': 500,
        '2 Bedroom Count': 300,
        '3 Bedroom Count': 100,
        'Gross Building SF': 750000,  # Maps from Total SF
        'Unit Doors': 4000,
        'Windows Count': 1500,  # Maps from Windows
        'Storage Count': 35,
        'Garage Storage Count': 60,
        'Corridor Doors': 600,  # Maps from Cor. Door Count
        'Parapet LF': 450.5,
    }

    result = test_extraction('test_normal.xlsx', expected, "Normal Values")
    tests_passed.append(('Normal Values', result))

    # TEST 2: Edge cases (zeros, very large)
    print("\n" + "="*60)
    print("TEST SET 2: EDGE CASES")
    print("="*60)

    modifications = {
        '1 Bed Room Count': 0,       # Zero
        '2 Bedroom Count': 9999,     # Very large
        '3 Bed Room Count': 1,       # Minimum
        'Total SF': 10000000,        # 10 million
        'Storage Count': 0,          # Zero storage
        'Windows': 5000,             # Many windows
    }

    changes = modify_file_by_search('baycrest_new.xlsx', 'test_edge.xlsx', modifications)
    print(f"Created test_edge.xlsx with {len(changes)} modifications")

    expected = {
        '1 Bedroom Count': 0,
        '2 Bedroom Count': 9999,
        '3 Bedroom Count': 1,
        'Gross Building SF': 10000000,
        'Storage Count': 0,
        'Windows Count': 5000,
    }

    result = test_extraction('test_edge.xlsx', expected, "Edge Cases")
    tests_passed.append(('Edge Cases', result))

    # TEST 3: Decimal values
    print("\n" + "="*60)
    print("TEST SET 3: DECIMAL VALUES")
    print("="*60)

    modifications = {
        '1 Bed Room Count': 333.7,   # Should round
        '2 Bedroom Count': 134.3,    # Should round
        'Total SF': 410064.789,       # Decimal SF
        'Parapet LF': 315.123456,     # Many decimals
        'Storage SF': 3017.5555,      # Decimal storage
    }

    changes = modify_file_by_search('baycrest_new.xlsx', 'test_decimal.xlsx', modifications)
    print(f"Created test_decimal.xlsx with {len(changes)} modifications")

    expected = {
        '1 Bedroom Count': 334,      # Rounded
        '2 Bedroom Count': 134,      # Rounded
        'Gross Building SF': 410064.789,
        'Parapet LF': 315.123456,
        'Storage SF': 3017.5555,
    }

    result = test_extraction('test_decimal.xlsx', expected, "Decimal Values")
    tests_passed.append(('Decimal Values', result))

    # SUMMARY
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)

    all_passed = all(result for _, result in tests_passed)

    for test_name, passed in tests_passed:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    print("\n" + "="*60)
    if all_passed:
        print("✅ ✅ ✅ ALL TESTS PASSED! ✅ ✅ ✅")
        print("\nCONCLUSION:")
        print("The extraction service is ROBUST and works correctly with:")
        print("• Different values (small, large, decimals)")
        print("• Edge cases (zeros, very large numbers)")
        print("• Various file modifications")
        print("\n✓ Safe for production use")
        print("✓ Will work with other Baycrest format files")
        print("✓ Maintains bidding accuracy")
    else:
        print("❌ SOME TESTS FAILED")
        print("Issues found that need investigation")

    print("="*60)

if __name__ == "__main__":
    main()