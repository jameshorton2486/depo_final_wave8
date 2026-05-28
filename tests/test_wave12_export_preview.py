"""Wave 12 tests — canonical export renderer and export-preview endpoints."""
from __future__ import annotations

from backend.transcript.export_render import (
    LINES_PER_PAGE,
    render_export_document,
)


def _working_lines(n=4):
    base = [
        {"line_type": "Q", "speaker_label": "MR. VANCE",
         "text": "Please state your full name for the record."},
        {"line_type": "A", "speaker_label": "DR. LEIFER",
         "text": "Dr. Donald Leifer, neurosurgeon."},
        {"line_type": "colloquy", "speaker_label": "MS. ZAHN",
         "text": "Objection, form."},
        {"line_type": "flagged", "speaker_label": "Speaker 7",
         "text": "Unmapped audio segment."},
    ]
    return base[:n]


# --- renderer --------------------------------------------------------

def test_render_produces_pages():
    doc = render_export_document(_working_lines())
    assert doc.total_pages >= 1
    assert len(doc.pages) == doc.total_pages


def test_render_paginates_at_25_lines():
    # Many utterances must overflow onto multiple pages.
    many = [{"line_type": "Q", "speaker_label": "MR. VANCE",
             "text": f"Question number {i}."} for i in range(60)]
    doc = render_export_document(many)
    assert doc.total_pages > 1
    for page in doc.pages:
        assert len(page.lines) == LINES_PER_PAGE


def test_render_line_numbers_reset_each_page():
    many = [{"line_type": "Q", "speaker_label": "MR. VANCE",
             "text": f"Q {i}."} for i in range(60)]
    doc = render_export_document(many)
    for page in doc.pages:
        assert page.lines[0].line_number == 1
        assert page.lines[-1].line_number == LINES_PER_PAGE


def test_render_qa_prefixes():
    doc = render_export_document(_working_lines(2))
    texts = [l.text for p in doc.pages for l in p.lines]
    assert any("Q.  Please state" in t for t in texts)
    assert any("A.  Dr. Donald Leifer" in t for t in texts)


def test_render_colloquy_has_speaker_label():
    doc = render_export_document([_working_lines()[2]])
    texts = [l.text for p in doc.pages for l in p.lines]
    assert any(t.startswith("MS. ZAHN:") for t in texts)


def test_render_flagged_line_kind_preserved():
    doc = render_export_document([_working_lines()[3]])
    kinds = [l.line_kind for p in doc.pages for l in p.lines]
    assert "flagged" in kinds


def test_render_no_word_loss():
    # Every word of input text must survive into the rendered output.
    wl = [{"line_type": "Q", "speaker_label": "MR. VANCE",
           "text": "alpha bravo charlie delta echo foxtrot golf hotel"}]
    doc = render_export_document(wl)
    joined = " ".join(l.text for p in doc.pages for l in p.lines)
    for word in ["alpha", "bravo", "charlie", "delta",
                 "echo", "foxtrot", "golf", "hotel"]:
        assert word in joined


def test_render_is_deterministic():
    a = render_export_document(_working_lines()).to_dict()
    b = render_export_document(_working_lines()).to_dict()
    assert a == b


def test_render_front_matter_excludes_ritual():
    # The opening ritual (EXAMINATION header, BY-line) and the witness-sworn
    # line are owned by backend/stage_s/ and arrive via working_lines -- so
    # export_render no longer emits them from the witness / examiner params.
    # Front matter is limited to the caption metadata and the PROCEEDINGS
    # date header. Critically, NO "(...) duly sworn" line is auto-asserted
    # from a witness name (that assertion is now gated in stage_s).
    doc = render_export_document(
        _working_lines(2),  # plain Q/A only -- no stage_s ritual lines supplied
        caption="SMITH vs. JONES",
        witness="Dr. Donald Leifer",
        proceedings_date="Tuesday, May 19, 2026",
        examining_attorney_label="MR. VANCE",
    )
    assert doc.caption == "SMITH vs. JONES"
    texts = [l.text for p in doc.pages for l in p.lines]
    assert any("PROCEEDINGS" in t for t in texts)
    # Front matter must NOT auto-emit the ritual or the sworn line:
    assert not any("EXAMINATION BY MR. VANCE" in t for t in texts)
    assert not any("sworn" in t.lower() for t in texts)


def test_render_empty_transcript_is_safe():
    doc = render_export_document([])
    assert doc.total_pages >= 0
    assert isinstance(doc.pages, list)


def test_render_approximate_flag():
    doc = render_export_document(_working_lines(), is_approximate=True)
    assert doc.is_approximate is True


# --- endpoints -------------------------------------------------------

def test_export_preview_rejects_unknown_job(client):
    res = client.get("/api/transcripts/jobs/no-such-job/export-preview")
    assert res.status_code == 404


def test_export_preview_fallback_renders(client):
    res = client.post("/api/transcripts/export-preview/fallback", json={
        "lines": [
            {"line_type": "Q", "speaker_label": "MR. VANCE",
             "text": "State your name."},
            {"line_type": "A", "speaker_label": "DR. LEIFER",
             "text": "Donald Leifer."},
        ],
        "caption": "SMITH vs. JONES",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["is_approximate"] is True
    assert body["caption"] == "SMITH vs. JONES"
    assert body["total_pages"] >= 1


def test_export_preview_fallback_empty_is_safe(client):
    res = client.post("/api/transcripts/export-preview/fallback",
                       json={"lines": []})
    assert res.status_code == 200
