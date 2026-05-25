"""Tests for the /api/transcripts router (Stage 2 transcripts engine).

These run against the offline fallback transcriber, so they need no
Deepgram API key and no network. The temp_db fixture (conftest.py)
redirects SQLite and the data root into a tmp_path.
"""
from __future__ import annotations


def _create_bound_case_session(client):
    case = client.post("/api/cases", json={
        "case_number_value": "2024-CI-28593",
        "caption_full": "SARAH JENKINS vs. NEXUS PHARMA INC.",
        "judicial_district": "101st Judicial District",
        "county": "Dallas County",
        "state": "Texas",
    }).json()
    session = client.post("/api/sessions", json={
        "case_id": case["case_id"],
        "scheduled_at": "2026-05-19T10:00:00-05:00",
        "scheduled_end_at": "2026-05-19T12:30:00-05:00",
        "witness_name": "Dr. Donald Leifer",
        "location_address": "201 Main Street, Fort Worth, TX 76102",
        "custodial_attorney_name": "Ms. Elizabeth R. Flora, Esq.",
        "requesting_party_name": "Vance & Partners LLP",
    }).json()
    return case, session


def _upload(client, filename="morning_session.mp3", seq=0, case_id=None, session_id=None):
    """Upload a small fake media file and return the created job dict."""
    fake_audio = b"fake-media-bytes-for-offline-fallback" * 40
    if not case_id or not session_id:
        case, session = _create_bound_case_session(client)
        case_id = case["case_id"]
        session_id = session["session_id"]
    data = {"sequence_index": str(seq), "case_id": case_id, "session_id": session_id}
    res = client.post(
        "/api/transcripts/upload",
        files={"file": (filename, fake_audio, "audio/mpeg")},
        data=data,
    )
    return res


def test_upload_creates_and_processes_job(client):
    res = _upload(client)
    assert res.status_code == 201
    job = res.json()
    assert job["source_filename"] == "morning_session.mp3"
    assert job["media_kind"] == "prerecorded"

    # Background ingestion runs before the next request resolves.
    follow = client.get(f"/api/transcripts/jobs/{job['job_id']}")
    assert follow.status_code == 200
    processed = follow.json()
    assert processed["status"] == "completed"
    assert processed["transcription_source"] == "offline-fallback"
    assert processed["word_count"] > 0
    assert processed["utterance_count"] > 0
    assert processed["speaker_count"] >= 2


def test_rejects_unsupported_file_type(client):
    res = client.post(
        "/api/transcripts/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 400


def test_rejects_empty_file(client):
    case, session = _create_bound_case_session(client)
    res = client.post(
        "/api/transcripts/upload",
        files={"file": ("clip.wav", b"", "audio/wav")},
        data={"case_id": case["case_id"], "session_id": session["session_id"]},
    )
    assert res.status_code == 400


def test_get_content_returns_canonical_objects(client):
    job = _upload(client).json()
    res = client.get(f"/api/transcripts/jobs/{job['job_id']}/content")
    assert res.status_code == 200
    content = res.json()
    assert content["job"]["job_id"] == job["job_id"]
    assert len(content["words"]) == content["job"]["word_count"]
    assert len(content["utterances"]) == content["job"]["utterance_count"]
    # Word objects carry the canonical fields.
    first = content["words"][0]
    for key in ("word_id", "raw_text", "start_time", "end_time", "confidence"):
        assert key in first
    # raw_text is present; working_text is unedited at ingestion.
    assert first["working_text"] is None


def test_raw_and_working_packets(client):
    job = _upload(client).json()
    raw = client.get(f"/api/transcripts/jobs/{job['job_id']}/raw")
    working = client.get(f"/api/transcripts/jobs/{job['job_id']}/packet")
    assert raw.status_code == 200
    assert working.status_code == 200
    assert raw.json()["layer"] == "raw"
    assert working.json()["layer"] == "working"
    # Both packets describe the same job and word count at ingestion time.
    assert raw.json()["job"]["word_count"] == working.json()["job"]["word_count"]


def test_readback_search_finds_phrase(client):
    _upload(client)
    res = client.post("/api/transcripts/readback", json={"query": "MRI scans"})
    assert res.status_code == 200
    body = res.json()
    assert body["count"] >= 1
    assert all("MRI scans".lower() in m["text"].lower() for m in body["matches"])


def test_readback_empty_query_rejected(client):
    res = client.post("/api/transcripts/readback", json={"query": ""})
    assert res.status_code == 422  # pydantic min_length


def test_jobs_list_and_case_filter(client, created_case):
    session = client.post("/api/sessions", json={
        "case_id": created_case["case_id"],
        "scheduled_at": "2026-05-19T10:00:00-05:00",
        "scheduled_end_at": "2026-05-19T12:30:00-05:00",
        "witness_name": "Dr. Donald Leifer",
    }).json()
    _upload(client, filename="a.mp3", seq=0, case_id=created_case["case_id"], session_id=session["session_id"])
    _upload(client, filename="b.mp3", seq=1, case_id=created_case["case_id"], session_id=session["session_id"])
    _upload(client, filename="orphan.mp3", seq=0)

    all_jobs = client.get("/api/transcripts/jobs").json()
    assert all_jobs["count"] == 3

    case_jobs = client.get(
        f"/api/transcripts/jobs?case_id={created_case['case_id']}"
    ).json()
    assert case_jobs["count"] == 2
    # Case-scoped list is ordered by sequence_index.
    assert [j["source_filename"] for j in case_jobs["jobs"]] == ["a.mp3", "b.mp3"]


def test_delete_job(client):
    job = _upload(client).json()
    res = client.delete(f"/api/transcripts/jobs/{job['job_id']}")
    assert res.status_code == 204
    assert client.get(f"/api/transcripts/jobs/{job['job_id']}").status_code == 404


def test_get_missing_job_is_404(client):
    assert client.get("/api/transcripts/jobs/does-not-exist").status_code == 404


def test_upload_requires_saved_case_and_session(client):
    fake_audio = b"fake-media-bytes-for-offline-fallback" * 40
    res = client.post(
        "/api/transcripts/upload",
        files={"file": ("morning_session.mp3", fake_audio, "audio/mpeg")},
        data={"sequence_index": "0"},
    )
    assert res.status_code == 400
    assert "Save Stage 1 Intake before uploading transcripts" in res.json()["detail"]
