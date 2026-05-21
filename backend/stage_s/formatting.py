"""Stage S formatting helpers.

Pure string helpers shared across the Stage S handlers. Geometry
(twips, points, colour) is deliberately NOT here -- that belongs to the
export layer. These helpers only touch semantic text content.
"""
from __future__ import annotations


def normalize_ws(text: str) -> str:
    """Collapse internal whitespace runs to single spaces; strip ends.

    Does not touch words -- only whitespace. Safe under the verbatim
    mandate (whitespace is not spoken content).
    """
    return " ".join((text or "").split())


def is_blank(text: str) -> bool:
    return not (text or "").strip()
