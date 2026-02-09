"""
Catalog service for bid form rendering.

The catalog is the source of truth for:
- Item definitions (id, label, section)
- UOM (unit of measure)
- Pricing rates by difficulty level

Extraction provides:
- Quantities (qty)
- Source provenance

UI renders catalog rows, not extracted items directly.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CatalogItem:
    """A single item in the bid catalog."""
    id: str
    label: str
    uom: str
    rates: Dict[str, float]  # Difficulty level (1-5) -> rate
    default_multiplier: float = 1.0
    is_alt: bool = False
    section_id: str = ""
    section_name: str = ""

    # Populated from extraction
    qty: float = 0.0
    qty_raw: Optional[float] = None
    source_classification: Optional[str] = None
    confidence: float = 0.0
    provenance: Dict[str, Any] = field(default_factory=dict)

    def get_rate(self, difficulty: int) -> float:
        """Get the rate for a specific difficulty level."""
        return self.rates.get(str(difficulty), self.rates.get("1", 0.0))

    def calculate_total(self, difficulty: int, multiplier: float = 1.0) -> float:
        """Calculate line total for this item."""
        rate = self.get_rate(difficulty)
        return self.qty * rate * multiplier * self.default_multiplier


@dataclass
class CatalogSection:
    """A section containing multiple items."""
    id: str
    name: str
    items: List[CatalogItem] = field(default_factory=list)


class BidCatalog:
    """
    Manages the bid catalog.

    Usage:
        catalog = BidCatalog.load()
        catalog.merge_extraction(bid_items)
        rendered_sections = catalog.get_sections()
    """

    def __init__(self, sections: List[CatalogSection], aliases: Dict[str, str] = None):
        self.sections = sections
        self.aliases = aliases or {}
        self._items_by_id: Dict[str, CatalogItem] = {}

        # Build lookup index
        for section in sections:
            for item in section.items:
                self._items_by_id[item.id] = item

        # Track merge metrics
        self.matched_count = 0
        self.missing_count = 0
        self.missing_items: List[Dict[str, Any]] = []

    @classmethod
    def load(cls, config_path: str = "config/bid_catalog.json") -> "BidCatalog":
        """Load catalog from JSON config file."""
        path = Path(config_path)

        if not path.exists():
            logger.warning(f"Catalog not found at {config_path}, using empty catalog")
            return cls(sections=[], aliases={})

        with open(path, 'r') as f:
            data = json.load(f)

        # Load aliases
        aliases = data.get('aliases', {})

        sections = []
        for section_data in data.get('sections', []):
            items = []
            for item_data in section_data.get('items', []):
                item = CatalogItem(
                    id=item_data['id'],
                    label=item_data['label'],
                    uom=item_data['uom'],
                    rates=item_data.get('rates', {}),
                    default_multiplier=item_data.get('default_multiplier', 1.0),
                    is_alt=item_data.get('is_alt', False),
                    section_id=section_data['id'],
                    section_name=section_data['name']
                )
                items.append(item)

            section = CatalogSection(
                id=section_data['id'],
                name=section_data['name'],
                items=items
            )
            sections.append(section)

        logger.info(f"Loaded catalog with {len(sections)} sections, {sum(len(s.items) for s in sections)} items, {len(aliases)} aliases")
        return cls(sections=sections, aliases=aliases)

    def _resolve_item_id(self, item_id: str) -> Optional[str]:
        """
        Resolve an item ID, checking aliases if direct lookup fails.

        Returns the resolved ID or None if not found.
        """
        # Direct lookup
        if item_id in self._items_by_id:
            return item_id

        # Check aliases
        if item_id in self.aliases:
            aliased_id = self.aliases[item_id]
            if aliased_id in self._items_by_id:
                return aliased_id

        return None

    def merge_extraction(self, bid_items: List[Dict[str, Any]]) -> List[str]:
        """
        Merge extracted bid_items into the catalog.

        Supports aliases: if an extracted ID doesn't match directly,
        it will check the aliases map for a redirect.

        Args:
            bid_items: List of extracted items with id, qty, etc.

        Returns:
            List of warning messages for any issues
        """
        warnings = []

        # Reset metrics
        self.matched_count = 0
        self.missing_count = 0
        self.missing_items = []

        # Build lookup map from extraction
        extraction_map = {item['id']: item for item in bid_items}

        # Merge into catalog items
        for item_id, extracted in extraction_map.items():
            resolved_id = self._resolve_item_id(item_id)

            if resolved_id:
                catalog_item = self._items_by_id[resolved_id]

                # Set quantity from extraction
                catalog_item.qty = extracted.get('qty', 0.0)
                catalog_item.qty_raw = extracted.get('qty_raw', extracted.get('qty'))
                catalog_item.source_classification = extracted.get('source_classification', '')
                catalog_item.confidence = extracted.get('confidence', 1.0)
                catalog_item.provenance = extracted.get('provenance', extracted.get('source', {}))

                self.matched_count += 1

                # Note if alias was used
                if resolved_id != item_id:
                    logger.debug(f"Alias used: {item_id} -> {resolved_id}")

                # Check UOM consistency
                extracted_uom = extracted.get('uom', '').upper()
                catalog_uom = catalog_item.uom.upper()

                if extracted_uom and extracted_uom != catalog_uom:
                    warnings.append(
                        f"UOM mismatch for {catalog_item.label}: "
                        f"extraction has '{extracted_uom}', catalog expects '{catalog_uom}'"
                    )
            else:
                # Item not in catalog - track as missing
                self.missing_count += 1
                self.missing_items.append(extracted)
                warnings.append(f"Extracted item '{item_id}' not found in catalog")

        logger.info(f"Merged {self.matched_count} items, {self.missing_count} missing")

        return warnings

    def get_item(self, item_id: str) -> Optional[CatalogItem]:
        """Get a catalog item by ID."""
        return self._items_by_id.get(item_id)

    def get_sections(self) -> List[CatalogSection]:
        """Get all sections with their items."""
        return self.sections

    def get_items_with_qty(self) -> List[CatalogItem]:
        """Get all items that have a quantity > 0."""
        return [item for item in self._items_by_id.values() if item.qty > 0]

    def get_all_items(self) -> List[CatalogItem]:
        """Get all catalog items."""
        return list(self._items_by_id.values())

    def calculate_section_total(self, section_id: str, difficulty: int, multiplier: float = 1.0) -> float:
        """Calculate total for a section."""
        for section in self.sections:
            if section.id == section_id:
                return sum(
                    item.calculate_total(difficulty, multiplier)
                    for item in section.items
                    if not item.is_alt  # Exclude ALT items by default
                )
        return 0.0

    def calculate_grand_total(self, difficulty: int, multiplier: float = 1.0) -> float:
        """Calculate grand total across all sections."""
        return sum(
            self.calculate_section_total(section.id, difficulty, multiplier)
            for section in self.sections
        )

    def generate_missing_stubs(self) -> Dict[str, Any]:
        """
        Generate catalog stubs for missing extracted items.

        Returns a dict that can be merged into the catalog JSON:
        {
            "sections_to_add": [...],
            "items_to_add": {
                "section_id": [item, item, ...]
            }
        }
        """
        if not self.missing_items:
            return {"sections_to_add": [], "items_to_add": {}}

        # Group missing items by section
        items_by_section: Dict[str, List[Dict]] = {}
        new_sections = set()

        for item in self.missing_items:
            item_id = item.get('id', '')
            section_id = item_id.split('.')[0] if '.' in item_id else 'unknown'

            # Check if this section exists
            section_exists = any(s.id == section_id for s in self.sections)
            if not section_exists:
                new_sections.add(section_id)

            if section_id not in items_by_section:
                items_by_section[section_id] = []

            # Create stub with default rates
            stub = {
                "id": item_id,
                "label": item.get('label', item.get('source_classification', item_id.split('.')[-1].replace('_', ' ').title())),
                "uom": item.get('uom', 'EA'),
                "rates": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                "default_multiplier": 1.0,
                "_source_classification": item.get('source_classification', ''),
                "_qty_sample": item.get('qty', 0)
            }
            items_by_section[section_id].append(stub)

        # Build result
        sections_to_add = [
            {
                "id": section_id,
                "name": section_id.title(),
                "items": []
            }
            for section_id in new_sections
        ]

        return {
            "sections_to_add": sections_to_add,
            "items_to_add": items_by_section,
            "total_missing": len(self.missing_items)
        }

    def get_metrics(self) -> Dict[str, int]:
        """Get merge metrics."""
        return {
            "catalog_items_total": len(self._items_by_id),
            "matched_extracted_count": self.matched_count,
            "missing_extracted_count": self.missing_count,
            "items_with_qty": len(self.get_items_with_qty())
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export catalog state to dictionary."""
        return {
            'sections': [
                {
                    'id': section.id,
                    'name': section.name,
                    'items': [
                        {
                            'id': item.id,
                            'label': item.label,
                            'uom': item.uom,
                            'qty': item.qty,
                            'rates': item.rates,
                            'confidence': item.confidence,
                            'source_classification': item.source_classification
                        }
                        for item in section.items
                    ]
                }
                for section in self.sections
            ],
            'metrics': self.get_metrics()
        }
