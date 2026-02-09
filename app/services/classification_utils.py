"""
Classification text normalization and canonicalization utilities.
Makes mapping more stable and reduces rule count.
"""
import re
from typing import Dict


# Common synonyms for normalization
CLASSIFICATION_SYNONYMS: Dict[str, str] = {
    # Materials
    "mdf": "mdf",
    "medium density fiberboard": "mdf",
    "gypsum": "drywall",
    "gypsum board": "drywall",
    "gyp board": "drywall",

    # Measurements
    "linear": "linear",
    "square": "square",
    "cubic": "cubic",

    # Actions
    "install": "install",
    "installation": "install",
    "remove": "remove",
    "removal": "remove",
    "demo": "demolition",
    "demolish": "demolition",

    # Building elements
    "baseboard": "baseboard",
    "base board": "baseboard",
    "base moulding": "baseboard",
    "wallpaper": "wallpaper",
    "wall paper": "wallpaper",
    "countertop": "countertop",
    "counter top": "countertop",
}


def canonicalize_classification(classification: str) -> str:
    """
    Normalize classification string for consistent matching.

    Process:
    1. Lowercase
    2. Strip whitespace
    3. Collapse multiple spaces to single space
    4. Remove common punctuation (: - ,)
    5. Apply synonym normalization

    Args:
        classification: Raw classification string (e.g., "Baseboard - MDF")

    Returns:
        Canonicalized string (e.g., "baseboard mdf")

    Examples:
        >>> canonicalize_classification("Baseboard - MDF")
        'baseboard mdf'
        >>> canonicalize_classification("Paint: Walls")
        'paint walls'
        >>> canonicalize_classification("Gypsum Board, 1/2\"")
        'drywall 1/2"'
    """
    if not classification:
        return ""

    # Step 1: Lowercase
    result = classification.lower()

    # Step 2 & 3: Strip and collapse whitespace
    result = result.strip()

    # Step 4: Remove common punctuation (but keep quotes for dimensions)
    # Remove: colon, dash/hyphen, comma, semicolon, pipe
    result = re.sub(r'[:\-,;|]', ' ', result)

    # Step 3 (again): Collapse multiple spaces
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()

    # Step 5: Apply synonyms (word-by-word replacement)
    words = result.split()
    normalized_words = []

    for word in words:
        # Check if this word (or phrase ending with this word) has a synonym
        if word in CLASSIFICATION_SYNONYMS:
            normalized_words.append(CLASSIFICATION_SYNONYMS[word])
        else:
            # Check for multi-word phrases
            # Try progressively longer phrases ending with current position
            found_phrase = False
            for i in range(len(normalized_words)):
                phrase = ' '.join(normalized_words[i:] + [word])
                if phrase in CLASSIFICATION_SYNONYMS:
                    # Replace the phrase
                    normalized_words = normalized_words[:i] + [CLASSIFICATION_SYNONYMS[phrase]]
                    found_phrase = True
                    break

            if not found_phrase:
                normalized_words.append(word)

    return ' '.join(normalized_words)


def add_classification_synonym(phrase: str, normalized: str):
    """
    Add a custom synonym to the canonicalization map.

    Args:
        phrase: The phrase to normalize (will be lowercased)
        normalized: The canonical form
    """
    CLASSIFICATION_SYNONYMS[phrase.lower()] = normalized.lower()


def get_classification_synonyms() -> Dict[str, str]:
    """Get a copy of the current synonym map."""
    return CLASSIFICATION_SYNONYMS.copy()
