from __future__ import annotations

from pathlib import Path

from backend.transcript import packet
from backend.transcript import repository as trepo


def _valid_metadata() -> dict:
    return {
        "cause_number": "2024-CI-09912",
        "caption": "Acme Corp. v. Dana Reed",
        "court": "288th Judicial District Court, Bexar County, Texas",
        "witness_name": "Dana Reed",
        "reporter_name": "Miah Bardot",
        "reporter_csr_number": "TX-10423",
        "reporter_csr_expiration": "12/31/2027",
        "firm_registration_no": "10698",
        "proceedings_date": "May 21, 2026",
        "location": "1100 NW Loop 410, San Antonio, Texas",
        "examination_disposition": "waived",
        "custodial_attorney": "Ms. Elizabeth R. Flora, Esq.",
        "officer_charges_amount": "450.00",
        "charges_party": "Acme Corp.",
        "certificate_service_date": "June 5, 2026",
        "time_per_party": [{"party": "Plaintiff Counsel", "duration": "1:30"}],
        "counsel_of_record": [{"name": "Mr. Nunez", "role": "Attorney for Acme Corp."}],
        "appearances": [
            {
                "role": "plaintiff",
                "attorney": "Mr. Nunez",
                "firm": "Nunez & Associates",
                "party": "Acme Corp.",
                "sbot_no": "24098765",
            }
        ],
    }


def _create_authoritative_job(temp_db: Path) -> str:
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
    utterances = [
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
    ]
    trepo.save_transcript_content(job_id, speakers, utterances, words=[])
    trepo.save_participants(
        job_id,
        [
            {"name": "Vance", "role": "examining_attorney", "speaker_indices": [0]},
            {"name": "Dana Reed", "role": "witness", "speaker_indices": [1]},
        ],
    )

    raw_packet = {
        "packet_version": 1,
        "layer": "raw",
        "generated_at": "2026-05-25T00:00:00+00:00",
        "job": {
            "job_id": job_id,
            "source_filename": "authoritative.mp3",
            "source_size_bytes": 100,
            "duration_seconds": 10.0,
            "word_count": 6,
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
        "utterances": utterances,
        "words": [],
        "keyterms": [],
        "artifacts": {"audio_path": ""},
    }
    working_packet = dict(raw_packet)
    working_packet["layer"] = "working"

    transcript_dir = temp_db.parent / "transcripts" / job_id
    raw_path = packet.write_raw_packet(raw_packet, transcript_dir / "raw.json")
    working_path = packet.write_packet(working_packet, transcript_dir / "working.json")
    trepo.update_job(
        job_id,
        {
            "status": "completed",
            "transcription_source": "deepgram",
            "raw_packet_path": str(raw_path),
            "working_packet_path": str(working_path),
            "word_count": 6,
            "utterance_count": 2,
            "speaker_count": 2,
        },
    )
    return job_id


def _assemble_and_certify(client, job_id: str):
    snap_res = client.post(f"/api/snapshots/jobs/{job_id}", json={"category": "CERTIFIED"})
    assert snap_res.status_code == 200
    snap_id = snap_res.json()["snapshot_id"]
    assert client.post(f"/api/snapshots/{snap_id}/lock").status_code == 200
    assemble_res = client.post(
        f"/api/packages/jobs/{job_id}",
        json={"snapshot_id": snap_id, "metadata": _valid_metadata()},
    )
    assert assemble_res.status_code == 200
    package_id = assemble_res.json()["package_id"]
    return client.post(
        f"/api/packages/{package_id}/certify",
        json={"metadata": _valid_metadata()},
    )


def test_logged_working_correction_does_not_block_certification(client, temp_db: Path):
    job_id = _create_authoritative_job(temp_db)
    trepo.save_working_utterance_overrides(
        job_id,
        [{"utterance_id": "utt-1", "working_text": "Please state your full name."}],
        source="REGEX:TEST-01",
    )

    certify = _assemble_and_certify(client, job_id)
    assert certify.status_code == 200
    provenance = client.get(f"/api/transcripts/jobs/{job_id}/provenance").json()["events"]
    assert any(event["event_type"] == "mutation_detection_warning" for event in provenance)


def test_silent_word_deletion_blocks_certification(client, temp_db: Path):
    job_id = _create_authoritative_job(temp_db)
    with trepo.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transcript_working_utterances
            (working_row_id, job_id, utterance_id, working_text, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (trepo.new_id(), job_id, "utt-1", "Please state", None),
        )

    certify = _assemble_and_certify(client, job_id)
    assert certify.status_code == 422
    assert "mutation detection" in certify.json()["detail"].lower()
    provenance = client.get(f"/api/transcripts/jobs/{job_id}/provenance").json()["events"]
    assert any(event["event_type"] == "mutation_detection_blocked" for event in provenance)
