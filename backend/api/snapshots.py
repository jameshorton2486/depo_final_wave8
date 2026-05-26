"""Router for /api/snapshots -- the Transcript State Engine (Wave 18.5).

Endpoints:
    POST /api/snapshots/jobs/{job_id}                create a snapshot
    GET  /api/snapshots/jobs/{job_id}                list a job's snapshots
    GET  /api/snapshots/{snapshot_id}                get one snapshot
    POST /api/snapshots/{snapshot_id}/lock           lock (certify) it
    POST /api/snapshots/jobs/{job_id}/rollback       rollback to a snapshot

History is append-only: nothing here deletes or mutates a snapshot's
captured state. Locking is one-way; rollback creates a new snapshot.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.transcript import repository as trepo
from backend.transcript import provenance as provenance_mod
from backend.transcript_state import snapshot_repo
from backend.transcript_state import snapshot_service
from backend.transcript_state.model import SNAPSHOT_CATEGORIES

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


class CreateSnapshotRequest(BaseModel):
    category: str = "MANUAL"
    note: str = ""
    created_by: str = ""


class RollbackRequest(BaseModel):
    snapshot_id: str
    created_by: str = ""


@router.post("/jobs/{job_id}")
def create_snapshot(job_id: str, payload: CreateSnapshotRequest) -> dict:
    """Capture the current transcript state as an immutable snapshot."""
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found")
    category = (payload.category or "MANUAL").upper()
    if category not in SNAPSHOT_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown snapshot category: {category}")
    snap = snapshot_service.create_snapshot(
        job_id, category=category, note=payload.note,
        created_by=payload.created_by)
    return snap.to_dict()


@router.get("/jobs/{job_id}")
def list_snapshots(job_id: str) -> dict:
    """List a job's snapshots, newest first (summary form)."""
    snaps = snapshot_repo.list_snapshots(job_id)
    return {
        "job_id": job_id,
        "snapshots": [s.to_summary() for s in snaps],
        "count": len(snaps),
    }


@router.get("/{snapshot_id}")
def get_snapshot(snapshot_id: str) -> dict:
    """Retrieve one snapshot, including its captured state."""
    snap = snapshot_repo.get_snapshot(snapshot_id)
    if snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found")
    return {**snap.to_dict(), "state": snap.state}


@router.post("/{snapshot_id}/lock")
def lock_snapshot(snapshot_id: str) -> dict:
    """Lock a snapshot as a Certification Snapshot (immutable, one-way)."""
    snap = snapshot_repo.get_snapshot(snapshot_id)
    if snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found")
    snapshot_repo.lock_snapshot(snapshot_id)
    try:
        provenance_mod.record_event(
            snap.job_id,
            event_type="certification_snapshot_locked",
            title="Certification Snapshot Locked",
            detail="Snapshot locked as immutable certification state.",
            actor_type="system",
            source="snapshots",
            metadata={"category": snap.category, "state_hash": snap.state_hash},
            related_snapshot_id=snapshot_id,
        )
    except Exception:
        pass
    return {"snapshot_id": snapshot_id, "locked": True,
            "is_certification_snapshot": True}


@router.post("/jobs/{job_id}/rollback")
def rollback(job_id: str, payload: RollbackRequest) -> dict:
    """Roll the transcript back to a prior snapshot (append-only).

    The prior snapshot is untouched; a new snapshot is recorded.
    """
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found")
    new_snap = snapshot_service.rollback_to(
        job_id, payload.snapshot_id, created_by=payload.created_by)
    if new_snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {payload.snapshot_id} not found for this job")
    return {
        "job_id": job_id,
        "rolled_back_to": payload.snapshot_id,
        "new_snapshot": new_snap.to_dict(),
    }
