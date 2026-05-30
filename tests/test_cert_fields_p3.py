"""Phase 3 tests: packaging engine wired with auto-populated metadata.

Key test: a job with all fields persisted in the DB assembles a package
whose certificate page contains NO [BRACKETED] placeholders.
"""
from __future__ import annotations

import json

import pytest

from backend.db import repository as dbrepo
from backend.db.depo_meta_repo import upsert_depo_meta
from backend.services import intake_store
from backend.transcript import repository as trepo


# ---------------------------------------------------------------------------
# Fixture: a fully-populated job with case, session, reporter, and depo meta
# ---------------------------------------------------------------------------

@pytest.fixture()
def full_job(client) -> str:
    """Create a complete job with all certificate fields populated.

    Creates: reporting_firm + office → reporter → case → Stage 1 appearance
    sync into normalized attorney tables → session (linked) → transcript job
    (linked) + deposition_metadata.
    Returns job_id.
    """
    from backend.db.repository import get_connection
    import uuid

    # Reporting firm + default office
    firm_id = str(uuid.uuid4())
    office_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO reporting_firms (reporting_firm_id, name, firm_registration_number) "
            "VALUES (?, ?, ?)",
            (firm_id, "Vance Reporting Group", "10698"),
        )
        conn.execute(
            "INSERT INTO reporting_firm_offices "
            "(office_id, reporting_firm_id, address_line, city, state, zip, is_default) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (office_id, firm_id, "1100 NW Loop 410", "San Antonio", "TX", "78213"),
        )

    # Reporter linked to firm
    reporter = dbrepo.create_reporter({
        "full_name": "Miah Bardot",
        "csr_number": "TX-10423",
        "csr_expiration": "12/31/2027",
        "firm_registration_number": "10698",
    })
    reporter_id = reporter["reporter_id"]
    dbrepo.update_reporter(reporter_id, {"default_reporting_firm_id": firm_id})

    # Case
    case = dbrepo.create_case({
        "case_number_value": "2026-CI-10001",
        "caption_full": "Acme Corp. v. Dana Reed",
        "judicial_district": "288th Judicial District",
        "county": "Bexar County",
        "state": "Texas",
    })
    case_id = case["case_id"]
    intake_store.sync_stage1_artifacts({
        "case_id": case_id,
        "origin": "parse",
        "ufmStyle": "Acme Corp. v. Dana Reed",
        "parser_metadata": {
            "appearances": [
                {
                    "name": "Mr. D. Nunez",
                    "firm": "Nunez & Associates",
                    "bar_number": "24098765",
                    "side": "plaintiff",
                },
            ],
        },
    })

    # Session
    session = dbrepo.create_session({
        "case_id": case_id,
        "scheduled_at": "2026-05-21T10:00:00-05:00",
        "scheduled_end_at": "2026-05-21T12:30:00-05:00",
        "witness_name": "Dana Reed",
        "location_type": "zoom",
        "witness_type": "individual",
        "service_type": "Zoom_only",
        "reporter_id": reporter_id,
    })
    session = dbrepo.update_session(session["session_id"], {
        "custodial_attorney_name": "Ms. Elizabeth Flora, Esq.",
        "requesting_party_name": "Plaintiff",
    })
    session_id = session["session_id"]

    # Transcript job with content
    job = trepo.create_job({
        "source_filename": "depo_full.mp3",
        "case_id": case_id,
        "session_id": session_id,
    })
    job_id = job["job_id"]

    # Real utterances so the body is non-empty (needed for certify)
    speakers = [
        {"speaker_row_id": "s0", "speaker_index": 0, "speaker_label": "Speaker 0",
         "assigned_name": "Mr. Vance", "speaker_role": "examining_attorney",
         "word_count": 10},
        {"speaker_row_id": "s1", "speaker_index": 1, "speaker_label": "Speaker 1",
         "assigned_name": "Dana Reed", "speaker_role": "witness", "word_count": 12},
    ]
    utterances = [
        {"utterance_id": "u0", "utterance_index": 0, "speaker_index": 0,
         "speaker_label": "Speaker 0", "start_time": 0.0, "end_time": 4.0,
         "text": "Please state your name for the record.", "avg_confidence": 0.99},
        {"utterance_id": "u1", "utterance_index": 1, "speaker_index": 1,
         "speaker_label": "Speaker 1", "start_time": 5.0, "end_time": 9.0,
         "text": "My name is Dana Reed.", "avg_confidence": 0.99},
    ]
    trepo.save_transcript_content(job_id, speakers, utterances, words=[])
    trepo.save_participants(job_id, [
        {"name": "Mr. Vance", "role": "examining_attorney",
         "speaker_indices": [0], "honorific": "MR."},
        {"name": "Dana Reed", "role": "witness", "speaker_indices": [1]},
    ])

    # Deposition-specific cert fields
    upsert_depo_meta(job_id, {
        "volume": "1",
        "examination_disposition": "waived",
        "officer_charges_amount": "450.00",
        "charges_party": "Plaintiff",
        "certificate_service_date": "June 1, 2026",
        "time_per_party_json": json.dumps([
            {"party": "Plaintiff Counsel", "duration": "1:30"},
            {"party": "Defense Counsel", "duration": "1:00"},
        ]),
    })

    return job_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_assemble_auto_populates_case_fields(client, full_job):
    """Assembling a package auto-fills case/session/reporter metadata."""
    job_id = full_job

    snap_res = client.post(f"/api/snapshots/jobs/{job_id}",
                           json={"category": "CERTIFIED"})
    assert snap_res.status_code == 200
    snap_id = snap_res.json()["snapshot_id"]
    assert client.post(f"/api/snapshots/{snap_id}/lock").status_code == 200

    # Assemble with empty explicit metadata — everything should come from DB.
    res = client.post(f"/api/packages/jobs/{job_id}",
                      json={"snapshot_id": snap_id, "metadata": {}})
    assert res.status_code == 200
    body = res.json()
    assert body["package_state"] == "DRAFT"

    pkg_data = client.get(f"/api/packages/{body['package_id']}").json()
    pkg = pkg_data["package"]
    cert_text = "\n".join(pkg["administrative_pages"]["certificate"]["lines"])
    caption_text = "\n".join(pkg["administrative_pages"]["caption"]["lines"])

    # cause_number is on the caption page
    assert "2026-CI-10001" in caption_text    # cause_number
    # reporter/witness fields are on the certificate page
    assert "DANA REED" in cert_text           # witness_name (cert uppercases it)
    assert "Miah Bardot" in cert_text         # reporter_name
    assert "TX-10423" in cert_text            # reporter_csr_number
    assert "Mr. D. Nunez" in cert_text        # counsel_of_record from synced appearances


def test_assembled_certificate_has_no_placeholders(client, full_job):
    """The certificate page contains zero [BRACKETED] placeholders."""
    job_id = full_job

    snap_res = client.post(f"/api/snapshots/jobs/{job_id}",
                           json={"category": "CERTIFIED"})
    snap_id = snap_res.json()["snapshot_id"]
    client.post(f"/api/snapshots/{snap_id}/lock")

    res = client.post(f"/api/packages/jobs/{job_id}",
                      json={"snapshot_id": snap_id, "metadata": {}})
    assert res.status_code == 200

    pkg_data = client.get(f"/api/packages/{res.json()['package_id']}").json()
    cert_lines = pkg_data["package"]["administrative_pages"]["certificate"]["lines"]

    bracketed = [ln for ln in cert_lines if "[" in ln]
    assert bracketed == [], f"Certificate still has placeholders: {bracketed}"


def test_certify_succeeds_with_auto_populated_metadata(client, full_job):
    """Full assemble → certify path succeeds with auto-populated metadata."""
    job_id = full_job

    snap_res = client.post(f"/api/snapshots/jobs/{job_id}",
                           json={"category": "CERTIFIED"})
    snap_id = snap_res.json()["snapshot_id"]
    client.post(f"/api/snapshots/{snap_id}/lock")

    assemble_res = client.post(f"/api/packages/jobs/{job_id}",
                               json={"snapshot_id": snap_id, "metadata": {}})
    assert assemble_res.status_code == 200
    pkg_id = assemble_res.json()["package_id"]

    # Certify with empty explicit metadata — auto-populate fills required fields.
    certify_res = client.post(f"/api/packages/{pkg_id}/certify",
                              json={"metadata": {}})
    assert certify_res.status_code == 200, certify_res.json()
    assert certify_res.json()["certified"] is True
    assert certify_res.json()["generation_report"]["certification_status"] == "CERTIFIED"


def test_explicit_metadata_overrides_auto_populated(client, full_job):
    """Caller-supplied metadata keys take priority over auto-populated values."""
    job_id = full_job

    snap_res = client.post(f"/api/snapshots/jobs/{job_id}",
                           json={"category": "CERTIFIED"})
    snap_id = snap_res.json()["snapshot_id"]
    client.post(f"/api/snapshots/{snap_id}/lock")

    res = client.post(f"/api/packages/jobs/{job_id}", json={
        "snapshot_id": snap_id,
        "metadata": {"witness_name": "OVERRIDE WITNESS"},
    })
    assert res.status_code == 200

    pkg_data = client.get(f"/api/packages/{res.json()['package_id']}").json()
    cert_lines = "\n".join(
        pkg_data["package"]["administrative_pages"]["certificate"]["lines"])
    assert "OVERRIDE WITNESS" in cert_lines


def test_existing_packaging_tests_unaffected(client, sample_job):
    """Regression: jobs with no case/session still assemble (produce placeholders)."""
    snap_res = client.post(f"/api/snapshots/jobs/{sample_job}",
                           json={"category": "CERTIFIED"})
    snap_id = snap_res.json()["snapshot_id"]
    client.post(f"/api/snapshots/{snap_id}/lock")

    metadata = {
        "cause_number": "2024-CI-00001",
        "caption": "Test v. Test",
        "court": "288th Judicial District Court",
        "witness_name": "John Doe",
        "reporter_name": "Jane Smith",
        "reporter_csr_number": "TX-99999",
        "proceedings_date": "May 22, 2026",
    }
    res = client.post(f"/api/packages/jobs/{sample_job}",
                      json={"snapshot_id": snap_id, "metadata": metadata})
    assert res.status_code == 200
    assert res.json()["package_state"] == "DRAFT"
