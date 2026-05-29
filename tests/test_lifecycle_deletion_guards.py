"""Lifecycle hardening: delete-endpoint guards.

Certified (non-DRAFT) packages and a tampered RAW both block deletion unless
force=true; every successful delete writes a durable deletion-log record.
"""
from __future__ import annotations

import uuid
from pathlib import Path


def _trepo_job(trepo, fn="lh.mp3"):
    return trepo.create_job({"source_filename": fn})["job_id"]


def _insert_package(job_id, state="CERTIFIED"):
    from backend.db.repository import get_connection
    pkg_id = f"pkg-{uuid.uuid4().hex[:8]}"
    with get_connection() as c:
        c.execute(
            "INSERT INTO transcript_packages "
            "(package_id, job_id, snapshot_id, state_hash, package_state, "
            " manifest_json, package_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pkg_id, job_id, "snap-1", "hash-1", state, "{}", "{}"),
        )
    return pkg_id


def _upload(client, filename="lh_raw.mp3"):
    case = client.post("/api/cases", json={
        "case_number_value": "2024-CI-28593", "caption_full": "A vs. B",
        "judicial_district": "101st", "county": "Dallas", "state": "Texas"}).json()
    session = client.post("/api/sessions", json={
        "case_id": case["case_id"], "scheduled_at": "2026-05-19T10:00:00-05:00",
        "witness_name": "W", "location_address": "X", "service_type": "CR_only"}).json()
    return client.post(
        "/api/transcripts/upload",
        files={"file": (filename, b"fake-media-bytes" * 40, "audio/mpeg")},
        data={"sequence_index": "0", "case_id": case["case_id"],
              "session_id": session["session_id"]},
    ).json()


def test_delete_certified_without_force_409_and_intact(client):
    from backend.transcript import repository as trepo
    job_id = _trepo_job(trepo)
    _insert_package(job_id, "CERTIFIED")
    res = client.delete(f"/api/transcripts/jobs/{job_id}")
    assert res.status_code == 409
    body = res.json()
    assert "package" in body["detail"].lower()
    assert body["package_ids"]
    assert trepo.get_job(job_id) is not None  # left intact


def test_delete_non_draft_states_all_blocked(client):
    from backend.transcript import repository as trepo
    for state in ("EXPORTED", "SEALED", "AMENDED", "SUPERSEDED"):
        job_id = _trepo_job(trepo)
        _insert_package(job_id, state)
        assert client.delete(f"/api/transcripts/jobs/{job_id}").status_code == 409, state


def test_delete_certified_with_force_deletes_and_logs(client):
    from backend.transcript import repository as trepo
    from backend.transcript import deletion_log
    job_id = _trepo_job(trepo)
    _insert_package(job_id, "CERTIFIED")
    res = client.delete(f"/api/transcripts/jobs/{job_id}?force=true")
    assert res.status_code == 204
    assert trepo.get_job(job_id) is None
    events = deletion_log.list_deletion_events()
    assert any(e["job_id"] == job_id and e["force"] and e["package_ids"] for e in events)


def test_delete_clean_job_succeeds_and_logs(client):
    from backend.transcript import repository as trepo
    from backend.transcript import deletion_log
    job_id = _trepo_job(trepo)
    res = client.delete(f"/api/transcripts/jobs/{job_id}")
    assert res.status_code == 204
    assert trepo.get_job(job_id) is None
    assert any(e["job_id"] == job_id for e in deletion_log.list_deletion_events())


def test_delete_tampered_raw_blocked_then_forced(client):
    from backend.transcript import repository as trepo
    job = _upload(client)
    job_id = job["job_id"]
    raw_path = trepo.get_job(job_id).get("raw_packet_path")
    assert raw_path and Path(raw_path).exists()
    # Tamper the immutable RAW packet on disk.
    Path(raw_path).write_text('{"tampered": true}', encoding="utf-8")

    assert client.delete(f"/api/transcripts/jobs/{job_id}").status_code == 409
    assert trepo.get_job(job_id) is not None  # still intact
    assert client.delete(f"/api/transcripts/jobs/{job_id}?force=true").status_code == 204
    assert trepo.get_job(job_id) is None
