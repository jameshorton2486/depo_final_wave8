"""Tests for the /api/sessions router."""
from __future__ import annotations


def test_list_sessions_for_nonexistent_case(client):
    res = client.get("/api/sessions", params={"case_id": "no-such"})
    assert res.status_code == 200
    assert res.json() == {"sessions": [], "count": 0}


def test_create_session_requires_case_id_query_param(client):
    res = client.get("/api/sessions")
    assert res.status_code == 422  # missing required query parameter


def test_create_session(client, created_case, sample_session_payload):
    sample_session_payload["case_id"] = created_case["case_id"]
    res = client.post("/api/sessions", json=sample_session_payload)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["case_id"] == created_case["case_id"]
    assert body["witness_name"] == "Dr. Donald Leifer"
    assert body["location_type"] == "in_person"  # default
    assert body["service_type"] == "CR_only"  # default
    assert body["outcome"] == "pending"  # default
    assert body["custodial_attorney_name"] == "Ms. Elizabeth R. Flora, Esq."
    assert body["requesting_party_name"] == "Vance & Partners LLP"


def test_create_session_against_missing_case_returns_400(client, sample_session_payload):
    sample_session_payload["case_id"] = "no-such-case"
    res = client.post("/api/sessions", json=sample_session_payload)
    assert res.status_code == 400
    assert "does not exist" in res.json()["detail"]


def test_create_session_missing_witness_returns_422(client, created_case):
    res = client.post(
        "/api/sessions",
        json={"case_id": created_case["case_id"], "scheduled_at": "2026-01-01T00:00:00"},
    )
    assert res.status_code == 422


def test_read_session(client, created_case, sample_session_payload):
    sample_session_payload["case_id"] = created_case["case_id"]
    create = client.post("/api/sessions", json=sample_session_payload).json()
    res = client.get(f"/api/sessions/{create['session_id']}")
    assert res.status_code == 200
    assert res.json() == create


def test_read_unknown_session_returns_404(client):
    res = client.get("/api/sessions/no-such")
    assert res.status_code == 404


def test_update_session(client, created_case, sample_session_payload):
    sample_session_payload["case_id"] = created_case["case_id"]
    sid = client.post("/api/sessions", json=sample_session_payload).json()["session_id"]
    res = client.put(
        f"/api/sessions/{sid}",
        json={"location_address": "500 Different St"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["location_address"] == "500 Different St"
    # Other fields preserved
    assert body["witness_name"] == "Dr. Donald Leifer"


def test_list_sessions_filtered_by_case(client, created_case, sample_session_payload):
    sample_session_payload["case_id"] = created_case["case_id"]
    client.post("/api/sessions", json=sample_session_payload)
    res = client.get("/api/sessions", params={"case_id": created_case["case_id"]})
    assert res.status_code == 200
    assert res.json()["count"] == 1


def test_delete_session(client, created_case, sample_session_payload):
    sample_session_payload["case_id"] = created_case["case_id"]
    sid = client.post("/api/sessions", json=sample_session_payload).json()["session_id"]
    res = client.delete(f"/api/sessions/{sid}")
    assert res.status_code == 204
    follow_up = client.get(f"/api/sessions/{sid}")
    assert follow_up.status_code == 404


def test_invalid_location_type_returns_422(client, created_case, sample_session_payload):
    sample_session_payload["case_id"] = created_case["case_id"]
    sample_session_payload["location_type"] = "underwater"
    res = client.post("/api/sessions", json=sample_session_payload)
    assert res.status_code == 422


def test_session_cascades_when_case_deleted(client, created_case, sample_session_payload):
    sample_session_payload["case_id"] = created_case["case_id"]
    sid = client.post("/api/sessions", json=sample_session_payload).json()["session_id"]
    client.delete(f"/api/cases/{created_case['case_id']}")
    res = client.get(f"/api/sessions/{sid}")
    assert res.status_code == 404
