"""Phase 1 pagination migration validation tests."""
from __future__ import annotations

from backend.pagination.validation import validate_formatted_stream
from backend.transcript.export_render import (
    _build_formatted_stream,
    render_export_with_layout,
)


def _working_lines() -> list[dict]:
    return [
        {
            "line_type": "Q",
            "speaker_label": "MR. VANCE",
            "text": "Please state your full name for the record and spell your last name.",
        },
        {
            "line_type": "A",
            "speaker_label": "DR. LEIFER",
            "text": "Donald Leifer, L-e-i-f-e-r.",
        },
        {
            "line_type": "colloquy",
            "speaker_label": "MS. ZAHN",
            "text": "Objection, form and foundation.",
        },
        {
            "line_type": "flagged",
            "speaker_label": "Speaker 7",
            "text": "Unmapped audio segment requiring review.",
        },
    ] * 18


def test_phase1_adapter_matches_authoritative_page_allocation():
    working = _working_lines()
    _, authoritative = render_export_with_layout(working)
    assert authoritative is not None

    stream = _build_formatted_stream(working)
    candidate, comparison = validate_formatted_stream(stream, authoritative)

    assert candidate.total_pages == authoritative.total_pages
    assert comparison.page_count_match is True
    assert comparison.page_break_match is True
    assert comparison.line_count_match is True
    assert comparison.line_number_match is True
    assert comparison.page_reference_match is True
    assert comparison.ok is True


def test_phase1_adapter_marks_continuations_as_not_comparable():
    working = _working_lines()
    _, authoritative = render_export_with_layout(working)
    assert authoritative is not None

    stream = _build_formatted_stream(working)
    _candidate, comparison = validate_formatted_stream(stream, authoritative)

    assert "semantic continuation parity not yet authoritative" in comparison.continuation_status
