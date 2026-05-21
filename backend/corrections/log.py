"""The Correction Log.

Spec 17.1 / Q6: every change the engine makes is recorded — rule ID,
utterance ID, before, after, stage. The log is a firm build requirement,
not optional: a certifiable system must let the reporter audit every
automatic edit, and the diff harness uses the log to verify that net
word_delta is 0 in Parity Mode.

This module is a thin collector. The CorrectionLogEntry type itself lives
in model.py; this adds aggregation and serialisation around it.

Build reference: deterministic_correction_engine_spec.md v1.2 section 17.1.
"""
from __future__ import annotations

from backend.corrections.model import CorrectionLogEntry


class CorrectionLog:
    """Collects every CorrectionLogEntry produced during one ``run``."""

    def __init__(self) -> None:
        self._entries: list[CorrectionLogEntry] = []

    def extend(self, entries: list[CorrectionLogEntry]) -> None:
        self._entries.extend(entries)

    @property
    def entries(self) -> list[CorrectionLogEntry]:
        return list(self._entries)

    def net_word_delta(self) -> int:
        """Total word-count effect of every logged correction. The diff
        harness subtracts this from gross word_delta; the result must be 0
        in Parity Mode."""
        return sum(e.word_delta() for e in self._entries)

    def count_by_rule(self) -> dict[str, int]:
        """How many times each rule fired — useful for the diff report."""
        counts: dict[str, int] = {}
        for e in self._entries:
            counts[e.rule_id] = counts.get(e.rule_id, 0) + 1
        return counts

    def to_dicts(self) -> list[dict]:
        """JSON-serialisable form, for persistence alongside the WORKING
        transcript (Q6) and for the harness ``correction_log.json``."""
        return [
            {
                "rule_id": e.rule_id,
                "stage": e.stage,
                "utterance_id": e.utterance_id,
                "before": e.before,
                "after": e.after,
                "word_delta": e.word_delta(),
            }
            for e in self._entries
        ]
