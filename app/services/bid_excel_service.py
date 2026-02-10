"""
Excel import/export helpers for bid workflows.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

from app.ui.viewmodels import BidFormState, LineItem, ToggleMask, ProjectInfo

INTERNAL_MARKER = "__RCW_INTERNAL_BID_V1__"
PROPOSAL_TEMPLATE_PATH = Path("data/templates/proposal_template.xlsx")


def is_internal_bid_workbook(file_path: str) -> bool:
    """Detect whether a workbook is an editable internal bid export."""
    wb = load_workbook(file_path, data_only=False)
    try:
        ws = wb[wb.sheetnames[0]]
        return ws["A1"].value == INTERNAL_MARKER
    finally:
        wb.close()


def export_internal_bid_workbook(state: BidFormState) -> bytes:
    """
    Export a professional internal workbook with section headers, per-row
    pricing, exclusions, and a pricing summary table.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Internal Bid"

    # -- Styles --
    CURRENCY_FMT = '"$"#,##0.00'
    dark_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    label_font = Font(bold=True, size=10)
    normal_font = Font(size=10)
    exclusion_font = Font(italic=True, color="FF0000", size=10)
    bold_font = Font(bold=True, size=10)
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")

    # -- Column widths --
    col_widths = {"A": 40, "B": 10, "C": 8, "D": 12, "E": 10, "F": 10, "G": 10, "H": 15}
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = width

    # -- Header block (rows 1-9) matching proposal layout --
    info = state.project_info
    today = datetime.now(timezone.utc).date().isoformat()

    # Row 1
    ws["A1"] = "Developer:"
    ws["A1"].font = label_font
    ws["B1"] = info.developer or ""
    ws["E1"] = "Date:"
    ws["E1"].font = label_font
    ws["F1"] = today

    # Row 2
    ws["A2"] = "Address:"
    ws["A2"].font = label_font
    ws["B2"] = info.address or ""
    ws["E2"] = "Contact:"
    ws["E2"].font = label_font
    ws["F2"] = info.contact or ""

    # Row 3
    ws["A3"] = "City:"
    ws["A3"].font = label_font
    ws["B3"] = info.city or ""
    ws["E3"] = "Phone:"
    ws["E3"].font = label_font
    ws["F3"] = info.phone or ""

    # Row 4
    ws["E4"] = "Email:"
    ws["E4"].font = label_font
    ws["F4"] = info.email or ""

    # Row 6 - project details
    ws["A6"] = "PROJECT"
    ws["A6"].font = label_font
    ws["B6"] = state.project_name or ""
    ws["E6"] = "PLANS"
    ws["E6"].font = label_font
    ws["G6"] = "DATED"
    ws["G6"].font = label_font

    # Row 7
    unit_count = int(
        sum(
            item.qty
            for item in state.raw_items
            if not item.excluded
            and "unit" in item.name.lower()
            and "count" in item.name.lower()
        )
    )
    total_sf = sum(
        item.qty for item in state.raw_items if not item.excluded and item.uom.upper() == "SF"
    )
    ws["A7"] = "UNITS"
    ws["A7"].font = label_font
    ws["B7"] = f"{unit_count} Units" if unit_count else ""
    ws["E7"] = "ARCH"
    ws["E7"].font = label_font
    ws["G7"] = info.arch_date or ""

    # Row 8
    ws["A8"] = "CITY"
    ws["A8"].font = label_font
    ws["B8"] = info.project_city or info.city or ""
    ws["E8"] = "LANDSCAPE"
    ws["E8"].font = label_font
    ws["G8"] = info.landscape_date or ""

    # Row 9
    ws["A9"] = "SF"
    ws["A9"].font = label_font
    ws["B9"] = round(total_sf, 2) if total_sf else ""
    ws["E9"] = "9900 SPEC"
    ws["E9"].font = label_font
    ws["G9"] = "N/A"

    # -- Helper to write a dark section-header row --
    def write_section_header(row: int, title: str, subtotal: float | None = None):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
        cell = ws.cell(row, 1)
        cell.value = title.upper()
        cell.font = header_font
        cell.fill = dark_fill
        cell.alignment = left_align
        # Apply fill to all merged columns
        for c in range(2, 8):
            ws.cell(row, c).fill = dark_fill
        # Subtotal in column H
        h_cell = ws.cell(row, 8)
        h_cell.fill = dark_fill
        if subtotal is not None:
            h_cell.value = round(subtotal, 2)
            h_cell.number_format = CURRENCY_FMT
            h_cell.font = header_font
            h_cell.alignment = right_align
        else:
            h_cell.font = header_font

    # -- Scope sections --
    row = 12  # start after header block + blank row

    section_totals_map = {s.section_name.lower(): s.total for s in state.section_totals}

    for section_name in state.get_raw_sections():
        section_items = state.get_raw_items_by_section(section_name)
        active = [i for i in section_items if not i.excluded and not i.is_exclusion and i.qty > 0 and not i.is_alternate]
        exclusions = [i for i in section_items if i.is_exclusion]
        subtotal = section_totals_map.get(section_name.lower(), 0.0)

        # Section header row
        write_section_header(row, section_name, subtotal)
        row += 1

        # Column sub-headers
        for col, label in [(1, "Item"), (2, "Qty"), (3, "UOM"), (4, "$/Unit"), (8, "Total")]:
            c = ws.cell(row, col)
            c.value = label
            c.font = bold_font
            c.alignment = right_align if col >= 2 else left_align
        row += 1

        # Active item rows
        for item in active:
            ws.cell(row, 1).value = item.name
            ws.cell(row, 1).font = normal_font

            ws.cell(row, 2).value = float(item.qty)
            ws.cell(row, 2).font = normal_font

            ws.cell(row, 3).value = item.uom
            ws.cell(row, 3).font = normal_font

            ws.cell(row, 4).value = round(float(item.unit_price_effective), 2)
            ws.cell(row, 4).number_format = CURRENCY_FMT
            ws.cell(row, 4).font = normal_font

            ws.cell(row, 8).value = round(float(item.row_total), 2)
            ws.cell(row, 8).number_format = CURRENCY_FMT
            ws.cell(row, 8).font = normal_font

            row += 1

        # Exclusion rows
        for item in exclusions:
            ws.cell(row, 1).value = f"Excludes {item.name}"
            ws.cell(row, 1).font = exclusion_font
            row += 1

        # Blank spacer
        row += 1

    # -- Pricing Summary Table --
    write_section_header(row, "PRICING")
    row += 1

    # Column headers
    ws.cell(row, 1).value = "Section"
    ws.cell(row, 1).font = bold_font
    ws.cell(row, 8).value = "Amount"
    ws.cell(row, 8).font = bold_font
    ws.cell(row, 8).alignment = right_align
    row += 1

    for section_name in state.get_raw_sections():
        subtotal = section_totals_map.get(section_name.lower(), 0.0)
        ws.cell(row, 1).value = section_name
        ws.cell(row, 1).font = normal_font
        ws.cell(row, 8).value = round(subtotal, 2)
        ws.cell(row, 8).number_format = CURRENCY_FMT
        ws.cell(row, 8).font = normal_font
        row += 1

    # Grand total
    ws.cell(row, 1).value = "Total"
    ws.cell(row, 1).font = bold_font
    ws.cell(row, 8).value = round(float(state.grand_total), 2)
    ws.cell(row, 8).number_format = CURRENCY_FMT
    ws.cell(row, 8).font = bold_font
    ws.cell(row, 8).alignment = right_align
    row += 2

    # -- Alternates section --
    alternates = [i for i in state.raw_items if i.is_alternate]
    if alternates:
        write_section_header(row, "ADD ALTERNATES")
        row += 1

        for item in alternates:
            ws.cell(row, 1).value = item.name
            ws.cell(row, 1).font = normal_font
            ws.cell(row, 8).value = round(float(item.row_total), 2)
            ws.cell(row, 8).number_format = CURRENCY_FMT
            ws.cell(row, 8).font = normal_font
            row += 1

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def import_internal_bid_workbook(file_path: str) -> BidFormState:
    """Import state from an editable internal workbook export."""
    wb = load_workbook(file_path, data_only=False)
    try:
        ws = wb[wb.sheetnames[0]]
        if ws["A1"].value != INTERNAL_MARKER:
            raise ValueError("Not a supported internal workbook format")

        project_info = ProjectInfo(
            developer=_string(ws["B3"].value),
            address=_string(ws["B4"].value),
            city=_string(ws["B5"].value),
            contact=_string(ws["B6"].value),
            phone=_string(ws["B7"].value),
            email=_string(ws["B8"].value),
        )

        items: list[LineItem] = []
        row = 11
        while True:
            section = ws.cell(row, 1).value
            name = ws.cell(row, 2).value
            if not section and not name:
                break

            qty = _float(ws.cell(row, 3).value)
            uom = _string(ws.cell(row, 4).value) or "EA"
            base_price = _float(ws.cell(row, 5).value)
            difficulty = int(_float(ws.cell(row, 6).value) or 1)
            adders = {
                1: _float(ws.cell(row, 7).value),
                2: _float(ws.cell(row, 8).value),
                3: _float(ws.cell(row, 9).value),
                4: _float(ws.cell(row, 10).value),
                5: _float(ws.cell(row, 11).value),
            }

            toggle_mask = ToggleMask(
                tax=_bool(ws.cell(row, 12).value, True),
                labor=_bool(ws.cell(row, 13).value, True),
                materials=_bool(ws.cell(row, 14).value, True),
                equipment=_bool(ws.cell(row, 15).value, False),
                subcontractor=_bool(ws.cell(row, 16).value, False),
            )
            mult = _float(ws.cell(row, 17).value, 1.0)
            notes = _string(ws.cell(row, 20).value)
            is_alt = _bool(ws.cell(row, 21).value, False)

            items.append(
                LineItem(
                    id=f"imported_{row}",
                    section=_string(section) or "General",
                    name=_string(name) or f"Item {row}",
                    qty=qty,
                    uom=uom,
                    unit_price_base=base_price,
                    difficulty=max(1, min(5, difficulty)),
                    difficulty_adders=adders,
                    toggle_mask=toggle_mask,
                    mult=mult,
                    notes=notes,
                    is_alternate=is_alt,
                )
            )
            row += 1

        project_name = _string(ws["B2"].value) or Path(file_path).stem
        return BidFormState(
            project_name=project_name,
            raw_items=items,
            created_at=datetime.now(timezone.utc).isoformat(),
            source_file=Path(file_path).name,
            project_info=project_info,
        )
    finally:
        wb.close()


def export_proposal_workbook(state: BidFormState) -> bytes:
    """
    Export client-facing proposal workbook using Sheet1 from template.
    """
    if PROPOSAL_TEMPLATE_PATH.exists():
        wb = load_workbook(PROPOSAL_TEMPLATE_PATH)
    else:
        wb = Workbook()
        wb.active.title = "Sheet1"

    ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb[wb.sheetnames[0]]

    # Header metadata
    _set_ws_value(ws, "B1", state.project_info.developer or ws["B1"].value)
    _set_ws_value(ws, "B2", state.project_info.address or ws["B2"].value)
    _set_ws_value(ws, "B3", state.project_info.city or ws["B3"].value)
    _set_ws_value(ws, "F1", datetime.now(timezone.utc).date().isoformat())
    _set_ws_value(ws, "F2", state.project_info.contact or ws["F2"].value)
    _set_ws_value(ws, "F3", state.project_info.phone or ws["F3"].value)
    _set_ws_value(ws, "F4", state.project_info.email or ws["F4"].value)
    _set_ws_value(ws, "B6", state.project_name or ws["B6"].value)

    # Derived metrics
    unit_count = int(
        sum(item.qty for item in state.raw_items if not item.excluded and "unit" in item.name.lower() and "count" in item.name.lower())
    )
    total_sf = float(sum(item.qty for item in state.raw_items if not item.excluded and item.uom.upper() == "SF"))
    _set_ws_value(ws, "B7", f"{unit_count} Units" if unit_count else ws["B7"].value)
    _set_ws_value(ws, "B8", state.project_info.project_city or ws["B8"].value)
    _set_ws_value(ws, "B9", round(total_sf, 2) if total_sf else ws["B9"].value)

    # Write scope items and exclusions into each section's row range
    scope_sections = {
        "units": {"start": 13, "end": 26},
        "stairs": {"start": 29, "end": 36},
        "corridors": {"start": 39, "end": 53},
        "amenity": {"start": 56, "end": 66},
        "exterior": {"start": 69, "end": 84},
        "garage": {"start": 87, "end": 90},
        "landscape": {"start": 92, "end": 95},
    }

    scope_font = Font(italic=False)
    exclusion_font = Font(italic=True, color="FF0000")

    for section_key, row_range in scope_sections.items():
        # Clear existing content in the range
        for r in range(row_range["start"], row_range["end"] + 1):
            try:
                ws[f"A{r}"] = None
            except AttributeError:
                pass

        # Find matching items by section name (case-insensitive)
        section_items = []
        for sec_name in state.get_raw_sections():
            if sec_name.lower() == section_key:
                section_items = state.get_raw_items_by_section(sec_name)
                break

        active = [i for i in section_items if not i.excluded and i.qty > 0]
        exclusions = [i for i in section_items if i.is_exclusion]

        r = row_range["start"]
        for item in active:
            if r > row_range["end"]:
                break
            try:
                ws[f"A{r}"] = item.name
                ws[f"A{r}"].font = scope_font
            except AttributeError:
                pass
            r += 1
        for item in exclusions:
            if r > row_range["end"]:
                break
            try:
                ws[f"A{r}"] = f"Excludes {item.name}"
                ws[f"A{r}"].font = exclusion_font
            except AttributeError:
                pass
            r += 1

    section_totals = {s.section_name.lower(): s.total for s in state.section_totals}
    pricing_rows = [
        (98, "units"),
        (99, "corridors"),
        (100, "stairs"),
        (101, "amenity"),
        (102, "exterior"),
        (103, "garage"),
        (104, "landscape"),
    ]
    for row, section_key in pricing_rows:
        _set_ws_value(ws, f"E{row}", round(float(section_totals.get(section_key, 0.0)), 2))
        ws[f"E{row}"].number_format = '"$"#,##0.00'
    # Use actual grand total so standalone/unmapped priced rows remain included.
    _set_ws_value(ws, "E105", round(float(state.grand_total), 2))
    ws["E105"].number_format = '"$"#,##0.00'

    # Add alternates list
    for r in range(121, 220):
        for col in ("A", "D"):
            try:
                ws[f"{col}{r}"] = None
            except AttributeError:
                # Skip merged/read-only cells in template regions.
                pass
    alt_row = 121
    for item in [i for i in state.raw_items if i.is_alternate]:
        ws[f"A{alt_row}"] = item.name
        try:
            ws[f"D{alt_row}"] = round(float(item.row_total), 2)
            ws[f"D{alt_row}"].number_format = '"$"#,##0.00'
        except AttributeError:
            pass
        alt_row += 1

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _float(value, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _string(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return default


def _set_ws_value(ws, cell_ref: str, value) -> None:
    """Set a worksheet value, redirecting to merged-cell anchor when needed."""
    try:
        ws[cell_ref] = value
        return
    except AttributeError:
        pass

    for merged_range in ws.merged_cells.ranges:
        if cell_ref in merged_range:
            anchor = ws.cell(merged_range.min_row, merged_range.min_col).coordinate
            ws[anchor] = value
            return
