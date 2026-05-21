"""Stage T — Typography & Spacing.

Universal formatting, no judgement: the two-space rule, objection
double-space, honorific formatting, Miss normalisation, em-dash, and the
deterministic time/money/percent rules. Source rule IDs POST-01..08.

Honorific spacing is ONE space after the period (Q2 decision —
``MR. GARCIA``, not ``MR.  GARCIA``). The colon two-space (POST-02 family)
is separate and unchanged.

Large-number commas (POST-09) are flag-only per Q5 and are not applied
here.

Build reference: deterministic_correction_engine_spec.md v1.2 section 13.
"""
from __future__ import annotations

from backend.corrections import patterns as P
from backend.corrections.model import CorrectionLogEntry

_STAGE = "T"


def _log(rule_id: str, uid: str, before: str, after: str) -> CorrectionLogEntry:
    return CorrectionLogEntry(
        rule_id=rule_id, stage=_STAGE, utterance_id=uid, before=before, after=after
    )


def _post01_two_space(text, uid):
    """POST-01 — two spaces after . ? ! before a capital, EXCEPT after a
    known abbreviation. Idempotent: \\s+ collapses any run to exactly two."""
    log: list[CorrectionLogEntry] = []

    def _sub(match):
        # Guard: is the punctuation part of an abbreviation like "Mr."?
        start = match.start()
        prefix = text[:start + 1]
        if P.POST01_ABBREV_RE.search(prefix):
            return match.group(0)
        return match.group(1) + "  "

    new = P.POST01_TWO_SPACE_RE.sub(_sub, text)
    if new != text:
        log.append(_log("POST-01", uid, text, new))
    return new, log


def _post02_objection(text, uid):
    """POST-02 — two spaces between ``Objection.`` and its basis."""
    new = P.POST02_OBJECTION_RE.sub("Objection.  ", text)
    if new != text:
        return new, [_log("POST-02", uid, text, new)]
    return text, []


def _post03_honorifics(text, uid):
    """POST-03/04 — Mr./Ms./Mrs. -> ALL-CAPS, ONE space after the period.
    ``Dr.`` in body text stays lowercase (POST-04 exception)."""
    log: list[CorrectionLogEntry] = []

    def _sub(match):
        return match.group(1).upper() + ". "

    new = P.POST03_HONORIFIC_RE.sub(_sub, text)
    if new != text:
        log.append(_log("POST-03", uid, text, new))
    return new, log


def _post05_miss(text, uid):
    """POST-05 — ``Miss Smith`` -> ``Ms. Smith``. Skips quoted ``Miss``
    (deterministic proxy: not inside double quotes)."""
    if '"' in text:
        return text, []
    new = P.POST05_MISS_RE.sub("Ms. ", text)
    if new != text:
        return new, [_log("POST-05", uid, text, new)]
    return text, []


def _post06_emdash(text, uid):
    """POST-06 — em dash -> spaced double hyphen."""
    new = P.POST06_EMDASH_RE.sub(" -- ", text)
    if new != text:
        return new, [_log("POST-06", uid, text, new)]
    return text, []


def _post07_time(text, uid):
    """POST-07 — strip leading zero from times; AM/PM -> a.m./p.m."""
    log: list[CorrectionLogEntry] = []
    out = text

    new = P.POST07_LEADING_ZERO_RE.sub(r"\1:\2", out)
    if new != out:
        log.append(_log("POST-07", uid, out, new))
        out = new

    def _ampm(match):
        return match.group(1) + " " + match.group(2).lower() + ".m."

    new = P.POST07_AMPM_RE.sub(_ampm, out)
    if new != out:
        log.append(_log("POST-07", uid, out, new))
        out = new
    return out, log


def _post08_money_percent(text, uid):
    """POST-08 — strip even-dollar .00; percent symbol -> word."""
    log: list[CorrectionLogEntry] = []
    out = text

    new = P.POST08_MONEY_RE.sub(r"$\1", out)
    if new != out:
        log.append(_log("POST-08", uid, out, new))
        out = new

    new = P.POST08_PERCENT_RE.sub(r"\1 percent", out)
    if new != out:
        log.append(_log("POST-08", uid, out, new))
        out = new
    return out, log


def apply(text: str, uid: str, ctx) -> tuple[str, list[CorrectionLogEntry]]:
    """Run Stage T over one utterance's guarded text."""
    log: list[CorrectionLogEntry] = []
    for fn in (
        _post03_honorifics,
        _post05_miss,
        _post06_emdash,
        _post07_time,
        _post08_money_percent,
        _post02_objection,
        _post01_two_space,
    ):
        text, entries = fn(text, uid)
        log.extend(entries)
    return text, log
