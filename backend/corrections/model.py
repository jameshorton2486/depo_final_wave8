"""Data types for the deterministic correction engine.

The correction engine (``backend/corrections/``) is a fully deterministic,
no-AI transcript correction layer. It operates on the WORKING layer only;
the RAW Deepgram packet and ``transcript_words.raw_text`` are never written.

This module defines the small, self-contained types the engine speaks, so
the package is testable in isolation from the app's pydantic models.

Build reference: docs/architecture/transcript_engine/
deterministic_correction_engine_spec.md (v1.2), section 4 (Input / Output
Contract) and section 17.1 (Correction Log).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


class SpeakerMapUnverifiedError(RuntimeError):
    """Raised when the engine is asked to run before the Wave 9 speaker
    mapping is confirmed. The engine's role-scoped stages (X, Q) require
    confirmed roles; running without them is a hard error."""


# ---------------------------------------------------------------------
# Input: the working transcript
# ---------------------------------------------------------------------


@dataclass
class Utterance:
    """One working-layer utterance fed to the engine.

    ``role`` is the confirmed Wave 9 participant role for this utterance's
    speaker (examining_attorney, witness, defending_attorney, co_counsel,
    court_reporter, videographer, interpreter, off_record, other). It is
    'other' when the speaker is unmapped.
    """

    utterance_id: str
    speaker_index: Optional[int]
    role: str
    text: str
    participant_name: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0


# ---------------------------------------------------------------------
# Output: correction log + flags + rendered lines
# ---------------------------------------------------------------------


@dataclass
class CorrectionLogEntry:
    """One auditable change. Spec 17.1 / Q6: every change the engine makes
    is recorded — nothing is silent."""

    rule_id: str          # e.g. "PRE-04", "POST-01"
    stage: str            # e.g. "A", "M", "T"
    utterance_id: str
    before: str
    after: str

    def word_delta(self) -> int:
        """Net change in word-token count caused by this edit. Used by the
        diff harness to verify net word_delta == 0 in Parity Mode."""
        return len(self.after.split()) - len(self.before.split())


@dataclass
class Flag:
    """One ``[SCOPIST: FLAG N]`` raised by Stage F. Spec section 5."""

    flag_number: int
    utterance_id: str
    category: str         # entity | speaker | garble | date | boundary | number | oath
    reason: str
    as_transcribed: str
    char_offset: int = 0

    def marker(self) -> str:
        """The inline marker string inserted into the working text."""
        return (
            f'[SCOPIST: FLAG {self.flag_number}: "{self.reason}" '
            f"-- verify from audio or case materials]"
        )


@dataclass
class RenderedLine:
    """One line of the corrected WORKING transcript.

    In the foundation (Parity Mode) every line is line_type 'utterance' and
    maps 1:1 to an input utterance. The structural stages (S, Q) — added
    later — introduce Q/A/colloquy/parenthetical line types.
    """

    line_type: str        # utterance | Q | A | speaker_label | parenthetical | header
    text: str
    utterance_ids: list[str] = field(default_factory=list)
    speaker_index: Optional[int] = None
    role: Optional[str] = None
    tab_level: int = 0


@dataclass
class CorrectionResult:
    """What ``pipeline.run`` returns. Spec section 4.2."""

    lines: list[RenderedLine]
    log: list[CorrectionLogEntry]
    flags: list[Flag]
    parity_mode: bool

    def gross_word_delta(self, raw_word_count: int) -> int:
        """APP word count minus RAW word count. Net of logged corrections
        this must be 0 in Parity Mode (harness spec section 4.1)."""
        app_words = sum(len(ln.text.split()) for ln in self.lines)
        return app_words - raw_word_count
