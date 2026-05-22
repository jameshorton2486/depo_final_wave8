"""The Transcript Packaging Engine — Wave 20.

The primary engine of certified-package assembly. It takes a frozen
transcript body (the Wave 19 PaginatedDocument), structured case
metadata, and structured index-tracking events, and assembles a
Certified Transcript Package: body + administrative pages + indices +
manifest + certificate, in the authoritative order.

Determinism: the same locked snapshot always assembles to the same
package — same section order, same identity, same manifest hash
(Package Reproducibility).

Immutability: once certified, a package is frozen. Any change must
produce a NEW package version; the engine never mutates a certified
package in place (review item 14 — Immutable Certified Artifact).

See docs/wave20_packaging.md sections 0-5.
"""
from __future__ import annotations

from backend.packaging import admin_pages
from backend.packaging.indices import IndexInputs, generate_indices
from backend.packaging.manifest import build_identity, build_manifest
from backend.packaging.model import (
    GenerationReport,
    TranscriptPackage,
)
from backend.packaging.validation import (
    validate_for_certification,
    validate_metadata,
)

# --- Package Ordering Authority -------------------------------------
# The Packaging Engine is the SOLE authority for package structure.
# This single tuple defines the authoritative section order; the
# certificate is always last, the caption always first.
SECTION_ORDER: tuple[str, ...] = (
    "caption",
    "appearances",
    "chronological_index",
    "witness_index",
    "exhibit_index",
    TranscriptPackage.BODY_MARKER,
    "corrections_signature",
    "certificate",
)


def _count_unresolved_flags(paginated_document) -> int:
    """Count flagged (unmapped/unresolved) physical lines in the body."""
    if paginated_document is None:
        return 0
    count = 0
    for page in getattr(paginated_document, "pages", []):
        for slot in page.slots:
            phys = slot.physical_line
            if phys is not None and phys.line_type == "flagged":
                count += 1
    return count


def assemble_package(
    *,
    snapshot_id: str,
    state_hash: str,
    metadata: dict,
    index_inputs: IndexInputs,
    paginated_document,
    freelance: bool = True,
    package_version: int = 1,
    package_timestamp: str = "",
    ai_review_summary: dict | None = None,
) -> TranscriptPackage:
    """Assemble a Certified Transcript Package in the DRAFT state.

    Parameters
    ----------
    snapshot_id, state_hash
        The locked Wave 18.5 snapshot the package is built from. These
        bind the package to a reproducible transcript state.
    metadata
        Structured case metadata (caption, cause number, court,
        reporter, appearances, ...). Never parsed transcript text.
    index_inputs
        Structured witness/exhibit tracking events for index generation.
    paginated_document
        The frozen Wave 19 PaginatedDocument — the transcript body.
        Indices resolve page references against it.
    freelance
        When True, a Corrections / Signature page is included.

    Returns a DRAFT TranscriptPackage. Certification is a separate,
    explicit step (`certify_package`).
    """
    metadata = metadata or {}
    body_page_count = getattr(paginated_document, "total_pages", 0) or 0

    # --- 1. validate inputs (warnings do not block a DRAFT) ---------
    meta_result = validate_metadata(metadata)

    # --- 2. Index Generation Engine ---------------------------------
    indices, exhibits = generate_indices(index_inputs, paginated_document)

    # --- 3. administrative page generators --------------------------
    pages: dict = {}
    pages["caption"] = admin_pages.build_caption_page(metadata)
    pages["appearances"] = admin_pages.build_appearances_page(metadata)
    pages["chronological_index"] = admin_pages.build_chronological_index_page(
        indices["chronological"])
    pages["witness_index"] = admin_pages.build_witness_index_page(
        indices["witness"])
    pages["exhibit_index"] = admin_pages.build_exhibit_index_page(
        indices["exhibit"])
    if freelance:
        pages["corrections_signature"] = (
            admin_pages.build_corrections_signature_page(metadata))

    # --- 4. identity + manifest (deterministic) ---------------------
    identity = build_identity(snapshot_id, state_hash, package_version)

    # The certificate binds to the package it certifies.
    pages["certificate"] = admin_pages.build_certificate_page(
        metadata,
        package_id=identity.package_id,
        snapshot_id=snapshot_id,
        state_hash=state_hash,
        certification_id=identity.certification_id)

    template_versions = {
        kind: admin_pages.ADMIN_TEMPLATE_VERSIONS[kind]
        for kind in pages
    }
    manifest = build_manifest(
        identity,
        certification_state="DRAFT",
        package_timestamp=package_timestamp,
        included_exhibits=[e.exhibit_number for e in exhibits],
        generated_indices=list(indices.keys()),
        template_versions=template_versions)

    # --- 5. Package Ordering Authority ------------------------------
    section_order = [key for key in SECTION_ORDER
                     if key == TranscriptPackage.BODY_MARKER
                     or key in pages]

    # --- 6. Generation Report ---------------------------------------
    report = GenerationReport(
        body_pages=body_page_count,
        administrative_pages=len(pages),
        exhibits_indexed=len(exhibits),
        witnesses_indexed=len(indices["witness"].entries),
        unresolved_flags=_count_unresolved_flags(paginated_document),
        warnings=list(meta_result.warnings),
        ai_review_summary=dict(ai_review_summary or {}),
        certification_status="DRAFT",
        validation_passed=meta_result.ok)

    return TranscriptPackage(
        identity=identity,
        manifest=manifest,
        generation_report=report,
        administrative_pages=pages,
        section_order=section_order,
        body_page_count=body_page_count,
        indices=indices,
        state="DRAFT")


def certify_package(
    package: TranscriptPackage,
    metadata: dict,
) -> TranscriptPackage:
    """Certify a DRAFT/REVIEW package — the one-way finalization step.

    Runs the full pre-certification validation pass. If validation
    fails, the package is NOT certified and the blocking errors are
    raised. On success the package transitions to CERTIFIED and becomes
    immutable.

    Raises ValueError when validation blocks certification.
    """
    result = validate_for_certification(
        metadata, package.indices, package.body_page_count)

    package.generation_report.warnings = list(
        dict.fromkeys(package.generation_report.warnings + result.warnings))
    package.generation_report.validation_passed = result.ok

    if not result.ok:
        raise ValueError(
            "Package cannot be certified — validation failed: "
            + "; ".join(result.errors))

    package.transition("CERTIFIED")
    return package
