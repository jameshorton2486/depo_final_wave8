"""Tests for the /api/cases router."""
from __future__ import annotations


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["application"] == "DEPO-PRO"


def test_list_cases_empty(client):
    res = client.get("/api/cases")
    assert res.status_code == 200
    body = res.json()
    assert body == {"cases": [], "count": 0}


def test_create_case(client, sample_case_payload):
    res = client.post("/api/cases", json=sample_case_payload)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["case_number_value"] == sample_case_payload["case_number_value"]
    assert body["caption_full"] == sample_case_payload["caption_full"]
    assert body["jurisdiction_type"] == "texas_state"  # default
    assert body["case_number_label"] == "cause_no"  # default
    assert body["state"] == "Texas"
    assert body["case_id"]  # UUID present
    assert body["created_at"]
    assert body["updated_at"]


def test_create_then_read(client, sample_case_payload):
    create_res = client.post("/api/cases", json=sample_case_payload)
    case_id = create_res.json()["case_id"]

    read_res = client.get(f"/api/cases/{case_id}")
    assert read_res.status_code == 200
    assert read_res.json() == create_res.json()


def test_create_then_update(client, sample_case_payload):
    create_res = client.post("/api/cases", json=sample_case_payload)
    case_id = create_res.json()["case_id"]

    update_res = client.put(
        f"/api/cases/{case_id}",
        json={"county": "Tarrant County"},
    )
    assert update_res.status_code == 200
    body = update_res.json()
    assert body["county"] == "Tarrant County"
    # Other fields preserved
    assert body["caption_full"] == sample_case_payload["caption_full"]
    assert body["case_number_value"] == sample_case_payload["case_number_value"]


def test_update_unknown_case_returns_404(client):
    res = client.put("/api/cases/no-such-id", json={"county": "X"})
    assert res.status_code == 404


def test_read_unknown_case_returns_404(client):
    res = client.get("/api/cases/no-such-id")
    assert res.status_code == 404


def test_post_missing_required_field_returns_422(client):
    res = client.post("/api/cases", json={})
    assert res.status_code == 422


def test_post_blank_required_field_returns_422(client):
    res = client.post("/api/cases", json={"case_number_value": ""})
    assert res.status_code == 422


def test_list_after_creates_newest_first(client, sample_case_payload):
    first = client.post("/api/cases", json=sample_case_payload).json()
    second_payload = {**sample_case_payload, "case_number_value": "2024-CI-99999"}
    second = client.post("/api/cases", json=second_payload).json()

    listing = client.get("/api/cases").json()
    assert listing["count"] == 2
    ids = [c["case_id"] for c in listing["cases"]]
    # Newest first
    assert ids[0] == second["case_id"]
    assert ids[1] == first["case_id"]


def test_delete_case(client, sample_case_payload):
    case_id = client.post("/api/cases", json=sample_case_payload).json()["case_id"]
    del_res = client.delete(f"/api/cases/{case_id}")
    assert del_res.status_code == 204
    follow_up = client.get(f"/api/cases/{case_id}")
    assert follow_up.status_code == 404


def test_invalid_jurisdiction_returns_422(client):
    res = client.post(
        "/api/cases",
        json={"case_number_value": "X", "jurisdiction_type": "mars"},
    )
    assert res.status_code == 422


def test_partial_update_preserves_other_columns(client, sample_case_payload):
    case_id = client.post("/api/cases", json=sample_case_payload).json()["case_id"]
    before = client.get(f"/api/cases/{case_id}").json()

    client.put(f"/api/cases/{case_id}", json={"state": "Oklahoma"})
    after = client.get(f"/api/cases/{case_id}").json()

    assert after["state"] == "Oklahoma"
    assert after["county"] == before["county"]
    assert after["caption_full"] == before["caption_full"]
    assert after["case_number_value"] == before["case_number_value"]
