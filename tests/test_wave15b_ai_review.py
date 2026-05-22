"""Wave 15b — AI review layer tests.

These tests do NOT call the live Anthropic API. They verify the
suggestion model, the four-part test, the review queue, graceful
no-key degradation, and the endpoints' behaviour when the AI layer is
inert (the default test environment has no ANTHROPIC_API_KEY).
"""
from __future__ import annotations

import os

from backend.ai_review import client as ai_client
from backend.ai_review.four_part_test import evaluate
from backend.ai_review.speaker_map import _parse_map
from backend.ai_review.suggestions import (
    KIND_FLAG,
    KIND_GARBLE,
    KIND_SPEAKER_MAP,
    STATUS_APPROVED,
    STATUS_PENDING,
    Suggestion,
)


# --- four-part test --------------------------------------------------

def test_four_part_passes_when_all_true():
    r = evaluate(True, True, True, True)
    assert r.passes
    assert r.failed_conditions() == []


def test_four_part_fails_when_any_false():
    r = evaluate(True, True, False, True)
    assert not r.passes
    assert "may alter testimony meaning" in r.failed_conditions()


def test_four_part_lists_all_failures():
    r = evaluate(False, False, True, True)
    assert len(r.failed_conditions()) == 2


# --- suggestion model -----------------------------------------------

def test_failed_four_part_suggestion_is_not_applicable():
    s = Suggestion(job_id="j1", kind=KIND_GARBLE, reason="maybe",
                   four_part_pass=False)
    # A suggestion that failed the test is a flag, not an applicable edit.
    assert not s.is_applicable_edit


def test_passed_four_part_garble_is_applicable():
    s = Suggestion(job_id="j1", kind=KIND_GARBLE, reason="clear artifact",
                   four_part_pass=True)
    assert s.is_applicable_edit


def test_flag_kind_is_never_applicable_even_if_passed():
    s = Suggestion(job_id="j1", kind=KIND_FLAG, reason="review this",
                   four_part_pass=True)
    assert not s.is_applicable_edit


def test_suggestion_has_stable_id():
    s = Suggestion(job_id="j1", kind=KIND_FLAG, reason="x")
    assert s.suggestion_id
    assert s.to_dict()["suggestion_id"] == s.suggestion_id


# --- client graceful degradation ------------------------------------

def test_is_available_false_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ai_client.is_available() is False


def test_call_claude_raises_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import pytest
    with pytest.raises(ai_client.AIUnavailableError):
        ai_client.call_claude("sys", "user")


# --- speaker-map JSON parsing ---------------------------------------

def test_parse_map_plain_json():
    out = _parse_map('{"0": "THE REPORTER", "1": "MR. NUNEZ"}')
    assert out == {"0": "THE REPORTER", "1": "MR. NUNEZ"}


def test_parse_map_strips_markdown_fence():
    out = _parse_map('```json\n{"0": "THE WITNESS"}\n```')
    assert out == {"0": "THE WITNESS"}


def test_parse_map_rejects_non_json():
    assert _parse_map("I think speaker 0 is the reporter") == {}


# --- review queue (DB) ----------------------------------------------

def test_review_queue_save_and_list(client):
    from backend.ai_review import review_queue
    s = Suggestion(job_id="job-q1", kind=KIND_SPEAKER_MAP,
                   reason="test", payload={"speaker_map": {"0": "THE REPORTER"}})
    review_queue.save_suggestions([s])
    listed = review_queue.list_suggestions("job-q1")
    assert len(listed) == 1
    assert listed[0].kind == KIND_SPEAKER_MAP
    assert listed[0].payload["speaker_map"]["0"] == "THE REPORTER"


def test_review_queue_approve(client):
    from backend.ai_review import review_queue
    s = Suggestion(job_id="job-q2", kind=KIND_FLAG, reason="review")
    review_queue.save_suggestions([s])
    assert review_queue.set_status(s.suggestion_id, STATUS_APPROVED)
    got = review_queue.get_suggestion(s.suggestion_id)
    assert got.status == STATUS_APPROVED


# --- endpoints ------------------------------------------------------

def test_ai_status_endpoint(client):
    res = client.get("/api/ai-review/status")
    assert res.status_code == 200
    # Test env has no key -> inert.
    assert res.json()["available"] is False


def test_speaker_map_endpoint_inert_without_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    res = client.post("/api/ai-review/jobs/no-such-job/speaker-map")
    # Unknown job -> 404 before the AI layer is even consulted.
    assert res.status_code == 404


def test_suggestions_list_endpoint(client):
    res = client.get("/api/ai-review/jobs/some-job/suggestions")
    assert res.status_code == 200
    assert res.json()["count"] == 0


def test_approve_unknown_suggestion_404(client):
    res = client.post("/api/ai-review/suggestions/nope/approve")
    assert res.status_code == 404
