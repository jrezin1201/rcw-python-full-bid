#!/usr/bin/env python3
"""Test CORS configuration for NextJS integration."""

import requests
import json


def test_cors_preflight():
    """Test OPTIONS request for CORS preflight."""
    url = "http://127.0.0.1:8000/api/v1/jobs/"

    # Simulate preflight request from NextJS
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-api-key,content-type"
    }

    try:
        response = requests.options(url, headers=headers)

        print("CORS Preflight Test")
        print("=" * 50)
        print(f"Request URL: {url}")
        print(f"Request Method: OPTIONS")
        print(f"Origin: {headers['Origin']}")
        print(f"\nResponse Status: {response.status_code}")
        print("\nCORS Headers:")

        # Check for CORS headers
        cors_headers = {
            "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin"),
            "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods"),
            "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers"),
            "Access-Control-Allow-Credentials": response.headers.get("Access-Control-Allow-Credentials"),
        }

        for header, value in cors_headers.items():
            status = "✓" if value else "✗"
            print(f"  {status} {header}: {value}")

        # Validate expected values
        print("\nValidation:")
        checks = [
            ("Origin allowed", cors_headers["Access-Control-Allow-Origin"] == "http://localhost:3000"),
            ("POST method allowed", "POST" in (cors_headers["Access-Control-Allow-Methods"] or "")),
            ("x-api-key header allowed", "x-api-key" in (cors_headers["Access-Control-Allow-Headers"] or "").lower()),
            ("content-type header allowed", "content-type" in (cors_headers["Access-Control-Allow-Headers"] or "").lower()),
        ]

        for check_name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"  {status} {check_name}")

        return all(passed for _, passed in checks)

    except Exception as e:
        print(f"Error testing CORS: {e}")
        return False


def test_cors_actual_request():
    """Test actual GET request with CORS headers."""
    url = "http://127.0.0.1:8000/api/v1/jobs/test-job-id"

    headers = {
        "Origin": "http://localhost:3000",
        "X-API-Key": "test-api-key",
    }

    try:
        response = requests.get(url, headers=headers)

        print("\n\nCORS Actual Request Test")
        print("=" * 50)
        print(f"Request URL: {url}")
        print(f"Request Method: GET")
        print(f"Origin: {headers['Origin']}")
        print(f"\nResponse Status: {response.status_code}")

        # Check for CORS headers in actual response
        cors_origin = response.headers.get("Access-Control-Allow-Origin")
        cors_credentials = response.headers.get("Access-Control-Allow-Credentials")

        print("\nCORS Response Headers:")
        print(f"  Access-Control-Allow-Origin: {cors_origin}")
        print(f"  Access-Control-Allow-Credentials: {cors_credentials}")

        print("\nValidation:")
        checks = [
            ("Origin header present", cors_origin == "http://localhost:3000"),
            ("Credentials allowed", cors_credentials == "true"),
        ]

        for check_name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"  {status} {check_name}")

        return all(passed for _, passed in checks)

    except Exception as e:
        print(f"Error testing CORS: {e}")
        return False


if __name__ == "__main__":
    print("Testing CORS Configuration for NextJS Integration")
    print("=" * 50)

    # Note: Ensure server is running on port 8000
    print("\nNote: Make sure the API server is running on http://127.0.0.1:8000\n")

    preflight_ok = test_cors_preflight()
    actual_ok = test_cors_actual_request()

    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Preflight (OPTIONS): {'✓ PASSED' if preflight_ok else '✗ FAILED'}")
    print(f"  Actual Request (GET): {'✓ PASSED' if actual_ok else '✗ FAILED'}")

    if preflight_ok and actual_ok:
        print("\n✓ CORS is properly configured for NextJS development!")
        print("  - Origin http://localhost:3000 is allowed")
        print("  - Headers x-api-key and content-type are allowed")
        print("  - Methods GET, POST, OPTIONS are allowed")
    else:
        print("\n✗ CORS configuration needs adjustment")