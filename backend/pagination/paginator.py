"""The Pagination Engine — Wave 19A.

The primary engine of physical transcript production. Takes Stage S
RenderLines and produces a PaginatedDocument: an ordered list of Pages,
each with exactly 25 numbered PageSlots, plus explicit ContinuationState
records for every structure that crosses a page boundary.

Layout Determinism: the same input always paginates identically --
same page breaks, same slot numbers, same continuations. The engine is
pure; it holds no state between calls.

Page Composition Pipeline (docs/wave19_ufm_layout.md section 2):
    RenderLines -> WrappedLines -> PhysicalLines -> PageSlots -> Pages
"""
from __future__ import annotations

import uuid

from backend.pagination.flow_rules import can_start_on_page
from backend.pagination.model import (
    LINES_PER_PAGE,
    ContinuationState,
    Page,
    PageSlot,
    PaginatedDocument,
    PhysicalLine,
)
from backend.pagination.wrapping import DEFAULT_WRAP_WIDTH, wrap_render_line
from backend.stage_s.models import RenderLine


def _new_page(page_number: int) -> Page:
    """An empty page with LINES_PER_PAGE numbered, empty slots."""
    return Page(
        page_number=page_number,
        page_id=f"page-{page_number:04d}",
        slots=[PageSlot(slot_number=n)
               for n in range(1, LINES_PER_PAGE + 1)],
    )


def paginate(
    render_lines: list[RenderLine],
    wrap_width: int = DEFAULT_WRAP_WIDTH,
) -> PaginatedDocument:
    """Paginate Stage S render lines into a PaginatedDocument.

    Each RenderLine is wrapped into PhysicalLines, then those lines are
    placed into 25-slot pages. When a RenderLine's physical lines span
    a page boundary a ContinuationState is recorded. Flow rules decide
    whether a structure may start in the slots left on a page.
    """
    pages: list[Page] = []
    continuations: list[ContinuationState] = []

    current = _new_page(1)
    pages.append(current)
    next_slot = 0          # 0-based index into current.slots

    def _advance_page() -> None:
        nonlocal current, next_slot
        current = _new_page(len(pages) + 1)
        pages.append(current)
        next_slot = 0

    for rline in render_lines:
        physical = wrap_render_line(rline, wrap_width)
        if not physical:
            continue

        remaining = LINES_PER_PAGE - next_slot

        # Flow rules: may this structure start in the slots remaining?
        # If not, move wholly to a fresh page (orphan avoidance).
        if remaining > 0 and not can_start_on_page(remaining, physical):
            _advance_page()
            remaining = LINES_PER_PAGE

        # Place each physical line; cross a page boundary as needed and
        # record an explicit ContinuationState when one structure's
        # lines land on two pages.
        structure_start_page = current.page_number
        crossed = False
        for phys in physical:
            if next_slot >= LINES_PER_PAGE:
                _advance_page()
                crossed = True
            current.slots[next_slot].physical_line = phys
            next_slot += 1

        if crossed:
            continuations.append(ContinuationState(
                render_line_id=rline.line_id,
                line_type=rline.line_type,
                from_page=structure_start_page,
                to_page=current.page_number,
            ))

    return PaginatedDocument(pages=pages, continuations=continuations)


def paginated_to_render_check(doc: PaginatedDocument) -> dict:
    """Diagnostic: count placed physical lines and verify slot integrity.

    Returns a dict used by tests to assert no line loss and exact
    25-slot pages.
    """
    placed = 0
    for page in doc.pages:
        assert len(page.slots) == LINES_PER_PAGE
        placed += sum(1 for s in page.slots if not s.is_empty)
    return {"total_pages": doc.total_pages, "placed_lines": placed}
