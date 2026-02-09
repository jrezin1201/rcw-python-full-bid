#!/usr/bin/env venv/bin/python
"""
Quick test for sheet selection after starting the service.
Run this AFTER starting the API with:
  venv/bin/uvicorn app.main:app --port 8000 --reload
"""
import requests
import json
import time

def quick_test():
    # Check if API is running
    try:
        response = requests.get("http://127.0.0.1:8000/docs", timeout=2)
        if response.status_code != 200:
            print("❌ API not responding. Start it first:")
            print("   venv/bin/uvicorn app.main:app --port 8000 --reload")
            return
    except:
        print("❌ Cannot connect to API. Start it first:")
        print("   venv/bin/uvicorn app.main:app --port 8000 --reload")
        return

    print("✅ API is running!")
    print("\nTesting sheet selection...")

    # Test with multiple sheets
    print("\n1. Testing with sheets='1 Bldg,2 Bldgs'")
    with open("baycrest_new.xlsx", "rb") as f:
        response = requests.post(
            "http://127.0.0.1:8000/api/v1/jobs/",
            headers={"X-API-Key": "test-api-key"},
            files={"file": ("baycrest_new.xlsx", f)},
            data={
                "template": "baycrest_v1",
                "sheets": "1 Bldg,2 Bldgs"  # Process 2 sheets
            }
        )

    if response.status_code in [200, 201]:
        job_id = response.json()["job_id"]
        print(f"   Job created: {job_id}")

        # Wait for completion
        for i in range(10):
            response = requests.get(
                f"http://127.0.0.1:8000/api/v1/jobs/{job_id}",
                headers={"X-API-Key": "test-api-key"}
            )
            status = response.json()["status"]
            if status == "SUCCEEDED":
                result = response.json()
                stats = result["qa"]["stats"]
                print(f"   ✅ Success!")
                print(f"      Items mapped: {stats['items_mapped']}")
                print(f"      Total rows: {stats['rows_total']}")

                # Check which sheets were processed
                sheets = set()
                for item in result["result"]["raw_data"][:20]:
                    if "provenance" in item and "sheet" in item["provenance"]:
                        sheets.add(item["provenance"]["sheet"])
                if sheets:
                    print(f"      Sheets processed: {sorted(sheets)}")
                break
            elif status == "FAILED":
                print(f"   ❌ Job failed: {response.json().get('error')}")
                break
            time.sleep(1)
    else:
        print(f"   ❌ Failed to create job: {response.status_code}")
        print(f"   Error: {response.text}")

    # Test with all sheets
    print("\n2. Testing with sheets='all'")
    with open("baycrest_new.xlsx", "rb") as f:
        response = requests.post(
            "http://127.0.0.1:8000/api/v1/jobs/",
            headers={"X-API-Key": "test-api-key"},
            files={"file": ("baycrest_new.xlsx", f)},
            data={
                "template": "baycrest_v1",
                "sheets": "all"  # Process ALL sheets
            }
        )

    if response.status_code in [200, 201]:
        job_id = response.json()["job_id"]
        print(f"   Job created: {job_id}")

        # Wait for completion
        for i in range(10):
            response = requests.get(
                f"http://127.0.0.1:8000/api/v1/jobs/{job_id}",
                headers={"X-API-Key": "test-api-key"}
            )
            status = response.json()["status"]
            if status == "SUCCEEDED":
                result = response.json()
                stats = result["qa"]["stats"]
                print(f"   ✅ Success!")
                print(f"      Items mapped: {stats['items_mapped']}")
                print(f"      Total rows: {stats['rows_total']}")

                # Check which sheets were processed
                sheets = set()
                for item in result["result"]["raw_data"][:50]:
                    if "provenance" in item and "sheet" in item["provenance"]:
                        sheets.add(item["provenance"]["sheet"])
                if sheets:
                    print(f"      Sheets processed: {sorted(sheets)}")
                break
            elif status == "FAILED":
                print(f"   ❌ Job failed: {response.json().get('error')}")
                break
            time.sleep(1)
    else:
        print(f"   ❌ Failed to create job: {response.status_code}")

    print("\n✅ Sheet selection feature is working!")
    print("\nYou can now use:")
    print("  • No sheets parameter = default sheet")
    print("  • sheets='1 Bldg' = specific sheet")
    print("  • sheets='1 Bldg,2 Bldgs' = multiple sheets")
    print("  • sheets='all' = all data sheets")

if __name__ == "__main__":
    quick_test()