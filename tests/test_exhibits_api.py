from __future__ import annotations


def test_list_exhibits_unknown_job_404(client):
    res = client.get("/api/exhibits/jobs/does-not-exist")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_create_exhibit_unknown_job_404(client):
    res = client.post(
        "/api/exhibits/jobs/does-not-exist",
        json={
            "exhibit_number": "1",
            "exhibit_title": "Photo",
            "anchor_utterance_id": "utt-1",
        },
    )
    assert res.status_code == 404


def test_create_exhibit_rejects_unknown_anchor(client, sample_job_with_content):
    res = client.post(
        f"/api/exhibits/jobs/{sample_job_with_content}",
        json={
            "exhibit_number": "1",
            "exhibit_title": "Photo",
            "anchor_utterance_id": "utt-does-not-exist",
        },
    )
    assert res.status_code == 400
    detail = res.json()["detail"].lower()
    assert "utterance" in detail
    assert "does not belong to job" in detail


def test_duplicate_exhibit_number_returns_409(client, sample_job_with_content):
    job_id = sample_job_with_content
    first = client.post(
        f"/api/exhibits/jobs/{job_id}",
        json={
            "exhibit_number": "5",
            "exhibit_title": "Contract",
            "anchor_utterance_id": "utt-2",
        },
    )
    assert first.status_code == 201

    dup = client.post(
        f"/api/exhibits/jobs/{job_id}",
        json={
            "exhibit_number": "5",
            "exhibit_title": "Another Contract",
            "anchor_utterance_id": "utt-3",
        },
    )
    assert dup.status_code == 409
    assert "already exists" in dup.json()["detail"].lower()


def test_exhibit_crud_records_provenance(client, sample_job_with_content):
    job_id = sample_job_with_content
    created = client.post(
        f"/api/exhibits/jobs/{job_id}",
        json={
            "exhibit_number": "8",
            "exhibit_title": "Dispatch Log",
            "offering_attorney": "Mr. Vance",
            "anchor_utterance_id": "utt-4",
        },
    )
    assert created.status_code == 201
    exhibit = created.json()

    updated = client.put(
        f"/api/exhibits/{exhibit['exhibit_id']}",
        json={
            "exhibit_title": "Updated Dispatch Log",
            "anchor_utterance_id": "utt-5",
        },
    )
    assert updated.status_code == 200

    deleted = client.delete(f"/api/exhibits/{exhibit['exhibit_id']}")
    assert deleted.status_code == 204

    provenance = client.get(f"/api/transcripts/jobs/{job_id}/provenance")
    assert provenance.status_code == 200
    event_types = [ev["event_type"] for ev in provenance.json()["events"]]
    assert "exhibit_created" in event_types
    assert "exhibit_updated" in event_types
    assert "exhibit_deleted" in event_types
