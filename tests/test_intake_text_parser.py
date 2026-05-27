"""Tests for the intake text parser (Stage 1 'Run Text Parser on Pasted Notes')."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from backend.services.intake_text_parser import (
    _normalize_date,
    _normalize_time,
    parse_intake_text,
)

client = TestClient(app)

SAMPLE_NOTES = """\
Deposition location: Lexitas Fort Worth, 201 Main Street, Suite 600, Fort Worth, Texas 76102.
Court Reporter: Richard Vance, CSR License 3465, expiration 2027-12-31, Firm Registration 10698.
Custodial Attorney: Ms. Elizabeth R. Flora, Esq. representing Plaintiff sarah jenkins.
Cause No: 2024-CI-28593
Deponent: Dr. Donald Leifer
Date: 5/19/2026
Start Time: 10:00 a.m.
Acoustic spellings to sync: Acoustic Neuroma, cranial, Leifer."""


# --- date / time normalization --------------------------------------

def test_normalize_date_iso():
    assert _normalize_date("2027-12-31") == "2027-12-31"


def test_normalize_date_slash():
    assert _normalize_date("5/19/2026") == "2026-05-19"


def test_normalize_date_two_digit_year():
    assert _normalize_date("5/19/26") == "2026-05-19"


def test_normalize_date_month_name():
    assert _normalize_date("May 19, 2026") == "2026-05-19"


def test_normalize_date_invalid():
    assert _normalize_date("not a date") is None


def test_normalize_time_with_minutes():
    assert _normalize_time("10:00 a.m.") == "10:00 AM"


def test_normalize_time_hour_only():
    assert _normalize_time("3 p.m.") == "3:00 PM"


# --- field extraction ------------------------------------------------

def test_extracts_address():
    result = parse_intake_text(SAMPLE_NOTES)
    assert "Lexitas Fort Worth" in result["fields"]["ufmAddress"]


def test_extracts_csr_name():
    result = parse_intake_text(SAMPLE_NOTES)
    assert result["fields"]["ufmCSRName"] == "Richard Vance"


def test_extracts_csr_license():
    result = parse_intake_text(SAMPLE_NOTES)
    assert result["fields"]["ufmCSRLicense"] == "3465"


def test_extracts_firm_registration():
    result = parse_intake_text(SAMPLE_NOTES)
    assert result["fields"]["ufmFirmReg"] == "10698"


def test_extracts_csr_expiration_as_iso():
    result = parse_intake_text(SAMPLE_NOTES)
    assert result["fields"]["ufmCSRCertExp"] == "2027-12-31"


def test_extracts_custodial_attorney_without_representing_clause():
    result = parse_intake_text(SAMPLE_NOTES)
    # 'representing Plaintiff ...' must NOT be part of the attorney name
    assert result["fields"]["ufmCustodialName"] == "Ms. Elizabeth R. Flora, Esq."


def test_extracts_cause_number():
    result = parse_intake_text(SAMPLE_NOTES)
    assert result["fields"]["ufmCause"] == "2024-CI-28593"


def test_extracts_witness():
    result = parse_intake_text(SAMPLE_NOTES)
    assert result["fields"]["ufmWitness"] == "Dr. Donald Leifer"


def test_extracts_and_normalizes_date():
    result = parse_intake_text(SAMPLE_NOTES)
    assert result["fields"]["ufmDate"] == "2026-05-19"


def test_extracts_and_normalizes_start_time():
    result = parse_intake_text(SAMPLE_NOTES)
    assert result["fields"]["ufmStartTime"] == "10:00 AM"


# --- keyterms --------------------------------------------------------

def test_explicit_acoustic_spellings_become_keyterms():
    result = parse_intake_text(SAMPLE_NOTES)
    terms = {kt["term"] for kt in result["keyterms"]}
    assert "Acoustic Neuroma" in terms
    assert "Leifer" in terms


def test_csr_name_becomes_reporter_keyterm():
    result = parse_intake_text(SAMPLE_NOTES)
    reporter_terms = [kt for kt in result["keyterms"] if kt["category"] == "Reporter"]
    assert any(kt["term"] == "Richard Vance" for kt in reporter_terms)


def test_represented_party_becomes_keyterm():
    result = parse_intake_text(SAMPLE_NOTES)
    # 'sarah jenkins' should be title-cased and present as a Party keyterm
    terms = {kt["term"] for kt in result["keyterms"]}
    assert "Sarah Jenkins" in terms


# --- edge cases ------------------------------------------------------

def test_empty_text_returns_warning():
    result = parse_intake_text("")
    assert result["fields"] == {}
    assert result["metadata"]["warnings"]


def test_unrecognized_text_returns_warning():
    result = parse_intake_text("just some rambling with no labels at all")
    assert result["metadata"]["warnings"]


# --- API endpoint ----------------------------------------------------

def test_endpoint_parses_notes():
    res = client.post("/api/intake/parse-text", json={"text": SAMPLE_NOTES})
    assert res.status_code == 200
    body = res.json()
    assert body["fields"]["ufmCause"] == "2024-CI-28593"
    assert "keyterms" in body
    assert "metadata" in body


def test_endpoint_empty_text():
    res = client.post("/api/intake/parse-text", json={"text": ""})
    assert res.status_code == 200
    assert res.json()["metadata"]["warnings"]


def test_endpoint_rejects_oversized_text():
    res = client.post("/api/intake/parse-text", json={"text": "x" * 60_000})
    assert res.status_code == 413


# --- field_sources emission (Stage 1 operator transparency) ----------

def test_text_parser_emits_field_sources_for_populated_fields():
    result = parse_intake_text(SAMPLE_NOTES)
    sources = result["metadata"]["field_sources"]
    # Every populated field must be tagged with text_parser.
    for field_id, value in result["fields"].items():
        if value:
            assert sources.get(field_id) == "text_parser", field_id


def test_text_parser_omits_field_sources_for_empty_input():
    result = parse_intake_text("")
    assert result["metadata"]["field_sources"] == {}
