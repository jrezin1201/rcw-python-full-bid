"""
Mapping service for takeoff data.
Maps normalized rows to sections/items using fuzzy matching.
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

from fuzzywuzzy import fuzz
from fuzzywuzzy import process

from app.core.logging import get_logger
from app.services.classification_utils import canonicalize_classification
from app.services.uom_utils import normalize_uom, normalize_uom_with_warning, check_uom_mismatch
from app.services.canonical_id import canonical_id, get_section_slug, get_item_slug

logger = get_logger(__name__)


class TakeoffMapper:
    """
    Maps normalized takeoff rows to sections and items using configuration.
    """

    def __init__(self, template: str = "baycrest_v1"):
        self.template = template
        self.config = self._load_config(template)
        self.sections = self.config.get('sections', {})
        self.section_order = self.config.get('section_order', list(self.sections.keys()))
        self.mapping_config = self.config.get('mapping_config', {})
        self.fuzzy_threshold = self.mapping_config.get('fuzzy_threshold', 0.85) * 100  # fuzzywuzzy uses 0-100
        self.strict_unmapped_threshold = self.mapping_config.get('strict_unmapped_threshold', 0.75) * 100  # Below this, always unmap
        self.prefer_largest = self.mapping_config.get('prefer_largest_measure', True)
        self.uom_mappings = self.mapping_config.get('uom_mappings', {})
        self.qty_formatting = self.mapping_config.get('qty_formatting', {})
        self.uom_canonicalization = self.mapping_config.get('uom_canonicalization', {})

    def _load_config(self, template: str) -> Dict[str, Any]:
        """Load mapping configuration from JSON file."""
        config_path = Path(f"config/{template}.mapping.json")

        if not config_path.exists():
            logger.error(f"Mapping config not found: {config_path}")
            raise FileNotFoundError(f"Mapping template '{template}' not found")

        with open(config_path, 'r') as f:
            return json.load(f)

    def _canonicalize_uom(self, uom: str) -> str:
        """
        Canonicalize UOM using standard normalization.
        Always returns canonical UOM: EA, SF, LF, LVL.
        Never returns FT.
        """
        # Use the new normalize_uom function as primary
        normalized = normalize_uom(uom)
        if normalized:
            return normalized
        # Fall back to config-based canonicalization if normalize_uom returns None
        return self.uom_canonicalization.get(uom, uom) if uom else uom

    def _format_quantity(self, value: float, uom: str) -> float:
        """
        Format quantity based on UOM type.
        - EA (each): Round to nearest integer
        - SF/LF/FT: Keep as decimal
        """
        # Use canonicalized UOM for formatting rules
        canonical_uom = self._canonicalize_uom(uom)
        format_type = self.qty_formatting.get(canonical_uom, "decimal")

        if format_type == "integer":
            # Round to nearest integer for EA
            return round(value)
        else:
            # Keep as float for SF/LF/FT, round to 2 decimals for cleaner display
            return round(value, 2) if value % 1 != 0 else float(int(value))

    def _format_unmapped_item(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format unmapped item with formatted measure values.
        Preserves raw values as 'value_raw' and 'uom_raw' for audit.
        Canonicalizes UOM for UI display (LF -> FT).
        """
        formatted_measures = []
        for measure in row.get('measures', []):
            normalized_uom = measure['uom']  # Already normalized (e.g., LF)
            canonical_uom = self._canonicalize_uom(normalized_uom)  # Convert LF -> FT

            formatted_measure = {
                'value': self._format_quantity(measure['value'], normalized_uom),
                'value_raw': measure['value'],  # Preserve raw for audit
                'uom': canonical_uom,  # Canonicalized for UI (FT)
                'uom_raw': normalized_uom,  # Original normalized (LF)
                'source': measure['source']
            }
            formatted_measures.append(formatted_measure)

        return {
            'classification': row['classification'],
            'measures': formatted_measures,
            'provenance': row['provenance']
        }

    def map_rows_to_sections(self, normalized_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Map normalized rows to sections and items.

        Args:
            normalized_rows: List of normalized row dictionaries

        Returns:
            Dictionary with sections, unmapped items, and QA report
        """
        # Initialize result structure
        result_sections = []
        unmapped = []
        warnings = []

        # Track what we've mapped
        mapped_items = set()
        ambiguous_matches = 0

        # Build a flat list of all expected items for fuzzy matching
        all_items = []
        for section_name, items in self.sections.items():
            for item_name, item_config in items.items():
                all_items.append({
                    'section': section_name,
                    'item': item_name,
                    'config': item_config,
                    'match_strings': item_config.get('match', [])
                })

        # Process each normalized row
        for row in normalized_rows:
            classification = row['classification']
            measures = row['measures']
            provenance = row['provenance']

            # Try to find a match
            match_result = self._find_best_match(classification, all_items)

            if match_result:
                item_info = match_result['item_info']
                confidence = match_result['confidence']
                match_type = match_result['match_type']

                # Find the best measure for this item
                required_uom = item_info['config']['uom']
                best_measure = self._select_best_measure(measures, required_uom)

                if best_measure:
                    # Create item key
                    item_key = f"{item_info['section']}.{item_info['item']}"

                    if item_key not in mapped_items:
                        mapped_items.add(item_key)

                        # Add warning for low confidence matches (75-85%)
                        if match_type == 'low_confidence':
                            warnings.append({
                                'type': 'low_confidence_match',
                                'severity': 'warning',
                                'classification': classification,
                                'matched_to': item_info['item'],
                                'confidence': confidence,
                                'message': f"LOW CONFIDENCE: Matched '{classification}' to '{item_info['item']}' with only {confidence:.1f}% confidence"
                            })
                            ambiguous_matches += 1

                        # Add warning for fuzzy matches (85%+)
                        elif match_type == 'fuzzy':
                            warnings.append({
                                'type': 'ambiguous_match',
                                'classification': classification,
                                'matched_to': item_info['item'],
                                'confidence': confidence,
                                'message': f"Fuzzy matched '{classification}' to '{item_info['item']}' with {confidence:.1f}% confidence"
                            })
                            ambiguous_matches += 1

                        # If multiple measures with same UOM, add warning
                        same_uom_measures = [m for m in measures if m['uom'] == required_uom]
                        if len(same_uom_measures) > 1:
                            # Check for conflicting values (>15% difference)
                            values = [m['value'] for m in same_uom_measures]
                            max_val = max(values)
                            min_val = min(values)

                            if min_val > 0:  # Avoid division by zero
                                percent_diff = ((max_val - min_val) / min_val) * 100

                                if percent_diff > 15:
                                    # Conflicting measures - stronger warning
                                    warnings.append({
                                        'type': 'conflicting_measures',
                                        'severity': 'high',
                                        'classification': classification,
                                        'measures': same_uom_measures,
                                        'selected': best_measure,
                                        'percent_difference': round(percent_diff, 1),
                                        'message': f"CONFLICTING VALUES: Multiple {required_uom} measures differ by {percent_diff:.1f}% for '{classification}', selected largest value"
                                    })
                                else:
                                    # Normal multiple measures warning
                                    warnings.append({
                                        'type': 'multiple_measures',
                                        'classification': classification,
                                        'measures': same_uom_measures,
                                        'selected': best_measure,
                                        'message': f"Multiple {required_uom} measures found for '{classification}', selected largest value"
                                    })
                            else:
                                # Normal warning if we can't calculate percentage
                                warnings.append({
                                    'type': 'multiple_measures',
                                    'classification': classification,
                                    'measures': same_uom_measures,
                                    'selected': best_measure,
                                    'message': f"Multiple {required_uom} measures found for '{classification}', selected largest value"
                                })
                else:
                    # No measure with required UOM
                    unmapped.append(self._format_unmapped_item(row))
                    warnings.append({
                        'type': 'missing_uom',
                        'classification': classification,
                        'required_uom': required_uom,
                        'available_uoms': [m['uom'] for m in measures],
                        'message': f"No {required_uom} measure found for '{classification}'"
                    })
            else:
                # No match found
                unmapped.append(self._format_unmapped_item(row))

        # Build a mapping of successfully matched rows to their items
        # This ensures each row is only used once and gets the correct value
        row_to_item_mapping = {}

        # First pass: map each row to its best matching item
        for row in normalized_rows:
            classification = row['classification']
            match_result = self._find_best_match(classification, all_items)

            if match_result:
                item_info = match_result['item_info']
                required_uom = item_info['config']['uom']
                best_measure = self._select_best_measure(row['measures'], required_uom)

                if best_measure:
                    item_key = f"{item_info['section']}.{item_info['item']}"

                    # Store the mapping - each row maps to exactly one item
                    if item_key not in row_to_item_mapping:
                        row_to_item_mapping[item_key] = {
                            'section': item_info['section'],
                            'item': item_info['item'],
                            'qty': self._format_quantity(best_measure['value'], required_uom),
                            'qty_raw': best_measure['value'],
                            'uom': self._canonicalize_uom(required_uom),
                            'uom_raw': required_uom,
                            'source_classification': classification,
                            'confidence': match_result['confidence'] / 100.0,
                            'provenance': row.get('provenance', {})
                        }

        # Build sections structure using explicit order
        for section_name in self.section_order:
            if section_name not in self.sections:
                continue  # Skip sections in order that don't exist
            items = self.sections[section_name]
            section_items = []

            for item_name, item_config in items.items():
                item_key = f"{section_name}.{item_name}"

                # Check if this item was successfully mapped to a row
                if item_key in row_to_item_mapping:
                    mapped_item = row_to_item_mapping[item_key]
                    section_items.append({
                        'key': item_name,
                        'qty': mapped_item['qty'],
                        'qty_raw': mapped_item['qty_raw'],
                        'uom': mapped_item['uom'],
                        'uom_raw': mapped_item['uom_raw'],
                        'source_classification': mapped_item['source_classification'],
                        'confidence': mapped_item['confidence']
                    })

            if section_items:
                result_sections.append({
                    'name': section_name,
                    'items': section_items
                })

        # Calculate statistics
        total_rows = len(normalized_rows)
        rows_with_measures = len([r for r in normalized_rows if r['measures']])
        items_mapped = len(mapped_items)

        # Count expected items
        total_expected_items = sum(len(items) for items in self.sections.values())
        items_missing = total_expected_items - items_mapped

        # Build QA report
        qa = self.build_qa_report(
            normalized_rows=normalized_rows,
            mapped_items=items_mapped,
            unmapped_items=unmapped,
            warnings=warnings,
            ambiguous_matches=ambiguous_matches,
            items_missing=items_missing
        )

        # Generate unmapped summary (what to map next)
        unmapped_summary = self._generate_unmapped_summary(unmapped)

        # Build flat bid_items list for UI consumption
        bid_items = self._build_bid_items(row_to_item_mapping, warnings)

        return {
            'sections': result_sections,
            'unmapped': unmapped,
            'unmapped_summary': unmapped_summary,
            'qa': qa,
            'bid_items': bid_items
        }

    def _find_best_match(self, classification: str, items: List[Dict]) -> Optional[Dict[str, Any]]:
        """
        Find the best matching item for a classification using 3-tier matching.

        Tier 1: Exact match on canonicalized classification
        Tier 2: Contains match (substring)
        Tier 3: Regex match (if pattern starts with 'regex:')
        Tier 4: Fuzzy match (fallback)

        Returns:
            Dictionary with item_info, confidence, match_type, matched_rule, and matched_value
        """
        # Canonicalize the input classification
        classification_norm = canonicalize_classification(classification)

        # Tier 1: Exact match on canonicalized text
        for item in items:
            for idx, match_string in enumerate(item['match_strings']):
                match_string_norm = canonicalize_classification(match_string)

                if classification_norm == match_string_norm:
                    return {
                        'item_info': item,
                        'confidence': 100.0,
                        'match_type': 'exact',
                        'matched_rule': f"exact:{idx}",
                        'matched_value': match_string
                    }

        # Tier 2: Contains match (substring) on canonicalized text
        for item in items:
            for idx, match_string in enumerate(item['match_strings']):
                # Skip regex patterns for contains matching
                if match_string.startswith('regex:'):
                    continue

                match_string_norm = canonicalize_classification(match_string)

                # Check if match_string is contained in classification
                if match_string_norm and match_string_norm in classification_norm:
                    return {
                        'item_info': item,
                        'confidence': 95.0,
                        'match_type': 'contains',
                        'matched_rule': f"contains:{idx}",
                        'matched_value': match_string
                    }

        # Tier 3: Regex match
        for item in items:
            for idx, match_string in enumerate(item['match_strings']):
                if match_string.startswith('regex:'):
                    # Extract regex pattern after 'regex:' prefix
                    pattern = match_string[6:].strip()
                    try:
                        if re.search(pattern, classification_norm, re.IGNORECASE):
                            return {
                                'item_info': item,
                                'confidence': 90.0,
                                'match_type': 'regex',
                                'matched_rule': f"regex:{idx}",
                                'matched_value': pattern
                            }
                    except re.error as e:
                        logger.warning(f"Invalid regex pattern '{pattern}': {e}")
                        continue

        # Tier 4: Fuzzy matching (fallback)
        all_match_strings = []
        match_to_item = {}
        match_to_index = {}

        for item in items:
            for idx, match_string in enumerate(item['match_strings']):
                # Skip regex patterns for fuzzy matching
                if not match_string.startswith('regex:'):
                    all_match_strings.append(match_string)
                    match_to_item[match_string] = item
                    match_to_index[match_string] = idx

        if all_match_strings:
            # Use fuzzywuzzy to find best match
            result = process.extractOne(
                classification,
                all_match_strings,
                scorer=fuzz.token_sort_ratio
            )

            if result:
                match_string, score = result[0], result[1]

                # Strict unmapped policy: Below 75% MUST go to unmapped
                if score < self.strict_unmapped_threshold:
                    return None  # Too weak, must go to unmapped

                # Between 75-85%: Map but mark as low confidence
                if score < self.fuzzy_threshold:
                    return {
                        'item_info': match_to_item[match_string],
                        'confidence': float(score),
                        'match_type': 'fuzzy_low',
                        'matched_rule': f"fuzzy:{match_to_index[match_string]}",
                        'matched_value': match_string
                    }

                # 85% and above: Normal fuzzy match
                return {
                    'item_info': match_to_item[match_string],
                    'confidence': float(score),
                    'match_type': 'fuzzy',
                    'matched_rule': f"fuzzy:{match_to_index[match_string]}",
                    'matched_value': match_string
                }

        return None

    def _select_best_measure(self, measures: List[Dict[str, Any]], required_uom: str) -> Optional[Dict[str, Any]]:
        """
        Select the best measure based on required UOM.
        If multiple measures with same UOM, select largest by default.
        """
        # Filter measures by UOM
        matching_measures = [m for m in measures if m['uom'] == required_uom]

        if not matching_measures:
            return None

        if len(matching_measures) == 1:
            return matching_measures[0]

        # Multiple measures with same UOM
        if self.prefer_largest:
            return max(matching_measures, key=lambda m: m['value'])
        else:
            # Return first one
            return matching_measures[0]

    def _generate_unmapped_summary(self, unmapped_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a frequency summary of unmapped classifications.

        Returns:
            Dictionary with total_unmapped and top classifications by frequency
        """
        if not unmapped_items:
            return {
                'total_unmapped': 0,
                'top': []
            }

        # Count classifications
        classification_counts = Counter()
        classification_examples = {}  # Store first example for each classification

        for item in unmapped_items:
            classification = item['classification']
            classification_counts[classification] += 1

            # Store first example if we don't have one yet
            if classification not in classification_examples:
                classification_examples[classification] = {
                    'classification': classification,
                    'measures': item.get('measures', []),
                    'provenance': item.get('provenance', {})
                }

        # Build top list sorted by count descending
        top_items = []
        for classification, count in classification_counts.most_common():
            top_items.append({
                'classification': classification,
                'count': count,
                'example': classification_examples[classification]
            })

        return {
            'total_unmapped': len(unmapped_items),
            'unique_classifications': len(classification_counts),
            'top': top_items
        }

    def _build_bid_items(self, row_to_item_mapping: Dict[str, Dict], warnings: List[Dict]) -> List[Dict[str, Any]]:
        """
        Build flat bid_items list for UI consumption.

        Each item has canonical structure:
        - id: canonical key using deterministic ID generation (e.g., "garage.parapet_garage_lf")
        - section: section name
        - label: human-readable label
        - qty: quantity (formatted)
        - uom: canonical UOM (EA, SF, LF, LVL - never FT)
        - uom_raw: original UOM before normalization
        - provenance: {sheet, row} info
        - source_classification: original classification text
        - confidence: match confidence (0-1)
        """
        bid_items = []

        # Build items in section order for consistent output
        for section_name in self.section_order:
            if section_name not in self.sections:
                continue

            items = self.sections[section_name]

            for item_name, item_config in items.items():
                item_key = f"{section_name}.{item_name}"

                if item_key in row_to_item_mapping:
                    mapped = row_to_item_mapping[item_key]

                    # Get source classification for canonical ID generation
                    source_classification = mapped.get('source_classification', item_name)

                    # Create canonical ID using deterministic ID generation
                    # This ensures the same source data always produces the same ID
                    item_canonical_id = canonical_id(section_name, source_classification)

                    # Get UOM - ensure it's canonical (never FT)
                    uom_raw = mapped.get('uom_raw', mapped.get('uom'))
                    uom_normalized = self._canonicalize_uom(uom_raw) if uom_raw else None

                    # Add warning if UOM was normalized or is missing
                    if uom_raw and uom_normalized and uom_raw != uom_normalized:
                        warnings.append({
                            'type': 'uom_normalized',
                            'severity': 'info',
                            'item_id': item_canonical_id,
                            'original_uom': uom_raw,
                            'normalized_uom': uom_normalized,
                            'message': f"UOM normalized: '{uom_raw}' -> '{uom_normalized}' for {item_name}"
                        })

                    if not uom_normalized:
                        warnings.append({
                            'type': 'uom_missing',
                            'severity': 'warning',
                            'item_id': item_canonical_id,
                            'message': f"UOM is missing for {item_name}"
                        })

                    # Check expected UOM from config
                    expected_uom = item_config.get('uom')
                    if expected_uom and uom_normalized:
                        expected_normalized = self._canonicalize_uom(expected_uom)
                        if uom_normalized != expected_normalized:
                            warnings.append({
                                'type': 'uom_mismatch',
                                'severity': 'warning',
                                'item_id': item_canonical_id,
                                'parsed_uom': uom_normalized,
                                'expected_uom': expected_normalized,
                                'message': f"UOM mismatch for {item_name}: parsed '{uom_normalized}' vs expected '{expected_normalized}'"
                            })

                    bid_item = {
                        'id': item_canonical_id,
                        'section': section_name,
                        'label': item_name,
                        'qty': mapped['qty'],
                        'qty_raw': mapped.get('qty_raw', mapped['qty']),
                        'uom': uom_normalized or 'EA',  # Default to EA if missing
                        'uom_raw': uom_raw,
                        'provenance': {
                            'sheet': mapped.get('provenance', {}).get('sheet', ''),
                            'row': mapped.get('provenance', {}).get('row', 0),
                        },
                        'source_classification': source_classification,
                        'confidence': mapped.get('confidence', 1.0)
                    }

                    bid_items.append(bid_item)

        return bid_items

    def build_qa_report(
        self,
        normalized_rows: List[Dict],
        mapped_items: int,
        unmapped_items: List[Dict],
        warnings: List[Dict],
        ambiguous_matches: int,
        items_missing: int
    ) -> Dict[str, Any]:
        """
        Build comprehensive QA report.
        """
        total_rows = len(normalized_rows)
        rows_with_measures = len([r for r in normalized_rows if r['measures']])

        # Calculate confidence score
        confidence = 1.0

        # Deduct for unmapped items
        if total_rows > 0:
            unmapped_ratio = len(unmapped_items) / total_rows
            confidence -= unmapped_ratio * 0.3

        # Deduct for missing expected items
        total_expected = sum(len(items) for items in self.sections.values())
        if total_expected > 0:
            missing_ratio = items_missing / total_expected
            confidence -= missing_ratio * 0.2

        # Deduct for ambiguous matches
        if mapped_items > 0 and ambiguous_matches > 0:
            ambiguous_ratio = ambiguous_matches / mapped_items
            confidence -= ambiguous_ratio * 0.2

        # Ensure confidence doesn't go below 0
        confidence = max(0.0, confidence)

        return {
            'warnings': warnings,
            'confidence': round(confidence, 2),
            'stats': {
                'rows_total': total_rows,
                'rows_with_measures': rows_with_measures,
                'items_mapped': mapped_items,
                'items_missing': items_missing,
                'items_unmapped': len(unmapped_items),
                'ambiguous_matches': ambiguous_matches
            }
        }