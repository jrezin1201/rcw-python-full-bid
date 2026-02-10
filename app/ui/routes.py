"""
UI routes for the Bid Form application.
Handles page rendering and HTMX partial updates.
"""

import os
import uuid
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, File, Form, Request, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.core.logging import get_logger
from app.ui.viewmodels import BidFormState, LineItem, ToggleMask, ProjectInfo
from app.ui.state import get_current_state, set_state, has_current_bid, get_current_warnings, set_warnings, set_debug, get_current_debug
from app.ui.catalog_service import BidCatalog
from app.ui.excel_mapper import map_excel_to_bid_form, map_excel_with_catalog
from app.ui.constants import DIFFICULTY_LEVELS, SECTION_ORDER
from app.services.baycrest_normalizer import BaycrestNormalizer
from app.services.validators.baycrest_signature import validate_baycrest_workbook
from app.services.bid_excel_service import (
    export_internal_bid_workbook,
    export_proposal_workbook,
    import_internal_bid_workbook,
    is_internal_bid_workbook,
)

logger = get_logger(__name__)

# Create router
router = APIRouter()

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# ========== Helper Functions ==========

def format_currency(value: float) -> str:
    """Format a number as currency."""
    return f"${value:,.2f}"

def format_number(value: float, max_decimals: int = 2) -> str:
    """Format number with comma separators and trimmed decimals."""
    formatted = f"{value:,.{max_decimals}f}"
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted

def format_currency_input(value: float) -> str:
    """Format number for currency input display."""
    return f"{value:,.2f}"

def parse_numeric_input(raw: str, field_name: str) -> float:
    """Parse numeric user input allowing commas and currency symbols."""
    cleaned = str(raw or "").strip().replace(",", "").replace("$", "")
    if cleaned == "":
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    try:
        return float(cleaned)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")


def get_template_context(request: Request, **kwargs):
    """Get base template context with common data."""
    context = {
        "request": request,
        "format_currency": format_currency,
        "format_number": format_number,
        "format_currency_input": format_currency_input,
        "current_year": datetime.now().year,
        **kwargs
    }

    # Add current bid if available
    if has_current_bid():
        context["has_bid"] = True
        state = get_current_state()
        if state:
            context["project_name"] = state.project_name
            context["total_items"] = state.total_items
            context["source_file"] = state.source_file

    return context


# ========== Page Routes ==========

@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Render the home page with upload form."""
    context = get_template_context(request, page="home")
    return templates.TemplateResponse("index.html", context)


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    template: str = Form(default="baycrest_v1")
):
    """
    Handle file upload, parse Excel, and redirect to bid form.
    """
    try:
        # Validate file type
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Please upload an Excel file (.xlsx or .xls)")

        # Save uploaded file temporarily
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, file.filename)

        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)

        logger.info(f"Processing uploaded file: {file.filename}")

        # If this is an editable internal workbook, import it directly.
        if is_internal_bid_workbook(file_path):
            bid_state = import_internal_bid_workbook(file_path)
            qa_warnings = []
            debug_payload = {}
        else:
            # Validate template signature
            if template == "baycrest_v1":
                sig = validate_baycrest_workbook(file_path)
                if not sig.ok:
                    # Clean up
                    os.remove(file_path)
                    os.rmdir(temp_dir)
                    raise HTTPException(
                        status_code=400,
                        detail=f"File doesn't match Baycrest template: {'; '.join(sig.warnings)}"
                    )

            # Parse the Excel file using CATALOG-DRIVEN mapping
            # This ensures UOM comes from catalog, not extraction defaults
            bid_state, qa_warnings, debug_payload = map_excel_with_catalog(file_path, template)

        # Store state
        bid_id = str(uuid.uuid4())
        bid_state.project_id = bid_id
        bid_state.source_file = file.filename
        bid_state.created_at = datetime.now(timezone.utc).isoformat()

        # Store warnings for display in UI
        set_warnings(bid_id, qa_warnings)

        set_state(bid_id, bid_state)
        set_debug(bid_id, debug_payload)

        # Clean up temp file
        os.remove(file_path)
        os.rmdir(temp_dir)

        # Redirect to bid form
        return RedirectResponse(url="/bid", status_code=303)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")



def sort_sections(sections: list) -> list:
    """Sort sections by the defined order."""
    def section_sort_key(section_name):
        name_lower = section_name.lower()
        for i, ordered in enumerate(SECTION_ORDER):
            if ordered.lower() == name_lower or ordered.lower() in name_lower or name_lower in ordered.lower():
                return (i, section_name)
        return (len(SECTION_ORDER), section_name)  # Unknown sections go at the end

    return sorted(sections, key=section_sort_key)


@router.get("/bid", response_class=HTMLResponse)
async def bid_form_page(request: Request):
    """Render the bid form page."""
    state = get_current_state()
    warnings = []

    if not state:
        # No bid form available, create a sample one for testing
        from app.ui.excel_mapper import create_sample_bid_form
        sample_state = create_sample_bid_form()
        set_state("sample", sample_state)
        state = sample_state
    else:
        # Get QA warnings for display
        warnings = get_current_warnings()

    # Sort sections to match proposal order
    sections = sort_sections(state.get_sections())

    debug_payload = get_current_debug()

    # Raw sections preserve Excel order
    raw_sections = state.get_raw_sections()

    context = get_template_context(
        request,
        page="bid",
        bid_state=state,
        sections=sections,
        raw_sections=raw_sections,
        difficulty_options=DIFFICULTY_LEVELS,
        qa_warnings=warnings,  # Include warnings for QA panel
        project_info=state.project_info,  # Include project info for form
        debug_payload=debug_payload
    )

    return templates.TemplateResponse("bid_form.html", context)


# ========== HTMX Partial Update Routes ==========

@router.get("/bid/totals", response_class=HTMLResponse)
async def get_totals(request: Request):
    """Return the totals panel HTML for HTMX refresh."""
    state = get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active bid form")

    context = get_template_context(
        request,
        bid_state=state
    )

    totals_html = templates.get_template("partials/totals.html").render(context)
    return HTMLResponse(totals_html)


@router.post("/bid/item/{item_id}/qty", response_class=HTMLResponse)
async def update_item_qty(
    request: Request,
    item_id: str,
    qty: str = Form(...)
):
    """Update item quantity and return updated row."""
    state = get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active bid form")

    # Update quantity
    parsed_qty = parse_numeric_input(qty, "quantity")
    if not state.update_item_qty(item_id, parsed_qty):
        raise HTTPException(status_code=404, detail="Item not found")

    item = state.get_item(item_id)

    context = get_template_context(
        request,
        item=item,
        bid_state=state,
        difficulty_options=DIFFICULTY_LEVELS
    )

    row_html = templates.get_template("partials/bid_row.html").render(context)

    # Return only the row HTML; use HX-Trigger header to refresh totals panel
    response = HTMLResponse(row_html)
    response.headers["HX-Trigger"] = "totals-updated"
    return response


@router.post("/bid/item/{item_id}/difficulty", response_class=HTMLResponse)
async def update_item_difficulty(
    request: Request,
    item_id: str,
    difficulty: int = Form(...)
):
    """Update item difficulty and return updated row."""
    state = get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active bid form")

    # Update difficulty
    if not state.set_item_difficulty(item_id, difficulty):
        raise HTTPException(status_code=404, detail="Item not found")

    item = state.get_item(item_id)

    context = get_template_context(
        request,
        item=item,
        bid_state=state,
        difficulty_options=DIFFICULTY_LEVELS
    )

    row_html = templates.get_template("partials/bid_row.html").render(context)

    # Return only the row HTML; use HX-Trigger header to refresh totals panel
    response = HTMLResponse(row_html)
    response.headers["HX-Trigger"] = "totals-updated"
    return response


@router.post("/bid/item/{item_id}/difficulty-add", response_class=HTMLResponse)
async def update_item_difficulty_add(
    request: Request,
    item_id: str,
    level: int = Form(...),
    amount: str = Form(...)
):
    """Update absolute difficulty add-on for an item and return updated row."""
    state = get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active bid form")

    parsed_amount = parse_numeric_input(amount, "difficulty amount")
    if not state.update_item_difficulty_add(item_id, level, parsed_amount):
        raise HTTPException(status_code=404, detail="Item not found")

    item = state.get_item(item_id)
    context = get_template_context(
        request,
        item=item,
        bid_state=state,
        difficulty_options=DIFFICULTY_LEVELS
    )

    row_html = templates.get_template("partials/bid_row.html").render(context)
    response = HTMLResponse(row_html)
    response.headers["HX-Trigger"] = "totals-updated"
    return response


@router.post("/bid/item/{item_id}/toggle", response_class=HTMLResponse)
async def toggle_item_flag(
    request: Request,
    item_id: str,
    toggle_name: str = Form(...)
):
    """Toggle an item flag and return updated row."""
    state = get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active bid form")

    # Toggle the flag
    if not state.toggle_item(item_id, toggle_name):
        raise HTTPException(status_code=404, detail="Item not found")

    item = state.get_item(item_id)

    context = get_template_context(
        request,
        item=item,
        bid_state=state,
        difficulty_options=DIFFICULTY_LEVELS
    )

    row_html = templates.get_template("partials/bid_row.html").render(context)

    # Return only the row HTML; use HX-Trigger header to refresh totals panel
    response = HTMLResponse(row_html)
    response.headers["HX-Trigger"] = "totals-updated"
    return response


@router.post("/bid/item/{item_id}/price", response_class=HTMLResponse)
async def update_item_price(
    request: Request,
    item_id: str,
    unit_price: str = Form(...)
):
    """Update item unit price and return updated row."""
    state = get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active bid form")

    # Find and update the item
    item = state.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    parsed_price = parse_numeric_input(unit_price, "unit price")
    item.unit_price_base = max(0, parsed_price)

    context = get_template_context(
        request,
        item=item,
        bid_state=state,
        difficulty_options=DIFFICULTY_LEVELS
    )

    row_html = templates.get_template("partials/bid_row.html").render(context)

    response = HTMLResponse(row_html)
    response.headers["HX-Trigger"] = "totals-updated"
    return response


@router.post("/bid/item/{item_id}/mult", response_class=HTMLResponse)
async def update_item_multiplier(
    request: Request,
    item_id: str,
    mult: str = Form(...)
):
    """Update item multiplier and return updated row."""
    state = get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active bid form")

    # Update multiplier
    parsed_mult = parse_numeric_input(mult, "multiplier")
    if not state.update_item_mult(item_id, parsed_mult):
        raise HTTPException(status_code=404, detail="Item not found")

    item = state.get_item(item_id)

    context = get_template_context(
        request,
        item=item,
        bid_state=state,
        difficulty_options=DIFFICULTY_LEVELS
    )

    row_html = templates.get_template("partials/bid_row.html").render(context)

    # Return only the row HTML; use HX-Trigger header to refresh totals panel
    response = HTMLResponse(row_html)
    response.headers["HX-Trigger"] = "totals-updated"
    return response


@router.post("/bid/item/{item_id}/notes", response_class=HTMLResponse)
async def update_item_notes(
    request: Request,
    item_id: str,
    notes: str = Form(default="")
):
    """Update item notes and return updated row."""
    state = get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active bid form")

    item = state.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Update notes (empty string becomes None)
    item.notes = notes.strip() if notes.strip() else None

    context = get_template_context(
        request,
        item=item,
        bid_state=state,
        difficulty_options=DIFFICULTY_LEVELS
    )

    row_html = templates.get_template("partials/bid_row.html").render(context)
    return HTMLResponse(row_html)


# ========== Additional Routes ==========

@router.get("/logic", response_class=HTMLResponse)
async def logic_page(request: Request):
    """Render the logic/business rules page."""
    state = get_current_state()

    if not state:
        # No bid form available, create a sample one for testing
        from app.ui.excel_mapper import create_sample_bid_form
        sample_state = create_sample_bid_form()
        set_state("sample", sample_state)
        state = sample_state

    # Build sections dictionary with items grouped by section
    sections_dict = {}
    for section_name in state.get_sections():
        sections_dict[section_name] = state.get_items_by_section(section_name)

    # Build concrete worked examples so logic is easy to validate.
    logic_examples = []
    for item in [i for i in state.items if i.qty > 0][:5]:
        difficulty_add = item.difficulty_adders.get(item.difficulty, 0.0)
        toggle_mult = item.toggle_mask.get_multiplier()
        base_plus_difficulty = item.unit_price_base + difficulty_add
        effective_unit = base_plus_difficulty * toggle_mult * item.mult
        row_total = item.qty * effective_unit

        logic_examples.append({
            "name": item.name,
            "section": item.section,
            "uom": item.uom,
            "qty": item.qty,
            "base_price": item.unit_price_base,
            "difficulty_level": item.difficulty,
            "difficulty_add": difficulty_add,
            "toggle_multiplier": toggle_mult,
            "manual_multiplier": item.mult,
            "effective_unit": effective_unit,
            "row_total": row_total,
        })

    toggle_rules = [
        {"name": "Tax", "flag": "tax", "on_effect": "x1.00", "off_effect": "x0.92"},
        {"name": "Labor", "flag": "labor", "on_effect": "x1.00", "off_effect": "x0.70"},
        {"name": "Materials", "flag": "materials", "on_effect": "x1.00", "off_effect": "x0.80"},
        {"name": "Equipment", "flag": "equipment", "on_effect": "x1.00", "off_effect": "x1.00"},
        {"name": "Subcontractor", "flag": "subcontractor", "on_effect": "x1.00", "off_effect": "x1.00"},
    ]

    # Get logic rules and calculations for display
    context = get_template_context(
        request,
        page="logic",
        bid_state=state,
        sections=sections_dict,  # Now a dictionary of section_name -> list of items
        total_items=state.total_items,
        grand_total=state.grand_total,
        section_totals=state.section_totals,
        logic_examples=logic_examples,
        toggle_rules=toggle_rules,
    )

    return templates.TemplateResponse("logic.html", context)


@router.get("/print", response_class=HTMLResponse)
async def print_page(request: Request):
    """Render the print-friendly bid proposal page."""
    from datetime import datetime

    state = get_current_state()
    if not state:
        # Redirect to home if no bid data
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=302)

    # Sort sections to match proposal order
    sections = sort_sections(state.get_sections())

    sections_data = {}
    for section_name in sections:
        sections_data[section_name] = state.get_items_by_section(section_name)

    # Calculate unit count and total SF from items
    unit_count = 0
    total_sf = 0.0
    alternates = []

    for item in state.items:
        # Count units (look for unit count items)
        name_lower = item.name.lower()
        if 'unit' in name_lower and 'count' in name_lower:
            unit_count += int(item.qty)
        # Sum up SF items for total
        if item.uom == 'SF':
            total_sf += item.qty
        # Collect alternates
        if item.is_alternate:
            alternates.append(item)

    context = get_template_context(
        request,
        page="print",
        bid_state=state,
        sections=sections,
        sections_data=sections_data,
        project_info=state.project_info,
        today_date=datetime.now().strftime("%Y-%m-%d"),
        unit_count=unit_count,
        total_sf=total_sf,
        alternates=alternates,
    )

    return templates.TemplateResponse("print.html", context)


@router.post("/bid/project-info", response_class=HTMLResponse)
async def update_project_info(
    request: Request,
    developer: str = Form(default=""),
    address: str = Form(default=""),
    city: str = Form(default=""),
    contact: str = Form(default=""),
    phone: str = Form(default=""),
    email: str = Form(default=""),
    project_city: str = Form(default=""),
    arch_date: str = Form(default=""),
    landscape_date: str = Form(default=""),
):
    """Update project info and return the updated form partial."""
    state = get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active bid form")

    # Update project info
    state.project_info = ProjectInfo(
        developer=developer or None,
        address=address or None,
        city=city or None,
        contact=contact or None,
        phone=phone or None,
        email=email or None,
        project_city=project_city or None,
        arch_date=arch_date or None,
        landscape_date=landscape_date or None,
    )

    context = get_template_context(
        request,
        project_info=state.project_info
    )

    form_html = templates.get_template("partials/project_info_form.html").render(context)
    response = HTMLResponse(form_html)
    response.headers["HX-Trigger"] = "project-info-updated"
    return response


@router.get("/bid/export", response_class=HTMLResponse)
async def export_bid(request: Request, format: str = "json"):
    """Export the current bid in various formats."""
    state = get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active bid form")

    if format == "json":
        return state.model_dump_json(indent=2)
    elif format == "internal_xlsx":
        content = export_internal_bid_workbook(state)
        filename = f"{state.project_name or 'bid'}-internal.xlsx"
        return StreamingResponse(
            BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    elif format == "proposal_xlsx":
        content = export_proposal_workbook(state)
        filename = f"{state.project_name or 'bid'}-proposal.xlsx"
        return StreamingResponse(
            BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    elif format == "csv":
        # TODO: Implement CSV export
        raise HTTPException(status_code=501, detail="CSV export not yet implemented")
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format")


@router.get("/bid/missing-stubs")
async def get_missing_catalog_stubs(request: Request):
    """
    Generate catalog stubs for missing extracted items.

    Returns JSON that can be merged into config/bid_catalog.json
    to add missing items and reduce warnings.
    """
    from app.ui.state import get_current_warnings

    # Get warnings from current session
    warnings = get_current_warnings()

    # Extract missing item IDs from warnings
    missing_ids = []
    for w in warnings:
        if isinstance(w, str) and "not found in catalog" in w:
            # Extract ID from warning like "Extracted item 'xxx.yyy' not found in catalog"
            start = w.find("'")
            end = w.find("'", start + 1)
            if start > 0 and end > start:
                missing_ids.append(w[start+1:end])

    if not missing_ids:
        return {"message": "No missing items found", "stubs": []}

    # Generate stubs
    stubs = []
    for item_id in missing_ids:
        parts = item_id.split('.')
        section_id = parts[0] if len(parts) > 1 else 'unknown'
        item_slug = parts[-1] if parts else 'unknown'
        label = item_slug.replace('_', ' ').title()

        stub = {
            "id": item_id,
            "label": label,
            "uom": "EA",  # Default - should be updated
            "rates": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
            "default_multiplier": 1.0
        }
        stubs.append(stub)

    return {
        "message": f"Found {len(stubs)} missing items. Add these to config/bid_catalog.json",
        "total_missing": len(stubs),
        "stubs": stubs
    }


@router.post("/bid/clear", response_class=RedirectResponse)
async def clear_bid(request: Request):
    """Clear the current bid and redirect to home."""
    from app.ui.state import clear_state
    clear_state()
    return RedirectResponse(url="/", status_code=303)
