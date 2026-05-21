"""Integration tests for POST /api/nod/parse.

These tests build a minimal in-memory PDF on the fly (via reportlab if
available, otherwise they skip) so no client documents are committed.
The parser logic itself is covered exhaustively in test_nod_parser.py;
these tests only verify the HTTP contract: status codes, error handling,
and response shape.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def _make_simple_pdf(text: str) -> bytes:
    """Build a tiny single-page PDF containing the given text."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed; skipping PDF integration test")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in text.split("\n"):
        c.drawString(72, y, line)
        y -= 14
    c.save()
    return buf.getvalue()


def test_nod_endpoint_rejects_non_pdf():
    res = client.post(
        "/api/nod/parse",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert res.status_code == 400
    assert "pdf" in res.json()["detail"].lower()


def test_nod_endpoint_rejects_empty_file():
    res = client.post(
        "/api/nod/parse",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert res.status_code == 400


def test_nod_endpoint_response_shape():
    pdf = _make_simple_pdf(
        "CAUSE NO. 2021CI17153\n"
        "DANIEL TREVINO\n"
        "Plaintiff,\n"
        "IN THE DISTRICT COURT\n"
        "VS. 225TH JUDICIAL DISTRICT\n"
        "YC PARTNERS LTD.\n"
        "Defendant. OF BEXAR COUNTY, TEXAS\n"
        "Date: Tuesday May 12, 2026\n"
        "Time: 3:00 p.m. (Central Time)\n"
    )
    res = client.post(
        "/api/nod/parse",
        files={"file": ("nod.pdf", pdf, "application/pdf")},
    )
    assert res.status_code == 200
    body = res.json()
    # Contract: three top-level keys
    assert "fields" in body
    assert "metadata" in body
    assert "keyterms" in body
    # Fields dict has all 16 UFM keys
    assert "ufmCause" in body["fields"]
    assert "ufmWitness" in body["fields"]
    # Metadata structure
    assert "jurisdiction_type" in body["metadata"]
    assert "detected_types" in body["metadata"]
    assert isinstance(body["keyterms"], list)


def test_nod_endpoint_extracts_cause_number():
    pdf = _make_simple_pdf(
        "CAUSE NO. 2021CI17153\n"
        "DANIEL TREVINO\n"
        "Plaintiff,\n"
        "VS. 225TH JUDICIAL DISTRICT\n"
        "YC PARTNERS LTD.\n"
        "Defendant. OF BEXAR COUNTY, TEXAS\n"
    )
    res = client.post(
        "/api/nod/parse",
        files={"file": ("nod.pdf", pdf, "application/pdf")},
    )
    assert res.status_code == 200
    assert res.json()["fields"]["ufmCause"] == "2021CI17153"
