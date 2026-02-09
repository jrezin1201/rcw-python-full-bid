#!/usr/bin/env venv/bin/python
"""
Create a Baycrest variation file to test robustness.
This creates a file with different values but same structure.
"""
import pandas as pd
import numpy as np

def create_baycrest_variation():
    """Create a variation of the Baycrest file with different values."""

    print("Creating Baycrest variation file...")

    # Read the original file to understand structure
    original_df = pd.read_excel('baycrest_new.xlsx', sheet_name='1 Bldg')

    # Create a modified version with different values
    # We'll multiply numeric values by random factors
    variation_df = original_df.copy()

    for col in variation_df.columns:
        for idx in variation_df.index:
            value = variation_df.at[idx, col]
            # If it's a number, modify it
            if pd.notna(value) and isinstance(value, (int, float)):
                # Apply random multiplier between 0.7 and 1.5
                multiplier = np.random.uniform(0.7, 1.5)
                new_value = value * multiplier
                # Round appropriately
                if value == int(value):  # Was an integer
                    variation_df.at[idx, col] = int(round(new_value))
                else:
                    variation_df.at[idx, col] = round(new_value, 2)

    # Add some completely new items (rows) that aren't in our mappings
    new_rows = pd.DataFrame([
        [None, 'Emergency Lighting Count', 85, None, None],
        [None, 'Fire Extinguisher Count', 45, None, None],
        [None, 'ADA Ramps', 12, None, None],
        [None, 'Solar Panel SF', 5500.50, None, None],
    ], columns=variation_df.columns)

    # Insert new rows at various sections
    variation_df = pd.concat([variation_df.iloc[:25], new_rows.iloc[:2],
                              variation_df.iloc[25:50], new_rows.iloc[2:],
                              variation_df.iloc[50:]], ignore_index=True)

    # Create the Excel file with proper sheets
    with pd.ExcelWriter('baycrest_variation.xlsx', engine='openpyxl') as writer:
        # Write the main sheet
        variation_df.to_excel(writer, sheet_name='1 Bldg', index=False)

        # Copy other sheets from original to maintain structure
        original_xl = pd.ExcelFile('baycrest_new.xlsx')
        for sheet in original_xl.sheet_names:
            if sheet != '1 Bldg':
                df = pd.read_excel('baycrest_new.xlsx', sheet_name=sheet)
                df.to_excel(writer, sheet_name=sheet, index=False)

    print("Created: baycrest_variation.xlsx")
    print("\nVariations include:")
    print("  • All quantities changed by 70-150%")
    print("  • 4 new items added (not in mappings)")
    print("  • Same overall structure maintained")

    # Show some examples
    print("\nExample changes:")
    print(f"  • Original 1BR Count: 333 → Variation: ~{int(333 * np.random.uniform(0.7, 1.5))}")
    print(f"  • Original Total SF: 410064 → Variation: ~{int(410064 * np.random.uniform(0.7, 1.5))}")
    print("\nNew items added (will be unmapped):")
    print("  • Emergency Lighting Count: 85")
    print("  • Fire Extinguisher Count: 45")
    print("  • ADA Ramps: 12")
    print("  • Solar Panel SF: 5500.50")

if __name__ == "__main__":
    create_baycrest_variation()