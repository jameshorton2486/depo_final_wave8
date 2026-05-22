"""Transcript Flow Rules — Wave 19A.

Flow control: more than widow/orphan logic. Certain transcript
structures have constraints on how they may cross a page boundary.

These are CONSERVATIVE DEFAULTS, marked for James's confirmation
(plan Q19-5). They are data-driven so precise UFM rules can replace
them without touching the paginator.
"""
from __future__ import annotations

from backend.pagination.model import PhysicalLine
from backend.stage_s.models import (
    LINE_COLLOQUY,
    LINE_PARENTHETICAL,
)

# Minimum physical lines of a structure that must fit on the current
# page for it to START there. If fewer than this many slots remain,
# the structure moves wholly to the next page (orphan avoidance).
# NEEDS_JAMES_CONFIRMATION (Q19-5).
MIN_LINES_TO_START = 2

# Line types that should never be split across a page boundary at all
# when they are short. NEEDS_JAMES_CONFIRMATION (Q19-5).
KEEP_TOGETHER_TYPES = frozenset({LINE_PARENTHETICAL})

# A "short" structure for keep-together purposes: this many physical
# lines or fewer. NEEDS_JAMES_CONFIRMATION (Q19-5).
SHORT_STRUCTURE_MAX = 3


def must_keep_together(physical_lines: list[PhysicalLine]) -> bool:
    """True when this group of physical lines (one RenderLine's wrap)
    must not be split across a page boundary."""
    if not physical_lines:
        return False
    if len(physical_lines) > SHORT_STRUCTURE_MAX:
        return False        # too long to keep whole; it must be allowed to split
    line_type = physical_lines[0].line_type
    return line_type in KEEP_TOGETHER_TYPES


def can_start_on_page(remaining_slots: int,
                       physical_lines: list[PhysicalLine]) -> bool:
    """True when a structure may begin in the remaining slots of the
    current page (orphan avoidance).

    A keep-together structure may start only if it fits whole. Any
    other structure needs at least MIN_LINES_TO_START slots.
    """
    if remaining_slots <= 0:
        return False
    if must_keep_together(physical_lines):
        return remaining_slots >= len(physical_lines)
    needed = min(MIN_LINES_TO_START, len(physical_lines))
    return remaining_slots >= needed
