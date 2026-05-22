"""Shared pytest fixtures for the DEPO-PRO test suite.

The fixtures here redirect the SQLite database to a temp file so the
test runs do not touch the developer's real data/sqlite/depo_pro.db.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.db import migrations, seeds


@pytest.fixture(autouse=True)
def _force_offline_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the test suite to run against the OFFLINE providers.

    The transcript-pipeline tests use a tiny synthetic audio file. With a
    real DEEPGRAM_API_KEY set in the developer's .env, that fake file is
    sent to the live Deepgram API, which correctly rejects it (HTTP 400
    'corrupt or unsupported data') -- making ~6 tests fail for a reason
    unrelated to the code under test.

    This autouse fixture removes the provider keys from the environment
    for every test, so transcription always uses the deterministic
    offline fallback and the AI review layer is always inert. Test
    outcomes no longer depend on whether a key happens to be set.

    A test that specifically needs a key present can still set one with
    its own monkeypatch.setenv -- that runs after this fixture.
    """
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture()
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the app's database to a temp file, apply schema, seed."""
    db_path = tmp_path / "depo_pro_test.db"
    sqlite_root = tmp_path

    # Patch the frozen Settings dataclass via monkeypatch.setattr
    monkeypatch.setattr(settings, "database_path", db_path, raising=False)
    monkeypatch.setattr(settings, "sqlite_root", sqlite_root, raising=False)
    monkeypatch.setattr(settings, "data_root", tmp_path, raising=False)

    # migrations.py captured DB_PATH at import time; override it directly
    monkeypatch.setattr(migrations, "DB_PATH", db_path, raising=False)

    # Apply schema + seeds against the fresh temp db
    migrations.apply()
    seeds.seed()

    return db_path


@pytest.fixture()
def client(temp_db: Path) -> TestClient:
    """FastAPI TestClient pointing at the temp DB. Runs lifespan, so /api/health and the routers are ready."""
    # Import inside fixture so the temp_db monkeypatch is already in place
    # before app.py touches settings.database_path during lifespan.
    from backend.app import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sample_case_payload() -> dict:
    return {
        "case_number_value": "2024-CI-28593",
        "caption_full": "SARAH JENKINS vs. NEXUS PHARMA INC.",
        "judicial_district": "101st Judicial District",
        "county": "Dallas County",
        "state": "Texas",
    }


@pytest.fixture()
def sample_session_payload() -> dict:
    return {
        "case_id": "<filled in by test>",
        "scheduled_at": "2026-05-19T10:00:00-05:00",
        "scheduled_end_at": "2026-05-19T12:30:00-05:00",
        "witness_name": "Dr. Donald Leifer",
        "location_address": "201 Main Street, Fort Worth, TX 76102",
        "custodial_attorney_name": "Ms. Elizabeth R. Flora, Esq.",
        "requesting_party_name": "Vance & Partners LLP",
    }


@pytest.fixture()
def sample_reporter_payload() -> dict:
    return {
        "full_name": "Richard Vance, CSR",
        "csr_number": "3465",
        "csr_expiration": "2027-12-31",
        "firm_registration_number": "10698",
    }


@pytest.fixture()
def created_case(client, sample_case_payload) -> dict:
    """Create a case and return its dict."""
    res = client.post("/api/cases", json=sample_case_payload)
    assert res.status_code == 201
    return res.json()


@pytest.fixture()
def sample_job(client) -> str:
    """Create a minimal transcript job and return its job_id.

    Used by packaging API tests that need a real job to exist in the DB.
    The job has no utterances/participants (empty transcript) so packaging
    will produce a zero-body-page package, which is valid for API tests.
    """
    from backend.transcript import repository as trepo
    job = trepo.create_job({"source_filename": "test_session.mp3"})
    return job["job_id"]


@pytest.fixture()
def sample_job_with_content(client) -> str:
    """Create a transcript job with real utterances and participants.

    Unlike `sample_job` (empty), this job has a short Q&A body, so the
    Packaging Engine produces body pages and the full
    assemble -> certify path can be exercised end-to-end (BLOCKER-4).
    """
    from backend.transcript import repository as trepo
    job = trepo.create_job({"source_filename": "depo_session.mp3"})
    job_id = job["job_id"]

    speakers = [
        {"speaker_row_id": "spk-0", "speaker_index": 0,
         "speaker_label": "Speaker 0", "assigned_name": "Mr. Vance",
         "speaker_role": "examining_attorney", "word_count": 24},
        {"speaker_row_id": "spk-1", "speaker_index": 1,
         "speaker_label": "Speaker 1", "assigned_name": "Dana Reed",
         "speaker_role": "witness", "word_count": 30},
    ]
    exchange = [
        (0, 0, "Speaker 0", "Please state your name for the record."),
        (1, 1, "Speaker 1", "My name is Dana Reed."),
        (2, 0, "Speaker 0", "And where do you currently reside?"),
        (3, 1, "Speaker 1", "I live in San Antonio, Texas."),
        (4, 0, "Speaker 0", "Were you working on the afternoon in question?"),
        (5, 1, "Speaker 1", "Yes, I was on duty that entire afternoon."),
    ]
    utterances = [
        {"utterance_id": f"utt-{i}", "utterance_index": i,
         "speaker_index": spk, "speaker_label": label,
         "start_time": float(i * 5), "end_time": float(i * 5 + 4),
         "text": text, "avg_confidence": 0.99}
        for (i, spk, label, text) in exchange
    ]
    trepo.save_transcript_content(job_id, speakers, utterances, words=[])

    trepo.save_participants(job_id, [
        {"name": "Vance", "role": "examining_attorney",
         "speaker_indices": [0], "honorific": "MR."},
        {"name": "Dana Reed", "role": "witness", "speaker_indices": [1]},
    ])
    return job_id
