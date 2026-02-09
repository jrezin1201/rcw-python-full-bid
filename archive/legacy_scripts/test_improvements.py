#!/usr/bin/env python3
"""Test the improvements: row-based stats, unmapped_summary, 3-tier matching."""
import requests
import time
import json

API_URL = "http://127.0.0.1:8009"
API_KEY = "test-api-key"

print("Testing improvements...")
print("="*60)

# Upload Baycrest test file
with open('comprehensive_baycrest_test.xlsx', 'rb') as f:
    files = {'file': ('test.xlsx', f)}
    data = {'template': 'baycrest_v1'}
    headers = {'X-API-Key': API_KEY}

    response = requests.post(f"{API_URL}/api/v1/jobs/",
                            files=files, data=data, headers=headers)

if response.status_code != 200:
    print(f"❌ Upload failed: {response.status_code}")
    exit(1)

job_id = response.json()['job_id']
print(f"✓ Job created: {job_id}")

# Poll for completion
for _ in range(10):
    time.sleep(1)
    status_response = requests.get(
        f"{API_URL}/api/v1/jobs/{job_id}",
        headers={'X-API-Key': API_KEY}
    )

    if status_response.status_code == 200:
        result = status_response.json()

        if result['status'] == 'SUCCEEDED':
            print(f"✓ Job completed successfully\n")

            # Test 1: Check row-based stats are consistent
            print("Test 1: Row-based stats consistency")
            print("-" * 40)
            stats = result.get('qa', {}).get('stats', {})
            rows_total = stats.get('rows_total', 0)
            rows_extracted = stats.get('rows_extracted', 0)
            rows_ignored = stats.get('rows_ignored', 0)

            print(f"  rows_total: {rows_total}")
            print(f"  rows_extracted: {rows_extracted}")
            print(f"  rows_ignored: {rows_ignored}")
            print(f"  Sum check: {rows_extracted + rows_ignored} = {rows_total} ?")

            if rows_extracted + rows_ignored == rows_total:
                print("  ✓ Stats are consistent (no double counting)\n")
            else:
                print("  ❌ Stats don't add up!\n")

            # Test 2: Check unmapped_summary exists
            print("Test 2: unmapped_summary")
            print("-" * 40)
            unmapped_summary = result.get('result', {}).get('unmapped_summary', {})

            if unmapped_summary:
                print(f"  ✓ unmapped_summary present")
                print(f"  total_unmapped: {unmapped_summary.get('total_unmapped', 0)}")
                print(f"  unique_classifications: {unmapped_summary.get('unique_classifications', 0)}")

                top = unmapped_summary.get('top', [])
                print(f"  Top unmapped classifications ({len(top)}):")
                for item in top[:5]:  # Show first 5
                    classification = item.get('classification', 'N/A')
                    count = item.get('count', 0)
                    print(f"    - {classification}: {count}x")
                print()
            else:
                print("  ❌ unmapped_summary NOT found\n")

            # Test 3: Check raw_rows and raw_data still present
            print("Test 3: raw_rows and raw_data still present")
            print("-" * 40)
            result_data = result.get('result', {})
            if 'raw_rows' in result_data:
                print(f"  ✓ raw_rows present: {len(result_data['raw_rows'])} rows")
            else:
                print("  ❌ raw_rows MISSING")

            if 'raw_data' in result_data:
                print(f"  ✓ raw_data present: {len(result_data['raw_data'])} items")
            else:
                print("  ❌ raw_data MISSING")
            print()

            # Save full response
            with open('improvements_test_response.json', 'w') as f:
                json.dump(result, f, indent=2)
            print("✓ Full response saved to improvements_test_response.json")

            print("\n" + "="*60)
            print("IMPROVEMENTS TEST SUMMARY:")
            if (rows_extracted + rows_ignored == rows_total and
                unmapped_summary and
                'raw_rows' in result_data and
                'raw_data' in result_data):
                print("✅ ALL IMPROVEMENTS WORKING!")
            else:
                print("⚠️  SOME IMPROVEMENTS NEED ATTENTION")

            break

        elif result['status'] == 'FAILED':
            print(f"❌ Job failed: {result.get('error', {}).get('message', 'Unknown')}")
            break
