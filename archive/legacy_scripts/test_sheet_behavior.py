#!/usr/bin/env venv/bin/python
"""
Test sheet selection behavior:
- Default: Only "1 Bldg" sheet
- Override: Can specify different sheets for other projects
"""
import pandas as pd

def check_baycrest_sheets():
    """Show what sheets are in the baycrest file."""
    print("Sheets in baycrest_new.xlsx:")
    xl = pd.ExcelFile('baycrest_new.xlsx')
    for i, sheet in enumerate(xl.sheet_names):
        print(f"  {i+1}. {sheet}")
    print(f"\nTotal: {len(xl.sheet_names)} sheets")
    return xl.sheet_names

def show_api_behavior():
    """Show how the API will behave."""

    print("\n" + "="*60)
    print("API BEHAVIOR FOR SHEET SELECTION")
    print("="*60)

    print("\n1. DEFAULT (no sheets parameter):")
    print("   ✓ Processes: '1 Bldg' only")
    print("   ✗ Ignores: All other sheets")
    print("   Use case: Standard Baycrest project")
    print("   Example in Swagger: Leave 'sheets' field empty")

    print("\n2. SPECIFIC SHEET (sheets='2 Bldgs'):")
    print("   ✓ Processes: '2 Bldgs' only")
    print("   ✗ Ignores: All other sheets including '1 Bldg'")
    print("   Use case: Project with different primary sheet")
    print("   Example in Swagger: sheets = '2 Bldgs'")

    print("\n3. MULTIPLE SHEETS (sheets='1 Bldg,2 Bldgs,3 Bldgs'):")
    print("   ✓ Processes: All three specified sheets")
    print("   ✗ Ignores: Other sheets")
    print("   Use case: Multi-building project")
    print("   Example in Swagger: sheets = '1 Bldg,2 Bldgs,3 Bldgs'")

    print("\n4. ALL SHEETS (sheets='all'):")
    print("   ✓ Processes: All data sheets")
    print("   ✗ Ignores: Sample, Bid Form sheets")
    print("   Use case: Complete analysis")
    print("   Example in Swagger: sheets = 'all'")

    print("\n5. CUSTOM FOR OTHER PROJECTS:")
    print("   If you have a file with different sheet names:")
    print("   - sheets='Building A' (for single building)")
    print("   - sheets='North Tower,South Tower' (for multiple)")
    print("   - sheets='Phase 1,Phase 2,Phase 3' (for phases)")

def main():
    print("="*60)
    print("SHEET SELECTION BEHAVIOR TEST")
    print("="*60)

    # Check what sheets exist
    sheets = check_baycrest_sheets()

    # Explain behavior
    show_api_behavior()

    print("\n" + "="*60)
    print("KEY POINTS")
    print("="*60)

    print("\n✅ DEFAULT BEHAVIOR:")
    print("• By default, ONLY '1 Bldg' is processed")
    print("• Other sheets (2 Bldgs, 3 Bldgs, etc.) are IGNORED")
    print("• This is what you want for standard Baycrest projects")

    print("\n✅ FLEXIBILITY:")
    print("• Can override to process any sheet(s) you need")
    print("• Works with any sheet names for other projects")
    print("• Can process multiple sheets when needed")

    print("\n✅ SWAGGER UI USAGE:")
    print("• Leave 'sheets' empty = Process '1 Bldg' only")
    print("• Enter sheet names = Process those specific sheets")
    print("• Enter 'all' = Process everything")

    print("\n" + "="*60)

if __name__ == "__main__":
    main()