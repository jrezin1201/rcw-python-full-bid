#!/usr/bin/env python3
"""
Compare rc_wendt_v1 vs baycrest_v1 templates with the same Baycrest Excel file.
This demonstrates why you need to use template=baycrest_v1 for Baycrest format files.
"""

import requests
import time
import json

API_URL = "http://127.0.0.1:8008"
API_KEY = "test-api-key"
TEST_FILE = "baycrest_test.xlsx"

def upload_and_check(template_name):
    """Upload file and check results with given template."""
    print(f"\n{'='*60}")
    print(f"Testing with template: {template_name}")
    print('='*60)

    # Upload file
    with open(TEST_FILE, 'rb') as f:
        files = {'file': (TEST_FILE, f)}
        data = {'template': template_name}
        headers = {'X-API-Key': API_KEY}

        response = requests.post(f"{API_URL}/api/v1/jobs/",
                                files=files, data=data, headers=headers)

    if response.status_code != 200:
        print(f"✗ Upload failed: {response.status_code}")
        return

    job_id = response.json()['job_id']
    print(f"✓ Job created: {job_id}")

    # Poll for completion
    for attempt in range(10):
        time.sleep(1)
        status_response = requests.get(
            f"{API_URL}/api/v1/jobs/{job_id}",
            headers={'X-API-Key': API_KEY}
        )

        if status_response.status_code == 200:
            result = status_response.json()

            if result['status'] == 'SUCCEEDED':
                print(f"✓ Job completed successfully")

                # Show extraction stats
                qa_stats = result.get('qa', {}).get('stats', {})
                print(f"\nExtraction Stats:")
                print(f"  - rows_total: {qa_stats.get('rows_total', 'N/A')}")
                print(f"  - rows_extracted: {qa_stats.get('rows_extracted', 'N/A')}")
                print(f"  - rows_ignored: {qa_stats.get('rows_ignored', 'N/A')}")
                print(f"  - items_mapped: {qa_stats.get('items_mapped', 0)}")
                print(f"  - items_unmapped: {qa_stats.get('items_unmapped', 0)}")

                # Show sections
                sections = result.get('result', {}).get('sections', [])
                print(f"\nMapped Sections: {len(sections)}")
                for section in sections[:3]:  # Show first 3
                    print(f"  - {section['name']}: {len(section.get('items', []))} items")
                    for item in section.get('items', [])[:2]:  # Show first 2 items
                        print(f"      • {item['key']}: {item['qty']} {item['uom']}")

                # Check for raw_rows/raw_data (Baycrest specific)
                if 'raw_rows' in result.get('result', {}):
                    print(f"\n✓ raw_rows present: {len(result['result']['raw_rows'])} rows")
                else:
                    print(f"\n✗ raw_rows NOT present (expected for {template_name})")

                if 'raw_data' in result.get('result', {}):
                    print(f"✓ raw_data present: {len(result['result']['raw_data'])} rows")
                else:
                    print(f"✗ raw_data NOT present (expected for {template_name})")

                break

            elif result['status'] == 'FAILED':
                print(f"✗ Job failed: {result.get('error', {}).get('message', 'Unknown')}")
                break

print("Demonstrating Template Usage with Baycrest Format Excel")
print(f"Test file: {TEST_FILE} (Sheet: '1 Bldg')")

# Test with wrong template (rc_wendt_v1) - will fail to extract
upload_and_check('rc_wendt_v1')

# Test with correct template (baycrest_v1) - will work properly
upload_and_check('baycrest_v1')

print("\n" + "="*60)
print("SUMMARY:")
print("  • rc_wendt_v1: Expects Togal format (Classification | Qty | UOM | ...)")
print("                 Will extract 0 rows from Baycrest format")
print("  • baycrest_v1: Expects Baycrest format (A=Section, B=Class, C=Qty)")
print("                 Will correctly extract all data rows")
print("\n✅ Always use template='baycrest_v1' for Baycrest format files!")
print("="*60)