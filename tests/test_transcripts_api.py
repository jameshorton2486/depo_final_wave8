"""Tests for the /api/transcripts router (Stage 2 transcripts engine).

These run against the offline fallback transcriber, so they need no
Deepgram API key and no network. The temp_db fixture (conftest.py)
redirects SQLite and the data root into a tmp_path.
"""
from __future__ import annotations


def _upload(client, filename="morning_session.mp3", seq=0, case_id=None):
    """Upload a small fake media file and return the created job dict."""
    fake_audio = b"fake-media-bytes-for-offline-fallback" * 40
    data = {"sequence_index": str(seq)}
    if case_id:
        data["case_id"] = case_id
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
    res = client.post(
        "/api/transcripts/upload",
        files={"file": ("clip.wav", b"", "audio/wav")},
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
    _upload(client, filename="a.mp3", seq=0, case_id=created_case["case_id"])
    _upload(client, filename="b.mp3", seq=1, case_id=created_case["case_id"])
    _upload(client, filename="orphan.mp3", seq=0)  # no case

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
