"""
Canonical ID generation for bid items.

Ensures 100% deterministic IDs that don't drift with source classification changes.
Format: <section_slug>.<item_slug>

Examples:
    "Units", "W/D" -> "units.washer_dryer"
    "Balconies", "Balc. Rail LF" -> "balconies.balcony_rail_lf"
    "Mechanical", "IDF etc. Count" -> "mechanical.idf_room_count"
"""

import re
from typing import List, Optional


# Alias map for common messy classifications -> canonical slugs
# Add entries here when you see new abbreviations in source data
CLASSIFICATION_ALIASES = {
    # Units section
    "w/d": "washer_dryer",
    "w / d": "washer_dryer",
    "washer/dryer": "washer_dryer",
    "washer / dryer": "washer_dryer",
    "wic": "walk_in_closet",
    "w.i.c.": "walk_in_closet",
    "walk-in closet": "walk_in_closet",

    # Balconies section
    "balc": "balcony_count",
    "balc.": "balcony_count",
    "balc count": "balcony_count",
    "balc. count": "balcony_count",
    "balcony": "balcony_count",
    "balc rail lf": "balcony_rail_lf",
    "balc. rail lf": "balcony_rail_lf",
    "balcony rail lf": "balcony_rail_lf",
    "balc rail count": "balcony_rail_count",
    "balc. rail count": "balcony_rail_count",
    "balcony rail count": "balcony_rail_count",
    "balc storage": "balcony_storage",
    "balc. storage": "balcony_storage",
    "balcony storage": "balcony_storage",

    # Storage section
    "storage": "storage_count",
    "storage count": "storage_count",
    "storage sf": "storage_sf",

    # Mechanical section
    "idf etc. count": "idf_room_count",
    "idf etc count": "idf_room_count",
    "idf count": "idf_room_count",
    "idf room count": "idf_room_count",
    "idf etc. sf": "idf_room_sf",
    "idf etc sf": "idf_room_sf",
    "idf sf": "idf_room_sf",
    "idf room sf": "idf_room_sf",
    "trash term room counr": "trash_room_count",
    "trash term room count": "trash_room_count",
    "trash term room sf": "trash_room_sf",
    "decorative metal grill count": "decorative_metal_grill_count",

    # Corridors section
    "cor. door count": "corridor_doors",
    "cor door count": "corridor_doors",
    "corridor door count": "corridor_doors",
    "cor. bumpouts count": "corridor_bumpouts",
    "cor bumpouts count": "corridor_bumpouts",
    "cor bumpouts": "corridor_bumpouts",
    "cor. lid sf": "corridor_ceiling_sf",
    "cor lid sf": "corridor_ceiling_sf",
    "corridor lid sf": "corridor_ceiling_sf",
    "cor rail": "corridor_rail",
    "cor. rail": "corridor_rail",
    "cor railing": "corridor_rail",
    "cor. wall sf": "corridor_wall_sf",
    "cor wall sf": "corridor_wall_sf",
    "stucco wall sf": "corridor_wall_sf",
    "stucco passthrough sf": "corridor_wall_sf",
    "drywall lid sf": "corridor_ceiling_sf",
    "drywall wall sf": "corridor_wall_sf",
    "stucco lid sf": "corridor_ceiling_sf",
    "doors": "corridor_doors",

    # Exterior section
    "ext. door count": "exterior_doors",
    "ext door count": "exterior_doors",
    "ext doors": "exterior_doors",
    "parapet facing garage lf": "parapet_garage_lf",
    "window/door trim count": "window_door_trim",
    "window door trim count": "window_door_trim",
    "large opening trim count": "large_opening_trim",
    "large opening trim  count": "large_opening_trim",
    "8 landscape retaining wall lf": "retaining_wall_lf",
    "eve lf": "foam_eave_lf",
    "gutter": "gutter_lf",
    "downspouts": "down_spouts",
    "roof stucco sf": "roof_stucco_lf",
    "stucco wall at roof sf": "roof_stucco_lf",
    "smooth stucco": "stucco_wall_sf",
    "smooth stucco sf": "stucco_wall_sf",
    "stucco wainscot": "wainscot_lf",
    "foam trim lf": "trim_lf",
    "foam trim panel": "foam_panel_count",
    "attic vents": "louvers",
    "ext vent": "louvers",
    "metal panel": "metal_panel_count",
    "corbel at eve": "corbel_count",
    "roof rail": "roof_rail_lf",

    # Units interior
    "unit doors": "unit_doors",
    "unit door count": "unit_doors",
    "coat": "wardrobes",
    "loft guard rail lf 7/a8.40": "loft_guard_rail_lf",
    "loft guard rail lf": "loft_guard_rail_lf",

    # General section
    "total sf": "gross_building_sf",
    "total unit sf": "gross_building_sf",
    "1 bed room count": "1_bedroom_count",
    "3 bed room count": "3_bedroom_count",
    "total": "unit_count",
    "units": "unit_count",

    # Common abbreviations
    "ave sf": "average_sf",
    "ave. sf": "average_sf",
    "average sf": "average_sf",
    "ave unit sf": "average_unit_sf",
    "ave. unit sf": "average_unit_sf",

    # Amenity section
    "lobby": "lobby",
    "common area bathrooms": "common_area_bathrooms",
    "lounge": "lounge",
    "fitness": "fitness",
    "gaurdhouse": "guardhouse",
    "guardhouse": "guardhouse",
    "residence services": "amenity_flooring_sf",
    "mail room": "amenity_flooring_sf",
    "amenities": "amenity_flooring_sf",

    # Garage section
    "garage lid sf": "garage_ceiling_sf",
    "garage parapet lf": "parapet_garage_lf",
    "garage roof wall sf": "garage_wall_sf",
    "garage storage count": "garage_storage_count",
    "garage storage sf": "garage_storage_sf",
    "garage storage wall sf": "garage_storage_wall_sf",
    "garage mech room gate": "garage_mech_room_gate",
    "garage vest count": "garage_vest_count",
    "garage vest sf": "garage_vest_sf",
    "garage column count": "garage_column_count",
    "garage door count": "garage_door_count",
    "vehicle entry gate count": "vehicle_entry_gate_count",
    "vehical gates": "vehicle_entry_gate_count",
    "garage stairs sf": "garage_stairs_sf",
    "garage trash vest count": "garage_trash_vest_count",
    "garage trash vest sf": "garage_trash_vest_sf",
    "garage trash term room count": "garage_trash_room_count",
    "garage trash term room sf": "garage_trash_room_sf",
    "garage wall subtract": "garage_wall_subtract",
    "ext stucco sf": "stucco_wall_sf",
    "ext foam trim lf": "trim_lf",
    "columns": "garage_column_count",
    "mech enclosures": "garage_mech_room_gate",
    "trash term room": "garage_trash_room_count",
    "trash vest": "garage_trash_vest_count",
    "storage with drywall sf": "garage_storage_sf",
    "dropped lid at 1st lvl sf": "garage_ceiling_sf",
    "pipe bollards 1/ag9.04": "pipe_bollards",
    "pipe bollards": "pipe_bollards",
}

# Section name aliases -> canonical section slugs
SECTION_ALIASES = {
    "general": "general",
    "corridors": "corridors",
    "corridor": "corridors",
    "exterior": "exterior",
    "ext": "exterior",
    "units": "units",
    "unit": "units",
    "stairs": "stairs",
    "stair": "stairs",
    "amenity": "amenity",
    "amenities": "amenity",
    "common areas": "amenity",
    "common_areas": "amenity",
    "bathrooms": "amenity",
    "garage": "garage",
    "garages": "garage",
    "landscape": "landscape",
    "landscaping": "landscape",
    "balconies": "balconies",
    "balcony": "balconies",
    "storage": "storage",
    "mechanical": "mechanical",
    "mech": "mechanical",
    "finishes": "exterior",
}


def _slugify(text: str) -> str:
    """
    Convert text to a slug: lowercase, alphanumeric + underscores only.

    Examples:
        "Stucco Wall SF" -> "stucco_wall_sf"
        "W/D" -> "w_d"
        "Balc. Rail LF" -> "balc_rail_lf"
    """
    if not text:
        return ""

    # Lowercase
    slug = text.lower().strip()

    # Replace common separators with spaces
    slug = slug.replace("/", " ").replace("-", " ").replace(".", " ")

    # Remove any non-alphanumeric characters except spaces
    slug = re.sub(r'[^a-z0-9\s]', '', slug)

    # Collapse multiple spaces and convert to underscores
    slug = re.sub(r'\s+', '_', slug.strip())

    # Remove leading/trailing underscores
    slug = slug.strip('_')

    return slug


def _normalize_classification(classification: str) -> str:
    """
    Normalize a classification string for alias lookup.

    Tries multiple normalization strategies to find a match.
    """
    if not classification:
        return ""

    # Lowercase and strip
    norm = classification.lower().strip()

    # Collapse multiple spaces
    norm = re.sub(r'\s+', ' ', norm)

    return norm


def _get_alias_variants(classification: str) -> List[str]:
    """
    Generate multiple variants of a classification for alias lookup.
    """
    if not classification:
        return []

    variants = []
    norm = classification.lower().strip()
    variants.append(norm)

    # With spaces collapsed
    collapsed = re.sub(r'\s+', ' ', norm)
    if collapsed not in variants:
        variants.append(collapsed)

    # With punctuation normalized (no spaces around . and /)
    no_space_punct = re.sub(r'\s*([/.])\s*', r'\1', collapsed)
    if no_space_punct not in variants:
        variants.append(no_space_punct)

    # With spaces around punctuation
    space_punct = re.sub(r'([/.])', r' \1 ', collapsed)
    space_punct = re.sub(r'\s+', ' ', space_punct).strip()
    if space_punct not in variants:
        variants.append(space_punct)

    # Without punctuation (replaced with space)
    no_punct = re.sub(r'[/.]', ' ', collapsed)
    no_punct = re.sub(r'\s+', ' ', no_punct).strip()
    if no_punct not in variants:
        variants.append(no_punct)

    return variants


def get_section_slug(section_name: str) -> str:
    """
    Get canonical section slug from section name.

    Examples:
        "General" -> "general"
        "Corridors" -> "corridors"
        "Balconies" -> "balconies"
    """
    if not section_name:
        return "unknown"

    normalized = section_name.lower().strip()

    # Check aliases first
    if normalized in SECTION_ALIASES:
        return SECTION_ALIASES[normalized]

    # Fall back to slugified version
    return _slugify(section_name)


def get_item_slug(source_classification: str) -> str:
    """
    Get canonical item slug from source classification.

    Checks alias map first (trying multiple variants), then falls back to slugification.

    Examples:
        "W/D" -> "washer_dryer" (via alias)
        "Balc. Rail LF" -> "balcony_rail_lf" (via alias)
        "Stucco Wall SF" -> "stucco_wall_sf" (via slugify)
    """
    if not source_classification:
        return "unknown"

    # Try all variants for alias lookup
    variants = _get_alias_variants(source_classification)
    for variant in variants:
        if variant in CLASSIFICATION_ALIASES:
            return CLASSIFICATION_ALIASES[variant]

    # Also check the slugified version in aliases
    slugified = _slugify(source_classification)
    if slugified in CLASSIFICATION_ALIASES:
        return CLASSIFICATION_ALIASES[slugified]

    # Fall back to slugified version
    return slugified


def canonical_id(section_name: str, source_classification: str) -> str:
    """
    Generate a canonical ID from section name and source classification.

    Format: <section_slug>.<item_slug>

    This ID is 100% deterministic - the same inputs always produce the same ID,
    even if the source data has slight variations in punctuation or spacing.

    Examples:
        ("Units", "W/D") -> "units.washer_dryer"
        ("Balconies", "Balc. Rail LF") -> "balconies.balcony_rail_lf"
        ("Exterior", "Stucco Wall SF") -> "exterior.stucco_wall_sf"

    Args:
        section_name: The section name (e.g., "Units", "Exterior")
        source_classification: The classification from the source data

    Returns:
        Canonical ID string
    """
    section_slug = get_section_slug(section_name)
    item_slug = get_item_slug(source_classification)

    return f"{section_slug}.{item_slug}"


def add_alias(source_classification: str, canonical_slug: str) -> None:
    """
    Add a new alias mapping at runtime.

    Useful for dynamically discovered classifications.
    """
    normalized = _normalize_classification(source_classification)
    CLASSIFICATION_ALIASES[normalized] = canonical_slug


def get_all_aliases() -> dict:
    """Return a copy of all classification aliases."""
    return CLASSIFICATION_ALIASES.copy()
