"""Stage F — Flag Generation.

When the engine detects a probable error it cannot fix within the rules,
it inserts a numbered ``[SCOPIST: FLAG N]`` and changes nothing else.
Spec section 5 / 14.

Foundation scope: this module implements the flag registry (sequential
numbering across the job) and two enumerable detectors that need no
semantic judgement:

  FLAG-02  known List-3 verbatim-sensitive items
  FLAG-06  garbled oath / certification language (Q3 decision)

FLAG-01 (unverified proper nouns), FLAG-03 (residual garble), FLAG-04
(boundary uncertainty, emitted by Stage S) and FLAG-05 (ambiguous
date/number) arrive with later stages and are not implemented yet.

Build reference: deterministic_correction_engine_spec.md v1.2 section 14.
"""
from __future__ import annotations

from backend.corrections import patterns as P
from backend.corrections.model import Flag


class FlagRegistry:
    """Issues sequential flag numbers across one job and collects every
    Flag raised. One registry per ``pipeline.run`` call."""

    def __init__(self) -> None:
        self._flags: list[Flag] = []

    def raise_flag(
        self, utterance_id: str, category: str, reason: str,
        as_transcribed: str, char_offset: int = 0,
    ) -> Flag:
        flag = Flag(
            flag_number=len(self._flags) + 1,
            utterance_id=utterance_id,
            category=category,
            reason=reason,
            as_transcribed=as_transcribed,
            char_offset=char_offset,
        )
        self._flags.append(flag)
        return flag

    @property
    def flags(self) -> list[Flag]:
        return list(self._flags)


def _detect_flag06_oath(text: str) -> list[tuple[str, str]]:
    """FLAG-06 — garbled oath language. Returns (matched_phrase, reason).
    Detect-and-flag only; never corrected."""
    found: list[tuple[str, str]] = []
    low = text.lower()
    for phrase in P.OATH_GARBLE_DETECT:
        if phrase in low:
            found.append((phrase, "garbled oath language -- verify (likely 'so help you God')"))
    return found


def _detect_flag02_list3(text: str) -> list[tuple[str, str]]:
    """FLAG-02 — known List-3 verbatim-sensitive items."""
    found: list[tuple[str, str]] = []
    for item, reason in P.LIST3_FLAG_ITEMS.items():
        if item in text:
            found.append((item, reason))
    return found


def detect(text: str, uid: str, ctx, registry: FlagRegistry) -> str:
    """Run Stage F over one utterance's text.

    Returns the text with any flag markers inserted. Detectors run on the
    UNGUARDED text (Stage F runs after corrections; the pipeline passes
    post-correction text). Each detected item raises a Flag and inserts
    its marker immediately after the offending phrase.
    """
    out = text

    for phrase, reason in _detect_flag06_oath(out):
        flag = registry.raise_flag(uid, "oath", reason, phrase)
        out = _insert_marker(out, phrase, flag.marker(), case_insensitive=True)

    for phrase, reason in _detect_flag02_list3(out):
        flag = registry.raise_flag(uid, "entity", reason, phrase)
        out = _insert_marker(out, phrase, flag.marker())

    return out


def _insert_marker(text: str, phrase: str, marker: str, case_insensitive: bool = False) -> str:
    """Insert ``marker`` immediately after the first occurrence of
    ``phrase``. Leaves the phrase itself verbatim."""
    haystack = text.lower() if case_insensitive else text
    needle = phrase.lower() if case_insensitive else phrase
    idx = haystack.find(needle)
    if idx == -1:
        return text
    end = idx + len(phrase)
    return text[:end] + " " + marker + text[end:]
