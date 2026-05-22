"""Transcript Flow Rules -- Wave 19A (BLOCKER-2 resolved per Texas UFM).

Flow control across page boundaries. The Texas UFM mandates EXACTLY 25
lines of text per page and PROHIBITS blank lines within the transcript
body. Standard word-processor orphan/widow control -- which holds
paragraphs together by leaving blank lines at the foot of a page --
therefore VIOLATES the UFM and is disabled here.

Consequences (James's BLOCKER-2 decision):
  * No orphan/widow blank-line control: every one of the 25 slots is
    filled; content flows continuously across page breaks.
  * Long answers, colloquy blocks, and multi-line parentheticals MUST
    be allowed to split across pages to keep the strict line count.
  * The ONE exception is the Q/A tether: a "Q." line may not be
    stranded at the foot of a page with its "A." beginning on the next
    page. That rule is enforced by the paginator via requires_qa_tether.
"""
from __future__ import annotations

from backend.pagination.model import PhysicalLine
from backend.stage_s.models import LINE_A, LINE_Q

# Minimum physical lines of a structure that must fit on the current
# page for it to START there. UFM: orphan/widow control is OFF, so any
# remaining slot is used -- a structure starts whenever >= 1 slot is
# free and simply continues onto the next page. (BLOCKER-2)
MIN_LINES_TO_START = 1

# Line types kept whole (never split) across a page boundary. The UFM
# requires colloquy and multi-line parentheticals to split for the
# 25-line count, so NOTHING is kept whole here. The only keep-together
# rule -- the Q/A tether -- is a pairing rule, handled separately by
# requires_qa_tether, not by holding a single structure whole.
# (BLOCKER-2)
KEEP_TOGETHER_TYPES = frozenset()

# Retained for API stability; with KEEP_TOGETHER_TYPES empty this is
# always 0-effect, but the constant is kept so callers do not break.
SHORT_STRUCTURE_MAX = 0


def must_keep_together(physical_lines: list[PhysicalLine]) -> bool:
    """True when a structure must not be split across a page boundary.

    Under the UFM (BLOCKER-2) no single structure is kept whole -- this
    always returns False. Retained so existing callers keep working.
    """
    if not physical_lines:
        return False
    return physical_lines[0].line_type in KEEP_TOGETHER_TYPES


def can_start_on_page(remaining_slots: int,
                       physical_lines: list[PhysicalLine]) -> bool:
    """True when a structure may begin in the remaining slots of the
    current page.

    With orphan/widow control disabled (UFM), a structure starts
    whenever at least one slot remains; it then flows onto the next
    page as needed.
    """
    if remaining_slots <= 0:
        return False
    if must_keep_together(physical_lines):
        return remaining_slots >= len(physical_lines)
    needed = min(MIN_LINES_TO_START, len(physical_lines))
    return remaining_slots >= needed


def requires_qa_tether(current_line_type: str,
                       next_line_type: str) -> bool:
    """True when `current` is a question immediately followed by its
    answer.

    The Q/A tether is the one UFM keep-together rule: the "Q." line and
    the START of its "A." must not be severed by a page break. The
    paginator uses this to decide whether to push a question to a fresh
    page so its answer can begin alongside it.
    """
    return current_line_type == LINE_Q and next_line_type == LINE_A
