from __future__ import annotations

from backend.ai_review import cross_speaker_flags, review_queue
from backend.ai_review.suggestions import STATUS_INFORMATIONAL
from backend.transcript import repository as trepo
from backend.transcript_state import snapshot_repo
from backend.transcript_state.model import Snapshot


def _create_cross_speaker_job() -> str:
    job = trepo.create_job({"source_filename": "cross-speaker.mp3"})
    job_id = job["job_id"]
    speakers = [
        {
            "speaker_row_id": f"spk-{idx}",
            "speaker_index": idx,
            "speaker_label": f"Speaker {idx}",
            "assigned_name": None,
            "speaker_role": None,
            "word_count": 0,
        }
        for idx in (0, 1, 2)
    ]
    utterances = [
        {
            "utterance_id": "utt-clean",
            "utterance_index": 0,
            "speaker_index": 0,
            "speaker_label": "Speaker 0",
            "start_time": 0.0,
            "end_time": 1.0,
            "text": "All one speaker here.",
            "avg_confidence": 0.99,
        },
        {
            "utterance_id": "utt-mid",
            "utterance_index": 1,
            "speaker_index": 0,
            "speaker_label": "Speaker 0",
            "start_time": 1.0,
            "end_time": 2.0,
            "text": "Question answer fused together.",
            "avg_confidence": 0.99,
        },
        {
            "utterance_id": "utt-flicker",
            "utterance_index": 2,
            "speaker_index": 0,
            "speaker_label": "Speaker 0",
            "start_time": 2.0,
            "end_time": 3.0,
            "text": "Mostly one speaker with a flicker.",
            "avg_confidence": 0.99,
        },
        {
            "utterance_id": "utt-short",
            "utterance_index": 3,
            "speaker_index": 2,
            "speaker_label": "Speaker 2",
            "start_time": 3.0,
            "end_time": 4.0,
            "text": "Yes okay thanks.",
            "avg_confidence": 0.99,
        },
    ]
    words = []

    def add_words(utterance_id: str, speaker_indices: list[int], tokens: list[str], start: float) -> None:
        for idx, (speaker_index, token) in enumerate(zip(speaker_indices, tokens)):
            words.append(
                {
                    "word_id": f"{utterance_id}-w{idx}",
                    "utterance_id": utterance_id,
                    "word_index": len(words),
                    "raw_text": token,
                    "working_text": None,
                    "speaker_index": speaker_index,
                    "start_time": start + idx * 0.1,
                    "end_time": start + idx * 0.1 + 0.08,
                    "confidence": 0.99,
                    "is_filler": 0,
                    "reviewed": 0,
                }
            )

    add_words("utt-clean", [0, 0, 0, 0], ["All", "one", "speaker", "here."], 0.0)
    add_words("utt-mid", [0, 0, 1, 1, 1, 1], ["Question", "part", "answer", "part", "fused", "together."], 1.0)
    add_words("utt-flicker", [0, 0, 0, 0, 0, 1], ["Mostly", "one", "speaker", "with", "a", "flicker."], 2.0)
    add_words("utt-short", [2, 0, 0], ["Yes", "okay", "thanks."], 3.0)

    trepo.save_transcript_content(job_id, speakers=speakers, utterances=utterances, words=words)
    return job_id


def test_detector_classifies_expected_cross_speaker_cases(client):
    job_id = _create_cross_speaker_job()
    before_utts = trepo.get_utterances(job_id, layer="raw")
    before_words = trepo.get_words(job_id)

    flags = cross_speaker_flags.detect_for_job(job_id)
    categories = {flag.utterance_id: flag.flag_category for flag in flags}

    assert categories == {
        "utt-mid": cross_speaker_flags.FLAG_MID_UTTERANCE_CHANGE,
        "utt-flicker": cross_speaker_flags.FLAG_FLICKER,
        "utt-short": cross_speaker_flags.FLAG_SHORT_TURN,
    }
    assert trepo.get_utterances(job_id, layer="raw") == before_utts
    assert trepo.get_words(job_id) == before_words


def test_lazy_compute_persist_and_reuse(client):
    job_id = _create_cross_speaker_job()
    before_utts = trepo.get_utterances(job_id, layer="raw")
    before_words = trepo.get_words(job_id)
    summary = cross_speaker_flags.ensure_persisted(job_id)

    assert summary.total == 3
    stored = review_queue.list_suggestions(job_id)
    assert len(stored) == 4  # 3 review flags + 1 detector marker
    assert trepo.get_utterances(job_id, layer="raw") == before_utts
    assert trepo.get_words(job_id) == before_words

    again = cross_speaker_flags.ensure_persisted(job_id)
    assert again.total == 3
    assert len(review_queue.list_suggestions(job_id)) == 4


def test_speaker_mapping_load_persists_and_apply_invalidates_then_recomputes(client):
    job_id = _create_cross_speaker_job()

    first = client.get(f"/api/transcripts/jobs/{job_id}/speaker-mapping")
    assert first.status_code == 200
    body = first.json()
    assert body["cross_speaker_flags"]["total"] == 3
    assert body["cross_speaker_flags"]["mid_utterance_change"] == 1
    assert body["cross_speaker_flags"]["flicker"] == 1
    assert body["cross_speaker_flags"]["short_turn"] == 1
    assert len(review_queue.list_suggestions(job_id)) == 4

    listed = client.get(f"/api/ai-review/jobs/{job_id}/suggestions")
    assert listed.status_code == 200
    assert listed.json()["count"] == 3

    payload = {"participants": []}
    for idx, p in enumerate(body["participants"]):
        payload["participants"].append(
            {
                "name": f"Person {idx}",
                "role": p["role"],
                "speaker_indices": p["speaker_indices"],
                "sort_order": idx,
            }
        )

    applied = client.post(
        f"/api/transcripts/jobs/{job_id}/speaker-mapping/apply",
        json=payload,
    )
    assert applied.status_code == 200
    assert review_queue.list_suggestions(job_id) == []

    second = client.get(f"/api/transcripts/jobs/{job_id}/speaker-mapping")
    assert second.status_code == 200
    assert second.json()["cross_speaker_flags"]["total"] == 3
    assert len(review_queue.list_suggestions(job_id)) == 4


def test_certified_job_flags_are_locked_informational(client):
    job_id = _create_cross_speaker_job()
    snap = Snapshot(job_id=job_id, state_hash="h", state={})
    snapshot_repo.save_snapshot(snap)
    assert snapshot_repo.lock_snapshot(snap.snapshot_id)

    res = client.get(f"/api/transcripts/jobs/{job_id}/speaker-mapping")
    assert res.status_code == 200
    summary = res.json()["cross_speaker_flags"]
    assert summary["certified_locked"] is True
    assert summary["informational_only"] is True

    visible = client.get(f"/api/ai-review/jobs/{job_id}/suggestions").json()["suggestions"]
    assert len(visible) == 3
    assert all(s["status"] == STATUS_INFORMATIONAL for s in visible)
    assert all(s["payload"]["locked_informational"] is True for s in visible)


def test_certified_after_the_fact_promotes_pending_flags_to_informational(client):
    job_id = _create_cross_speaker_job()

    first = client.get(f"/api/transcripts/jobs/{job_id}/speaker-mapping")
    assert first.status_code == 200
    visible = client.get(f"/api/ai-review/jobs/{job_id}/suggestions").json()["suggestions"]
    assert visible
    assert all(s["status"] == "pending" for s in visible)

    snap = Snapshot(job_id=job_id, state_hash="h", state={})
    snapshot_repo.save_snapshot(snap)
    assert snapshot_repo.lock_snapshot(snap.snapshot_id)

    summary = cross_speaker_flags.ensure_persisted(job_id)
    assert summary.certified_locked is True
    promoted = client.get(f"/api/ai-review/jobs/{job_id}/suggestions").json()["suggestions"]
    assert promoted
    assert all(s["status"] == STATUS_INFORMATIONAL for s in promoted)
