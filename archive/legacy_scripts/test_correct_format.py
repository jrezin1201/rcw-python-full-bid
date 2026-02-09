#!/usr/bin/env python3
"""Test correct Baycrest format file processing."""

import tempfile
import requests
import time
from openpyxl import Workbook

# Create correct Baycrest format file
wb = Workbook()

# Create Units sheet with expected headers
units_sheet = wb.active
units_sheet.title = "Units "

# Add headers in row 2
units_sheet['A1'] = "Units Summary"
units_sheet['A2'] = "Unit Type"
units_sheet['B2'] = "Unit Count"
units_sheet['C2'] = "Unit Doors"
units_sheet['D2'] = "WIC"
units_sheet['E2'] = "Wardrobes"
units_sheet['F2'] = "W/D"
units_sheet['G2'] = "Balc"
units_sheet['H2'] = "Balc Storage"
units_sheet['I2'] = "Windows"

# Add some data
units_sheet['A3'] = "1BR"
units_sheet['B3'] = 10
units_sheet['C3'] = 15
units_sheet['D3'] = 10
units_sheet['E3'] = 20
units_sheet['F3'] = 10
units_sheet['G3'] = 8
units_sheet['H3'] = 8
units_sheet['I3'] = 30

units_sheet['A4'] = "2BR"
units_sheet['B4'] = 5
units_sheet['C4'] = 10
units_sheet['D4'] = 10
units_sheet['E4'] = 15
units_sheet['F4'] = 5
units_sheet['G4'] = 5
units_sheet['H4'] = 5
units_sheet['I4'] = 20

# Create Bid Form sheet
bid_form = wb.create_sheet("Bid Form")
bid_form['A1'] = "Bid Information"
bid_form['A2'] = "Item"
bid_form['B2'] = "Quantity"

# Save to temp file
with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False, mode='wb') as tmp:
    wb.save(tmp.name)
    tmp_path = tmp.name
    print(f"Created test file: {tmp_path}")

# Submit job
url = "http://127.0.0.1:8000/api/v1/jobs/"
headers = {"X-API-Key": "test-api-key"}

with open(tmp_path, 'rb') as f:
    files = {'file': ('correct_baycrest.xlsx', f)}
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

            if status['status'] == 'SUCCEEDED':
                print(f"✓ Job succeeded as expected!")
                if 'qa' in status and status['qa'] and 'signature' in status['qa']:
                    sig = status['qa']['signature']
                    print(f"  Signature OK: {sig['ok']}")
                    print(f"  Signature Score: {sig['score']}")
                    print(f"  Matched Sheet: {sig['matched_sheet']}")
                break
            elif status['status'] == 'FAILED':
                print(f"✗ Job failed but should have succeeded!")
                print(f"  Error: {status.get('error')}")
                break
else:
    print(f"Failed to create job: {response.status_code}")
    print(response.text)

import os
os.remove(tmp_path)