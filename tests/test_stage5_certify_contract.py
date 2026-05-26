"""Stage 5 Certify — backend contract test.

Mirrors the exact call sequence the UI now performs:
  save cert fields -> create snapshot -> lock snapshot ->
  assemble package -> certify package

Positive path: a fully-populated job produces a CERTIFIED package with
all fields the UI depends on.

Negative path: an empty-body job returns 422 with a detail string the
UI error area can display.

NOTE: The test fixture (sample_job_with_content) creates a bare job with
utterances but no linked case/session/reporter, so the server cannot
auto-populate required metadata from the DB. Both assemble and certify
receive explicit metadata here — exactly as the UI would pass if the
job had no DB associations. In production the DB auto-population fills
these fields automatically; the API contract (request shape, response
shape, status codes) is identical either way.
"""
from __future__ import annotations

# Minimal metadata satisfying the validator — mirrors what an operator
# would have entered in Stages 1–3 before reaching Stage 5.
_VALID_METADATA = {
    "cause_number": "2024-CI-09912",
    "caption": "Acme Corp. v. Dana Reed",
    "court": "288th Judicial District Court, Bexar County, Texas",
    "witness_name": "Dana Reed",
    "reporter_name": "Miah Bardot",
    "reporter_csr_number": "TX-10423",
    "proceedings_date": "May 21, 2026",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_and_lock_snapshot(client, job_id: str) -> str:
    """Create a CERTIFIED snapshot and lock it; return snapshot_id."""
    snap_res = client.post(
        f"/api/snapshots/jobs/{job_id}",
        json={"category": "CERTIFIED"},
    )
    assert snap_res.status_code == 200, snap_res.text
    snap_id = snap_res.json()["snapshot_id"]
    lock_res = client.post(f"/api/snapshots/{snap_id}/lock")
    assert lock_res.status_code == 200, lock_res.text
    return snap_id


# ---------------------------------------------------------------------------
# Positive path: full workflow produces a CERTIFIED package
# ---------------------------------------------------------------------------

def test_certify_full_workflow_matches_ui_sequence(client, sample_job_with_content):
    """UI call sequence succeeds end-to-end on a populated job.

    Asserts every response field the UI reads so that a backend change
    that drops a field breaks this test immediately.
    """
    job_id = sample_job_with_content

    # Step 1: cert-fields save (depo-meta PUT) — UI calls _saveCertFields()
    meta_res = client.put(
        f"/api/depo-meta/jobs/{job_id}",
        json={"volume": "1", "examination_disposition": "waived"},
    )
    assert meta_res.status_code == 200

    # Step 2+3: create + lock snapshot
    snap_id = _create_and_lock_snapshot(client, job_id)

    # Step 4: assemble — UI calls api.assemblePackage(jobId, snapshotId)
    # Pass metadata explicitly; in production the server auto-populates from DB.
    assemble_res = client.post(
        f"/api/packages/jobs/{job_id}",
        json={"snapshot_id": snap_id, "metadata": _VALID_METADATA, "freelance": True},
    )
    assert assemble_res.status_code == 200, assemble_res.text
    assembled = assemble_res.json()

    # Fields the UI reads from assemble response
    package_id = assembled["package_id"]
    assert assembled["package_state"] == "DRAFT"
    assert "generation_report" in assembled
    assert assembled["generation_report"]["body_pages"] >= 1

    # Step 5: certify — UI calls api.certifyPackage(packageId)
    certify_res = client.post(
        f"/api/packages/{package_id}/certify",
        json={"metadata": _VALID_METADATA},
    )
    assert certify_res.status_code == 200, certify_res.text
    certified = certify_res.json()

    # Fields the UI reads from certify response (must all be present)
    assert certified["certified"] is True
    assert certified["package_id"] == package_id
    assert certified["package_state"] == "CERTIFIED"
    assert certified["manifest_hash"], "manifest_hash must be a non-empty string"
    assert certified["certified_at"], "certified_at must be a non-empty ISO datetime"
    assert certified["generation_report"]["certification_status"] == "CERTIFIED"
    assert certified["generation_report"]["validation_passed"] is True


# ---------------------------------------------------------------------------
# Negative path: empty-body job returns 422 with a displayable detail string
# ---------------------------------------------------------------------------

def test_certify_empty_body_returns_422_with_detail(client, sample_job):
    """Certifying an empty transcript returns 422 and a non-empty detail string.

    The UI error area displays `err.message`, which is sourced from
    `response.detail`. This test ensures that field is always present and
    contains useful text (not just an HTTP status code).
    """
    job_id = sample_job
    snap_id = _create_and_lock_snapshot(client, job_id)

    assemble_res = client.post(
        f"/api/packages/jobs/{job_id}",
        json={"snapshot_id": snap_id, "metadata": _VALID_METADATA, "freelance": True},
    )
    assert assemble_res.status_code == 200
    package_id = assemble_res.json()["package_id"]

    certify_res = client.post(
        f"/api/packages/{package_id}/certify",
        json={"metadata": _VALID_METADATA},
    )
    assert certify_res.status_code == 422
    detail = certify_res.json()["detail"]
    assert isinstance(detail, str) and detail.strip(), \
        "detail must be a non-empty string the UI can display"
    # The error must mention body pages so the reporter understands the problem
    assert "body" in detail.lower(), \
        f"expected 'body' in error detail; got: {detail!r}"


# ---------------------------------------------------------------------------
# Guard: certifying an already-CERTIFIED package returns 400
# ---------------------------------------------------------------------------

def test_certify_already_certified_returns_400(client, sample_job_with_content):
    """A second certify call on the same package must return 400, not 500."""
    job_id = sample_job_with_content
    snap_id = _create_and_lock_snapshot(client, job_id)

    assembled = client.post(
        f"/api/packages/jobs/{job_id}",
        json={"snapshot_id": snap_id, "metadata": _VALID_METADATA, "freelance": True},
    ).json()
    package_id = assembled["package_id"]

    first = client.post(
        f"/api/packages/{package_id}/certify",
        json={"metadata": _VALID_METADATA},
    )
    assert first.status_code == 200, first.text

    again = client.post(
        f"/api/packages/{package_id}/certify",
        json={"metadata": _VALID_METADATA},
    )
    assert again.status_code == 400
    assert "certified" in again.json()["detail"].lower()


def test_recertification_creates_new_immutable_lineage(client, sample_job_with_content):
    job_id = sample_job_with_content

    # First certification lineage.
    snap1 = _create_and_lock_snapshot(client, job_id)
    assembled1 = client.post(
        f"/api/packages/jobs/{job_id}",
        json={"snapshot_id": snap1, "metadata": _VALID_METADATA, "freelance": True},
    ).json()
    cert1 = client.post(
        f"/api/packages/{assembled1['package_id']}/certify",
        json={"metadata": _VALID_METADATA},
    )
    assert cert1.status_code == 200

    # Working transcript evolves after certification.
    edit = client.put(
        f"/api/transcripts/jobs/{job_id}/working-transcript",
        json={
            "utterances": [
                {"utterance_id": "utt-1", "working_text": "Second certified version text."}
            ],
            "source": "test_suite",
        },
    )
    assert edit.status_code == 200

    # Second certification lineage.
    snap2 = _create_and_lock_snapshot(client, job_id)
    assembled2 = client.post(
        f"/api/packages/jobs/{job_id}",
        json={"snapshot_id": snap2, "metadata": _VALID_METADATA, "freelance": True},
    ).json()
    cert2 = client.post(
        f"/api/packages/{assembled2['package_id']}/certify",
        json={"metadata": _VALID_METADATA},
    )
    assert cert2.status_code == 200

    packages = client.get(f"/api/packages/jobs/{job_id}").json()["packages"]
    certified = [p for p in packages if p["package_state"] == "CERTIFIED"]
    assert len(certified) == 2
    assert assembled1["package_id"] != assembled2["package_id"]
    assert snap1 != snap2

    provenance = client.get(f"/api/transcripts/jobs/{job_id}/provenance").json()["events"]
    assert any(ev["event_type"] == "recertification_created" for ev in provenance)
