"""Phase 1 tests: deposition_metadata persistence layer (schema_v9)."""
from __future__ import annotations

import json

import pytest

from backend.db.depo_meta_repo import get_depo_meta, upsert_depo_meta
from backend.transcript import repository as trepo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(client) -> str:
    job = trepo.create_job({"source_filename": "test.mp3"})
    return job["job_id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_get_missing_returns_none(temp_db):
    result = get_depo_meta("no-such-job")
    assert result is None


def test_upsert_creates_row(temp_db, client):
    job_id = _make_job(client)
    row = upsert_depo_meta(job_id, {
        "volume": "2",
        "examination_disposition": "waived",
    })
    assert row["job_id"] == job_id
    assert row["volume"] == "2"
    assert row["examination_disposition"] == "waived"
    assert row["officer_charges_amount"] is None


def test_upsert_updates_existing(temp_db, client):
    job_id = _make_job(client)
    upsert_depo_meta(job_id, {"volume": "1", "charges_party": "Plaintiff"})
    updated = upsert_depo_meta(job_id, {"charges_party": "Defendant"})
    assert updated["charges_party"] == "Defendant"
    assert updated["volume"] == "1"   # unchanged


def test_get_returns_created_row(temp_db, client):
    job_id = _make_job(client)
    upsert_depo_meta(job_id, {
        "officer_charges_amount": "525.00",
        "certificate_service_date": "June 1, 2026",
    })
    row = get_depo_meta(job_id)
    assert row is not None
    assert row["officer_charges_amount"] == "525.00"
    assert row["certificate_service_date"] == "June 1, 2026"


def test_time_per_party_json_roundtrip(temp_db, client):
    job_id = _make_job(client)
    tpp = [{"party": "Plaintiff", "duration": "1:45"}, {"party": "Defendant", "duration": "0:30"}]
    upsert_depo_meta(job_id, {"time_per_party_json": json.dumps(tpp)})
    row = get_depo_meta(job_id)
    stored = json.loads(row["time_per_party_json"])
    assert stored == tpp


def test_also_present_json_roundtrip(temp_db, client):
    job_id = _make_job(client)
    ap = [{"name": "Dr. Smith", "role": "Expert Witness"}]
    upsert_depo_meta(job_id, {"also_present_json": json.dumps(ap)})
    row = get_depo_meta(job_id)
    assert json.loads(row["also_present_json"]) == ap


def test_unknown_keys_ignored(temp_db, client):
    job_id = _make_job(client)
    row = upsert_depo_meta(job_id, {"bogus_field": "should be ignored", "volume": "3"})
    assert row["volume"] == "3"


def test_empty_upsert_creates_defaults(temp_db, client):
    job_id = _make_job(client)
    row = upsert_depo_meta(job_id, {})
    assert row["job_id"] == job_id
    assert row["volume"] == "1"
    assert row["examination_disposition"] is None
