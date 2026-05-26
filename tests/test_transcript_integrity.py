from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.transcript import packet
from backend.transcript import repository as trepo
from backend.transcript.integrity import (
    RawTranscriptImmutableError,
    integrity_sidecar_path,
)


def _create_bound_case_session(client):
    case = client.post(
        "/api/cases",
        json={
            "case_number_value": "2024-CI-28593",
            "caption_full": "SARAH JENKINS vs. NEXUS PHARMA INC.",
            "judicial_district": "101st Judicial District",
            "county": "Dallas County",
            "state": "Texas",
        },
    ).json()
    session = client.post(
        "/api/sessions",
        json={
            "case_id": case["case_id"],
            "scheduled_at": "2026-05-19T10:00:00-05:00",
            "scheduled_end_at": "2026-05-19T12:30:00-05:00",
            "witness_name": "Dr. Donald Leifer",
            "location_address": "201 Main Street, Fort Worth, TX 76102",
            "custodial_attorney_name": "Ms. Elizabeth R. Flora, Esq.",
            "requesting_party_name": "Vance & Partners LLP",
        },
    ).json()
    return case, session


def _upload(client, filename="morning_session.mp3", seq=0):
    fake_audio = b"fake-media-bytes-for-offline-fallback" * 40
    case, session = _create_bound_case_session(client)
    data = {
        "sequence_index": str(seq),
        "case_id": case["case_id"],
        "session_id": session["session_id"],
    }
    return client.post(
        "/api/transcripts/upload",
        files={"file": (filename, fake_audio, "audio/mpeg")},
        data=data,
    )


def _raw_packet(job_id: str) -> dict:
    return {
        "packet_version": 1,
        "layer": "raw",
        "generated_at": "2026-05-25T00:00:00+00:00",
        "job": {
            "job_id": job_id,
            "source_filename": "authoritative.mp3",
            "source_size_bytes": 100,
            "duration_seconds": 10.0,
            "word_count": 4,
            "utterance_count": 2,
            "speaker_count": 2,
            "avg_confidence": 0.99,
        },
        "engine": {
            "name": "deepgram-nova-3",
            "transcription_source": "deepgram",
            "full_text": "Please state your name. Dana Reed.",
        },
        "speakers": [],
        "utterances": [
            {
                "utterance_id": "utt-1",
                "utterance_index": 0,
                "speaker_index": 0,
                "speaker_label": "Speaker 0",
                "start_time": 0.0,
                "end_time": 4.0,
                "text": "Please state your name.",
                "avg_confidence": 0.99,
            },
            {
                "utterance_id": "utt-2",
                "utterance_index": 1,
                "speaker_index": 1,
                "speaker_label": "Speaker 1",
                "start_time": 5.0,
                "end_time": 8.0,
                "text": "Dana Reed.",
                "avg_confidence": 0.99,
            },
        ],
        "words": [],
        "keyterms": [],
        "artifacts": {"audio_path": ""},
    }


def _working_packet(job_id: str) -> dict:
    pkt = _raw_packet(job_id)
    pkt["layer"] = "working"
    return pkt


def _create_authoritative_job_with_packets(temp_db: Path) -> str:
    job = trepo.create_job({"source_filename": "authoritative.mp3"})
    job_id = job["job_id"]

    speakers = [
        {
            "speaker_row_id": "spk-0",
            "speaker_index": 0,
            "speaker_label": "Speaker 0",
            "assigned_name": "Mr. Vance",
            "speaker_role": "examining_attorney",
            "word_count": 4,
        },
        {
            "speaker_row_id": "spk-1",
            "speaker_index": 1,
            "speaker_label": "Speaker 1",
            "assigned_name": "Dana Reed",
            "speaker_role": "witness",
            "word_count": 2,
        },
    ]
    utterances = _raw_packet(job_id)["utterances"]
    trepo.save_transcript_content(job_id, speakers, utterances, words=[])
    trepo.save_participants(
        job_id,
        [
            {"name": "Vance", "role": "examining_attorney", "speaker_indices": [0]},
            {"name": "Dana Reed", "role": "witness", "speaker_indices": [1]},
        ],
    )

    transcripts_dir = temp_db.parent / "transcripts" / job_id
    raw_path = packet.write_raw_packet(_raw_packet(job_id), transcripts_dir / "raw.json")
    working_path = packet.write_packet(_working_packet(job_id), transcripts_dir / "working.json")
    trepo.update_job(
        job_id,
        {
            "status": "completed",
            "transcription_source": "deepgram",
            "raw_packet_path": str(raw_path),
            "working_packet_path": str(working_path),
            "word_count": 4,
            "utterance_count": 2,
            "speaker_count": 2,
        },
    )
    return job_id


def test_write_raw_packet_twice_raises(temp_db: Path):
    raw_path = temp_db.parent / "transcripts" / "job-1" / "raw.json"
    packet.write_raw_packet(_raw_packet("job-1"), raw_path)
    with pytest.raises(RawTranscriptImmutableError):
        packet.write_raw_packet(_raw_packet("job-1"), raw_path)


def test_save_transcript_content_twice_raises(sample_job):
    speakers = [
        {
            "speaker_row_id": "spk-0",
            "speaker_index": 0,
            "speaker_label": "Speaker 0",
            "assigned_name": None,
            "speaker_role": None,
            "word_count": 2,
        }
    ]
    utterances = [
        {
            "utterance_id": "utt-1",
            "utterance_index": 0,
            "speaker_index": 0,
            "speaker_label": "Speaker 0",
            "start_time": 0.0,
            "end_time": 1.0,
            "text": "Hello there.",
            "avg_confidence": 0.99,
        }
    ]
    trepo.save_transcript_content(sample_job, speakers, utterances, words=[])
    with pytest.raises(RawTranscriptImmutableError):
        trepo.save_transcript_content(sample_job, speakers, utterances, words=[])


def test_raw_integrity_sidecar_written_on_upload(client):
    res = _upload(client)
    assert res.status_code == 201
    job_id = res.json()["job_id"]
    job = trepo.get_job(job_id)
    sidecar = integrity_sidecar_path(job["raw_packet_path"])
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["algorithm"] == "sha256"
    assert payload["hash"]
    assert payload["captured_at"]


def test_raw_integrity_failure_blocks_content_load(client):
    res = _upload(client)
    assert res.status_code == 201
    job_id = res.json()["job_id"]
    job = trepo.get_job(job_id)
    raw_path = Path(job["raw_packet_path"])
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    payload["utterances"][0]["text"] = "Tampered raw transcript."
    raw_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    content = client.get(f"/api/transcripts/jobs/{job_id}/content")
    assert content.status_code == 409
    assert "integrity verification failed" in content.json()["detail"].lower()


def test_packaging_refuses_tampered_raw_packet(client, temp_db: Path):
    job_id = _create_authoritative_job_with_packets(temp_db)

    snap_res = client.post(
        f"/api/snapshots/jobs/{job_id}",
        json={"category": "CERTIFIED"},
    )
    assert snap_res.status_code == 200
    snap_id = snap_res.json()["snapshot_id"]
    assert client.post(f"/api/snapshots/{snap_id}/lock").status_code == 200

    job = trepo.get_job(job_id)
    raw_path = Path(job["raw_packet_path"])
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    payload["utterances"][1]["text"] = "Tampered witness answer."
    raw_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    assemble = client.post(
        f"/api/packages/jobs/{job_id}",
        json={
            "snapshot_id": snap_id,
            "metadata": {
                "cause_number": "2024-CI-09912",
                "caption": "Acme Corp. v. Dana Reed",
                "court": "288th Judicial District Court, Bexar County, Texas",
                "witness_name": "Dana Reed",
                "reporter_name": "Miah Bardot",
                "reporter_csr_number": "TX-10423",
                "proceedings_date": "May 21, 2026",
            },
        },
    )
    assert assemble.status_code == 409
    assert "integrity verification failed" in assemble.json()["detail"].lower()
