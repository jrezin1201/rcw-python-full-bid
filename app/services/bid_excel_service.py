"""
Excel import/export helpers for bid workflows.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone

from openpyxl import Workbook, load_workbook

from app.ui.viewmodels import BidFormState, LineItem, ToggleMask, ProjectInfo

INTERNAL_MARKER = "__RCW_INTERNAL_BID_V1__"
INTERNAL_TEMPLATE_PATH = Path("data/templates/internal_bid_template.xlsx")
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
    Export an internal workbook with editable rows and formulas.

    This output is re-importable via `import_internal_bid_workbook`.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Bid Form"

    ws["A1"] = INTERNAL_MARKER
    ws["A2"] = "Project"
    ws["B2"] = state.project_name
    ws["A3"] = "Developer"
    ws["B3"] = state.project_info.developer or ""
    ws["A4"] = "Address"
    ws["B4"] = state.project_info.address or ""
    ws["A5"] = "City"
    ws["B5"] = state.project_info.city or ""
    ws["A6"] = "Contact"
    ws["B6"] = state.project_info.contact or ""
    ws["A7"] = "Phone"
    ws["B7"] = state.project_info.phone or ""
    ws["A8"] = "Email"
    ws["B8"] = state.project_info.email or ""

    headers = [
        "Section",
        "Item",
        "Qty",
        "UOM",
        "BasePrice",
        "Difficulty",
        "Add_L1",
        "Add_L2",
        "Add_L3",
        "Add_L4",
        "Add_L5",
        "Tax",
        "Labor",
        "Materials",
        "Equipment",
        "Subcontractor",
        "Multiplier",
        "EffectiveUnit",
        "RowTotal",
        "Notes",
        "IsAlternate",
    ]
    header_row = 10
    for col, name in enumerate(headers, start=1):
        ws.cell(header_row, col).value = name

    start_row = header_row + 1
    for idx, item in enumerate(state.items):
        r = start_row + idx
        ws.cell(r, 1).value = item.section
        ws.cell(r, 2).value = item.name
        ws.cell(r, 3).value = float(item.qty)
        ws.cell(r, 4).value = item.uom
        ws.cell(r, 5).value = float(item.unit_price_base)
        ws.cell(r, 6).value = int(item.difficulty)
        ws.cell(r, 7).value = float(item.difficulty_adders.get(1, 0.0))
        ws.cell(r, 8).value = float(item.difficulty_adders.get(2, 0.0))
        ws.cell(r, 9).value = float(item.difficulty_adders.get(3, 0.0))
        ws.cell(r, 10).value = float(item.difficulty_adders.get(4, 0.0))
        ws.cell(r, 11).value = float(item.difficulty_adders.get(5, 0.0))
        ws.cell(r, 12).value = bool(item.toggle_mask.tax)
        ws.cell(r, 13).value = bool(item.toggle_mask.labor)
        ws.cell(r, 14).value = bool(item.toggle_mask.materials)
        ws.cell(r, 15).value = bool(item.toggle_mask.equipment)
        ws.cell(r, 16).value = bool(item.toggle_mask.subcontractor)
        ws.cell(r, 17).value = float(item.mult)
        ws.cell(r, 18).value = (
            f"=(E{r}+CHOOSE(F{r},G{r},H{r},I{r},J{r},K{r}))"
            f"*IF(L{r},1,0.92)*IF(M{r},1,0.7)*IF(N{r},1,0.8)*Q{r}"
        )
        ws.cell(r, 19).value = f"=C{r}*R{r}"
        ws.cell(r, 20).value = item.notes or ""
        ws.cell(r, 21).value = bool(item.is_alternate)

    total_row = start_row + len(state.items) + 1
    ws.cell(total_row, 18).value = "Grand Total"
    ws.cell(total_row, 19).value = f"=SUM(S{start_row}:S{total_row-2})"

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
            items=items,
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
        sum(item.qty for item in state.items if "unit" in item.name.lower() and "count" in item.name.lower())
    )
    total_sf = float(sum(item.qty for item in state.items if item.uom.upper() == "SF"))
    _set_ws_value(ws, "B7", f"{unit_count} Units" if unit_count else ws["B7"].value)
    _set_ws_value(ws, "B8", state.project_info.project_city or ws["B8"].value)
    _set_ws_value(ws, "B9", round(total_sf, 2) if total_sf else ws["B9"].value)

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
    for item in [i for i in state.items if i.is_alternate]:
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
