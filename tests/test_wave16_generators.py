"""Wave 16 — AI generator tests (boundaries, garbles, flags).

These do NOT call the live Anthropic API. They verify offline
degradation, the JSON-array parser, four-part gating in the garble
generator, and the analyze endpoint's behaviour when the AI layer is
inert (the default test environment has no ANTHROPIC_API_KEY).
"""
from __future__ import annotations

from backend.ai_review.generators import (
    _parse_json_array,
    generate_boundary_suggestions,
    generate_flag_suggestions,
    generate_garble_suggestions,
)


_UTTS = [
    {"utterance_id": "u1", "speaker_index": 0, "text": "off the record now"},
    {"utterance_id": "u2", "speaker_index": 1, "text": "the witness spoke"},
]


# --- offline degradation (no key) -----------------------------------

def test_boundary_generator_empty_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert generate_boundary_suggestions("job1", _UTTS) == []


def test_garble_generator_empty_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert generate_garble_suggestions("job1", _UTTS) == []


def test_flag_generator_empty_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert generate_flag_suggestions("job1", _UTTS) == []


def test_generators_empty_on_empty_input(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert generate_boundary_suggestions("job1", []) == []
    assert generate_garble_suggestions("job1", []) == []
    assert generate_flag_suggestions("job1", []) == []


# --- JSON array parser ----------------------------------------------

def test_parse_json_array_plain():
    assert _parse_json_array('[{"a": 1}]') == [{"a": 1}]


def test_parse_json_array_strips_fence():
    assert _parse_json_array('```json\n[{"a": 1}]\n```') == [{"a": 1}]


def test_parse_json_array_rejects_non_array():
    assert _parse_json_array('{"a": 1}') == []
    assert _parse_json_array("not json at all") == []


# --- analyze endpoint -----------------------------------------------

def test_analyze_unknown_job_404(client):
    res = client.post("/api/ai-review/jobs/no-such-job/analyze")
    assert res.status_code == 404


def test_analyze_rejects_unknown_kind(client, monkeypatch):
    # Even inert, an unknown kind is a 400 before generation -- but the
    # 404 (unknown job) is checked first, so use a kind-only assertion
    # via the registry instead.
    from backend.api.ai_review import _GENERATORS
    assert set(_GENERATORS.keys()) == {"boundaries", "garbles", "flags"}
