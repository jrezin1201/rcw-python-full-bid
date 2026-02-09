"""
Row-based extraction statistics tracking.
Ensures consistent, non-overlapping counts.
"""
from dataclasses import dataclass, field
from typing import Dict, Set
from collections import Counter


@dataclass
class RowDecision:
    """
    Represents the extraction decision for a single row.

    Attributes:
        status: Either "EXTRACTED" or "IGNORED"
        reasons: Set of reason codes (e.g., "empty", "no_quantity", "section_header")
    """
    status: str  # "EXTRACTED" or "IGNORED"
    reasons: Set[str] = field(default_factory=set)

    def add_reason(self, reason: str):
        """Add a reason code to this decision."""
        self.reasons.add(reason)

    def is_extracted(self) -> bool:
        """Check if row was extracted."""
        return self.status == "EXTRACTED"

    def is_ignored(self) -> bool:
        """Check if row was ignored."""
        return self.status == "IGNORED"


class ExtractionStats:
    """
    Tracks extraction statistics on a per-row basis.
    Ensures no double-counting and consistent totals.
    """

    def __init__(self):
        self.rows_total = 0
        self.rows_extracted = 0
        self.rows_ignored = 0
        self.ignored_reason_counts: Counter = Counter()

    def commit_row(self, decision: RowDecision):
        """
        Record a row decision and update stats.

        Args:
            decision: RowDecision indicating what happened to this row
        """
        self.rows_total += 1

        if decision.is_extracted():
            self.rows_extracted += 1
        elif decision.is_ignored():
            self.rows_ignored += 1
            # Count each reason this row was ignored for
            for reason in decision.reasons:
                self.ignored_reason_counts[reason] += 1

    def to_dict(self) -> Dict[str, any]:
        """
        Export stats as a dictionary for API response.

        Returns:
            Dictionary with consistent row-based stats
        """
        result = {
            "rows_total": self.rows_total,
            "rows_extracted": self.rows_extracted,
            "rows_ignored": self.rows_ignored,
        }

        # Add individual reason counts with clear prefixes
        for reason, count in self.ignored_reason_counts.items():
            result[f"ignored_{reason}"] = count

        # Add total reason count (can be > rows_ignored if rows have multiple reasons)
        if self.ignored_reason_counts:
            result["ignored_reasons_total"] = sum(self.ignored_reason_counts.values())

        return result

    def __repr__(self):
        return (
            f"ExtractionStats(total={self.rows_total}, "
            f"extracted={self.rows_extracted}, "
            f"ignored={self.rows_ignored}, "
            f"reasons={dict(self.ignored_reason_counts)})"
        )
