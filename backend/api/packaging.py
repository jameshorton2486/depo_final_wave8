"""Router for /api/packages -- the Transcript Packaging Engine (Wave 20).

Endpoints:
    POST /api/packages/jobs/{job_id}          assemble a DRAFT package
    GET  /api/packages/jobs/{job_id}          list a job's packages
    GET  /api/packages/{package_id}           get one package (full)
    POST /api/packages/{package_id}/certify   certify (one-way finalization)

Packages are assembled from a locked Certification Snapshot (Wave 18.5)
using the Packaging Engine (Wave 20). Once certified a package is
immutable -- any change requires assembling a new package version.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.packaging import (
    IndexInputs,
    assemble_package,
    certify_package,
)
from backend.packaging.package_repo import (
    get_package,
    get_package_for_update,
    get_package_summary,
    list_packages,
    save_package,
    update_package_state,
)
from backend.transcript import repository as trepo
from backend.transcript_state import snapshot_repo

router = APIRouter(prefix="/api/packages", tags=["packages"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AssembleRequest(BaseModel):
    snapshot_id: str
    metadata: dict = {}
    freelance: bool = True


class CertifyRequest(BaseModel):
    metadata: dict = {}


# ---------------------------------------------------------------------------
# Helper: build a paginated document for a job
# ---------------------------------------------------------------------------

def _build_paginated_for_job(job_id: str, job_row: dict):
    """Return a PaginatedDocument for a job's current working state.

    Runs the same Stage S pipeline as the export-preview endpoint so the
    packaging engine receives the same body the exporter would write.
    Returns None when the transcript body is empty (no utterances).
    """
    from backend.stage_s.renderer import render_stage_s
    from backend.transcript.export_render import render_export_with_layout

    utterances = trepo.get_utterances(job_id) or []
    participants = trepo.get_participants(job_id) or []

    # Stage S structural render
    stage_s = render_stage_s(utterances, participants)

    # Map to working line dicts (same mapping as export-preview)
    working: list[dict] = []
    for ln in stage_s.lines:
        if ln.render_state == "OFF_RECORD" and not ln.procedural:
            continue
        if ln.line_type == "parenthetical":
            lt = "colloquy"
        elif ln.line_type == "by_line":
            lt = "colloquy"
        elif ln.line_type in ("Q", "A", "colloquy", "flagged"):
            lt = ln.line_type
        else:
            lt = "colloquy"
        working.append({
            "line_type": lt,
            "speaker_label": ln.speaker_label,
            "text": ln.text,
        })

    _, paginated = render_export_with_layout(working)
    return paginated


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/jobs/{job_id}")
def assemble(job_id: str, payload: AssembleRequest) -> dict:
    """Assemble a Certified Transcript Package in the DRAFT state.

    The package is built from the provided locked Certification Snapshot.
    Metadata (caption, cause number, court, witness, reporter) must
    accompany the request; required fields are validated and any missing
    ones generate warnings in the Generation Report.
    """
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found")

    snap = snapshot_repo.get_snapshot(payload.snapshot_id)
    if snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {payload.snapshot_id} not found")
    if snap.job_id != job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Snapshot {payload.snapshot_id} does not belong to job {job_id}")
    if not snap.locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Snapshot {payload.snapshot_id} is not locked. "
                    "Lock the snapshot first (POST /api/snapshots/{id}/lock) "
                    "before assembling a package."))

    job_row = trepo.get_job(job_id) or {}

    # Build the paginated body from the job's working lines.
    try:
        paginated = _build_paginated_for_job(job_id, job_row)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to paginate transcript for packaging: {exc}")

    # Assemble the package using the Wave 20 engine.
    package = assemble_package(
        snapshot_id=snap.snapshot_id,
        state_hash=snap.state_hash,
        metadata=payload.metadata or {},
        index_inputs=IndexInputs(),  # empty by default; caller may extend
        paginated_document=paginated,
        freelance=payload.freelance,
    )

    # Persist and return.
    summary = save_package(package, job_id)
    return {
        **summary,
        "generation_report": package.generation_report.to_dict(),
        "section_order": package.section_order,
    }


@router.get("/jobs/{job_id}")
def list_job_packages(job_id: str) -> dict:
    """List all packages for a job, newest first."""
    packages = list_packages(job_id)
    return {
        "job_id": job_id,
        "packages": packages,
        "count": len(packages),
    }


@router.get("/{package_id}")
def get_one_package(package_id: str) -> dict:
    """Retrieve one package including the full stored package JSON."""
    pkg = get_package(package_id)
    if pkg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Package {package_id} not found")
    return pkg


@router.post("/{package_id}/certify")
def certify(package_id: str, payload: CertifyRequest) -> dict:
    """Certify a DRAFT/REVIEW package — the one-way finalization step.

    Runs the full pre-certification validation. If validation fails, the
    package is NOT certified and the blocking errors are returned as a
    422. On success the package transitions to CERTIFIED and becomes
    immutable.
    """
    summary = get_package_summary(package_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Package {package_id} not found")

    if summary["package_state"] not in ("DRAFT", "REVIEW"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Package {package_id} is {summary['package_state']} "
                    "and cannot be certified again."))

    package = get_package_for_update(package_id)
    if package is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reconstruct package {package_id} for certification")

    metadata = payload.metadata or {}

    try:
        certified = certify_package(package, metadata)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc))

    update_package_state(package_id, "CERTIFIED", certified)

    result = get_package(package_id) or {}
    return {
        **result,
        "certified": True,
        "generation_report": certified.generation_report.to_dict(),
    }
