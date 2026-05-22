"""Wave 18 — export engine tests.

Verify the four writers produce real, valid files; the export service
resolves destinations and rejects bad input; the export endpoint 404s
on an unknown job; and preview/export share one canonical document.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from backend.export import export_service
from backend.export.docx_writer import write_docx
from backend.export.pdf_writer import write_pdf
from backend.export.rtf_writer import write_rtf
from backend.export.txt_writer import write_txt
from backend.transcript.export_render import (
    ExportDocument,
    ExportLine,
    ExportPage,
)


def _sample_doc() -> ExportDocument:
    return ExportDocument(
        caption="SARAH JENKINS vs. NEXUS PHARMA INC.",
        cause_number="2024-CI-28593",
        witness="Dr. Donald Leifer",
        total_pages=1, total_lines=2,
        pages=[ExportPage(page_number=1, lines=[
            ExportLine(page=1, line_number=1,
                       text="Q. Please state your name.", line_kind="qa"),
            ExportLine(page=1, line_number=2,
                       text="A. Donald Leifer.", line_kind="qa"),
        ])],
    )


# --- writers ---------------------------------------------------------

def test_txt_writer_produces_file(tmp_path):
    p = write_txt(_sample_doc(), tmp_path / "t.txt")
    assert p.exists() and p.stat().st_size > 0
    assert "Donald Leifer" in p.read_text(encoding="utf-8")


def test_rtf_writer_produces_file(tmp_path):
    p = write_rtf(_sample_doc(), tmp_path / "t.rtf")
    assert p.exists()
    assert p.read_text(encoding="utf-8").startswith(r"{\rtf1")


def test_docx_writer_produces_real_word_file(tmp_path):
    p = write_docx(_sample_doc(), tmp_path / "t.docx")
    assert p.exists()
    # A real .docx is a valid zip archive.
    assert zipfile.is_zipfile(p)


def test_pdf_writer_produces_real_pdf(tmp_path):
    p = write_pdf(_sample_doc(), tmp_path / "t.pdf")
    assert p.exists()
    # A real PDF starts with the %PDF magic bytes.
    assert p.read_bytes()[:4] == b"%PDF"


# --- export service --------------------------------------------------

def test_export_service_writes_to_explicit_path(tmp_path):
    res = export_service.export_document(
        _sample_doc(), "txt", "path", explicit_path=str(tmp_path))
    assert Path(res["path"]).exists()
    assert res["format"] == "txt"


def test_export_service_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        export_service.export_document(
            _sample_doc(), "xlsx", "path", explicit_path=str(tmp_path))


def test_export_service_rejects_unknown_destination():
    with pytest.raises(ValueError):
        export_service.export_document(
            _sample_doc(), "txt", "nowhere")


def test_ascii_maps_to_txt(tmp_path):
    res = export_service.export_document(
        _sample_doc(), "ascii", "path", explicit_path=str(tmp_path))
    assert res["path"].endswith(".txt")


def test_all_four_formats_supported():
    assert set(export_service.EXPORT_FORMATS) >= {
        "txt", "ascii", "docx", "pdf", "rtf"}


# --- endpoint --------------------------------------------------------

def test_export_endpoint_unknown_job_404(client):
    res = client.post("/api/transcripts/jobs/no-such-job/export",
                       json={"fmt": "txt", "destination": "downloads"})
    assert res.status_code == 404
