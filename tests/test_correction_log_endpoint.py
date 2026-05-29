"""Pass 2: correction-log JSONL sidecar + GET /correction-log endpoint.

Both run sites (the engine auto-run and the manual Apply Rule endpoint) append
to the sidecar; the endpoint returns the most recent run's entries.
"""
from __future__ import annotations


def _seed(trepo):
    job_id = trepo.create_job({"source_filename": "corrlog.mp3"})["job_id"]
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


def test_correction_log_empty_before_any_run(client):
    from backend.transcript import repository as trepo
    job_id = _seed(trepo)
    res = client.get(f"/api/transcripts/jobs/{job_id}/correction-log")
    assert res.status_code == 200
    assert res.json()["entries"] == []


def test_correction_log_after_auto_run(client):
    from backend.transcript import repository as trepo
    from backend.services.correction_trigger import run_correction_engine_for_job
    job_id = _seed(trepo)
    run_correction_engine_for_job(job_id)
    entries = client.get(f"/api/transcripts/jobs/{job_id}/correction-log").json()["entries"]
    assert len(entries) > 0
    assert all(e["source"] == "auto" for e in entries)
    assert all({"timestamp", "rule_id", "before", "after", "stage", "source"} <= set(e) for e in entries)


def test_correction_log_returns_most_recent_run(client):
    from backend.transcript import repository as trepo
    from backend.services.correction_trigger import run_correction_engine_for_job
    job_id = _seed(trepo)
    run_correction_engine_for_job(job_id)  # auto run
    client.post(f"/api/corrections/jobs/{job_id}/apply-rules",
                json={"rules": [{"find_pattern": r"\btrinaty\b", "replace_with": "Trinity"}]})
    entries = client.get(f"/api/transcripts/jobs/{job_id}/correction-log").json()["entries"]
    # The manual regex run is most recent -> its entries are returned.
    assert len(entries) > 0
    assert all(e["source"] == "manual_regex" for e in entries)
    assert any("Trinity" in e["after"] for e in entries)


def test_correction_log_404_unknown_job(client):
    assert client.get("/api/transcripts/jobs/nope/correction-log").status_code == 404
