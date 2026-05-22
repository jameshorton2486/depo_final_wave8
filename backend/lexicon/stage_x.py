"""Stage X — deterministic lexicon substitution.

Applies the merged Lexicon to transcript text as WHOLE-WORD,
possessive-aware substitution. Never mutates a substring inside a
larger word; never invents or guesses; every substitution is audited.

Match rule
----------
A token matches a lexicon key when, lowercased, it equals the key. The
token may be followed by a possessive (`'s` / `'s`), which is preserved
on the replacement. Word boundaries are non-word characters, so
`ultrinaty` never matches `trinaty`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.lexicon.model import Lexicon

# A token = run of word characters, optionally + apostrophe-s.
# Apostrophe variants: straight ' and curly '.
_TOKEN_RE = re.compile(r"[^\W\d_][\w]*(?:['\u2019]s)?|\d[\w]*", re.UNICODE)
_POSSESSIVE_RE = re.compile(r"(['\u2019]s)$", re.UNICODE)


@dataclass
class StageXSubstitution:
    """One applied lexicon substitution, for the audit log."""

    before: str
    after: str
    source: str
    utterance_id: str = ""

    def to_dict(self) -> dict:
        return {
            "before": self.before,
            "after": self.after,
            "source": self.source,
            "utterance_id": self.utterance_id,
        }


@dataclass
class StageXResult:
    """Result of applying Stage X to a body of text."""

    text: str
    substitutions: list[StageXSubstitution] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return len(self.substitutions) > 0


def _split_possessive(token: str) -> tuple[str, str]:
    """Split a trailing possessive off a token: ("Trinity's") -> ("Trinity","'s")."""
    m = _POSSESSIVE_RE.search(token)
    if m:
        return token[: m.start()], m.group(1)
    return token, ""


def _apply_multiword(
    text: str,
    lexicon: Lexicon,
    utterance_id: str,
    subs: list[StageXSubstitution],
) -> str:
    """Apply multi-word lexicon entries (e.g. 'acoustic neuroma').

    Each multi-word key is matched whole, case-insensitively, bounded
    by word boundaries. Single-word keys are skipped here -- the
    token pass handles them (with possessive awareness).
    """
    multiword = [
        (e.match_key, e) for e in lexicon.entries.values()
        if " " in e.match_key
    ]
    if not multiword:
        return text
    # Longest key first so "texas rules of civil procedure" wins over
    # any shorter overlapping phrase.
    multiword.sort(key=lambda kv: len(kv[0]), reverse=True)
    out = text
    for key, entry in multiword:
        if entry.replacement == key:
            continue
        pattern = re.compile(
            r"(?<!\w)" + re.escape(key) + r"(?!\w)", re.IGNORECASE)

        def _sub(m: re.Match) -> str:
            found = m.group(0)
            if found == entry.replacement:
                return found
            subs.append(StageXSubstitution(
                before=found, after=entry.replacement,
                source=entry.source, utterance_id=utterance_id))
            return entry.replacement

        out = pattern.sub(_sub, out)
    return out


def apply_stage_x_to_text(
    text: str,
    lexicon: Lexicon,
    utterance_id: str = "",
) -> StageXResult:
    """Apply the lexicon to one body of text. RAW input is never mutated."""
    if not text or len(lexicon) == 0:
        return StageXResult(text=text or "")

    subs: list[StageXSubstitution] = []

    # Multi-word phrases first, then single tokens.
    working = _apply_multiword(text, lexicon, utterance_id, subs)

    def _replace(match: re.Match) -> str:
        token = match.group(0)
        base, possessive = _split_possessive(token)
        entry = lexicon.get(base.lower())
        if entry is None or " " in entry.match_key:
            return token
        replacement = entry.replacement
        if base == replacement:
            return token
        new_token = replacement + possessive
        subs.append(StageXSubstitution(
            before=token, after=new_token,
            source=entry.source, utterance_id=utterance_id))
        return new_token

    new_text = _TOKEN_RE.sub(_replace, working)
    return StageXResult(text=new_text, substitutions=subs)


def apply_stage_x(
    utterances: list[dict],
    lexicon: Lexicon,
) -> tuple[list[dict], list[StageXSubstitution]]:
    """Apply Stage X across a list of utterance dicts.

    Returns (new_utterances, all_substitutions). The input list and its
    dicts are NOT mutated -- new dicts are returned. RAW stays intact.
    """
    out: list[dict] = []
    all_subs: list[StageXSubstitution] = []
    for utt in utterances:
        result = apply_stage_x_to_text(
            utt.get("text") or "", lexicon,
            utterance_id=utt.get("utterance_id") or "")
        new_utt = dict(utt)            # shallow copy -- never mutate input
        new_utt["text"] = result.text
        out.append(new_utt)
        all_subs.extend(result.substitutions)
    return out, all_subs
