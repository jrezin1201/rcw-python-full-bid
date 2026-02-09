#!/usr/bin/env venv/bin/python
"""
Simple test to verify if modifications are actually being processed.
"""
import pandas as pd
import requests
import json
import time
import os
import shutil

API_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY", "test-api-key")

def create_simple_test():
    """Create a simple modified test file."""

    print("Creating simple test file with known modifications...")

    # Copy the original file
    shutil.copy('baycrest_new.xlsx', 'simple_test.xlsx')

    # Load and modify specific values
    xl = pd.ExcelFile('simple_test.xlsx')
    sheets = {}

    # Load all sheets
    for sheet_name in xl.sheet_names:
        sheets[sheet_name] = pd.read_excel('simple_test.xlsx', sheet_name=sheet_name)

    # Modify the '1 Bldg' sheet with VERY SPECIFIC values
    df = sheets['1 Bldg']

    # Find and modify specific items by searching column B
    modifications = []
    for i in range(len(df)):
        cell_value = df.iloc[i, 1]  # Column B
        if pd.notna(cell_value):
            if cell_value == '1 Bed Room Count':
                old_val = df.iloc[i, 2]
                df.iloc[i, 2] = 777  # Set to 777 (was 333)
                modifications.append(f"1BR: {old_val} -> 777")
            elif cell_value == '2 Bedroom Count':
                old_val = df.iloc[i, 2]
                df.iloc[i, 2] = 888  # Set to 888 (was 134)
                modifications.append(f"2BR: {old_val} -> 888")
            elif cell_value == 'Total SF':
                old_val = df.iloc[i, 2]
                df.iloc[i, 2] = 999999  # Set to 999999 (was 410064)
                modifications.append(f"Total SF: {old_val} -> 999999")

    sheets['1 Bldg'] = df

    # Write back all sheets
    with pd.ExcelWriter('simple_test.xlsx', engine='openpyxl') as writer:
        for sheet_name, sheet_df in sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Made {len(modifications)} modifications:")
    for mod in modifications:
        print(f"  • {mod}")

    # Verify the file was written correctly
    verify_df = pd.read_excel('simple_test.xlsx', sheet_name='1 Bldg')
    print("\nVerifying file contents:")
    for i in range(len(verify_df)):
        cell_value = verify_df.iloc[i, 1]
        if pd.notna(cell_value):
            if cell_value == '1 Bed Room Count':
                print(f"  • 1BR Count in file: {verify_df.iloc[i, 2]} (should be 777)")
            elif cell_value == '2 Bedroom Count':
                print(f"  • 2BR Count in file: {verify_df.iloc[i, 2]} (should be 888)")
            elif cell_value == 'Total SF':
                print(f"  • Total SF in file: {verify_df.iloc[i, 2]} (should be 999999)")

    return 'simple_test.xlsx'

def test_simple_file(file_path):
    """Test the simple file."""

    print(f"\n{'='*60}")
    print("TESTING SIMPLE MODIFIED FILE")
    print('='*60)

    # Submit job
    print(f"\nSubmitting {file_path}...")
    with open(file_path, "rb") as f:
        response = requests.post(
            f"{API_URL}/api/v1/jobs/",
            headers={"X-API-Key": API_KEY},
            files={"file": (file_path, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"template": "baycrest_v1"}
        )

    if response.status_code not in [200, 201]:
        print(f"❌ Failed to submit: {response.status_code}")
        return

    job_id = response.json()["job_id"]
    print(f"Job ID: {job_id}")

    # Wait for completion
    print("Processing...")
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
        return

    # Check specific values
    print("\n" + "-"*40)
    print("CHECKING EXTRACTED VALUES:")
    print("-"*40)

    for section in result["result"]["sections"]:
        for item in section["items"]:
            if item["key"] == "1 Bedroom Count":
                expected = 777
                actual = item["qty_raw"]
                if abs(actual - expected) < 0.01:
                    print(f"✅ 1 Bedroom Count: {actual} (correct!)")
                else:
                    print(f"❌ 1 Bedroom Count: {actual} (expected {expected}) WRONG!")

            elif item["key"] == "2 Bedroom Count":
                expected = 888
                actual = item["qty_raw"]
                if abs(actual - expected) < 0.01:
                    print(f"✅ 2 Bedroom Count: {actual} (correct!)")
                else:
                    print(f"❌ 2 Bedroom Count: {actual} (expected {expected}) WRONG!")

            elif item["key"] == "Gross Building SF":
                expected = 999999
                actual = item["qty_raw"]
                if abs(actual - expected) < 0.01:
                    print(f"✅ Gross Building SF: {actual} (correct!)")
                else:
                    print(f"❌ Gross Building SF: {actual} (expected {expected}) WRONG!")

    # Check the uploaded file
    print(f"\nChecking uploaded file in: data/uploads/{job_id}/")
    import glob
    uploaded_files = glob.glob(f"data/uploads/{job_id}/*")
    if uploaded_files:
        print(f"Uploaded file: {uploaded_files[0]}")

        # Read the uploaded file to see what was actually processed
        uploaded_df = pd.read_excel(uploaded_files[0], sheet_name='1 Bldg')
        print("\nValues in uploaded file:")
        for i in range(len(uploaded_df)):
            cell_value = uploaded_df.iloc[i, 1]
            if pd.notna(cell_value):
                if cell_value == '1 Bed Room Count':
                    print(f"  • 1BR in uploaded: {uploaded_df.iloc[i, 2]}")
                elif cell_value == '2 Bedroom Count':
                    print(f"  • 2BR in uploaded: {uploaded_df.iloc[i, 2]}")

def main():
    print("="*60)
    print("SIMPLE ROBUSTNESS TEST")
    print("="*60)

    # Create test file
    test_file = create_simple_test()

    # Test it
    test_simple_file(test_file)

    print("\n" + "="*60)

if __name__ == "__main__":
    main()