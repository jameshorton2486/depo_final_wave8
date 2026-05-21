"""Stage S audit log.

Records every structural transformation so human reviewers retain
ultimate authority and the render is fully defensible: Q/A splits,
objection isolation, off-record suppression spans, dash insertions.

The audit log is data, not side-effects -- it travels with the render
result so the Workspace / Export can surface it.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AuditEntry:
    """One logged structural transformation."""

    kind: str            # qa_split | objection_isolated | off_record_span
                         #  | dash_inserted | parenthetical_emitted
                         #  | by_line_emitted
    detail: str          # human-readable description
    source_utterance_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "detail": self.detail,
            "source_utterance_ids": list(self.source_utterance_ids),
        }


class AuditLog:
    """Collects AuditEntry records during a Stage S render pass."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(
        self,
        kind: str,
        detail: str,
        source_utterance_ids: list[str] | None = None,
    ) -> None:
        self._entries.append(AuditEntry(
            kind=kind,
            detail=detail,
            source_utterance_ids=list(source_utterance_ids or []),
        ))

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def to_list(self) -> list[dict]:
        return [e.to_dict() for e in self._entries]

    def count(self, kind: str | None = None) -> int:
        if kind is None:
            return len(self._entries)
        return sum(1 for e in self._entries if e.kind == kind)
