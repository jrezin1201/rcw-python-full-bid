#!/usr/bin/env venv/bin/python
"""
Test the new Baycrest file with the correct template.
This shows how to properly process a Baycrest format file.
"""
import json
import requests
import time
import os

API_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY", "test-api-key")

def test_baycrest_new_file():
    """Test the new Baycrest file with correct template."""

    print("=" * 60)
    print("Testing baycrest_new.xlsx with CORRECT template (baycrest_v1)")
    print("=" * 60)

    # 1. Submit job with the CORRECT template
    print("\n1. Submitting job with baycrest_v1 template...")

    with open("baycrest_new.xlsx", "rb") as f:
        response = requests.post(
            f"{API_URL}/api/v1/jobs/",
            headers={"X-API-Key": API_KEY},
            files={"file": ("baycrest_new.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"template": "baycrest_v1"}  # Using the correct template!
        )

    if response.status_code not in [200, 201]:
        print(f"Error submitting job: {response.status_code}")
        print(response.text)
        return

    job_data = response.json()
    job_id = job_data["job_id"]
    print(f"Job submitted successfully: {job_id}")

    # 2. Poll for completion
    print("\n2. Waiting for job to complete...")
    max_attempts = 30
    for i in range(max_attempts):
        response = requests.get(
            f"{API_URL}/api/v1/jobs/{job_id}",
            headers={"X-API-Key": API_KEY}
        )

        if response.status_code != 200:
            print(f"Error getting job status: {response.status_code}")
            return

        job_status = response.json()
        status = job_status["status"]
        progress = job_status.get("progress", 0)

        print(f"   Status: {status}, Progress: {progress}%")

        if status in ["SUCCEEDED", "FAILED"]:
            break

        time.sleep(1)

    # 3. Display results
    print("\n3. Final Job Results:")
    print("-" * 40)
    print(f"Status: {job_status['status']}")
    print(f"Progress: {job_status.get('progress', 0)}%")

    if job_status['status'] == 'FAILED':
        print(f"\nError: {job_status.get('error')}")
        if 'qa' in job_status and 'signature' in job_status['qa']:
            sig = job_status['qa']['signature']
            print(f"\nSignature validation:")
            print(f"  - OK: {sig.get('ok')}")
            print(f"  - Score: {sig.get('score')}")
            print(f"  - Warnings: {sig.get('warnings')}")
    else:
        # Show extraction results
        result = job_status.get('result', {})
        qa = job_status.get('qa', {})

        print("\nExtraction Results:")
        print(f"  - Sections: {len(result.get('sections', []))}")
        print(f"  - Unmapped items: {result.get('unmapped_summary', {}).get('total_unmapped', 0)}")

        print("\nQA Statistics:")
        stats = qa.get('stats', {})
        print(f"  - Total rows: {stats.get('rows_total', 0)}")
        print(f"  - Rows with measures: {stats.get('rows_with_measures', 0)}")
        print(f"  - Items mapped: {stats.get('items_mapped', 0)}")
        print(f"  - Items missing: {stats.get('items_missing', 0)}")
        print(f"  - Items unmapped: {stats.get('items_unmapped', 0)}")
        print(f"  - Rows ignored: {stats.get('rows_ignored', 0)}")

        if 'signature' in qa:
            sig = qa['signature']
            print(f"\nSignature validation:")
            print(f"  - OK: {sig.get('ok')}")
            print(f"  - Score: {sig.get('score')}")
            print(f"  - Matched sheet: {sig.get('matched_sheet')}")

        # Show some extracted data
        if result.get('sections'):
            print("\nSample extracted sections:")
            for i, section in enumerate(result['sections'][:3]):
                print(f"\n  Section {i+1}:")
                print(f"    - Section: {section.get('section')}")
                print(f"    - Category: {section.get('category')}")
                print(f"    - Item: {section.get('item')}")
                print(f"    - Description: {section.get('description')}")
                print(f"    - Quantity: {section.get('quantity')}")
                print(f"    - Unit: {section.get('unit')}")

    print("\n" + "=" * 60)
    print("COMPARISON WITH PREVIOUS JOB:")
    print("-" * 40)
    print("Previous job (b0bdfdea-44c1-4d6f-a0c2-718bfa0793ab):")
    print("  - Template used: rc_wendt_v1 (WRONG)")
    print("  - Result: 0 items extracted, 148 rows ignored")
    print("\nThis test:")
    print(f"  - Template used: baycrest_v1 (CORRECT)")
    print(f"  - Result: {stats.get('items_mapped', 0)} items mapped")
    print("\nConclusion: Using the correct template is essential!")
    print("=" * 60)

if __name__ == "__main__":
    test_baycrest_new_file()