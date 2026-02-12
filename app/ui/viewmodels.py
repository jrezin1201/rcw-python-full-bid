"""
View models for the Bid Form UI.
These models represent the data structures used in the UI layer.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, computed_field
import uuid

DEFAULT_DIFFICULTY_ADDERS = {
    1: 0.0,
    2: 0.0,
    3: 0.0,
    4: 0.0,
    5: 0.0,
}


class ToggleMask(BaseModel):
    """Toggle states for a line item (tax, labor, materials, etc.)"""
    tax: bool = True
    labor: bool = True
    materials: bool = True
    equipment: bool = False
    subcontractor: bool = False

    def get_multiplier(self) -> float:
        """Calculate combined multiplier based on toggle states."""
        # This is a simplified calculation - you can make it more complex
        multiplier = 1.0
        if not self.tax:
            multiplier *= 0.92  # Remove 8% tax
        if not self.labor:
            multiplier *= 0.7  # Remove 30% labor
        if not self.materials:
            multiplier *= 0.8  # Remove 20% materials
        return multiplier


class LineItem(BaseModel):
    """Represents a single line item in the bid form."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    section: str  # e.g. "General", "Units", "Exterior"
    name: str  # e.g. "Eggshell Walls", "Studio Unit Count"
    qty: float
    uom: str  # Unit of measure: "EA", "SF", "LF", etc.
    unit_price_base: float  # Base price (difficulty 1)
    difficulty: int = Field(default=1, ge=1, le=5)
    # Absolute add-on per unit/SF for each difficulty level.
    # Example: level 2 = 3.0 means add $3.00 per qty unit.
    difficulty_adders: Dict[int, float] = Field(default_factory=lambda: DEFAULT_DIFFICULTY_ADDERS.copy())
    toggle_mask: ToggleMask = Field(default_factory=ToggleMask)
    mult: float = Field(default=1.0, ge=0)  # Manual multiplier
    is_alternate: bool = False  # For ALT items
    excluded: bool = False  # Soft-delete: greyed out, excluded from totals
    is_exclusion: bool = False  # Show as "Excludes X" on print proposal
    notes: Optional[str] = None

    @computed_field
    @property
    def unit_price_effective(self) -> float:
        """Calculate effective unit price with all multipliers."""
        difficulty_add = self.difficulty_adders.get(self.difficulty, 0.0)
        toggle_mult = self.toggle_mask.get_multiplier()
        unit_with_difficulty = max(0.0, self.unit_price_base + difficulty_add)
        return unit_with_difficulty * toggle_mult * self.mult

    @computed_field
    @property
    def row_total(self) -> float:
        """Calculate total for this row."""
        return self.qty * self.unit_price_effective

    def update_qty(self, new_qty: float) -> None:
        """Update quantity."""
        self.qty = max(0, new_qty)

    def set_difficulty(self, difficulty: int) -> None:
        """Set difficulty level (1-5)."""
        self.difficulty = max(1, min(5, difficulty))

    def set_difficulty_add(self, level: int, amount: float) -> None:
        """Set absolute difficulty add-on for a specific level."""
        safe_level = max(1, min(5, level))
        self.difficulty_adders[safe_level] = max(0.0, amount)

    def toggle(self, toggle_name: str) -> None:
        """Toggle a specific boolean flag."""
        if hasattr(self.toggle_mask, toggle_name):
            current = getattr(self.toggle_mask, toggle_name)
            setattr(self.toggle_mask, toggle_name, not current)

    def update_mult(self, new_mult: float) -> None:
        """Update manual multiplier."""
        self.mult = max(0, new_mult)


class SpecItem(BaseModel):
    """A single spec line item with exclude support."""
    name: str
    excluded: bool = False


class MaterialItem(BaseModel):
    """A single material line item with optional yellow highlight."""
    name: str
    value: str = ""
    highlight: bool = False


class SectionTotals(BaseModel):
    """Totals for a section."""
    section_name: str
    item_count: int
    total: float


class ProjectInfo(BaseModel):
    """Project metadata for proposals."""
    # Developer/Client info
    developer: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    contact: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    # Project details
    project_city: Optional[str] = None
    units_text: Optional[str] = None

    # Plan dates
    plans_date: Optional[str] = None
    arch_date: Optional[str] = None
    landscape_date: Optional[str] = None
    interior_design_date: Optional[str] = None
    owner_specs_date: Optional[str] = None


class BidFormState(BaseModel):
    """Represents the complete state of a bid form."""
    project_name: str = "Untitled Project"
    project_id: Optional[str] = None
    items: List[LineItem] = Field(default_factory=list)
    raw_items: List[LineItem] = Field(default_factory=list)

    # Metadata
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    source_file: Optional[str] = None

    # Project info for proposals
    project_info: ProjectInfo = Field(default_factory=ProjectInfo)

    # Spec items per section: section_name -> list of SpecItem
    spec_items: Dict[str, List[SpecItem]] = Field(default_factory=dict)

    # Spec section labels: section_name -> label string (e.g. "Flat One Tone")
    spec_section_labels: Dict[str, str] = Field(default_factory=dict)

    # Normal exclusions: single list for the whole bid
    spec_exclusions: List[str] = Field(default_factory=list)

    # Materials included in bid
    materials_brand: str = "VISTA PAINTS"
    materials_sections: Dict[str, List[MaterialItem]] = Field(default_factory=dict)
    materials_section_order: List[str] = Field(default_factory=list)

    @computed_field
    @property
    def grand_total(self) -> float:
        """Calculate grand total across all raw items."""
        return sum(item.row_total for item in self.raw_items if not item.excluded)

    @computed_field
    @property
    def section_totals(self) -> List[SectionTotals]:
        """Calculate totals per section from raw items."""
        sections: Dict[str, List[LineItem]] = {}

        # Group raw items by section
        for item in self.raw_items:
            if item.section not in sections:
                sections[item.section] = []
            sections[item.section].append(item)

        # Calculate totals (exclude soft-deleted items)
        totals = []
        for section_name, section_items in sections.items():
            active = [i for i in section_items if not i.excluded]
            totals.append(SectionTotals(
                section_name=section_name,
                item_count=len(active),
                total=sum(item.row_total for item in active)
            ))

        return sorted(totals, key=lambda x: x.section_name)

    @computed_field
    @property
    def total_items(self) -> int:
        """Total number of line items."""
        return len(self.raw_items)

    def get_item(self, item_id: str) -> Optional[LineItem]:
        """Get a specific item by ID (searches both catalog and raw items)."""
        for item in self.items:
            if item.id == item_id:
                return item
        for item in self.raw_items:
            if item.id == item_id:
                return item
        return None

    def get_raw_sections(self) -> List[str]:
        """Get list of sections from raw items, preserving Excel order."""
        seen = set()
        ordered = []
        for item in self.raw_items:
            if item.section not in seen:
                seen.add(item.section)
                ordered.append(item.section)
        return ordered

    def get_raw_items_by_section(self, section: str) -> List[LineItem]:
        """Get raw items in a specific section, preserving Excel order."""
        return [item for item in self.raw_items if item.section == section]

    def update_item_qty(self, item_id: str, new_qty: float) -> bool:
        """Update quantity for a specific item."""
        item = self.get_item(item_id)
        if item:
            item.update_qty(new_qty)
            return True
        return False

    def set_item_difficulty(self, item_id: str, difficulty: int) -> bool:
        """Set difficulty for a specific item."""
        item = self.get_item(item_id)
        if item:
            item.set_difficulty(difficulty)
            return True
        return False

    def toggle_item(self, item_id: str, toggle_name: str) -> bool:
        """Toggle a specific flag for an item."""
        item = self.get_item(item_id)
        if item:
            item.toggle(toggle_name)
            return True
        return False

    def update_item_mult(self, item_id: str, new_mult: float) -> bool:
        """Update multiplier for a specific item."""
        item = self.get_item(item_id)
        if item:
            item.update_mult(new_mult)
            return True
        return False

    def update_item_difficulty_add(self, item_id: str, level: int, amount: float) -> bool:
        """Update absolute difficulty add-on for a specific item and level."""
        item = self.get_item(item_id)
        if item:
            item.set_difficulty_add(level, amount)
            return True
        return False

    def toggle_excluded(self, item_id: str) -> bool:
        """Toggle excluded state for an item (soft delete/restore)."""
        item = self.get_item(item_id)
        if item:
            item.excluded = not item.excluded
            return True
        return False

    def add_item(self, item: LineItem) -> None:
        """Add a new line item."""
        self.items.append(item)

    def remove_item(self, item_id: str) -> bool:
        """Remove a line item by ID."""
        for i, item in enumerate(self.items):
            if item.id == item_id:
                self.items.pop(i)
                return True
        return False

    def get_sections(self) -> List[str]:
        """Get list of unique sections."""
        return sorted(list(set(item.section for item in self.items)))

    def get_items_by_section(self, section: str) -> List[LineItem]:
        """Get all items in a specific section."""
        return [item for item in self.items if item.section == section]
