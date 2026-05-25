"""POST /api/intake/parse-text — parse pasted scheduling notes into UFM fields.
POST /api/intake/workspace — synchronize authoritative Stage 1 artifacts.
GET  /api/intake/cases/{case_id} — read authoritative Stage 1 artifacts.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from backend.services import intake_store
from backend.services.intake_text_parser import parse_intake_text

router = APIRouter(prefix="/api/intake", tags=["intake"])

MAX_TEXT_CHARS = 50_000


class IntakeTextRequest(BaseModel):
    text: str = Field(..., description="Raw pasted scheduling notes / emails")


@router.post("/parse-text")
def parse_text_endpoint(payload: IntakeTextRequest) -> dict:
    """Parse free-text intake notes.

    Returns the same {fields, metadata, keyterms} shape as the NOD parser,
    so the frontend can apply the result with the same code path.
    """
    text = payload.text or ""
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Text too long ({len(text)} chars; max {MAX_TEXT_CHARS}).",
        )
    try:
        return parse_intake_text(text)
    except Exception as exc:  # best-effort parser; never 500
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse notes: {type(exc).__name__}: {exc}",
        ) from exc


# ---------------------------------------------------------------------
# Workspace initialization
# ---------------------------------------------------------------------

class WorkspaceInitRequest(BaseModel):
    """Payload to synchronize authoritative Stage 1 artifacts.

    Field names mirror the frontend's UFM keys so the existing Stage 1 UI
    can post its current form state with minimal translation.
    """

    case_id: str
    session_id: Optional[str] = None
    reporter_name: Optional[str] = None

    # Block 1 — case identity
    ufmCause: Optional[str] = None
    ufmStyle: Optional[str] = None
    ufmCourt: Optional[str] = None
    ufmCounty: Optional[str] = None
    ufmState: Optional[str] = "Texas"
    jurisdiction_type: Optional[str] = "texas_state"

    # Block 2 — session
    ufmWitness: Optional[str] = None
    ufmDate: Optional[str] = None
    ufmStartTime: Optional[str] = None
    ufmEndTime: Optional[str] = None
    ufmAddress: Optional[str] = None
    location_type: Optional[str] = "unknown"

    # Block 3 — reporter credentials
    ufmCSRName: Optional[str] = None
    ufmCSRLicense: Optional[str] = None
    ufmFirmReg: Optional[str] = None
    ufmCSRCertExp: Optional[str] = None

    raw_intake_notes: Optional[str] = None
    parser_metadata: dict = Field(default_factory=dict)

    # Keyterms (term/boost/category/source dicts from the frontend)
    keyterms: list[dict] = Field(default_factory=list)


@router.post("/workspace")
def create_workspace_endpoint(payload: WorkspaceInitRequest) -> dict:
    """Persist Stage 1 metadata/keyterms and initialize workspace idempotently."""
    try:
        result = intake_store.sync_stage1_artifacts(payload.model_dump())
        logger.info(
            f"Stage 1 workspace sync endpoint completed for case {payload.case_id}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to synchronize Stage 1 artifacts: {type(exc).__name__}: {exc}",
        ) from exc

    return result


@router.get("/cases/{case_id}")
def read_case_stage1_endpoint(case_id: str) -> dict:
    """Return the authoritative Stage 1 artifact record for a case."""
    try:
        record = intake_store.read_stage1_record(case_id)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to read Stage 1 artifacts: {type(exc).__name__}: {exc}",
        ) from exc
    return {
        "case_id": case_id,
        "raw_intake_notes": record.get("raw_intake_notes") or "",
        "parser_metadata": record.get("parser_metadata") or {},
        "keyterms": record.get("keyterms") or [],
        "workspace": record.get("workspace") or {"sessions": {}},
        "metadata_path": str(intake_store.intake_metadata_path(case_id)),
        "keyterms_path": str(intake_store.keyterms_path(case_id)),
        "keyterms_meta_path": str(intake_store.keyterms_meta_path(case_id)),
    }
