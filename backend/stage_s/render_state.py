"""Stage S render state.

A small mutable container threaded through the renderer. Tracks whether
the transcript is currently ON or OFF the record, and remembers the
current examining attorney so the off-record state machine can re-emit
the "BY [examiner]:" attribution line on resumption.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.stage_s.models import ON_RECORD


@dataclass
class RenderState:
    """Mutable deposition state threaded through the Stage S render."""

    record_state: str = ON_RECORD
    current_examiner_label: str = ""   # e.g. "MR. VANCE"
    examiner_seen: bool = False

    def is_on_record(self) -> bool:
        return self.record_state == ON_RECORD

    def set_examiner(self, label: str) -> None:
        if label:
            self.current_examiner_label = label
            self.examiner_seen = True
