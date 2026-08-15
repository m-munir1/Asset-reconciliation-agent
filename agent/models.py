"""
Core data models.

A "FieldReport" is one source's claim about the value of one field
of an asset, at a point in time. The whole system is built around
collecting these, comparing them, and producing a ReconciledField
with an auditable decision trail.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class FieldReport:
    """One source's claim about one field's value."""
    source: str
    field_name: str
    value: Any
    reported_at: datetime          # when the source says the event happened
    ingested_at: datetime          # when we received this report
    raw: Optional[dict] = None     # original payload, for audit purposes

    def __repr__(self) -> str:
        return (f"FieldReport(source={self.source!r}, field={self.field_name!r}, "
                f"value={self.value!r}, reported_at={self.reported_at.isoformat()})")


@dataclass
class DecisionStep:
    """One step in the agent's reasoning process, for audit/replay."""
    action: str            # e.g. "compare", "query_tool", "apply_rule", "flag_contradiction"
    detail: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReconciledField:
    """The final decision for a single field, with full justification."""
    field_name: str
    value: Any
    chosen_source: str
    confidence: Confidence
    reasoning: str
    contradiction_flagged: bool
    candidates: list[FieldReport]           # all reports considered for this field
    decision_trail: list[DecisionStep]      # ordered steps the agent took

    def to_dict(self) -> dict:
        return {
            "field": self.field_name,
            "value": self.value,
            "chosen_source": self.chosen_source,
            "confidence": self.confidence.value,
            "reasoning": self.reasoning,
            "contradiction_flagged": self.contradiction_flagged,
            "candidates_considered": [
                {
                    "source": c.source,
                    "value": c.value,
                    "reported_at": c.reported_at.isoformat(),
                    "ingested_at": c.ingested_at.isoformat(),
                }
                for c in self.candidates
            ],
            "decision_trail": [
                {"action": s.action, "detail": s.detail, "timestamp": s.timestamp.isoformat()}
                for s in self.decision_trail
            ],
        }


@dataclass
class ReconciledAsset:
    """Full reconciled record for one asset: one ReconciledField per field."""
    asset_id: str
    fields: dict[str, ReconciledField]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "generated_at": self.generated_at.isoformat(),
            "fields": {name: f.to_dict() for name, f in self.fields.items()},
        }

    def query(self, field_name: str) -> Optional[ReconciledField]:
        """Look up the reasoning for a single field — the 'queryable and
        reviewable' audit trail the assessment asks for."""
        return self.fields.get(field_name)
