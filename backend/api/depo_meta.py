"""Router for /api/depo-meta — deposition-metadata capture (cert fields).

Endpoints:
    GET  /api/depo-meta/jobs/{job_id}   retrieve current metadata for a job
    PUT  /api/depo-meta/jobs/{job_id}   create or update metadata for a job

These fields feed the packaging engine's metadata dict at assemble/certify
time so the Reporter's Certificate renders with no [BRACKETED] placeholders.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.db.depo_meta_repo import get_depo_meta, upsert_depo_meta
from backend.transcript import repository as trepo

router = APIRouter(prefix="/api/depo-meta", tags=["depo-meta"])


class TimePartyEntry(BaseModel):
    party: str
    duration: str


class AlsoPresentEntry(BaseModel):
    name: str
    role: str = ""


class DepoMetaWrite(BaseModel):
    volume: str | None = None
    examination_disposition: str | None = None
    officer_charges_amount: str | None = None
    charges_party: str | None = None
    certificate_service_date: str | None = None
    time_per_party: list[TimePartyEntry] | None = None
    also_present: list[AlsoPresentEntry] | None = None


class DepoMetaRead(BaseModel):
    job_id: str
    volume: str
    examination_disposition: str | None
    officer_charges_amount: str | None
    charges_party: str | None
    certificate_service_date: str | None
    time_per_party: list[dict]
    also_present: list[dict]
    created_at: str
    updated_at: str


def _row_to_read(row: dict) -> dict:
    """Expand JSON columns to lists for the response."""
    tpp_json = row.get("time_per_party_json") or "[]"
    ap_json = row.get("also_present_json") or "[]"
    try:
        tpp = json.loads(tpp_json)
    except Exception:
        tpp = []
    try:
        ap = json.loads(ap_json)
    except Exception:
        ap = []
    return {
        "job_id": row["job_id"],
        "volume": row.get("volume") or "1",
        "examination_disposition": row.get("examination_disposition"),
        "officer_charges_amount": row.get("officer_charges_amount"),
        "charges_party": row.get("charges_party"),
        "certificate_service_date": row.get("certificate_service_date"),
        "time_per_party": tpp,
        "also_present": ap,
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
    }


@router.get("/jobs/{job_id}")
def get_meta(job_id: str) -> dict:
    """Return the deposition metadata for a job.

    Returns 404 when the job does not exist. Returns an empty-defaults
    row when the job exists but no metadata has been saved yet.
    """
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    row = get_depo_meta(job_id)
    if row is None:
        return {
            "job_id": job_id,
            "volume": "1",
            "examination_disposition": None,
            "officer_charges_amount": None,
            "charges_party": None,
            "certificate_service_date": None,
            "time_per_party": [],
            "also_present": [],
            "created_at": "",
            "updated_at": "",
        }
    return _row_to_read(row)


@router.put("/jobs/{job_id}")
def put_meta(job_id: str, payload: DepoMetaWrite) -> dict:
    """Create or update the deposition metadata for a job.

    Only provided (non-None) fields are written; omitted fields are
    unchanged on an existing row.
    """
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )

    data = payload.model_dump(exclude_none=True)

    # Serialize list fields to JSON strings for storage.
    if "time_per_party" in data:
        data["time_per_party_json"] = json.dumps(
            [e.model_dump() for e in payload.time_per_party]
        )
        del data["time_per_party"]
    if "also_present" in data:
        data["also_present_json"] = json.dumps(
            [e.model_dump() for e in payload.also_present]
        )
        del data["also_present"]

    row = upsert_depo_meta(job_id, data)
    return _row_to_read(row)
