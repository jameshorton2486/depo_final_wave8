"""Lexicon merge — combine the five lexicon sources by priority.

Reporter-confirmed corrections always win over lower-priority sources.
A key collision is resolved by SOURCE_PRIORITY rank (lower rank wins).
Within the same source, last-write-wins.

All inputs are read-only; the merge produces a fresh Lexicon.
"""
from __future__ import annotations

from typing import Optional

from backend.lexicon.model import Lexicon, LexiconEntry


def _norm_key(text: str) -> str:
    """Normalise a match key: stripped, lowercased."""
    return (text or "").strip().lower()


def _add(lex: Lexicon, match_key: str, replacement: str, source: str) -> None:
    """Add an entry, respecting source priority on collision."""
    key = _norm_key(match_key)
    rep = (replacement or "").strip()
    if not key or not rep:
        return
    existing = lex.entries.get(key)
    new_entry = LexiconEntry(match_key=key, replacement=rep, source=source)
    if existing is None or new_entry.rank <= existing.rank:
        # New entry wins if it is equal or higher priority (lower rank).
        lex.entries[key] = new_entry


def merge_lexicon(
    confirmed_spellings: Optional[dict] = None,
    reporter_case_corrections: Optional[dict] = None,
    deepgram_keyterms: Optional[list] = None,
    intake_keyterms: Optional[list] = None,
    global_dictionary: Optional[dict] = None,
) -> Lexicon:
    """Merge the five lexicon sources into one priority-resolved Lexicon.

    Parameters
    ----------
    confirmed_spellings, reporter_case_corrections, global_dictionary
        dict of {misspelled-or-lowercase : canonical}.
    deepgram_keyterms, intake_keyterms
        list of canonical terms. The match key is the lowercased term;
        the replacement is the term itself (a casing correction).

    Lower-priority sources are added first so higher-priority sources
    overwrite them.
    """
    lex = Lexicon()

    # Add lowest priority first so higher priority overwrites.
    for term in (global_dictionary or {}).items():
        _add(lex, term[0], term[1], "global_dictionary")

    for term in (intake_keyterms or []):
        _add(lex, term, term, "intake_keyterms")

    for term in (deepgram_keyterms or []):
        _add(lex, term, term, "deepgram_keyterms")

    for k, v in (reporter_case_corrections or {}).items():
        _add(lex, k, v, "reporter_case")

    for k, v in (confirmed_spellings or {}).items():
        _add(lex, k, v, "confirmed_spellings")

    return lex


def merge_from_job_config(job_config: Optional[dict]) -> Lexicon:
    """Build a Lexicon from a job_config dict (the engine's config shape).

    Recognised keys: confirmed_spellings, reporter_case_corrections,
    deepgram_keyterms, intake_keyterms, global_dictionary.
    """
    cfg = job_config or {}
    return merge_lexicon(
        confirmed_spellings=cfg.get("confirmed_spellings"),
        reporter_case_corrections=cfg.get("reporter_case_corrections"),
        deepgram_keyterms=cfg.get("deepgram_keyterms"),
        intake_keyterms=cfg.get("intake_keyterms"),
        global_dictionary=cfg.get("global_dictionary"),
    )
