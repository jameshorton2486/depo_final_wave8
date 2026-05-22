"""The four-part permitted-correction test.

From the AI Processing Reference and Legal Standards STD-VRB-05. An AI
suggestion may be presented as an applicable *correction* only when ALL
four conditions hold:

  (a) the error is clearly a speech-to-text artifact;
  (b) the intended wording is unambiguous from context;
  (c) the correction does not alter testimony meaning;
  (d) a reasonable scopist would make the same call.

A suggestion that cannot assert all four is downgraded to a FLAG -- it
is surfaced for human review but never presented as an edit to apply.

This module is deterministic: it does not call AI. It evaluates the
four booleans the AI layer attaches to each candidate suggestion.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FourPartResult:
    """Outcome of the four-part test for one candidate suggestion."""

    is_stt_artifact: bool
    wording_unambiguous: bool
    meaning_unchanged: bool
    reasonable_scopist_agrees: bool

    @property
    def passes(self) -> bool:
        """True only when all four conditions hold."""
        return (self.is_stt_artifact
                and self.wording_unambiguous
                and self.meaning_unchanged
                and self.reasonable_scopist_agrees)

    def failed_conditions(self) -> list[str]:
        """Names of the conditions that did not hold (for the audit note)."""
        out = []
        if not self.is_stt_artifact:
            out.append("not a clear STT artifact")
        if not self.wording_unambiguous:
            out.append("intended wording ambiguous")
        if not self.meaning_unchanged:
            out.append("may alter testimony meaning")
        if not self.reasonable_scopist_agrees:
            out.append("a reasonable scopist might disagree")
        return out


def evaluate(
    is_stt_artifact: bool,
    wording_unambiguous: bool,
    meaning_unchanged: bool,
    reasonable_scopist_agrees: bool,
) -> FourPartResult:
    """Build a FourPartResult from the four claimed conditions."""
    return FourPartResult(
        is_stt_artifact=bool(is_stt_artifact),
        wording_unambiguous=bool(wording_unambiguous),
        meaning_unchanged=bool(meaning_unchanged),
        reasonable_scopist_agrees=bool(reasonable_scopist_agrees),
    )
