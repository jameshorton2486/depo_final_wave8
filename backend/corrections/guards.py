"""Stage G (Verbatim Guards) and Stage U (Unguard).

Stage G shields protected verbatim spans — fillers, stutters, false
starts, ellipses, LC markers — by replacing each with an opaque sentinel
before any other stage runs. Sentinels survive every later stage
untouched. Stage U restores them, strictly last.

Guards never *change* text; they *shield* it. Spec section 7 / 15.

Build reference: deterministic_correction_engine_spec.md v1.2.
"""
from __future__ import annotations

from backend.corrections import patterns as P

# Patterns whose matches are wrapped, in priority order. GUARD-05 (LC
# markers) is first — highest-priority, absolute protection.
_GUARD_PATTERNS = (
    ("GUARD-05", P.GUARD05_LC_MARKER_RE),
    ("GUARD-04", P.GUARD04_ELLIPSIS_RE),
    ("GUARD-03", P.GUARD03_FALSE_START_RE),
    ("GUARD-02", P.GUARD02_STUTTER_RE),
    ("GUARD-01", P.GUARD01_FILLER_RE),
)


class Vault:
    """Per-utterance store of guarded spans. ``guard`` fills it; ``unguard``
    drains it. One Vault is created per utterance and discarded after."""

    def __init__(self) -> None:
        self._spans: list[str] = []

    def stash(self, original: str) -> str:
        """Store ``original``, return its sentinel token."""
        idx = len(self._spans)
        self._spans.append(original)
        return f"{P.SENTINEL_OPEN}{idx}{P.SENTINEL_CLOSE}"

    def restore(self, token_index: int) -> str:
        return self._spans[token_index]

    def __len__(self) -> int:
        return len(self._spans)


def guard(text: str) -> tuple[str, Vault]:
    """Stage G. Replace every protected span with a sentinel.

    Returns ``(guarded_text, vault)``. The vault must be passed to
    ``unguard`` at the end of the pipeline for the same utterance.
    """
    vault = Vault()

    def _wrap(match) -> str:
        return vault.stash(match.group(0))

    guarded = text
    for _rule_id, pattern in _GUARD_PATTERNS:
        guarded = pattern.sub(_wrap, guarded)
    return guarded, vault


def unguard(text: str, vault: Vault) -> str:
    """Stage U. Restore every sentinel to its original literal text.

    Strictly last. After this, zero sentinels must remain — a leftover
    sentinel is a build error (verified by the pipeline self-check).
    """

    def _restore(match) -> str:
        return vault.restore(int(match.group(1)))

    return P.SENTINEL_RE.sub(_restore, text)


def has_sentinels(text: str) -> bool:
    """True if any unrestored sentinel remains. Pipeline asserts this is
    False after Stage U."""
    return P.SENTINEL_RE.search(text) is not None
