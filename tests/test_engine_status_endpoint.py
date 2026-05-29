"""Pass 2: GET /engine-status — last correction run (auto or manual regex)."""
from __future__ import annotations


def _seed(trepo):
    job_id = trepo.create_job({"source_filename": "enginestatus.mp3"})["job_id"]
    speakers = [
        {"speaker_row_id": "spk-0", "speaker_index": 0, "speaker_label": "Speaker 0",
         "assigned_name": "Vance", "speaker_role": "examining_attorney", "word_count": 6},
        {"speaker_row_id": "spk-1", "speaker_index": 1, "speaker_label": "Speaker 1",
         "assigned_name": "Reed", "speaker_role": "witness", "word_count": 6},
    ]
    exchange = [
        (0, 0, "Doctor. Smith, did you see trinaty there?"),
        (1, 1, "Yes, I worked worked with trinaty."),
    ]
    utterances = [
        {"utterance_id": f"u{i}", "utterance_index": i, "speaker_index": spk,
         "speaker_label": f"Speaker {spk}", "start_time": float(i), "end_time": float(i) + 1,
         "text": text, "avg_confidence": 0.99}
        for (i, spk, text) in exchange
    ]
    trepo.save_transcript_content(job_id, speakers, utterances, words=[])
    trepo.save_participants(job_id, [
        {"name": "Vance", "role": "examining_attorney", "speaker_indices": [0], "honorific": "MR."},
        {"name": "Reed", "role": "witness", "speaker_indices": [1]},
    ])
    return job_id


def test_engine_status_null_before_any_run(client):
    from backend.transcript import repository as trepo
    job_id = _seed(trepo)
    body = client.get(f"/api/transcripts/jobs/{job_id}/engine-status").json()
    assert body["last_run_at"] is None
    assert body["last_run_source"] is None
    assert body["last_run_event_id"] is None


def test_engine_status_after_manual_apply(client):
    from backend.transcript import repository as trepo
    job_id = _seed(trepo)
    client.post(f"/api/corrections/jobs/{job_id}/apply-rules",
                json={"rules": [{"find_pattern": r"\btrinaty\b", "replace_with": "Trinity"}]})
    body = client.get(f"/api/transcripts/jobs/{job_id}/engine-status").json()
    assert body["last_run_at"] is not None
    assert body["last_run_source"] == "manual_regex"
    assert body["last_run_substitutions"] == 2
    assert body["last_run_event_id"]


def test_engine_status_reports_most_recent_run(client):
    from backend.transcript import repository as trepo
    from backend.services.correction_trigger import run_correction_engine_for_job
    job_id = _seed(trepo)
    run_correction_engine_for_job(job_id)              # auto first
    client.post(f"/api/corrections/jobs/{job_id}/apply-rules",
                json={"rules": [{"find_pattern": r"\btrinaty\b", "replace_with": "Trinity"}]})  # manual last
    body = client.get(f"/api/transcripts/jobs/{job_id}/engine-status").json()
    assert body["last_run_source"] == "manual_regex"


def test_engine_status_404_unknown_job(client):
    assert client.get("/api/transcripts/jobs/nope/engine-status").status_code == 404
