#!/usr/bin/env python3
"""Quick test for wrong format file validation."""

import tempfile
import requests
import time
from openpyxl import Workbook

# Create a wrong format file
wb = Workbook()
sheet = wb.active
sheet.title = "Sample"
sheet['A1'] = "Product"
sheet['B1'] = "Price"
sheet['C1'] = "Quantity"
sheet['A2'] = "Item 1"
sheet['B2'] = 100
sheet['C2'] = 5

# Save to temp file
with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False, mode='wb') as tmp:
    wb.save(tmp.name)
    tmp_path = tmp.name
    print(f"Created test file: {tmp_path}")

# Submit job
url = "http://127.0.0.1:8000/api/v1/jobs/"
headers = {"X-API-Key": "test-api-key"}

with open(tmp_path, 'rb') as f:
    files = {'file': ('wrong_format.xlsx', f)}
    data = {'template': 'baycrest_v1'}
    response = requests.post(url, headers=headers, files=files, data=data)

if response.status_code == 200:
    job = response.json()
    job_id = job['job_id']
    print(f"Job created: {job_id}")

    # Poll for status
    for i in range(10):
        time.sleep(1)
        status_resp = requests.get(f"http://127.0.0.1:8000/api/v1/jobs/{job_id}", headers=headers)
        if status_resp.status_code == 200:
            status = status_resp.json()
            print(f"Attempt {i+1}: Status = {status['status']}, Progress = {status['progress']}")

            if status['status'] == 'FAILED':
                print(f"✓ Job failed as expected!")
                print(f"  Error: {status.get('error')}")
                if 'qa' in status and status['qa']:
                    print(f"  QA: {status['qa']}")
                break
            elif status['status'] == 'SUCCEEDED':
                print(f"✗ Job succeeded but should have failed!")
                break
else:
    print(f"Failed to create job: {response.status_code}")
    print(response.text)

import os
os.remove(tmp_path)