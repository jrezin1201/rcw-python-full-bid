"""
UOM (Unit of Measure) normalization utilities.

Canonical UOM set: EA, SF, LF, LVL
Never emit FT - always normalize to LF.
"""

from typing import Optional, Tuple


# Canonical UOM set
CANONICAL_UOMS = {"EA", "SF", "LF", "LVL"}


def normalize_uom(uom: Optional[str]) -> Optional[str]:
    """
    Normalize UOM to canonical set: EA, SF, LF, LVL.

    Never outputs FT - always converts to LF.

    Args:
        uom: Raw UOM string (may be None)

    Returns:
        Canonical UOM string or None if input is None/empty
    """
    if not uom:
        return None

    u = uom.strip().upper()

    # Linear feet variants -> LF
    if u in {"FT", "FEET", "FOOT"}:
        return "LF"
    if u in {"LINEAR FT", "LINEAR FEET", "L.F.", "LFT", "LIN FT", "LIN. FT."}:
        return "LF"
    if u == "LF":
        return "LF"

    # Square feet variants -> SF
    if u in {"SF", "SQFT", "SQ FT", "SQ.FT.", "SQUARE FEET", "SQUARE FT"}:
        return "SF"

    # Each variants -> EA
    if u in {"EA", "EACH", "PCS", "PIECES", "COUNT", "UNIT", "UNITS"}:
        return "EA"

    # Level variants -> LVL
    if u in {"LVL", "LEVEL", "LEVELS", "FLOOR", "FLOORS"}:
        return "LVL"

    # Return as-is if not in our normalization rules
    return u


def normalize_uom_with_warning(uom: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalize UOM and return warning if normalization changed the value.

    Args:
        uom: Raw UOM string

    Returns:
        Tuple of (normalized_uom, warning_message or None)
    """
    if not uom:
        return None, "UOM is missing"

    normalized = normalize_uom(uom)
    original = uom.strip().upper()

    if normalized != original:
        return normalized, f"UOM normalized: '{uom}' -> '{normalized}'"

    return normalized, None


def is_canonical_uom(uom: Optional[str]) -> bool:
    """Check if UOM is in the canonical set."""
    if not uom:
        return False
    return uom.strip().upper() in CANONICAL_UOMS


def check_uom_mismatch(parsed_uom: Optional[str], expected_uom: Optional[str]) -> Optional[str]:
    """
    Check if parsed UOM conflicts with expected UOM from mapping.

    Args:
        parsed_uom: UOM from extraction
        expected_uom: UOM expected by mapping config

    Returns:
        Warning message if mismatch, None if OK
    """
    if not parsed_uom or not expected_uom:
        return None

    parsed_norm = normalize_uom(parsed_uom)
    expected_norm = normalize_uom(expected_uom)

    if parsed_norm != expected_norm:
        return f"UOM mismatch: parsed '{parsed_uom}' (normalized: {parsed_norm}) vs expected '{expected_uom}' (normalized: {expected_norm})"

    return None
