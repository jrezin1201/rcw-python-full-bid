#!/usr/bin/env venv/bin/python
"""
Simple test for sheet selection API.
"""
import requests
import json

# Test basic API
response = requests.get("http://127.0.0.1:8000/docs")
print(f"API Status: {response.status_code}")

if response.status_code != 200:
    print("❌ API is not running. Please start the service:")
    print("   cd /Users/jordanhill/code/py-py-code/rcw-extract")
    print("   venv/bin/uvicorn app.main:app --port 8000 --reload")
else:
    print("✅ API is running")

    # Test with sheet parameter
    print("\nTesting with sheet parameter...")
    with open("baycrest_new.xlsx", "rb") as f:
        response = requests.post(
            "http://127.0.0.1:8000/api/v1/jobs/",
            headers={"X-API-Key": "test-api-key"},
            files={"file": ("baycrest_new.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"template": "baycrest_v1", "sheets": "1 Bldg"}
        )

    print(f"Response status: {response.status_code}")
    if response.status_code == 500:
        print("Error response:", response.text)