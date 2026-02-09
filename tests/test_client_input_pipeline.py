"""
Regression checks for the client-provided input workbook.
"""

from pathlib import Path

from app.ui.excel_mapper import map_excel_with_catalog


def test_client_input_catalog_merge_and_unmapped_regression():
    """
    Ensures client workbook loads and all mapped IDs resolve to catalog items.

    Unmapped classifications are tracked explicitly as a regression guard so
    future mapping/config updates can be reviewed intentionally.
    """
    file_path = Path(__file__).parent / "test_data" / "client_input_data.xlsx"
    assert file_path.exists(), f"Missing fixture: {file_path}"

    state, warnings, debug = map_excel_with_catalog(str(file_path), template="baycrest_v1")

    assert state.total_items > 0
    assert debug["catalog"]["metrics"]["missing_extracted_count"] == 0

    unmapped = {item["classification"] for item in debug["mapping"]["unmapped"]}
    assert unmapped == {
        "Storage",
        "Window Wood Verticals Count",
        "Rec Room",
        "Chain Link Fence LF",
        "Garage Bike Rack Count",
    }

