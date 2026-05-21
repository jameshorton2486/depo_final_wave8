"""Stage M — Metadata & Confirmed-Spelling Substitution.

Exact-match replacement from ``job_config`` and fixed maps: reporter-name
garbles, speaker-label standardisation, confirmed_spellings, keyterms, and
structural identifiers. No phonetic matching at this layer — exact strings
only. Source rule IDs PRE-01/02/07/08/09.

Texas-terminology (PRE-03) is caption/metadata only and is intentionally
NOT applied to transcript body text, so it is not run here.

Build reference: deterministic_correction_engine_spec.md v1.2 section 9.
"""
from __future__ import annotations

import re

from backend.corrections import patterns as P
from backend.corrections.model import CorrectionLogEntry

_STAGE = "M"


def _log(rule_id: str, uid: str, before: str, after: str) -> CorrectionLogEntry:
    return CorrectionLogEntry(
        rule_id=rule_id, stage=_STAGE, utterance_id=uid, before=before, after=after
    )


def _replace_exact(text: str, key: str, value: str) -> str:
    """Plain substring replace — exact, case-sensitive."""
    return text.replace(key, value)


def _pre01_reporter_name(text, uid, ctx):
    """PRE-01 — known reporter-name garbles -> the canonical reporter name
    from job_config. No-op if no reporter_name is configured."""
    canonical = (ctx.job_config.get("reporter_name") or "").strip()
    if not canonical:
        return text, []
    log: list[CorrectionLogEntry] = []
    out = text
    for garble in P.REPORTER_NAME_GARBLES:
        if garble in out:
            new = out.replace(garble, canonical)
            log.append(_log("PRE-01", uid, out, new))
            out = new
    return out, log


def _pre02_labels(text, uid, ctx):
    """PRE-02 — THE COURT REPORTER: -> THE REPORTER:, etc. Longest key
    first so 'THE COURT REPORTER:' wins over 'COURT REPORTER:'."""
    log: list[CorrectionLogEntry] = []
    out = text
    for key in sorted(P.LABEL_MAP, key=len, reverse=True):
        if key in out:
            new = out.replace(key, P.LABEL_MAP[key])
            log.append(_log("PRE-02", uid, out, new))
            out = new
    return out, log


_MASK_OPEN = "\x02"
_MASK_CLOSE = "\x03"
_MASK_RE = re.compile(_MASK_OPEN + r"(\d+)" + _MASK_CLOSE)


def _masked_replace(text: str, pairs: list[tuple[str, str]]) -> str:
    """Multi-key find/replace that is idempotent and cross-contamination-free.

    A confirmed spelling often EXPANDS a key into a value that contains the
    key ("Home Depot" -> "Home Depot U.S.A., Inc."). Naive replacement then
    (a) re-fires on a second run and (b) lets one key match inside another
    key's freshly inserted value. Both are wrong.

    Fix: mask every value before it can be re-matched.
      1. mask values already present in the text;
      2. for each key (longest first) replace it with a MASKED value;
      3. restore all masks.

    ``pairs`` must already be sorted longest-key-first.
    """
    masks: list[str] = []

    def _stash(s: str) -> str:
        masks.append(s)
        return f"{_MASK_OPEN}{len(masks) - 1}{_MASK_CLOSE}"

    # 1. Pre-mask any already-correct value (idempotency).
    for _key, value in sorted(pairs, key=lambda kv: len(kv[1]), reverse=True):
        if value and value in text:
            text = text.replace(value, _stash(value))

    # 2. Replace each key with a masked value (no cross-contamination).
    for key, value in pairs:
        if key and key != value and key in text:
            text = text.replace(key, _stash(value))

    # 3. Restore.
    return _MASK_RE.sub(lambda m: masks[int(m.group(1))], text)


def _pre07_confirmed_spellings(text, uid, ctx):
    """PRE-07 — apply job_config.confirmed_spellings, longest key first.

    These are operator-verified entities; the engine is applying a
    confirmed fact, not guessing. Idempotent and substring-safe via
    ``_masked_replace``.
    """
    spellings: dict[str, str] = ctx.job_config.get("confirmed_spellings") or {}
    if not spellings:
        return text, []
    pairs = sorted(spellings.items(), key=lambda kv: len(kv[0]), reverse=True)
    new = _masked_replace(text, pairs)
    if new != text:
        return new, [_log("PRE-07", uid, text, new)]
    return text, []


def _pre08_keyterms(text, uid, ctx):
    """PRE-08 — apply job_config.deepgram_keyterms by exact match only.

    A keyterm is applied when its lowercased form appears but the exact
    cased form does not — a pure casing correction. Near-misses are NOT
    corrected here (that is semantic; Stage F flags them).
    """
    keyterms: list[str] = ctx.job_config.get("deepgram_keyterms") or []
    if not keyterms:
        return text, []
    log: list[CorrectionLogEntry] = []
    out = text
    for term in sorted(keyterms, key=len, reverse=True):
        if not term or term in out:
            continue
        low = term.lower()
        idx = out.lower().find(low)
        if idx != -1:
            new = out[:idx] + term + out[idx + len(term):]
            log.append(_log("PRE-08", uid, out, new))
            out = new
    return out, log


def _pre09_identifiers(text, uid, ctx):
    """PRE-09 — structural identifier formatting: cause numbers, e-tran."""
    log: list[CorrectionLogEntry] = []
    out = text

    new = P.PRE09_CAUSE_NUMBER_RE.sub(r"\1-\2-\3-\4", out)
    if new != out:
        log.append(_log("PRE-09", uid, out, new))
        out = new

    new = P.PRE09_ETRAN_RE.sub("e-tran", out)
    if new != out:
        log.append(_log("PRE-09", uid, out, new))
        out = new
    return out, log


def apply(text: str, uid: str, ctx) -> tuple[str, list[CorrectionLogEntry]]:
    """Run Stage M over one utterance's guarded text."""
    log: list[CorrectionLogEntry] = []
    for fn in (
        _pre01_reporter_name,
        _pre02_labels,
        _pre07_confirmed_spellings,
        _pre08_keyterms,
        _pre09_identifiers,
    ):
        text, entries = fn(text, uid, ctx)
        log.extend(entries)
    return text, log
