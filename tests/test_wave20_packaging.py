"""Wave 20 — Transcript Packaging Engine tests."""
from __future__ import annotations

import pytest

from backend.packaging import (
    ExhibitEvent,
    IndexInputs,
    WitnessEvent,
    assemble_package,
    can_transition,
    certify_package,
    compute_manifest_hash,
    validate_metadata,
    verify_package_integrity,
)
from backend.packaging.indices import build_page_reference_map, generate_indices
from backend.packaging.model import PackageImmutableError, TranscriptPackage
from backend.packaging.packager import SECTION_ORDER
from backend.pagination.paginator import paginate
from backend.stage_s.models import RenderLine


# --- fixtures --------------------------------------------------------

def _render_lines(n: int = 60) -> list[RenderLine]:
    """A run of short render lines with stable ids L0..L{n-1}."""
    return [RenderLine(line_id=f"L{i}", line_type="qa",
                       text=f"This is render line number {i}.", tab_level=2)
            for i in range(n)]


def _paginated(n: int = 60):
    return paginate(_render_lines(n))


def _valid_metadata() -> dict:
    return {
        "cause_number": "2024-CI-09912",
        "caption": "Acme Corp. v. Heath Thomas",
        "court": "288th Judicial District Court, Bexar County, Texas",
        "witness_name": "Heath Thomas",
        "reporter_name": "Miah Bardot",
        "reporter_csr_number": "TX-10423",
        "proceedings_date": "May 21, 2026",
        "location": "1100 NW Loop 410, San Antonio, Texas",
        "appearances": [
            {"role": "plaintiff", "attorney": "Mr. Nunez",
             "firm": "Nunez & Associates", "party": "Acme Corp."},
        ],
    }


def _index_inputs() -> IndexInputs:
    return IndexInputs(
        witness_events=[
            WitnessEvent(witness_name="Heath Thomas",
                         examination_type="direct", render_line_id="L3"),
            WitnessEvent(witness_name="Anna Alvarado",
                         examination_type="cross", render_line_id="L40"),
        ],
        exhibit_events=[
            ExhibitEvent(exhibit_number="2", exhibit_title="Contract",
                         render_line_id="L20"),
            ExhibitEvent(exhibit_number="1", exhibit_title="Photograph",
                         render_line_id="L10"),
        ],
    )


def _assemble(**overrides):
    kwargs = dict(
        snapshot_id="snap-abc",
        state_hash="hash-xyz",
        metadata=_valid_metadata(),
        index_inputs=_index_inputs(),
        paginated_document=_paginated(),
    )
    kwargs.update(overrides)
    return assemble_package(**kwargs)


# --- package state machine ------------------------------------------

def test_legal_state_transitions():
    assert can_transition("DRAFT", "CERTIFIED")
    assert can_transition("CERTIFIED", "EXPORTED")
    assert can_transition("CERTIFIED", "SEALED")


def test_illegal_state_transitions_blocked():
    assert not can_transition("DRAFT", "EXPORTED")
    assert not can_transition("CERTIFIED", "DRAFT")
    assert not can_transition("SUPERSEDED", "CERTIFIED")


# --- validation ------------------------------------------------------

def test_valid_metadata_passes():
    assert validate_metadata(_valid_metadata()).ok


def test_missing_required_field_is_an_error():
    meta = _valid_metadata()
    del meta["cause_number"]
    result = validate_metadata(meta)
    assert not result.ok
    assert any("cause_number" in e for e in result.errors)


def test_blank_required_field_is_an_error():
    meta = _valid_metadata()
    meta["reporter_csr_number"] = "   "
    assert not validate_metadata(meta).ok


def test_missing_appearances_is_warning_not_error():
    meta = _valid_metadata()
    meta["appearances"] = []
    result = validate_metadata(meta)
    assert result.ok
    assert result.warnings


# --- index generation ------------------------------------------------

def test_page_reference_map_resolves_render_lines():
    doc = _paginated(60)
    ref_map = build_page_reference_map(doc)
    assert "L0" in ref_map
    page, slot = ref_map["L0"]
    assert page == 1 and 1 <= slot <= 25


def test_witness_index_is_alphabetical_by_surname():
    indices, _ = generate_indices(_index_inputs(), _paginated())
    labels = [e.label for e in indices["witness"].entries]
    # Alvarado before Thomas.
    assert labels == ["Anna Alvarado", "Heath Thomas"]


def test_exhibit_index_is_numeric_order():
    indices, exhibits = generate_indices(_index_inputs(), _paginated())
    numbers = [e.exhibit_number for e in exhibits]
    assert numbers == ["1", "2"]


def test_index_entries_resolve_to_stable_page_references():
    indices, _ = generate_indices(_index_inputs(), _paginated())
    for entry in indices["chronological"].entries:
        assert entry.page is not None
        assert entry.reference.startswith("Page ")


def test_chronological_index_in_transcript_order():
    indices, _ = generate_indices(_index_inputs(), _paginated())
    pages = [e.page for e in indices["chronological"].entries]
    assert pages == sorted(pages)


def test_index_generation_is_deterministic():
    a, _ = generate_indices(_index_inputs(), _paginated())
    b, _ = generate_indices(_index_inputs(), _paginated())
    assert a["witness"].to_dict() == b["witness"].to_dict()
    assert a["exhibit"].to_dict() == b["exhibit"].to_dict()


def test_unresolved_event_sorts_last_without_crashing():
    inputs = IndexInputs(witness_events=[
        WitnessEvent(witness_name="Ghost", render_line_id="DOES_NOT_EXIST")])
    indices, _ = generate_indices(inputs, _paginated())
    assert indices["chronological"].entries[-1].page is None


# --- administrative pages -------------------------------------------

def test_all_admin_pages_generated_for_freelance():
    pkg = _assemble(freelance=True)
    for kind in ("caption", "appearances", "chronological_index",
                 "witness_index", "exhibit_index", "corrections_signature",
                 "certificate"):
        assert kind in pkg.administrative_pages


def test_corrections_page_omitted_when_not_freelance():
    pkg = _assemble(freelance=False)
    assert "corrections_signature" not in pkg.administrative_pages
    assert "certificate" in pkg.administrative_pages


def test_certificate_binds_to_package_identity():
    pkg = _assemble()
    cert_text = "\n".join(pkg.administrative_pages["certificate"].lines)
    assert pkg.identity.package_id in cert_text
    assert "snap-abc" in cert_text


# --- packaging engine: ordering -------------------------------------

def test_caption_is_first_and_certificate_is_last():
    pkg = _assemble()
    assert pkg.section_order[0] == "caption"
    assert pkg.section_order[-1] == "certificate"


def test_body_marker_present_in_section_order():
    pkg = _assemble()
    assert TranscriptPackage.BODY_MARKER in pkg.section_order


def test_section_order_follows_authority():
    pkg = _assemble()
    # The package order is a subsequence of the canonical SECTION_ORDER.
    canonical = [k for k in SECTION_ORDER if k in pkg.section_order]
    assert pkg.section_order == canonical


def test_iter_sections_yields_body_and_admin():
    pkg = _assemble()
    kinds = [k for (k, _) in pkg.iter_sections()]
    assert "body" in kinds and "admin" in kinds


# --- determinism / reproducibility ----------------------------------

def test_package_id_is_deterministic():
    a = _assemble()
    b = _assemble()
    assert a.identity.package_id == b.identity.package_id


def test_manifest_hash_is_deterministic():
    a = _assemble()
    b = _assemble()
    assert a.manifest.manifest_hash == b.manifest.manifest_hash


def test_manifest_hash_excludes_timestamp():
    a = _assemble(package_timestamp="2026-05-21T10:00:00Z")
    b = _assemble(package_timestamp="2026-05-21T23:59:59Z")
    assert a.manifest.manifest_hash == b.manifest.manifest_hash


def test_new_package_version_changes_identity():
    v1 = _assemble(package_version=1)
    v2 = _assemble(package_version=2)
    assert v1.identity.package_id != v2.identity.package_id


# --- generation report ----------------------------------------------

def test_generation_report_counts():
    pkg = _assemble()
    report = pkg.generation_report
    assert report.body_pages == pkg.body_page_count
    assert report.exhibits_indexed == 2
    assert report.witnesses_indexed == 2
    assert report.total_pages == report.body_pages + report.administrative_pages


def test_unresolved_flags_counted_in_report():
    flagged = [RenderLine(line_id="F0", line_type="flagged",
                          text="Speaker 4 unmapped.", tab_level=0)]
    pkg = _assemble(paginated_document=paginate(flagged))
    assert pkg.generation_report.unresolved_flags >= 1


# --- certification & immutability -----------------------------------

def test_certify_valid_package_succeeds():
    pkg = _assemble()
    certified = certify_package(pkg, _valid_metadata())
    assert certified.state == "CERTIFIED"
    assert certified.generation_report.certification_status == "CERTIFIED"


def test_certify_fails_on_invalid_metadata():
    pkg = _assemble()
    bad = _valid_metadata()
    del bad["reporter_name"]
    with pytest.raises(ValueError):
        certify_package(pkg, bad)
    assert pkg.state == "DRAFT"        # not certified


def test_certified_package_is_immutable():
    pkg = certify_package(_assemble(), _valid_metadata())
    with pytest.raises(PackageImmutableError):
        pkg._assert_mutable()


def test_certified_package_cannot_revert_to_draft():
    pkg = certify_package(_assemble(), _valid_metadata())
    with pytest.raises(PackageImmutableError):
        pkg.transition("DRAFT")


def test_certified_package_may_be_exported():
    pkg = certify_package(_assemble(), _valid_metadata())
    pkg.transition("EXPORTED")
    assert pkg.state == "EXPORTED"


# --- package integrity verification ---------------------------------

def test_integrity_verification_passes_for_intact_package():
    pkg = _assemble()
    result = verify_package_integrity(
        pkg, expected_snapshot_id="snap-abc", expected_state_hash="hash-xyz")
    assert result["ok"]


def test_integrity_detects_tampered_manifest():
    pkg = _assemble()
    pkg.manifest.geometry_profile = "tampered_profile"
    result = verify_package_integrity(pkg)
    assert not result["ok"]
    assert not result["checks"]["manifest_hash_intact"]


def test_integrity_detects_wrong_snapshot_binding():
    pkg = _assemble()
    result = verify_package_integrity(pkg, expected_snapshot_id="snap-OTHER")
    assert not result["ok"]


# --- recompute sanity ------------------------------------------------

def test_manifest_hash_recomputes_to_stored_value():
    pkg = _assemble()
    assert compute_manifest_hash(pkg.manifest) == pkg.manifest.manifest_hash


# --- API endpoint tests -----------------------------------------------

def test_packaging_list_unknown_job_returns_empty(client):
    res = client.get("/api/packages/jobs/no-such-job")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 0
    assert body["packages"] == []


def test_packaging_get_unknown_package_404(client):
    res = client.get("/api/packages/pkg-does-not-exist")
    assert res.status_code == 404


def test_packaging_certify_unknown_package_404(client):
    res = client.post("/api/packages/no-pkg/certify",
                      json={"metadata": {}})
    assert res.status_code == 404


def test_packaging_assemble_unknown_job_404(client):
    res = client.post("/api/packages/jobs/no-job",
                      json={"snapshot_id": "s1", "metadata": {}})
    assert res.status_code == 404


def test_packaging_assemble_unknown_snapshot_404(client, sample_job):
    """Assembling from a non-existent snapshot returns 404."""
    res = client.post(f"/api/packages/jobs/{sample_job}",
                      json={"snapshot_id": "no-such-snap", "metadata": {}})
    assert res.status_code == 404


def test_packaging_assemble_unlocked_snapshot_400(client, sample_job):
    """Assembling from an unlocked snapshot must fail with 400."""
    # Create a snapshot (unlocked by default)
    snap_res = client.post(f"/api/snapshots/jobs/{sample_job}",
                           json={"category": "MANUAL"})
    assert snap_res.status_code == 200
    snap_id = snap_res.json()["snapshot_id"]

    res = client.post(f"/api/packages/jobs/{sample_job}",
                      json={"snapshot_id": snap_id, "metadata": {}})
    assert res.status_code == 400
    assert "not locked" in res.json()["detail"].lower()


def test_packaging_assemble_list_get_workflow(client, sample_job):
    """Create snapshot, lock it, assemble a DRAFT package, list and get it."""
    # 1. Create and lock a snapshot
    snap_res = client.post(f"/api/snapshots/jobs/{sample_job}",
                           json={"category": "CERTIFIED"})
    assert snap_res.status_code == 200
    snap_id = snap_res.json()["snapshot_id"]

    lock_res = client.post(f"/api/snapshots/{snap_id}/lock")
    assert lock_res.status_code == 200

    # 2. Assemble package
    metadata = {
        "cause_number": "2024-CI-00001",
        "caption": "Test v. Test",
        "court": "288th Judicial District Court",
        "witness_name": "John Doe",
        "reporter_name": "Jane Smith",
        "reporter_csr_number": "TX-99999",
        "proceedings_date": "May 22, 2026",
    }
    assemble_res = client.post(
        f"/api/packages/jobs/{sample_job}",
        json={"snapshot_id": snap_id, "metadata": metadata})
    assert assemble_res.status_code == 200
    body = assemble_res.json()
    package_id = body["package_id"]
    assert body["package_state"] == "DRAFT"
    assert "generation_report" in body

    # 3. List packages for the job
    list_res = client.get(f"/api/packages/jobs/{sample_job}")
    assert list_res.status_code == 200
    assert list_res.json()["count"] == 1

    # 4. Get the full package
    get_res = client.get(f"/api/packages/{package_id}")
    assert get_res.status_code == 200
    full = get_res.json()
    assert full["package_id"] == package_id
    assert "package" in full


def test_packaging_certify_empty_body_blocked(client, sample_job):
    """Certifying a package with no body pages returns 422.

    An empty transcript (no utterances → body_page_count=0) cannot be
    certified. This is a validation rule, not an API bug.
    """
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
    assemble_res = client.post(
        f"/api/packages/jobs/{sample_job}",
        json={"snapshot_id": snap_id, "metadata": metadata})
    assert assemble_res.status_code == 200
    pkg_id = assemble_res.json()["package_id"]

    # Certify -- should fail because body_page_count == 0
    certify_res = client.post(
        f"/api/packages/{pkg_id}/certify",
        json={"metadata": metadata})
    assert certify_res.status_code == 422
    assert "body" in certify_res.json()["detail"].lower()


def test_packaging_certify_invalid_metadata_422(client, sample_job):
    """Certifying with incomplete metadata returns 422."""
    snap_res = client.post(f"/api/snapshots/jobs/{sample_job}",
                           json={"category": "CERTIFIED"})
    snap_id = snap_res.json()["snapshot_id"]
    client.post(f"/api/snapshots/{snap_id}/lock")

    # Assemble with full metadata
    metadata = {
        "cause_number": "2024-CI-00002",
        "caption": "Test v. Test",
        "court": "288th Judicial District Court",
        "witness_name": "John Doe",
        "reporter_name": "Jane Smith",
        "reporter_csr_number": "TX-99998",
        "proceedings_date": "May 22, 2026",
    }
    assemble_res = client.post(
        f"/api/packages/jobs/{sample_job}",
        json={"snapshot_id": snap_id, "metadata": metadata})
    assert assemble_res.status_code == 200
    pkg_id = assemble_res.json()["package_id"]

    # Certify with missing required field
    bad_meta = {k: v for k, v in metadata.items() if k != "reporter_csr_number"}
    certify_res = client.post(
        f"/api/packages/{pkg_id}/certify",
        json={"metadata": bad_meta})
    assert certify_res.status_code == 422


def test_packaging_certify_full_workflow(client, sample_job_with_content):
    """End-to-end positive path: snapshot -> lock -> assemble -> certify.

    BLOCKER-4 regression. The empty-job fixture can only test the
    negative path (422 on no body); this exercises a real-content job
    all the way to a CERTIFIED package.
    """
    job_id = sample_job_with_content

    # 1. Snapshot and lock.
    snap_res = client.post(f"/api/snapshots/jobs/{job_id}",
                           json={"category": "CERTIFIED"})
    assert snap_res.status_code == 200
    snap_id = snap_res.json()["snapshot_id"]
    assert client.post(f"/api/snapshots/{snap_id}/lock").status_code == 200

    metadata = {
        "cause_number": "2024-CI-09912",
        "caption": "Acme Corp. v. Dana Reed",
        "court": "288th Judicial District Court, Bexar County, Texas",
        "witness_name": "Dana Reed",
        "reporter_name": "Miah Bardot",
        "reporter_csr_number": "TX-10423",
        "proceedings_date": "May 21, 2026",
    }

    # 2. Assemble a DRAFT package -- real content => a non-empty body.
    assemble_res = client.post(
        f"/api/packages/jobs/{job_id}",
        json={"snapshot_id": snap_id, "metadata": metadata})
    assert assemble_res.status_code == 200
    assembled = assemble_res.json()
    pkg_id = assembled["package_id"]
    assert assembled["package_state"] == "DRAFT"
    assert assembled["generation_report"]["body_pages"] >= 1

    # 3. Certify -- the positive path the empty fixture cannot reach.
    certify_res = client.post(
        f"/api/packages/{pkg_id}/certify",
        json={"metadata": metadata})
    assert certify_res.status_code == 200
    certified = certify_res.json()
    assert certified["certified"] is True
    assert certified["generation_report"]["certification_status"] == "CERTIFIED"

    # 4. A certified package cannot be certified again.
    again = client.post(f"/api/packages/{pkg_id}/certify",
                        json={"metadata": metadata})
    assert again.status_code == 400

    provenance = client.get(f"/api/transcripts/jobs/{job_id}/provenance").json()
    assert any(ev["event_type"] == "certification_frozen" for ev in provenance["events"])


def test_packaging_uses_locked_snapshot_state_not_live_db(client, sample_job_with_content):
    from backend.api.packaging import _build_paginated_and_index_inputs_from_snapshot_state
    from backend.transcript import working_state
    from backend.transcript_state import snapshot_repo

    job_id = sample_job_with_content
    working_state.persist_working_transcript(
        job_id,
        [{"utterance_id": "utt-1", "working_text": "Snapshot-owned witness answer."}],
        source="test_suite",
    )

    snap_res = client.post(f"/api/snapshots/jobs/{job_id}", json={"category": "CERTIFIED"})
    assert snap_res.status_code == 200
    snap_id = snap_res.json()["snapshot_id"]
    assert client.post(f"/api/snapshots/{snap_id}/lock").status_code == 200

    # Mutate the LIVE working transcript after the snapshot is locked.
    working_state.persist_working_transcript(
        job_id,
        [{"utterance_id": "utt-1", "working_text": "Live database text after lock."}],
        source="test_suite",
    )

    snap = snapshot_repo.get_snapshot(snap_id)
    paginated, _ = _build_paginated_and_index_inputs_from_snapshot_state(snap.state)
    body_text = "\n".join(
        slot.physical_line.text
        for page in paginated.pages
        for slot in page.slots
        if slot.physical_line is not None
    )
    assert "Snapshot-owned witness answer." in body_text
    assert "Live database text after lock." not in body_text


def test_packaging_uses_snapshot_exhibit_events_not_live_db(client, sample_job_with_content):
    from backend.api.packaging import _build_paginated_and_index_inputs_from_snapshot_state
    from backend.transcript import repository as trepo
    from backend.transcript_state import snapshot_repo

    job_id = sample_job_with_content
    trepo.create_exhibit(job_id, {
        "exhibit_number": "1",
        "exhibit_title": "Photograph",
        "anchor_utterance_id": "utt-2",
    })

    snap_res = client.post(f"/api/snapshots/jobs/{job_id}", json={"category": "CERTIFIED"})
    snap_id = snap_res.json()["snapshot_id"]
    assert client.post(f"/api/snapshots/{snap_id}/lock").status_code == 200

    exhibit = trepo.list_exhibits(job_id)[0]
    trepo.update_exhibit(exhibit["exhibit_id"], {
        "exhibit_title": "Changed After Lock",
        "anchor_utterance_id": "utt-5",
    })

    snap = snapshot_repo.get_snapshot(snap_id)
    _, index_inputs = _build_paginated_and_index_inputs_from_snapshot_state(snap.state)
    assert len(index_inputs.exhibit_events) == 1
    assert index_inputs.exhibit_events[0].exhibit_number == "1"
    assert index_inputs.exhibit_events[0].exhibit_title == "Photograph"


def test_packaging_assembles_authoritative_exhibit_index_from_snapshot(client, sample_job_with_content):
    from backend.transcript import repository as trepo

    job_id = sample_job_with_content
    trepo.create_exhibit(job_id, {
        "exhibit_number": "3",
        "exhibit_title": "Contract",
        "anchor_utterance_id": "utt-4",
    })

    snap_res = client.post(f"/api/snapshots/jobs/{job_id}", json={"category": "CERTIFIED"})
    snap_id = snap_res.json()["snapshot_id"]
    assert client.post(f"/api/snapshots/{snap_id}/lock").status_code == 200

    metadata = {
        "cause_number": "2024-CI-09912",
        "caption": "Acme Corp. v. Dana Reed",
        "court": "288th Judicial District Court, Bexar County, Texas",
        "witness_name": "Dana Reed",
        "reporter_name": "Miah Bardot",
        "reporter_csr_number": "TX-10423",
        "proceedings_date": "May 21, 2026",
    }
    assemble_res = client.post(
        f"/api/packages/jobs/{job_id}",
        json={"snapshot_id": snap_id, "metadata": metadata},
    )
    assert assemble_res.status_code == 200
    body = assemble_res.json()
    assert body["generation_report"]["exhibits_indexed"] == 1

    package_detail = client.get(f"/api/packages/{body['package_id']}").json()
    exhibit_entries = package_detail["package"]["indices"]["exhibit"]["entries"]
    assert exhibit_entries[0]["label"] == "Exhibit 3"
