"""
Maps parsed Excel data to BidFormState for UI display.
Bridges the gap between the parser output and the UI models.

IMPORTANT: This module uses CATALOG-DRIVEN rendering.
- The catalog defines all items with UOM and rates (source of truth)
- Extraction only provides quantities
- UI renders catalog rows, not extracted items directly
"""

import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from app.ui.viewmodels import BidFormState, LineItem, ToggleMask
from app.ui.catalog_service import BidCatalog
from app.services.baycrest_normalizer import BaycrestNormalizer
from app.services.takeoff_mapper import TakeoffMapper
from app.services.uom_utils import normalize_uom
from app.core.logging import get_logger

logger = get_logger(__name__)

# Default pricing table (base prices for items)
# In production, this would come from a database or config file
DEFAULT_PRICING = {
    # Units
    "Studio Unit Count": 1400.00,
    "1 Bed Room Count": 1500.00,
    "2 Bedroom Count": 1600.00,
    "3 Bedroom Count": 1800.00,
    "4 Bedroom Count": 2000.00,
    "Total Unit Count": 1550.00,

    # Square footage
    "Total SF": 8.50,
    "Total GSF": 8.75,
    "Parking Area SF": 12.00,
    "Common Area SF": 15.00,
    "Residential SF": 18.00,
    "Commercial SF": 22.00,

    # Prime coat items
    "True Prime Coat": 300.00,
    "Dry Fall Black Primer on Steel": 280.00,
    "Dry Fall White Primer on Steel": 280.00,
    "Prime Coat Black": 250.00,
    "Prime Coat White": 250.00,

    # Walls
    "Eggshell Walls": 200.00,
    "Semi-Gloss Walls": 220.00,
    "Flat Walls": 180.00,
    "Satin Walls": 210.00,

    # Doors and trim
    "Metal Doors & Frames": 450.00,
    "Wood Doors": 380.00,
    "Door Frames": 120.00,
    "Base Board LF": 12.00,
    "Crown Molding LF": 18.00,

    # Ceilings
    "Flat Ceilings": 150.00,
    "Textured Ceilings": 180.00,
    "Acoustic Ceilings": 200.00,

    # Exterior
    "Exterior Walls": 350.00,
    "Stucco": 420.00,
    "Siding": 380.00,

    # Specialty
    "Epoxy Floors": 850.00,
    "Anti-Graffiti Coating": 450.00,
    "Fire Retardant Paint": 550.00,

    # Default for unknown items
    "_default": 100.00
}

# Section categorization rules
SECTION_RULES = {
    "Units": ["unit count", "unit", "bedroom", "studio", "bed room"],
    "Areas": ["sf", "square", "gsf", "area", "footage"],
    "Prime Coat": ["prime", "primer", "dry fall"],
    "Interior Walls": ["wall", "eggshell", "semi-gloss", "flat", "satin"],
    "Doors & Trim": ["door", "frame", "base board", "crown", "molding", "trim"],
    "Ceilings": ["ceiling", "acoustic"],
    "Exterior": ["exterior", "stucco", "siding", "outside"],
    "Specialty": ["epoxy", "anti-graffiti", "fire retardant", "special"],
    "General": []  # Catch-all
}


def categorize_item(item_name: str) -> str:
    """
    Categorize an item based on its name.
    Returns the section name.
    """
    item_lower = item_name.lower()

    for section, keywords in SECTION_RULES.items():
        if section == "General":
            continue  # Skip catch-all for now

        for keyword in keywords:
            if keyword in item_lower:
                return section

    return "General"  # Default section


def get_base_price(item_name: str) -> float:
    """
    Get the base price for an item.
    Tries exact match first, then partial match, then default.
    """
    # Try exact match
    if item_name in DEFAULT_PRICING:
        return DEFAULT_PRICING[item_name]

    # Try partial match
    item_lower = item_name.lower()
    for key, price in DEFAULT_PRICING.items():
        if key.lower() in item_lower or item_lower in key.lower():
            return price

    # Return default
    return DEFAULT_PRICING.get("_default", 100.00)


def parse_uom(raw_uom: Optional[str]) -> str:
    """
    Parse and standardize unit of measure using canonical normalization.
    Canonical set: EA, SF, LF, LVL (never FT).
    """
    if not raw_uom:
        return "EA"

    # Use centralized normalization
    normalized = normalize_uom(raw_uom)
    if normalized:
        return normalized

    # Fallback for unknown UOMs
    uom_upper = str(raw_uom).upper().strip()
    return uom_upper[:5] if len(uom_upper) > 5 else uom_upper


def map_excel_with_catalog(
    file_path: str,
    template: str = "baycrest_v1",
    catalog_path: str = "config/bid_catalog.json"
) -> tuple[BidFormState, List[str], Dict[str, Any]]:
    """
    Map Excel file to BidFormState using CATALOG-DRIVEN rendering.

    This is the preferred method:
    - Catalog defines items with UOM and rates (source of truth)
    - Extraction provides quantities
    - Returns warnings for any issues

    Args:
        file_path: Path to Excel file
        template: Mapping template name
        catalog_path: Path to catalog JSON

    Returns:
        Tuple of (BidFormState, list of warnings, debug payload)
    """
    logger.info(f"Mapping Excel with catalog: {file_path}")

    warnings: List[str] = []

    # Load catalog
    catalog = BidCatalog.load(catalog_path)

    # Run extraction and mapping
    normalizer = BaycrestNormalizer()
    result = normalizer.normalize_file(file_path)
    raw_data = result.get('raw_data', [])

    # Map to sections using the template
    mapper = TakeoffMapper(template=template)
    mapping_result = mapper.map_rows_to_sections(raw_data)

    # Get bid_items from mapping result
    bid_items = mapping_result.get('bid_items', [])

    # Merge extraction into catalog
    merge_warnings = catalog.merge_extraction(bid_items)
    warnings.extend(merge_warnings)

    # Add QA warnings from mapping
    qa_warnings = mapping_result.get('qa', {}).get('warnings', [])
    for w in qa_warnings:
        if isinstance(w, dict):
            warnings.append(w.get('message', str(w)))
        else:
            warnings.append(str(w))

    # Convert catalog to BidFormState
    items = []
    for section in catalog.get_sections():
        for catalog_item in section.items:
            # Get rate for default difficulty (1)
            base_rate = catalog_item.get_rate(1)
            difficulty_adders = {
                level: max(0.0, catalog_item.get_rate(level) - base_rate)
                for level in range(1, 6)
            }

            line_item = LineItem(
                id=catalog_item.id.replace('.', '_'),  # Make ID safe
                section=section.name,
                name=catalog_item.label,
                qty=catalog_item.qty,
                uom=catalog_item.uom,  # UOM from catalog (source of truth)
                unit_price_base=base_rate,
                difficulty=1,
                difficulty_adders=difficulty_adders,
                toggle_mask=ToggleMask(),
                mult=catalog_item.default_multiplier,
                notes=catalog_item.source_classification
            )
            items.append(line_item)

    # Ensure all extracted rows appear in the UI, even if they don't map to the catalog.
    for idx, unmapped in enumerate(mapping_result.get("unmapped", [])):
        measures = unmapped.get("measures", [])
        primary = measures[0] if measures else {}
        qty = float(primary.get("value", 0) or 0)
        uom = primary.get("uom", "EA") or "EA"
        source_class = unmapped.get("classification", "Unmapped Item")
        provenance = unmapped.get("provenance", {})

        items.append(
            LineItem(
                id=f"unmapped_{idx}",
                section="Unmapped",
                name=source_class,
                qty=qty,
                uom=uom,
                unit_price_base=0.0,
                difficulty=1,
                toggle_mask=ToggleMask(),
                mult=1.0,
                notes=f"{provenance.get('sheet', '')}:{provenance.get('row', '')}".strip(":"),
            )
        )

    project_name = file_path.split("/")[-1].replace(".xlsx", "").replace(".xls", "")

    bid_state = BidFormState(
        project_name=project_name,
        items=items,
        created_at=datetime.now(timezone.utc).isoformat(),
        source_file=file_path
    )

    logger.info(f"Created catalog-based bid form: {len(items)} items, {len(warnings)} warnings")

    debug_payload = {
        "extraction": {
            "stats": result.get("stats", {}),
            "raw_rows": result.get("raw_rows", []),
            "raw_data": result.get("raw_data", [])
        },
        "mapping": mapping_result,
        "catalog": {
            "metrics": catalog.get_metrics(),
            "missing_items": catalog.missing_items
        }
    }

    return bid_state, warnings, debug_payload


def map_excel_to_bid_form(file_path: str, template: str = "baycrest_v1") -> BidFormState:
    """
    Main function to map Excel file to BidFormState.

    Args:
        file_path: Path to the Excel file
        template: Template type (e.g., "baycrest_v1")

    Returns:
        BidFormState with all parsed items
    """
    logger.info(f"Mapping Excel file to bid form: {file_path}")

    # Parse based on template
    if template == "baycrest_v1":
        normalizer = BaycrestNormalizer()
        result = normalizer.normalize_file(file_path)

        # Extract the raw rows from the result
        raw_rows = result.get('raw_rows', []) if isinstance(result, dict) else result

        # Convert to line items directly (simpler approach)
        items = []
        current_section = "General"

        for row in raw_rows:
            # Skip empty rows
            if not row.get('B') or not row.get('C'):
                continue

            # Check if this is a section header
            b_value = str(row.get('B', '')).strip()
            c_value = row.get('C')

            # Update section if this looks like a section header
            section_keywords = ["General", "Corridors", "Exterior", "Units", "Stairs", "Amenity", "Garage"]
            for keyword in section_keywords:
                if keyword.lower() in b_value.lower():
                    current_section = keyword
                    break

            # Skip if no quantity
            try:
                qty = float(c_value) if c_value else 0
                if qty <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            # Extract item name and UOM
            item_name = b_value
            d_value = str(row.get('D', '')).strip() if row.get('D') else ''

            # Try to extract UOM from column D or from the item name
            uom = "EA"  # Default
            if d_value:
                # Common UOM patterns
                if any(x in d_value.upper() for x in ['SF', 'SQ', 'SQUARE']):
                    uom = "SF"
                elif any(x in d_value.upper() for x in ['LF', 'LINEAR', 'LIN']):
                    uom = "LF"
                elif any(x in d_value.upper() for x in ['EA', 'EACH']):
                    uom = "EA"
                elif any(x in d_value.upper() for x in ['HR', 'HOUR']):
                    uom = "HR"
                elif any(x in d_value.upper() for x in ['GAL', 'GALLON']):
                    uom = "GAL"
                else:
                    uom = d_value[:5].upper() if len(d_value) <= 5 else "EA"

            # Create line item
            line_item = LineItem(
                id=str(uuid.uuid4()),
                section=current_section,
                name=item_name,
                qty=qty,
                uom=uom,
                unit_price_base=get_base_price(item_name),
                difficulty=1,  # Default to base difficulty
                toggle_mask=ToggleMask(),
                mult=1.0
            )
            items.append(line_item)

        logger.info(f"Created {len(items)} line items from {len(raw_rows)} raw rows")

    else:
        # Fallback for other templates
        logger.warning(f"Unknown template: {template}, using basic parsing")
        items = []

    # Create bid form state
    project_name = file_path.split("/")[-1].replace(".xlsx", "").replace(".xls", "")

    bid_state = BidFormState(
        project_name=project_name,
        items=items,
        created_at=datetime.now(timezone.utc).isoformat(),
        source_file=file_path
    )

    logger.info(f"Created bid form with {len(items)} items across {len(bid_state.get_sections())} sections")

    return bid_state


def create_sample_bid_form() -> BidFormState:
    """
    Create a blank bid form from the catalog with all items at qty=0.
    """
    catalog = BidCatalog()
    items = []

    for section in catalog.get_sections():
        for catalog_item in section.items:
            base_rate = catalog_item.get_rate(1)
            difficulty_adders = {
                level: max(0.0, catalog_item.get_rate(level) - base_rate)
                for level in range(1, 6)
            }

            line_item = LineItem(
                id=catalog_item.id.replace('.', '_'),
                section=section.name,
                name=catalog_item.label,
                qty=0,
                uom=catalog_item.uom,
                unit_price_base=base_rate,
                difficulty=1,
                difficulty_adders=difficulty_adders,
                toggle_mask=ToggleMask(),
                mult=catalog_item.default_multiplier,
            )
            items.append(line_item)

    return BidFormState(
        project_name="New Project",
        items=items,
        created_at=datetime.now(timezone.utc).isoformat()
    )
