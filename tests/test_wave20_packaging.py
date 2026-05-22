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
