#!/usr/bin/env python3
"""
Test the API with the Baycrest file to ensure everything works.
"""

import requests
import time
import json
import os

# API configuration
API_URL = "http://127.0.0.1:8000"
API_KEY = "test-api-key"
EXCEL_FILE = "Apartment Takeoffs - Baycrest 1 (Western National).xlsx"

# Check if file exists
if not os.path.exists(EXCEL_FILE):
    print(f"❌ File not found: {EXCEL_FILE}")
    print("Looking for Excel files in the directory...")
    xlsx_files = [f for f in os.listdir('.') if f.endswith('.xlsx')]
    if xlsx_files:
        print(f"Found Excel files: {xlsx_files}")
        # Try to find the Baycrest file
        for f in xlsx_files:
            if 'Baycrest' in f or 'baycrest' in f:
                EXCEL_FILE = f
                print(f"Using file: {EXCEL_FILE}")
                break
    else:
        print("No Excel files found in the directory")
        exit(1)

def test_create_job_default():
    """Test creating a job with default settings (baycrest_v1 template, default sheet)"""

    print("\n" + "="*60)
    print("TEST 1: Create job with default settings")
    print("="*60)

    # Prepare the file upload
    with open(EXCEL_FILE, 'rb') as f:
        files = {'file': (EXCEL_FILE, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {
            # Not specifying template - should use default baycrest_v1
            # Not specifying sheets - should use default "1 Bldg"
        }
        headers = {'X-API-Key': API_KEY}

        # Make the request
        print(f"Uploading file: {EXCEL_FILE}")
        print(f"Using defaults (template=baycrest_v1, sheets=1 Bldg)")

        response = requests.post(
            f"{API_URL}/api/v1/jobs/",
            files=files,
            data=data,
            headers=headers
        )

    if response.status_code == 200:
        job_data = response.json()
        print(f"✅ Job created successfully!")
        print(f"   Job ID: {job_data['job_id']}")
        print(f"   Status: {job_data['status']}")
        return job_data['job_id']
    else:
        print(f"❌ Failed to create job")
        print(f"   Status code: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

def test_create_job_with_sheets():
    """Test creating a job with specific sheets"""

    print("\n" + "="*60)
    print("TEST 2: Create job with specific sheets")
    print("="*60)

    # Prepare the file upload
    with open(EXCEL_FILE, 'rb') as f:
        files = {'file': (EXCEL_FILE, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {
            'template': 'baycrest_v1',
            'sheets': '1 Bldg'  # Explicitly specify sheet
        }
        headers = {'X-API-Key': API_KEY}

        # Make the request
        print(f"Uploading file: {EXCEL_FILE}")
        print(f"Template: baycrest_v1")
        print(f"Sheets: 1 Bldg")

        response = requests.post(
            f"{API_URL}/api/v1/jobs/",
            files=files,
            data=data,
            headers=headers
        )

    if response.status_code == 200:
        job_data = response.json()
        print(f"✅ Job created successfully!")
        print(f"   Job ID: {job_data['job_id']}")
        print(f"   Status: {job_data['status']}")
        return job_data['job_id']
    else:
        print(f"❌ Failed to create job")
        print(f"   Status code: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

def wait_for_job(job_id):
    """Wait for a job to complete and show results"""

    print(f"\nWaiting for job {job_id} to complete...")

    headers = {'X-API-Key': API_KEY}
    max_wait = 30  # Maximum 30 seconds
    start_time = time.time()

    while time.time() - start_time < max_wait:
        response = requests.get(
            f"{API_URL}/api/v1/jobs/{job_id}",
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            status = data['status']
            progress = data['progress']

            print(f"  Status: {status}, Progress: {progress}%")

            if status == 'SUCCEEDED':
                print("\n✅ Job completed successfully!")

                # Show stats
                if data.get('qa') and data['qa'].get('stats'):
                    stats = data['qa']['stats']
                    print("\nExtraction Statistics:")
                    print(f"  • Items mapped: {stats.get('items_mapped', 'N/A')}")
                    print(f"  • Items unmapped: {stats.get('items_unmapped', 'N/A')}")
                    print(f"  • Total rows processed: {stats.get('rows_total', 'N/A')}")
                    print(f"  • Rows with data: {stats.get('rows_with_measures', 'N/A')}")

                # Show sections
                if data.get('result') and data['result'].get('sections'):
                    sections = data['result']['sections']
                    print(f"\nSections extracted: {len(sections)}")
                    for section in sections[:3]:  # Show first 3 sections
                        print(f"  • {section['name']}: {len(section.get('items', []))} items")

                return True

            elif status == 'FAILED':
                print(f"\n❌ Job failed!")
                if data.get('error'):
                    print(f"  Error: {data['error'].get('message', 'Unknown error')}")
                    print(f"  Detail: {data['error'].get('detail', 'No details')}")
                return False

        time.sleep(2)  # Wait 2 seconds before checking again

    print(f"\n⚠️ Job did not complete within {max_wait} seconds")
    return False

def main():
    """Run all tests"""

    print("="*60)
    print("API TEST WITH BAYCREST FILE")
    print("="*60)
    print(f"API URL: {API_URL}")
    print(f"File: {EXCEL_FILE}")

    # Test 1: Default settings
    job_id = test_create_job_default()
    if job_id:
        wait_for_job(job_id)

    # Test 2: With explicit sheets
    job_id = test_create_job_with_sheets()
    if job_id:
        wait_for_job(job_id)

    print("\n" + "="*60)
    print("TESTING COMPLETE")
    print("="*60)
    print("\n⚠️ IMPORTANT: In the Swagger UI:")
    print("1. For 'sheets' parameter:")
    print("   - Leave it empty to use default ('1 Bldg')")
    print("   - Or specify: '1 Bldg' or '1 Bldg,2 Bldgs,3 Bldgs' or 'all'")
    print("   - Do NOT use 'string' - that's just a placeholder")
    print("2. Template now defaults to 'baycrest_v1'")
    print("3. Make sure your Excel file exists in the current directory")

if __name__ == "__main__":
    main()