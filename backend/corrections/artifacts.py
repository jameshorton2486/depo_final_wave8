"""Stage A — Deepgram Artifact Removal.

Mechanical speech-to-text errors detectable by pattern: consecutive
duplicate words, standalone artifacts (K. / Mhmm), the Doctor-period
artifact, and orphaned punctuation. Source rule IDs PRE-04/05/06/10.

Every stage function takes the working text plus a ``ctx`` and returns
``(new_text, log_entries)``. The text is the guarded text — sentinels
are opaque and simply pass through.

Build reference: deterministic_correction_engine_spec.md v1.2 section 8.
"""
from __future__ import annotations

from backend.corrections import patterns as P
from backend.corrections.model import CorrectionLogEntry

_STAGE = "A"


def _log(rule_id: str, uid: str, before: str, after: str) -> CorrectionLogEntry:
    return CorrectionLogEntry(
        rule_id=rule_id, stage=_STAGE, utterance_id=uid, before=before, after=after
    )


def _pre04_duplicates(text: str, uid: str) -> tuple[str, list[CorrectionLogEntry]]:
    """PRE-04 — collapse ``the witness witness`` -> ``the witness``.

    Skips any word in AFFIRMATION_PROTECTED (``correct correct`` and
    ``right right`` are intentional verbatim affirmations). 1-3 char
    duplicates are left intact — they may be stutter evidence.
    """
    log: list[CorrectionLogEntry] = []

    def _sub(match) -> str:
        word = match.group(1)
        if word.lower() in P.AFFIRMATION_PROTECTED:
            return match.group(0)
        log.append(_log("PRE-04", uid, match.group(0), word))
        return word

    return P.PRE04_DUPLICATE_RE.sub(_sub, text), log


def _pre05_standalone(text: str, uid: str) -> tuple[str, list[CorrectionLogEntry]]:
    """PRE-05 — K. -> Okay. , Mhmm -> Mm-hmm. Idempotent (target forms are
    not themselves matched)."""
    log: list[CorrectionLogEntry] = []
    out = text

    def _apply(pattern, replacement, rule="PRE-05"):
        nonlocal out
        new = pattern.sub(replacement, out)
        if new != out:
            log.append(_log(rule, uid, out, new))
            out = new

    _apply(P.PRE05_K_RE, "Okay.")
    _apply(P.PRE05_K_LOWER_RE, "Okay.")
    _apply(P.PRE05_MHMM_RE, "Mm-hmm")
    return out, log


def _pre06_doctor(text: str, uid: str) -> tuple[str, list[CorrectionLogEntry]]:
    """PRE-06 — ``Doctor. Smith`` -> ``Dr. Smith`` (only before a capital)."""
    new = P.PRE06_DOCTOR_PERIOD_RE.sub("Dr. ", text)
    if new != text:
        return new, [_log("PRE-06", uid, text, new)]
    return text, []


def _pre10_orphan_dash(text: str, uid: str) -> tuple[str, list[CorrectionLogEntry]]:
    """PRE-10 — collapse ``-- --`` orphaned punctuation to one space."""
    new = P.PRE10_ORPHAN_DASH_RE.sub(" ", text)
    if new != text:
        return new, [_log("PRE-10", uid, text, new)]
    return text, []


def apply(text: str, uid: str, ctx) -> tuple[str, list[CorrectionLogEntry]]:
    """Run Stage A over one utterance's guarded text."""
    log: list[CorrectionLogEntry] = []
    for fn in (_pre04_duplicates, _pre05_standalone, _pre06_doctor, _pre10_orphan_dash):
        text, entries = fn(text, uid)
        log.extend(entries)
    return text, log
