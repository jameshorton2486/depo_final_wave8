from __future__ import annotations

from pathlib import Path

from backend.pagination.legal_validation import (
    _authoritative_paginate_stage_s,
    _build_categories,
    _compare_reference_artifact,
    _stage_s_to_working_lines,
    validate_legal_page_map,
)
from backend.stage_s.models import OFF_RECORD, ON_RECORD, RenderLine
from backend.stage_s.renderer import StageSResult


def _stage_s_fixture() -> StageSResult:
    return StageSResult(
        lines=[
            RenderLine(
                line_id="s-1",
                line_type="Q",
                text="Please state your name for the record.",
                speaker_label="MR. VANCE",
                render_state=ON_RECORD,
            ),
            RenderLine(
                line_id="s-2",
                line_type="A",
                text="My name is Dana Reed and I object to nothing here." + " extra" * 45,
                speaker_label="DANA REED",
                render_state=ON_RECORD,
            ),
            RenderLine(
                line_id="s-3",
                line_type="colloquy",
                text="Objection, form and foundation.",
                speaker_label="MS. ZAHN",
                render_state=ON_RECORD,
            ),
            RenderLine(
                line_id="s-4",
                line_type="parenthetical",
                text="(Exhibit 7 was marked for identification.)",
                procedural=True,
                render_state=ON_RECORD,
            ),
            RenderLine(
                line_id="s-5",
                line_type="colloquy",
                text="This off-record remark should not export.",
                speaker_label="REPORTER",
                render_state=OFF_RECORD,
                procedural=False,
            ),
        ]
    )


def test_stage_s_mapping_matches_live_export_suppression_rules():
    working, source_lines = _stage_s_to_working_lines(_stage_s_fixture())
    assert [ln.line_id for ln in source_lines] == ["s-1", "s-2", "s-3", "s-4"]
    assert [item["line_type"] for item in working] == ["Q", "A", "colloquy", "colloquy"]


def test_category_builder_counts_legal_stress_groups():
    working, source_lines = _stage_s_to_working_lines(_stage_s_fixture())
    categories = _build_categories(source_lines)
    assert categories["long_answers"] == {"s-2"}
    assert categories["colloquy"] == {"s-3"}
    assert categories["objections"] == {"s-3"}
    assert categories["exhibit_discussions"] == {"s-4"}
    assert categories["parentheticals"] == {"s-4"}


def test_authoritative_pagination_preserves_first_reference_per_logical_line():
    working, source_lines = _stage_s_to_working_lines(_stage_s_fixture())
    doc, refs = _authoritative_paginate_stage_s(source_lines, working)
    assert doc.total_pages >= 1
    assert refs["s-1"] == (1, 1)
    assert refs["s-2"][0] == 1
    assert refs["s-4"][0] >= refs["s-3"][0]


def test_reference_artifact_comparison_reads_pdf_page_counts(tmp_path: Path):
    from reportlab.pdfgen import canvas

    pdf_path = tmp_path / "reference.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(72, 720, "Page one")
    c.showPage()
    c.drawString(72, 720, "Page two")
    c.save()

    result = _compare_reference_artifact(str(pdf_path), live_pages=3, semantic_pages=2)
    assert result.available is True
    assert result.reference_pages == 2
    assert result.live_page_delta == 1
    assert result.semantic_page_delta == 0


def test_validate_legal_page_map_runs_on_real_render_fixture(temp_db, sample_job_with_content):
    result = validate_legal_page_map(job_id=sample_job_with_content)
    assert result.job_id == sample_job_with_content
    assert result.logical_lines > 0
    assert result.live_pages >= 1
    assert result.semantic_pages >= 1
    assert "long_answers" in result.categories
    assert result.reference_artifact.available is False
    assert any("no independent certified pdf" in note.lower() for note in result.notes)
