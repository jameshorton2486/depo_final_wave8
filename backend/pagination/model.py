"""Pagination model — Wave 19A.

The precise line-concept vocabulary from docs/wave19_ufm_layout.md:

    RenderLine    one semantic transcript line   (input, from Stage S)
    PhysicalLine  one physically printed line    (after wrapping)
    PageSlot      one numbered UFM line position 1..25 on a page
    Page          an assembled 25-slot page

One RenderLine may wrap into multiple PhysicalLines and therefore
occupy multiple PageSlots, possibly spanning a page boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field

LINES_PER_PAGE = 25          # UFM mandate: exactly 25 PageSlots per page


@dataclass
class PhysicalLine:
    """One physically printed line, after page-aware wrapping.

    A PhysicalLine carries its origin RenderLine id and tab level so
    the Geometry Layer can position it. `is_continuation` is True when
    this line is a wrap-continuation of a RenderLine (not its first
    physical line).
    """

    text: str
    tab_level: int
    line_type: str
    source_render_line_id: str
    is_continuation: bool = False        # wrap-continuation of a RenderLine
    procedural: bool = False

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "tab_level": self.tab_level,
            "line_type": self.line_type,
            "source_render_line_id": self.source_render_line_id,
            "is_continuation": self.is_continuation,
            "procedural": self.procedural,
        }


@dataclass
class PageSlot:
    """One numbered UFM line position (1..25) on a page.

    A slot holds at most one PhysicalLine. An empty slot (blank line)
    has physical_line = None but still occupies a numbered position.
    """

    slot_number: int                     # 1..LINES_PER_PAGE
    physical_line: PhysicalLine | None = None

    @property
    def is_empty(self) -> bool:
        return self.physical_line is None

    def to_dict(self) -> dict:
        return {
            "slot_number": self.slot_number,
            "physical_line": (self.physical_line.to_dict()
                              if self.physical_line else None),
        }


@dataclass
class ContinuationState:
    """Explicit record of a structure crossing a page boundary.

    Produced whenever a RenderLine's physical lines are split across a
    page break, so continuation is testable and deterministic rather
    than inferred.
    """

    render_line_id: str
    line_type: str
    from_page: int
    to_page: int

    def to_dict(self) -> dict:
        return {
            "render_line_id": self.render_line_id,
            "line_type": self.line_type,
            "from_page": self.from_page,
            "to_page": self.to_page,
        }


@dataclass
class Page:
    """One assembled page -- exactly LINES_PER_PAGE numbered slots."""

    page_number: int
    page_id: str
    slots: list[PageSlot] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "page_id": self.page_id,
            "slots": [s.to_dict() for s in self.slots],
        }


@dataclass
class PaginatedDocument:
    """The fully paginated transcript -- the Pagination Engine output."""

    pages: list[Page] = field(default_factory=list)
    continuations: list[ContinuationState] = field(default_factory=list)

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    def to_dict(self) -> dict:
        return {
            "pages": [p.to_dict() for p in self.pages],
            "continuations": [c.to_dict() for c in self.continuations],
            "total_pages": self.total_pages,
        }
