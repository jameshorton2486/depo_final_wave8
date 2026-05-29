"""Pass 2: the consolidated AI review run.

POST /api/ai-review/jobs/{id}/analyze with no `kinds` runs all three
generators and records a single ai_review_run provenance event. The live
Anthropic API is never called -- availability is monkeypatched and the
generators are stubbed, so the test stays offline.
"""
from __future__ import annotations


def _seed(trepo):
    job_id = trepo.create_job({"source_filename": "aireview.mp3"})["job_id"]
    speakers = [
        {"speaker_row_id": "spk-0", "speaker_index": 0, "speaker_label": "Speaker 0",
         "assigned_name": "Vance", "speaker_role": "examining_attorney", "word_count": 4},
        {"speaker_row_id": "spk-1", "speaker_index": 1, "speaker_label": "Speaker 1",
         "assigned_name": "Reed", "speaker_role": "witness", "word_count": 4},
    ]
    utterances = [
        {"utterance_id": "u0", "utterance_index": 0, "speaker_index": 0,
         "speaker_label": "Speaker 0", "start_time": 0.0, "end_time": 1.0,
         "text": "State your name.", "avg_confidence": 0.99},
        {"utterance_id": "u1", "utterance_index": 1, "speaker_index": 1,
         "speaker_label": "Speaker 1", "start_time": 1.0, "end_time": 2.0,
         "text": "Dana Reed.", "avg_confidence": 0.99},
    ]
    trepo.save_transcript_content(job_id, speakers, utterances, words=[])
    return job_id


def test_analyze_runs_all_three_and_records_provenance(client, monkeypatch):
    from backend.transcript import repository as trepo
    from backend.transcript import provenance as prov
    import backend.api.ai_review as air

    # Make the AI layer "available" and stub each generator (no API call).
    monkeypatch.setattr(air.ai_client, "is_available", lambda: True)
    monkeypatch.setattr(air, "_GENERATORS", {
        "boundaries": lambda job_id, utts: [],
        "garbles": lambda job_id, utts: [],
        "flags": lambda job_id, utts: [],
    })

    job_id = _seed(trepo)
    res = client.post(f"/api/ai-review/jobs/{job_id}/analyze")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    # All three generators ran (each contributes a by_kind entry).
    assert set(body["by_kind"].keys()) == {"boundaries", "garbles", "flags"}
    assert body["provenance_event_id"]

    # Exactly one ai_review_run provenance event was recorded.
    events = [e for e in prov.list_events(job_id) if e["event_type"] == "ai_review_run"]
    assert len(events) == 1
    assert events[0]["metadata"]["by_kind"] == {"boundaries": 0, "garbles": 0, "flags": 0}


def test_analyze_inert_without_key_records_no_event(client, monkeypatch):
    from backend.transcript import repository as trepo
    from backend.transcript import provenance as prov
    import backend.api.ai_review as air

    monkeypatch.setattr(air.ai_client, "is_available", lambda: False)
    job_id = _seed(trepo)
    res = client.post(f"/api/ai-review/jobs/{job_id}/analyze")
    assert res.status_code == 200
    assert res.json()["available"] is False
    # Inert run records nothing.
    assert not [e for e in prov.list_events(job_id) if e["event_type"] == "ai_review_run"]
