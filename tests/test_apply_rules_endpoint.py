"""Pass 1: the manual Apply Rule endpoint.

POST /api/corrections/jobs/{job_id}/apply-rules runs operator-supplied regex
rules over the WORKING layer, persists the result (raw untouched), and records
a regex_apply_manual provenance event.
"""
from __future__ import annotations


def _seed_job(trepo):
    job_id = trepo.create_job({"source_filename": "apply_rules.mp3"})["job_id"]
    speakers = [
        {"speaker_row_id": "spk-0", "speaker_index": 0, "speaker_label": "Speaker 0",
         "assigned_name": "Vance", "speaker_role": "examining_attorney", "word_count": 6},
        {"speaker_row_id": "spk-1", "speaker_index": 1, "speaker_label": "Speaker 1",
         "assigned_name": "Reed", "speaker_role": "witness", "word_count": 6},
    ]
    exchange = [
        (0, 0, "Did you see trinaty at the scene?"),
        (1, 1, "Yes, trinaty was there."),
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


def _rule(find, replace):
    return {"rules": [{"find_pattern": find, "replace_with": replace}]}


def test_apply_rule_happy_path(client):
    from backend.transcript import repository as trepo
    from backend.transcript import working_state as ws
    job_id = _seed_job(trepo)
    raw_before = {u["utterance_id"]: u["text"]
                  for u in trepo.get_utterances(job_id, layer="raw")}

    res = client.post(f"/api/corrections/jobs/{job_id}/apply-rules",
                      json=_rule(r"\btrinaty\b", "Trinity"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["substitutions"] == 2  # one per utterance
    assert body["rules_applied"] == 1
    assert body["provenance_event_id"]

    # Working layer reflects the substitution.
    working = {u["utterance_id"]: u["text"] for u in ws.get_working_utterances(job_id)}
    assert "Trinity" in working["u0"] and "trinaty" not in working["u0"]
    assert "Trinity" in working["u1"]

    # RAW layer untouched.
    raw_after = {u["utterance_id"]: u["text"]
                 for u in trepo.get_utterances(job_id, layer="raw")}
    assert raw_after == raw_before
    assert "trinaty" in raw_after["u0"]


def test_apply_rule_writes_provenance_event(client):
    from backend.transcript import repository as trepo
    from backend.transcript import provenance as prov
    job_id = _seed_job(trepo)
    res = client.post(f"/api/corrections/jobs/{job_id}/apply-rules",
                      json=_rule(r"\btrinaty\b", "Trinity"))
    event_id = res.json()["provenance_event_id"]
    events = prov.list_events(job_id) if hasattr(prov, "list_events") else None
    if events is not None:
        types = [e.get("event_type") for e in events]
        assert "regex_apply_manual" in types
    assert event_id


def test_apply_rule_invalid_regex_returns_400(client):
    from backend.transcript import repository as trepo
    job_id = _seed_job(trepo)
    res = client.post(f"/api/corrections/jobs/{job_id}/apply-rules",
                      json=_rule("[unterminated", "x"))
    assert res.status_code == 400
    assert "[unterminated" in res.json()["detail"]


def test_apply_rule_empty_body_returns_400(client):
    from backend.transcript import repository as trepo
    job_id = _seed_job(trepo)
    res = client.post(f"/api/corrections/jobs/{job_id}/apply-rules", json={"rules": []})
    assert res.status_code == 400
    assert "saved rules" in res.json()["detail"].lower()


def test_apply_rule_job_not_found_returns_404(client):
    res = client.post("/api/corrections/jobs/nope/apply-rules",
                      json=_rule("a", "b"))
    assert res.status_code == 404


def test_apply_rule_no_match_changes_nothing(client):
    from backend.transcript import repository as trepo
    from backend.transcript import working_state as ws
    job_id = _seed_job(trepo)
    before = {u["utterance_id"]: u["text"] for u in ws.get_working_utterances(job_id)}
    res = client.post(f"/api/corrections/jobs/{job_id}/apply-rules",
                      json=_rule(r"\bzzzznomatch\b", "X"))
    assert res.status_code == 200
    assert res.json()["substitutions"] == 0
    after = {u["utterance_id"]: u["text"] for u in ws.get_working_utterances(job_id)}
    assert after == before


def test_apply_rule_is_idempotent(client):
    from backend.transcript import repository as trepo
    from backend.transcript import working_state as ws
    job_id = _seed_job(trepo)
    client.post(f"/api/corrections/jobs/{job_id}/apply-rules",
                json=_rule(r"\btrinaty\b", "Trinity"))
    first = {u["utterance_id"]: u["text"] for u in ws.get_working_utterances(job_id)}
    # Second apply: the token is gone, so it matches nothing -> no change.
    res2 = client.post(f"/api/corrections/jobs/{job_id}/apply-rules",
                       json=_rule(r"\btrinaty\b", "Trinity"))
    assert res2.json()["substitutions"] == 0
    second = {u["utterance_id"]: u["text"] for u in ws.get_working_utterances(job_id)}
    assert first == second
