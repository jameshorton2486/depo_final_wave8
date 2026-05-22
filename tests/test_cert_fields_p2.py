"""Phase 2 tests: /api/depo-meta endpoints."""
from __future__ import annotations

import json

import pytest

from backend.transcript import repository as trepo


def _make_job(client) -> str:
    job = trepo.create_job({"source_filename": "cert_test.mp3"})
    return job["job_id"]


def test_get_unknown_job_404(client):
    res = client.get("/api/depo-meta/jobs/no-such-job")
    assert res.status_code == 404


def test_get_job_with_no_meta_returns_defaults(client):
    job_id = _make_job(client)
    res = client.get(f"/api/depo-meta/jobs/{job_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["job_id"] == job_id
    assert body["volume"] == "1"
    assert body["examination_disposition"] is None
    assert body["time_per_party"] == []
    assert body["also_present"] == []


def test_put_unknown_job_404(client):
    res = client.put("/api/depo-meta/jobs/no-such-job", json={})
    assert res.status_code == 404


def test_put_creates_meta(client):
    job_id = _make_job(client)
    payload = {
        "volume": "2",
        "examination_disposition": "waived",
        "officer_charges_amount": "475.00",
        "charges_party": "Plaintiff",
    }
    res = client.put(f"/api/depo-meta/jobs/{job_id}", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["volume"] == "2"
    assert body["examination_disposition"] == "waived"
    assert body["officer_charges_amount"] == "475.00"
    assert body["charges_party"] == "Plaintiff"


def test_put_updates_partial(client):
    job_id = _make_job(client)
    client.put(f"/api/depo-meta/jobs/{job_id}",
               json={"volume": "1", "charges_party": "Plaintiff"})
    res = client.put(f"/api/depo-meta/jobs/{job_id}",
                     json={"charges_party": "Defendant"})
    assert res.status_code == 200
    body = res.json()
    assert body["charges_party"] == "Defendant"
    assert body["volume"] == "1"   # unchanged


def test_put_time_per_party_list(client):
    job_id = _make_job(client)
    tpp = [
        {"party": "Plaintiff Counsel", "duration": "1:45"},
        {"party": "Defense Counsel", "duration": "0:30"},
    ]
    res = client.put(f"/api/depo-meta/jobs/{job_id}",
                     json={"time_per_party": tpp})
    assert res.status_code == 200
    body = res.json()
    assert body["time_per_party"] == tpp


def test_put_also_present_list(client):
    job_id = _make_job(client)
    ap = [{"name": "Dr. Emily Walsh", "role": "Medical Expert"}]
    res = client.put(f"/api/depo-meta/jobs/{job_id}",
                     json={"also_present": ap})
    assert res.status_code == 200
    assert res.json()["also_present"] == ap


def test_get_after_put_reflects_values(client):
    job_id = _make_job(client)
    client.put(f"/api/depo-meta/jobs/{job_id}", json={
        "examination_disposition": "retained",
        "certificate_service_date": "June 5, 2026",
    })
    res = client.get(f"/api/depo-meta/jobs/{job_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["examination_disposition"] == "retained"
    assert body["certificate_service_date"] == "June 5, 2026"


def test_put_empty_body_creates_row_with_defaults(client):
    job_id = _make_job(client)
    res = client.put(f"/api/depo-meta/jobs/{job_id}", json={})
    assert res.status_code == 200
    assert res.json()["volume"] == "1"
