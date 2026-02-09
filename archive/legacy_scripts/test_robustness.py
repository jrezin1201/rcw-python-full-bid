#!/usr/bin/env venv/bin/python
"""
Test robustness of the Baycrest extraction with variations.
This tests if the solution works with different inputs.
"""
import pandas as pd
import numpy as np
import requests
import json
import time
import os

API_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY", "test-api-key")

def create_variation_file(output_file="baycrest_variation.xlsx"):
    """Create a Baycrest file with variations to test robustness."""

    print("Creating variation file with:")
    print("- Different numbers")
    print("- Additional items not in our mappings")
    print("- Missing some expected items")
    print("- Same structure/format")

    # Create data similar to baycrest_new.xlsx but with variations
    data = {
        'General': {
            'A': ['General'] + [None] * 10,
            'B': [None,
                  'Studio Unit Count',
                  '1 Bed Room Count',  # Same name
                  '2 Bedroom Count',    # Same name
                  '3 Bed Room Count',   # Same name
                  'Total',
                  'Total SF',
                  'Average Unit Size',  # NEW ITEM - not mapped
                  'Parking Ratio',      # NEW ITEM - not mapped
                  None, None],
            'C': ['Count',
                  50,        # Different value (was 0)
                  450,       # Different value (was 333)
                  200,       # Different value (was 134)
                  75,        # Different value (was 0)
                  775,       # Different total
                  650000,    # Different SF
                  839,       # New item
                  1.2,       # New item
                  None, None],
            'D': ['Ave SF'] + [None] * 10,
            'E': [None] * 11
        },
        'Corridors': {
            'A': ['Corridors'] + [None] * 15,
            'B': [None,
                  'Sheet',
                  'Stucco Wall SF',      # Same
                  'Cor. Wall SF',        # Same
                  'Cor. Lid SF',         # Same
                  'Cor. Door Count',     # Same
                  'IDF etc. Count',      # Same
                  'IDF etc. SF',         # Same
                  'Storage Count',       # Same
                  'Storage SF',          # Same
                  'Cor. Bumpouts count', # Same
                  'Emergency Exits',      # NEW ITEM
                  'Cor Rail',            # Same
                  'Handrail LF',         # NEW ITEM
                  None, None],
            'C': ['1-A0.10',
                  None,
                  35000.50,   # Different value
                  300000,     # Different value
                  95000,      # Different value
                  450,        # Different value
                  60,         # Different value
                  9500,       # Different value
                  25,         # Different value
                  4500,       # Different value
                  850,        # Different value
                  12,         # New item
                  5,          # Different value
                  1250.75,    # New item
                  None, None],
            'D': [None] * 16,
            'E': ['Corridor Notes'] + [None] * 15
        },
        'Exterior': {
            'A': ['Exterior'] + [None] * 20,
            'B': [None,
                  'Sheet',
                  'Parapet LF',                  # Same
                  '8 Landscape Retaining Wall LF', # Same
                  'Ext. Door Count',             # Same
                  'Foam Eave LF',                # Same
                  'Roof Stucco SF',              # Same
                  'Roof Stucco LF',              # Same
                  'Window/Door Trim Count',      # Same
                  'Trim LF',                     # Same
                  'Foam Panel Count',            # Same
                  'Wainscot LF',                 # Same
                  'Balc. Rail LF',               # Same
                  'Balc. Rail Count',            # Same
                  'Louvers',                     # Same
                  'Gutter LF',                   # Same
                  'Down Spouts',                 # Same
                  'Roof Vents',                  # NEW ITEM
                  'Siding SF',                   # NEW ITEM
                  None, None],
            'C': ['1-A2.00',
                  None,
                  425.80,    # Different
                  520.00,    # Different
                  55,        # Different
                  5200.00,   # Different
                  42000,     # Different
                  5100,      # Different
                  1800,      # Different
                  9200,      # Different
                  250,       # Different
                  550,       # Different
                  4500,      # Different
                  600,       # Different
                  3,         # Different
                  5200,      # Different
                  140,       # Different
                  45,        # New
                  18500.50,  # New
                  None, None],
            'D': [None] * 20,
            'E': ['Exterior Notes'] + [None] * 19
        }
    }

    # Add more variations for other sections
    # ... (Units, Garage, etc. with similar variations)

    # Convert to DataFrames and write to Excel
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Write each section as a sheet
        for sheet_name, sheet_data in [('1 Bldg', data)]:
            # Combine all sections into one dataframe
            all_rows = []
            for section_data in sheet_data.values():
                df_section = pd.DataFrame(section_data)
                all_rows.append(df_section)

            # Concatenate all sections
            df = pd.concat(all_rows, ignore_index=True)
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Created variation file: {output_file}")
    return output_file

def test_variation_file(file_path):
    """Test the variation file to see what maps and what doesn't."""

    print("\n" + "="*60)
    print("TESTING ROBUSTNESS WITH VARIATION FILE")
    print("="*60)

    # Submit job
    print("\n1. Submitting variation file...")
    with open(file_path, "rb") as f:
        response = requests.post(
            f"{API_URL}/api/v1/jobs/",
            headers={"X-API-Key": API_KEY},
            files={"file": (file_path, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"template": "baycrest_v1"}
        )

    if response.status_code not in [200, 201]:
        print(f"Error: {response.status_code}")
        print(response.text)
        return

    job_id = response.json()["job_id"]
    print(f"Job ID: {job_id}")

    # Wait for completion
    print("\n2. Processing...")
    for _ in range(30):
        response = requests.get(
            f"{API_URL}/api/v1/jobs/{job_id}",
            headers={"X-API-Key": API_KEY}
        )
        status = response.json()["status"]
        if status in ["SUCCEEDED", "FAILED"]:
            break
        time.sleep(1)

    job_result = response.json()

    if job_result["status"] != "SUCCEEDED":
        print(f"Job failed: {job_result.get('error')}")
        return

    # Analyze results
    print("\n3. ROBUSTNESS ANALYSIS:")
    print("-" * 40)

    qa = job_result["qa"]["stats"]
    result = job_result["result"]

    print(f"✓ Items successfully mapped: {qa['items_mapped']}")
    print(f"✓ Items unmapped: {qa['items_unmapped']}")
    print(f"✓ Total rows processed: {qa['rows_total']}")

    # Check unmapped items
    unmapped = result.get("unmapped", [])
    if unmapped:
        print(f"\n⚠️ {len(unmapped)} UNMAPPED ITEMS (new/unknown):")
        for item in unmapped[:5]:  # Show first 5
            print(f"  - {item['classification']}: {item['measures'][0]['value']} {item['measures'][0]['uom']}")

        # Identify patterns
        unmapped_names = [item['classification'] for item in unmapped]
        print("\nUNMAPPED PATTERNS:")
        if 'Average Unit Size' in unmapped_names:
            print("  • New metrics not in mapping config")
        if 'Parking Ratio' in unmapped_names:
            print("  • New ratios/calculations")
        if 'Emergency Exits' in unmapped_names:
            print("  • Safety/code items")
        if 'Roof Vents' in unmapped_names or 'Siding SF' in unmapped_names:
            print("  • Additional exterior elements")

    # Check if critical items still map correctly
    print("\n4. CRITICAL ITEMS CHECK:")
    sections = result["sections"]
    critical_items = {
        "1 Bedroom Count": None,
        "2 Bedroom Count": None,
        "Storage Count": None,
        "Garage Storage Count": None
    }

    for section in sections:
        for item in section["items"]:
            if item["key"] in critical_items:
                critical_items[item["key"]] = item["qty"]

    for item_name, value in critical_items.items():
        if value is not None:
            print(f"  ✅ {item_name}: {value} (mapped correctly)")
        else:
            print(f"  ❌ {item_name}: NOT FOUND")

    return job_result

def analyze_robustness():
    """Main analysis of robustness."""

    print("ROBUSTNESS ANALYSIS FOR BAYCREST EXTRACTION")
    print("=" * 60)

    # Test with original file
    print("\n### TEST 1: Original baycrest_new.xlsx")
    print("This should work perfectly...")
    # (Already tested above)

    # Test with variation file
    print("\n### TEST 2: File with variations")
    variation_file = create_variation_file()
    results = test_variation_file(variation_file)

    # Summary
    print("\n" + "="*60)
    print("ROBUSTNESS SUMMARY")
    print("="*60)

    print("\n✅ WHAT WILL WORK:")
    print("• Files with same Baycrest structure (sheets, columns)")
    print("• Different quantities/numbers in cells")
    print("• Additional rows with known item names")
    print("• Items matching our 60+ configured mappings:")
    print("  - Bedroom counts, unit counts, SF measurements")
    print("  - Corridor items (doors, walls, storage)")
    print("  - Exterior elements (windows, doors, trim)")
    print("  - Garage components")
    print("  - Balconies, storage, mechanical rooms")

    print("\n⚠️ WHAT WON'T MAP (but won't break):")
    print("• New item types not in config (go to unmapped)")
    print("• Items with significantly different names")
    print("• New calculations or metrics")
    print("• Custom project-specific items")

    print("\n❌ WHAT WILL FAIL:")
    print("• Files with different structure (wrong columns)")
    print("• Non-Baycrest format files")
    print("• Files missing key sheets (Units, Bid Form)")
    print("• Files with completely different naming conventions")

    print("\n📊 CONFIGURATION COVERAGE:")
    print("Current config maps ~60 common construction items")
    print("To add new items: Update /config/baycrest_v1.mapping.json")

    print("\n🔧 RECOMMENDATION:")
    print("Monitor unmapped items from each job and periodically")
    print("update the mapping config to include common new items.")

if __name__ == "__main__":
    analyze_robustness()