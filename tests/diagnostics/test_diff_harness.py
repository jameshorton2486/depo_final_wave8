from __future__ import annotations

from pathlib import Path

from backend.diagnostics import run_diff, write_job_artifacts
from backend.transcript import packet
from backend.transcript import repository as trepo


def _seed_job(temp_db: Path) -> str:
    job = trepo.create_job({"source_filename": "fixture.mp3"})
    job_id = job["job_id"]
    utterances = [
        {
            "utterance_id": "utt-1",
            "utterance_index": 0,
            "speaker_index": 0,
            "speaker_label": "Speaker 0",
            "start_time": 0.0,
            "end_time": 1.0,
            "text": "Please state your name.",
            "avg_confidence": 0.99,
        },
        {
            "utterance_id": "utt-2",
            "utterance_index": 1,
            "speaker_index": 1,
            "speaker_label": "Speaker 1",
            "start_time": 1.1,
            "end_time": 2.0,
            "text": "Dana Reed.",
            "avg_confidence": 0.99,
        },
    ]
    trepo.save_transcript_content(job_id, [], utterances, words=[])
    trepo.save_working_utterance_overrides(
        job_id,
        [{"utterance_id": "utt-1", "working_text": "Please state your full name."}],
        source="REGEX:TEST-01",
    )

    raw_packet = {
        "packet_version": 1,
        "layer": "raw",
        "generated_at": "2026-05-25T00:00:00+00:00",
        "job": {"job_id": job_id, "source_filename": "fixture.mp3", "source_size_bytes": 100, "duration_seconds": 2.0, "word_count": 6, "utterance_count": 2, "speaker_count": 2, "avg_confidence": 0.99},
        "engine": {"name": "deepgram", "transcription_source": "deepgram", "full_text": "Please state your name. Dana Reed."},
        "speakers": [],
        "utterances": utterances,
        "words": [],
        "keyterms": [],
        "artifacts": {"audio_path": ""},
    }
    working_packet = dict(raw_packet)
    working_packet["layer"] = "working"
    working_packet["utterances"] = [
        {**utterances[0], "text": "Please state your full name."},
        utterances[1],
    ]

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
        },
    )
    return job_id


def test_run_diff_is_deterministic(temp_db: Path):
    job_id = _seed_job(temp_db)
    first = run_diff(job_id)
    second = run_diff(job_id)
    assert first["metrics"] == second["metrics"]
    assert first["per_utterance"] == second["per_utterance"]


def test_write_job_artifacts_writes_stable_outputs(temp_db: Path):
    job_id = _seed_job(temp_db)
    first = write_job_artifacts(job_id, output_root=temp_db.parent / "diff" / job_id)
    second = write_job_artifacts(job_id, output_root=temp_db.parent / "diff" / job_id)
    report_path = Path(first["paths"]["report_path"])
    metrics_path = Path(first["paths"]["metrics_path"])
    assert report_path.exists()
    assert metrics_path.exists()
    assert report_path.read_text(encoding="utf-8") == Path(second["paths"]["report_path"]).read_text(encoding="utf-8")
    assert metrics_path.read_text(encoding="utf-8") == Path(second["paths"]["metrics_path"]).read_text(encoding="utf-8")
