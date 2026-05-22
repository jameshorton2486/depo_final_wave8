"""Transcript state model — Wave 18.5.

The Snapshot is an immutable capture of the COMPLETE transcript state.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

# Snapshot categories (docs/wave18_5_snapshot_versioning.md section 6).
SNAPSHOT_CATEGORIES: tuple[str, ...] = (
    "AUTO_SAVE",
    "MANUAL",
    "PRE_AI",
    "POST_AI",
    "POST_REVIEW",
    "PRE_EXPORT",
    "EXPORT",
    "CERTIFIED",
)


@dataclass
class ExportReference:
    """A record of one export produced from a snapshot."""

    export_id: str
    export_format: str
    export_timestamp: str
    export_profile: str = "texas_ufm"
    export_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "export_id": self.export_id,
            "export_format": self.export_format,
            "export_timestamp": self.export_timestamp,
            "export_profile": self.export_profile,
            "export_hash": self.export_hash,
        }


@dataclass
class Snapshot:
    """An immutable capture of the complete transcript state."""

    job_id: str
    state_hash: str
    state: dict                          # the full captured state
    category: str = "MANUAL"
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ai_trace: list = field(default_factory=list)   # AI review traceability
    export_refs: list = field(default_factory=list)
    locked: bool = False                 # True = Certification Snapshot
    note: str = ""
    created_by: str = ""
    created_at: str = ""

    @property
    def is_certification_snapshot(self) -> bool:
        return self.locked or self.category == "CERTIFIED"

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "job_id": self.job_id,
            "category": self.category,
            "state_hash": self.state_hash,
            "ai_trace": self.ai_trace,
            "export_refs": self.export_refs,
            "locked": self.locked,
            "is_certification_snapshot": self.is_certification_snapshot,
            "note": self.note,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }

    def to_summary(self) -> dict:
        """A lightweight dict for listing -- omits the full state blob."""
        d = self.to_dict()
        d["export_count"] = len(self.export_refs)
        return d
