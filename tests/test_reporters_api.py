"""Tests for the /api/reporters router."""
from __future__ import annotations


def test_list_reporters_empty(client):
    res = client.get("/api/reporters")
    assert res.status_code == 200
    assert res.json() == {"reporters": [], "count": 0}


def test_create_reporter(client, sample_reporter_payload):
    res = client.post("/api/reporters", json=sample_reporter_payload)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["full_name"] == "Richard Vance, CSR"
    assert body["csr_number"] == "3465"
    assert body["csr_expiration"] == "2027-12-31"
    assert body["firm_registration_number"] == "10698"
    assert body["csr_state"] == "TX"  # default
    assert body["reporter_id"]


def test_create_reporter_requires_full_name(client):
    res = client.post("/api/reporters", json={"csr_number": "X"})
    assert res.status_code == 422


def test_read_reporter(client, sample_reporter_payload):
    rid = client.post("/api/reporters", json=sample_reporter_payload).json()["reporter_id"]
    res = client.get(f"/api/reporters/{rid}")
    assert res.status_code == 200
    assert res.json()["reporter_id"] == rid


def test_read_unknown_reporter_returns_404(client):
    res = client.get("/api/reporters/no-such")
    assert res.status_code == 404


def test_update_reporter(client, sample_reporter_payload):
    rid = client.post("/api/reporters", json=sample_reporter_payload).json()["reporter_id"]
    res = client.put(f"/api/reporters/{rid}", json={"csr_number": "9999"})
    assert res.status_code == 200
    body = res.json()
    assert body["csr_number"] == "9999"
    # Other fields preserved
    assert body["full_name"] == "Richard Vance, CSR"


def test_delete_reporter(client, sample_reporter_payload):
    rid = client.post("/api/reporters", json=sample_reporter_payload).json()["reporter_id"]
    res = client.delete(f"/api/reporters/{rid}")
    assert res.status_code == 204
    assert client.get(f"/api/reporters/{rid}").status_code == 404


def test_reporter_can_be_linked_from_session(
    client, created_case, sample_session_payload, sample_reporter_payload
):
    rid = client.post("/api/reporters", json=sample_reporter_payload).json()["reporter_id"]
    sample_session_payload["case_id"] = created_case["case_id"]
    sample_session_payload["reporter_id"] = rid
    res = client.post("/api/sessions", json=sample_session_payload)
    assert res.status_code == 201
    assert res.json()["reporter_id"] == rid
