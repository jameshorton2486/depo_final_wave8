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
    first_utt = content["utterances"][0]
    assert first_utt["raw_text"] == first_utt["text"]
    assert first_utt["working_text"] is None
    assert first_utt["is_working_override"] is False


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


def test_save_working_transcript_persists_reload_and_packet(client):
    job = _upload(client).json()
    job_id = job["job_id"]
    content_before = client.get(f"/api/transcripts/jobs/{job_id}/content").json()
    target = content_before["utterances"][0]
    updated_text = (target["text"] or "") + " Confirmed by reporter."
    save_res = client.put(
        f"/api/transcripts/jobs/{job_id}/working-transcript",
        json={
            "utterances": [
                {
                    "utterance_id": target["utterance_id"],
                    "working_text": updated_text,
                }
            ],
            "source": "test_suite",
        },
    )
    assert save_res.status_code == 200
    body = save_res.json()
    assert body["saved"] == 1
    assert body["override_count"] == 1

    content = client.get(f"/api/transcripts/jobs/{job_id}/content").json()
    updated = next(u for u in content["utterances"] if u["utterance_id"] == target["utterance_id"])
    assert updated["text"] == updated_text
    assert updated["raw_text"] == target["text"]
    assert updated["working_text"] == updated_text
    assert updated["is_working_override"] is True
    assert updated["working_source"] == "test_suite"
    assert updated["working_updated_at"]

    packet = client.get(f"/api/transcripts/jobs/{job_id}/packet").json()
    packet_utt = next(u for u in packet["utterances"] if u["utterance_id"] == target["utterance_id"])
    assert packet_utt["text"] == updated_text


def test_save_working_transcript_preserves_raw_immutability(client):
    job = _upload(client).json()
    job_id = job["job_id"]
    content_before = client.get(f"/api/transcripts/jobs/{job_id}/content").json()
    target = content_before["utterances"][0]
    updated_text = (target["text"] or "") + " Revised."
    client.put(
        f"/api/transcripts/jobs/{job_id}/working-transcript",
        json={
            "utterances": [
                {
                    "utterance_id": target["utterance_id"],
                    "working_text": updated_text,
                }
            ]
        },
    )

    from backend.transcript import repository as trepo

    raw = next(u for u in trepo.get_utterances(job_id, layer="raw") if u["utterance_id"] == target["utterance_id"])
    working = next(u for u in trepo.get_utterances(job_id, layer="working") if u["utterance_id"] == target["utterance_id"])
    assert raw["text"] == target["text"]
    assert working["text"] == updated_text


def test_export_preview_uses_latest_working_transcript(client, sample_job_with_content):
    job_id = sample_job_with_content
    client.put(
        f"/api/transcripts/jobs/{job_id}/working-transcript",
        json={
            "utterances": [
                {
                    "utterance_id": "utt-5",
                    "working_text": "Yes, I remained on duty for that entire afternoon.",
                }
            ]
        },
    )
    preview = client.get(f"/api/transcripts/jobs/{job_id}/export-preview")
    assert preview.status_code == 200
    text = "\n".join(
        line["text"]
        for page in preview.json()["pages"]
        for line in page["lines"]
        if line["text"]
    )
    assert "Yes, I remained on duty for that entire afternoon." in text


def test_transcript_provenance_persists_and_lists(client, sample_job_with_content):
    job_id = sample_job_with_content
    create = client.post(
        f"/api/transcripts/jobs/{job_id}/provenance",
        json={
            "event_type": "manual_edit",
            "title": "Manual Edit",
            "detail": "Reporter corrected line 1.",
            "actor_type": "user",
            "source": "workspace",
            "metadata": {"utterance_id": "utt-1"},
        },
    )
    assert create.status_code == 201
    event = create.json()
    assert event["event_type"] == "manual_edit"
    assert event["metadata"]["utterance_id"] == "utt-1"

    listed = client.get(f"/api/transcripts/jobs/{job_id}/provenance")
    assert listed.status_code == 200
    body = listed.json()
    assert body["count"] >= 1
    assert any(ev["event_id"] == event["event_id"] for ev in body["events"])


def test_exhibit_create_reload_and_delete(client, sample_job_with_content):
    job_id = sample_job_with_content
    created = client.post(
        f"/api/exhibits/jobs/{job_id}",
        json={
            "exhibit_number": "1",
            "exhibit_title": "Photograph",
            "offering_attorney": "Mr. Vance",
            "anchor_utterance_id": "utt-2",
            "anchor_note": "And where do you currently reside?",
        },
    )
    assert created.status_code == 201
    exhibit = created.json()
    assert exhibit["job_id"] == job_id
    assert exhibit["anchor_utterance_id"] == "utt-2"

    listed = client.get(f"/api/exhibits/jobs/{job_id}")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["exhibits"][0]["exhibit_title"] == "Photograph"

    content = client.get(f"/api/transcripts/jobs/{job_id}/content")
    assert content.status_code == 200
    assert content.json()["exhibits"][0]["anchor_utterance_id"] == "utt-2"

    updated = client.put(
        f"/api/exhibits/{exhibit['exhibit_id']}",
        json={
            "exhibit_title": "Updated Photograph",
            "anchor_utterance_id": "utt-3",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["exhibit_title"] == "Updated Photograph"
    assert updated.json()["anchor_utterance_id"] == "utt-3"

    deleted = client.delete(f"/api/exhibits/{exhibit['exhibit_id']}")
    assert deleted.status_code == 204
    relisted = client.get(f"/api/exhibits/jobs/{job_id}")
    assert relisted.json()["count"] == 0


def test_exhibit_mutation_allowed_after_locked_snapshot_for_new_lineage(client, sample_job_with_content):
    job_id = sample_job_with_content
    snap = client.post(
        f"/api/snapshots/jobs/{job_id}",
        json={"category": "CERTIFIED"},
    ).json()
    assert client.post(f"/api/snapshots/{snap['snapshot_id']}/lock").status_code == 200

    created = client.post(
        f"/api/exhibits/jobs/{job_id}",
        json={
            "exhibit_number": "1",
            "exhibit_title": "Photograph",
            "anchor_utterance_id": "utt-1",
        },
    )
    assert created.status_code == 201

    transcript_saved = client.put(
        f"/api/transcripts/jobs/{job_id}/working-transcript",
        json={
            "utterances": [
                {"utterance_id": "utt-1", "working_text": "Working transcript continues after certification."}
            ]
        },
    )
    assert transcript_saved.status_code == 200


def test_exhibit_anchor_survives_transcript_edits(client, sample_job_with_content):
    job_id = sample_job_with_content
    created = client.post(
        f"/api/exhibits/jobs/{job_id}",
        json={
            "exhibit_number": "2",
            "exhibit_title": "Contract",
            "anchor_utterance_id": "utt-3",
        },
    ).json()

    updated = client.put(
        f"/api/transcripts/jobs/{job_id}/working-transcript",
        json={
            "utterances": [
                {"utterance_id": "utt-3", "working_text": "And where are you currently employed?"}
            ],
            "source": "test_suite",
        },
    )
    assert updated.status_code == 200
    listed = client.get(f"/api/exhibits/jobs/{job_id}").json()
    assert listed["exhibits"][0]["anchor_utterance_id"] == created["anchor_utterance_id"]


def test_export_from_locked_snapshot_returns_certified_source(client, sample_job_with_content, tmp_path):
    from backend.transcript import working_state

    job_id = sample_job_with_content
    client.put(
        f"/api/transcripts/jobs/{job_id}/working-transcript",
        json={
            "utterances": [
                {
                    "utterance_id": "utt-1",
                    "working_text": "Certified snapshot body text.",
                }
            ],
            "source": "test_suite",
        },
    )
    snap = client.post(
        f"/api/snapshots/jobs/{job_id}",
        json={"category": "CERTIFIED"},
    ).json()
    assert client.post(f"/api/snapshots/{snap['snapshot_id']}/lock").status_code == 200

    # Later working-state changes are allowed, but certified export must still
    # freeze to the locked snapshot lineage.
    follow_up = client.put(
        f"/api/transcripts/jobs/{job_id}/working-transcript",
        json={
            "utterances": [
                {"utterance_id": "utt-1", "working_text": "Live working transcript after certification lock."}
            ],
            "source": "test_suite",
        },
    )
    assert follow_up.status_code == 200
    working_state.persist_working_transcript(
        job_id,
        [{"utterance_id": "utt-1", "working_text": "Live working transcript after certification lock."}],
        source="test_suite",
    )
    exported = client.post(
        f"/api/transcripts/jobs/{job_id}/export",
        json={
            "fmt": "txt",
            "destination": "path",
            "explicit_path": str(tmp_path),
            "snapshot_id": snap["snapshot_id"],
        },
    )
    assert exported.status_code == 200
    body = exported.json()
    assert body["export_state"] == "certified_snapshot"
    assert body["snapshot_id"] == snap["snapshot_id"]
