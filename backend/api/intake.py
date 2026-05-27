"""POST /api/intake/parse-text — parse pasted scheduling notes into UFM fields.
POST /api/intake/workspace — synchronize authoritative Stage 1 artifacts.
GET  /api/intake/cases/{case_id} — read authoritative Stage 1 artifacts.
GET  /api/intake/cases/{case_id}/deepgram-preview — derived Deepgram request payload.
GET  /api/intake/cases/{case_id}/ufm-preview — derived UFM metadata payload.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from loguru import logger

from backend.db import repository as case_repo
from backend.deepgram.client import DEEPGRAM_PARAMS, normalize_keyterms
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

    # Operator-attested per-field confirmations. Only "confirmed" is a
    # storable value; any other value clears the entry on merge.
    field_confirmations: dict = Field(default_factory=dict)

    @field_validator("field_confirmations")
    @classmethod
    def _reject_unknown_field_ids(cls, value: dict) -> dict:
        if not isinstance(value, dict):
            raise ValueError("field_confirmations must be an object")
        unknown = [k for k in value if k not in intake_store.UFM_FIELD_IDS]
        if unknown:
            raise ValueError(
                f"Unknown field_confirmations key(s): {', '.join(sorted(unknown))}"
            )
        return value


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
        "field_confirmations": record.get("field_confirmations") or {},
        "keyterms": record.get("keyterms") or [],
        "workspace": record.get("workspace") or {"sessions": {}},
        "metadata_path": str(intake_store.intake_metadata_path(case_id)),
        "keyterms_path": str(intake_store.keyterms_path(case_id)),
        "keyterms_meta_path": str(intake_store.keyterms_meta_path(case_id)),
    }


# ---------------------------------------------------------------------
# Read-only payload previews (Stage 1 operator transparency)
# ---------------------------------------------------------------------

_UFM_PREVIEW_LABELS = {
    "ufmCause": "Cause Number",
    "ufmStyle": "Full Caption / Style",
    "ufmCourt": "Court / Judicial District",
    "ufmCounty": "County of Venue",
    "ufmState": "State",
    "ufmWitness": "Deponent / Witness Name",
    "ufmDate": "Deposition Date",
    "ufmStartTime": "Start Time",
    "ufmEndTime": "End Time",
    "ufmAddress": "Deposition Address",
    "ufmCSRName": "CSR Officer Name",
    "ufmCSRLicense": "CSR License Number",
    "ufmFirmReg": "Firm Registration Number",
    "ufmCSRCertExp": "CSR License Expiration",
    "ufmCustodialName": "Custodial Attorney Name",
    "ufmRequestingParty": "Requesting Firm / Party",
}


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_case_exists(case_id: str) -> None:
    if case_repo.get_case(case_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Case {case_id} not found"
        )


@router.get("/cases/{case_id}/deepgram-preview")
def deepgram_preview_endpoint(case_id: str) -> dict:
    """Return the exact payload the Deepgram client would send for this case.

    Derived view: `deepgram_request` is read directly from
    `backend.deepgram.client.DEEPGRAM_PARAMS` so any future change to the
    request shape automatically flows through. `keyterms` is the
    pre-normalization list the operator entered; `keyterms_note` explains
    the normalization that the live client applies before sending.
    """
    _ensure_case_exists(case_id)
    record = intake_store.read_stage1_record(case_id)
    keyterms = record.get("keyterms") or []
    normalized = normalize_keyterms(keyterms)
    note: Optional[str] = None
    if len(normalized) != len(keyterms):
        note = (
            "Deepgram receives a normalized list capped at "
            f"{len(normalized)} term(s); duplicates and overflow past the "
            "100-term cap are dropped before transmission."
        )
    return {
        "case_id": case_id,
        "computed_at": _utc_now_iso_z(),
        "deepgram_request": dict(DEEPGRAM_PARAMS),
        "keyterms": keyterms,
        "keyterms_count": len(keyterms),
        "keyterms_note": note,
    }


@router.get("/cases/{case_id}/ufm-preview")
def ufm_preview_endpoint(case_id: str) -> dict:
    """Return the canonical UFM metadata payload derived from intake state.

    Derived view: read only from `intake_store.read_stage1_record()`. No
    re-aggregation from cases/sessions/reporters — that would create a
    second source of truth.
    """
    _ensure_case_exists(case_id)
    record = intake_store.read_stage1_record(case_id)
    parser_meta = record.get("parser_metadata") or {}
    ufm_fields = record.get("ufm_fields") or {}

    ufm = {
        "cause_number": ufm_fields.get("ufmCause"),
        "caption": ufm_fields.get("ufmStyle"),
        "court": ufm_fields.get("ufmCourt"),
        "county": ufm_fields.get("ufmCounty"),
        "state": ufm_fields.get("ufmState"),
        "deponent": ufm_fields.get("ufmWitness"),
        "deposition_date": ufm_fields.get("ufmDate"),
        "start_time": ufm_fields.get("ufmStartTime"),
        "end_time": ufm_fields.get("ufmEndTime"),
        "address": ufm_fields.get("ufmAddress"),
        "csr_name": ufm_fields.get("ufmCSRName"),
        "csr_license": ufm_fields.get("ufmCSRLicense"),
        "firm_registration": ufm_fields.get("ufmFirmReg"),
        "csr_cert_expiration": ufm_fields.get("ufmCSRCertExp"),
        "custodial_attorney": ufm_fields.get("ufmCustodialName"),
        "requesting_party": ufm_fields.get("ufmRequestingParty"),
    }

    ufm_to_field_id = {
        "cause_number": "ufmCause",
        "caption": "ufmStyle",
        "court": "ufmCourt",
        "county": "ufmCounty",
        "state": "ufmState",
        "deponent": "ufmWitness",
        "deposition_date": "ufmDate",
        "start_time": "ufmStartTime",
        "end_time": "ufmEndTime",
        "address": "ufmAddress",
        "csr_name": "ufmCSRName",
        "csr_license": "ufmCSRLicense",
        "firm_registration": "ufmFirmReg",
        "csr_cert_expiration": "ufmCSRCertExp",
        "custodial_attorney": "ufmCustodialName",
        "requesting_party": "ufmRequestingParty",
    }
    missing_required: list[str] = []
    for ufm_key, value in ufm.items():
        field_id = ufm_to_field_id[ufm_key]
        label = _UFM_PREVIEW_LABELS[field_id]
        if value in (None, ""):
            missing_required.append(label)

    return {
        "case_id": case_id,
        "computed_at": _utc_now_iso_z(),
        "ufm_metadata": ufm,
        "field_sources": dict(parser_meta.get("field_sources") or {}),
        "field_confirmations": dict(record.get("field_confirmations") or {}),
        "missing_required_fields": missing_required,
    }
