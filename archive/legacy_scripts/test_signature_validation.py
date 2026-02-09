#!/usr/bin/env python3
"""
Test script for Baycrest signature validation.

This script tests:
1. Direct validation function
2. Debug API endpoint
3. Full job processing with validation
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.validators.baycrest_signature import validate_baycrest_workbook
from openpyxl import Workbook


def create_test_baycrest_file(sheet_name: str = "1 Bldg"):
    """Create a test Baycrest format Excel file with proper takeoff sheet."""
    wb = Workbook()

    # Create the takeoff sheet (1 Bldg) with Baycrest content structure
    takeoff_sheet = wb.active
    takeoff_sheet.title = sheet_name

    # Add Baycrest section headers in column A and data in B/C
    # Section: General
    takeoff_sheet['A1'] = "General"
    takeoff_sheet['B2'] = "Stucco Wall SF"
    takeoff_sheet['C2'] = 15000
    takeoff_sheet['B3'] = "Unit Doors"
    takeoff_sheet['C3'] = 150

    # Section: Corridors
    takeoff_sheet['A5'] = "Corridors"
    takeoff_sheet['B6'] = "Corridor Wall SF"
    takeoff_sheet['C6'] = 8000
    takeoff_sheet['B7'] = "Ceiling SF"
    takeoff_sheet['C7'] = 4500

    # Section: Exterior
    takeoff_sheet['A9'] = "Exterior"
    takeoff_sheet['B10'] = "Exterior Wall SF"
    takeoff_sheet['C10'] = 25000
    takeoff_sheet['B11'] = "Windows"
    takeoff_sheet['C11'] = 200

    # Section: Units
    takeoff_sheet['A13'] = "Units"
    takeoff_sheet['B14'] = "Unit Wall SF"
    takeoff_sheet['C14'] = 50000
    takeoff_sheet['B15'] = "Unit Ceiling SF"
    takeoff_sheet['C15'] = 30000
    takeoff_sheet['B16'] = "Bathroom SF"
    takeoff_sheet['C16'] = 5000

    # Section: Stairs
    takeoff_sheet['A18'] = "Stairs"
    takeoff_sheet['B19'] = "Stair Treads"
    takeoff_sheet['C19'] = 400
    takeoff_sheet['B20'] = "Handrails LF"
    takeoff_sheet['C20'] = 800

    # Section: Amenity
    takeoff_sheet['A22'] = "Amenity"
    takeoff_sheet['B23'] = "Clubhouse SF"
    takeoff_sheet['C23'] = 3500
    takeoff_sheet['B24'] = "Pool Deck SF"
    takeoff_sheet['C24'] = 2000

    # Section: Garage
    takeoff_sheet['A26'] = "Garage"
    takeoff_sheet['B27'] = "Garage Wall SF"
    takeoff_sheet['C27'] = 12000
    takeoff_sheet['B28'] = "Parking Spaces"
    takeoff_sheet['C28'] = 150

    # Section: Landscape
    takeoff_sheet['A30'] = "Landscape"
    takeoff_sheet['B31'] = "Planting Beds SF"
    takeoff_sheet['C31'] = 5000
    takeoff_sheet['B32'] = "Irrigation LF"
    takeoff_sheet['C32'] = 3000

    # Add more data rows to meet threshold (need at least 15 data rows)
    for i in range(33, 50):
        takeoff_sheet[f'B{i}'] = f"Item {i}"
        takeoff_sheet[f'C{i}'] = 100 + i

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        wb.save(tmp.name)
        return tmp.name


def create_wrong_format_file():
    """Create a file that doesn't match Baycrest format."""
    wb = Workbook()

    # Create a sheet with different structure
    sheet = wb.active
    sheet.title = "Sample"

    # Add different headers
    sheet['A1'] = "Product"
    sheet['B1'] = "Price"
    sheet['C1'] = "Quantity"

    # Add some data
    sheet['A2'] = "Item 1"
    sheet['B2'] = 100
    sheet['C2'] = 5

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        wb.save(tmp.name)
        return tmp.name


def test_direct_validation():
    """Test the validation function directly."""
    print("\n=== Testing Direct Validation ===\n")

    # Test with correct format
    print("1. Testing with correct Baycrest format...")
    correct_file = create_test_baycrest_file()
    try:
        result = validate_baycrest_workbook(correct_file)
        print(f"   ✓ Validation result: {'PASS' if result.ok else 'FAIL'}")
        print(f"   ✓ Score: {result.score:.2f}")
        print(f"   ✓ Matched sheet: {result.matched_sheet}")
        if result.sheet_selection:
            print(f"   ✓ Selection method: {result.sheet_selection.method}")
        if result.warnings:
            print(f"   ⚠ Warnings: {result.warnings}")
        print(f"   ✓ Debug info: {json.dumps(result.debug, indent=2)}")
        assert result.ok, "Should pass validation"
        assert result.matched_sheet == "1 Bldg", f"Should select '1 Bldg', got '{result.matched_sheet}'"
    finally:
        os.remove(correct_file)

    print("\n2. Testing with wrong format...")
    wrong_file = create_wrong_format_file()
    try:
        result = validate_baycrest_workbook(wrong_file)
        print(f"   ✓ Validation result: {'PASS' if result.ok else 'FAIL'}")
        print(f"   ✓ Score: {result.score:.2f}")
        print(f"   ✓ Matched sheet: {result.matched_sheet}")
        if result.warnings:
            print(f"   ✓ Warnings: {result.warnings}")
        assert not result.ok, "Should fail validation"
    finally:
        os.remove(wrong_file)

    # Test with "1 Bldg (4)" variant (prefix match)
    print("\n3. Testing with '1 Bldg (4)' variant (prefix match)...")
    variant_file = create_test_baycrest_file(sheet_name="1 Bldg (4)")
    try:
        result = validate_baycrest_workbook(variant_file)
        print(f"   ✓ Validation result: {'PASS' if result.ok else 'FAIL'}")
        print(f"   ✓ Score: {result.score:.2f}")
        print(f"   ✓ Matched sheet: {result.matched_sheet}")
        if result.sheet_selection:
            print(f"   ✓ Selection method: {result.sheet_selection.method}")
        if result.warnings:
            print(f"   ⚠ Warnings: {result.warnings}")
        assert result.ok, "Should pass validation for '1 Bldg (4)' variant"
        assert result.matched_sheet == "1 Bldg (4)", f"Should select '1 Bldg (4)', got '{result.matched_sheet}'"
        assert result.sheet_selection.method == "prefix", f"Should use prefix match, got '{result.sheet_selection.method}'"
    finally:
        os.remove(variant_file)

    print("\n✅ Direct validation tests passed!")


def test_api_endpoint():
    """Test the debug API endpoint."""
    print("\n=== Testing Debug API Endpoint ===\n")

    import requests

    # Start the server first (you need to have it running)
    print("Note: Make sure the FastAPI server is running (uvicorn app.main:app)")
    print("Testing endpoint: POST /api/v1/debug/signature/baycrest")

    # Create test file
    test_file = create_test_baycrest_file()

    try:
        # Test the endpoint
        url = "http://127.0.0.1:8000/api/v1/debug/signature/baycrest"
        headers = {"X-API-Key": os.getenv("API_KEY", "test-api-key")}

        with open(test_file, 'rb') as f:
            files = {'file': ('test_baycrest.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            response = requests.post(url, headers=headers, files=files)

        if response.status_code == 200:
            result = response.json()
            print(f"✓ API Response:")
            print(json.dumps(result, indent=2))
            assert result['ok'], "Should pass validation"
        else:
            print(f"✗ API request failed: {response.status_code}")
            print(f"  Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print("⚠ Could not connect to API. Make sure the server is running.")
    except Exception as e:
        print(f"✗ Error testing API: {e}")
    finally:
        os.remove(test_file)


def test_full_job_processing():
    """Test full job processing with validation."""
    print("\n=== Testing Full Job Processing ===\n")

    import requests
    import time

    print("Note: Make sure the FastAPI server is running")

    # Create test files
    correct_file = create_test_baycrest_file()
    wrong_file = create_wrong_format_file()

    api_key = os.getenv("API_KEY", "test-api-key")
    headers = {"X-API-Key": api_key}
    base_url = "http://127.0.0.1:8000/api/v1"

    try:
        # Test with correct format
        print("1. Testing job with correct Baycrest format...")
        with open(correct_file, 'rb') as f:
            files = {'file': ('correct_baycrest.xlsx', f)}
            data = {'template': 'baycrest_v1'}
            response = requests.post(f"{base_url}/jobs/", headers=headers, files=files, data=data)

        if response.status_code == 200:
            job = response.json()
            job_id = job['job_id']
            print(f"   ✓ Job created: {job_id}")

            # Poll for completion
            for _ in range(10):
                time.sleep(1)
                status_response = requests.get(f"{base_url}/jobs/{job_id}", headers=headers)
                if status_response.status_code == 200:
                    status = status_response.json()
                    if status['status'] in ['SUCCEEDED', 'FAILED']:
                        print(f"   ✓ Job status: {status['status']}")
                        if 'qa' in status and 'signature' in status['qa']:
                            print(f"   ✓ Signature validation: {status['qa']['signature']}")
                        assert status['status'] == 'SUCCEEDED', "Job should succeed"
                        break
        else:
            print(f"   ✗ Failed to create job: {response.status_code}")

        # Test with wrong format
        print("\n2. Testing job with wrong format (should fail)...")
        with open(wrong_file, 'rb') as f:
            files = {'file': ('wrong_format.xlsx', f)}
            data = {'template': 'baycrest_v1'}
            response = requests.post(f"{base_url}/jobs/", headers=headers, files=files, data=data)

        if response.status_code == 200:
            job = response.json()
            job_id = job['job_id']
            print(f"   ✓ Job created: {job_id}")

            # Poll for completion
            for _ in range(10):
                time.sleep(1)
                status_response = requests.get(f"{base_url}/jobs/{job_id}", headers=headers)
                if status_response.status_code == 200:
                    status = status_response.json()
                    if status['status'] in ['SUCCEEDED', 'FAILED']:
                        print(f"   ✓ Job status: {status['status']}")
                        if 'error_message' in status:
                            print(f"   ✓ Error message: {status['error_message']}")
                        assert status['status'] == 'FAILED', "Job should fail validation"
                        assert 'template' in status.get('error_message', '').lower(), "Should mention template mismatch"
                        break
        else:
            print(f"   ✗ Failed to create job: {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("⚠ Could not connect to API. Make sure the server is running.")
    except Exception as e:
        print(f"✗ Error testing job processing: {e}")
    finally:
        os.remove(correct_file)
        os.remove(wrong_file)


if __name__ == "__main__":
    print("=" * 60)
    print("Baycrest Signature Validation Test Suite")
    print("=" * 60)

    # Test 1: Direct validation
    test_direct_validation()

    # Test 2: API endpoint (requires server running)
    print("\n" + "=" * 60)
    test_api_endpoint()

    # Test 3: Full job processing (requires server running)
    print("\n" + "=" * 60)
    test_full_job_processing()

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)