"""Validation-only pagination adapter for Phase 1 migration work.

This module does NOT change runtime pagination authority. It adapts the
live export renderer's already-formatted `(text, kind)` stream into
synthetic RenderLines, runs `backend.pagination.paginate()` against
that adapted input, and compares the resulting PaginatedDocument to the
authoritative export-render PaginatedDocument.

Because the adapter starts from a pre-wrapped stream, it can validate
page allocation and page-reference parity, but it cannot yet prove full
semantic continuation behavior such as Q/A tethering. That remains a
later migration phase after the runtime authority cutover work.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.pagination.model import PaginatedDocument
from backend.pagination.paginator import paginate
from backend.stage_s.models import RenderLine


@dataclass
class PaginationValidationResult:
    """Structured comparison between runtime and candidate pagination."""

    adapted_render_lines: int
    authoritative_total_pages: int
    candidate_total_pages: int
    authoritative_line_count: int
    candidate_line_count: int
    page_count_match: bool
    page_break_match: bool
    line_count_match: bool
    line_number_match: bool
    page_reference_match: bool
    continuation_status: str
    differences: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.differences

    def to_dict(self) -> dict:
        return {
            "adapted_render_lines": self.adapted_render_lines,
            "authoritative_total_pages": self.authoritative_total_pages,
            "candidate_total_pages": self.candidate_total_pages,
            "authoritative_line_count": self.authoritative_line_count,
            "candidate_line_count": self.candidate_line_count,
            "page_count_match": self.page_count_match,
            "page_break_match": self.page_break_match,
            "line_count_match": self.line_count_match,
            "line_number_match": self.line_number_match,
            "page_reference_match": self.page_reference_match,
            "continuation_status": self.continuation_status,
            "differences": list(self.differences),
            "ok": self.ok,
        }


def adapt_formatted_stream(
    stream: list[tuple[str, str]],
) -> tuple[list[RenderLine], int]:
    """Convert a formatted `(text, kind)` stream into synthetic RenderLines.

    The adapter preserves the existing one-stream-entry -> one-physical-line
    runtime contract by setting the wrap width to the longest line in the
    current stream. This makes the candidate paginator validate page-slot
    allocation without rewriting the export renderer's live formatting path.
    """

    render_lines: list[RenderLine] = []
    max_width = 1
    for idx, (text, kind) in enumerate(stream):
        max_width = max(max_width, len(text or ""))
        render_lines.append(
            RenderLine(
                line_id=f"export-{idx}",
                line_type=kind,
                text=text,
                tab_level=0,
                procedural=(kind == "blank"),
            )
        )
    return render_lines, max_width


def _line_count(doc: PaginatedDocument) -> int:
    return sum(
        1
        for page in doc.pages
        for slot in page.slots
        if slot.physical_line is not None
    )


def _page_reference_map(doc: PaginatedDocument) -> dict[str, tuple[int, int]]:
    refs: dict[str, tuple[int, int]] = {}
    for page in doc.pages:
        for slot in page.slots:
            if slot.physical_line is None:
                continue
            refs[slot.physical_line.source_render_line_id] = (
                page.page_number,
                slot.slot_number,
            )
    return refs


def compare_paginated_documents(
    authoritative: PaginatedDocument,
    candidate: PaginatedDocument,
    *,
    adapted_render_lines: int,
) -> PaginationValidationResult:
    """Compare two PaginatedDocuments for Phase 1 parity checks."""

    auth_refs = _page_reference_map(authoritative)
    cand_refs = _page_reference_map(candidate)
    auth_breaks = {line_id: page for line_id, (page, _slot) in auth_refs.items()}
    cand_breaks = {line_id: page for line_id, (page, _slot) in cand_refs.items()}
    auth_slots = {line_id: slot for line_id, (_page, slot) in auth_refs.items()}
    cand_slots = {line_id: slot for line_id, (_page, slot) in cand_refs.items()}

    page_count_match = authoritative.total_pages == candidate.total_pages
    line_count_match = _line_count(authoritative) == _line_count(candidate)
    page_break_match = auth_breaks == cand_breaks
    line_number_match = auth_slots == cand_slots
    page_reference_match = auth_refs == cand_refs

    differences: list[str] = []
    if not page_count_match:
        differences.append(
            f"page_count: authoritative={authoritative.total_pages} "
            f"candidate={candidate.total_pages}"
        )
    if not line_count_match:
        differences.append(
            f"line_count: authoritative={_line_count(authoritative)} "
            f"candidate={_line_count(candidate)}"
        )
    if not page_break_match:
        differences.append("page_breaks: page assignments differ by source line id")
    if not line_number_match:
        differences.append("line_numbers: slot assignments differ by source line id")
    if not page_reference_match:
        differences.append("page_references: (page, slot) references differ")

    continuation_status = "NOT_COMPARABLE_PREWRAPPED_STREAM"
    if authoritative.continuations or candidate.continuations:
        continuation_status = (
            f"authoritative={len(authoritative.continuations)} "
            f"candidate={len(candidate.continuations)} "
            "(semantic continuation parity not yet authoritative in Phase 1 adapter)"
        )

    return PaginationValidationResult(
        adapted_render_lines=adapted_render_lines,
        authoritative_total_pages=authoritative.total_pages,
        candidate_total_pages=candidate.total_pages,
        authoritative_line_count=_line_count(authoritative),
        candidate_line_count=_line_count(candidate),
        page_count_match=page_count_match,
        page_break_match=page_break_match,
        line_count_match=line_count_match,
        line_number_match=line_number_match,
        page_reference_match=page_reference_match,
        continuation_status=continuation_status,
        differences=differences,
    )


def validate_formatted_stream(
    stream: list[tuple[str, str]],
    authoritative: PaginatedDocument,
) -> tuple[PaginatedDocument, PaginationValidationResult]:
    """Run backend.pagination against the adapted stream and compare outputs."""

    render_lines, wrap_width = adapt_formatted_stream(stream)
    candidate = paginate(render_lines, wrap_width=wrap_width)
    comparison = compare_paginated_documents(
        authoritative,
        candidate,
        adapted_render_lines=len(render_lines),
    )
    return candidate, comparison
