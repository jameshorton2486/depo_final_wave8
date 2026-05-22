"""Lexicon data model.

A LexiconEntry is one confirmed substitution: a lowercased match key
mapped to its canonical replacement, tagged with the source it came
from (so priority and audit are possible).

A Lexicon is the merged, priority-resolved collection used by Stage X.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Source identifiers, highest authority first. Index = priority
# (lower index wins on a key collision).
SOURCE_PRIORITY: tuple[str, ...] = (
    "confirmed_spellings",     # 1 — reporter-verified, highest
    "reporter_case",           # 2 — reporter per-case corrections
    "deepgram_keyterms",       # 3
    "intake_keyterms",         # 4 — intake-generated keyterms.json
    "global_dictionary",       # 5 — future shared dictionaries
)


def source_rank(source: str) -> int:
    """Priority rank of a source; lower wins. Unknown sources rank last."""
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(SOURCE_PRIORITY)


@dataclass
class LexiconEntry:
    """One confirmed substitution."""

    match_key: str        # lowercased token to match, e.g. "trinaty"
    replacement: str      # canonical form, e.g. "Trinity"
    source: str           # one of SOURCE_PRIORITY

    @property
    def rank(self) -> int:
        return source_rank(self.source)


@dataclass
class Lexicon:
    """The merged, priority-resolved lexicon used by Stage X."""

    entries: dict[str, LexiconEntry] = field(default_factory=dict)

    def get(self, token_lower: str) -> LexiconEntry | None:
        return self.entries.get(token_lower)

    def __len__(self) -> int:
        return len(self.entries)

    def to_list(self) -> list[dict]:
        return [
            {"match_key": e.match_key, "replacement": e.replacement,
             "source": e.source}
            for e in sorted(self.entries.values(),
                            key=lambda e: e.match_key)
        ]
