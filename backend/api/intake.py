"""POST /api/intake/parse-text — parse pasted scheduling notes into UFM fields.
POST /api/intake/workspace — create the on-disk case workspace + keyterms file.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.canonical import (
    CaseIdentity,
    CaseWorkspacePacket,
    DepositionSession,
    KeyTerm,
    ReporterCredentials,
    SessionPacket,
)
from backend.services import workspace as workspace_svc
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
    """Payload to create a case workspace on first Save.

    Field names mirror the frontend's UFM keys so the frontend can post
    its existing form state with minimal translation.
    """

    case_id: Optional[str] = None
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

    # Keyterms (term/boost/category/source dicts from the frontend)
    keyterms: list[dict] = Field(default_factory=list)


@router.post("/workspace")
def create_workspace_endpoint(payload: WorkspaceInitRequest) -> dict:
    """Create the on-disk case workspace tree and write keyterms.json.

    Called on first successful Save. Builds the
    Reporter/YYYY/YYYY-MM/case_slug/session/ tree, writes the canonical
    case_packet.json and session.json, and drops keyterms.json into the
    session's raw/ folder. workspace_state starts as 'draft'.
    """
    jt = payload.jurisdiction_type
    if jt not in ("federal", "texas_state", "other"):
        jt = "texas_state"
    lt = payload.location_type
    if lt not in ("zoom", "in_person", "hybrid", "phone", "unknown"):
        lt = "unknown"

    identity = CaseIdentity(
        case_number_value=payload.ufmCause,
        jurisdiction_type=jt,
        caption_full=payload.ufmStyle,
        judicial_district=payload.ufmCourt if jt != "federal" else None,
        court_district=payload.ufmCourt if jt == "federal" else None,
        county=payload.ufmCounty,
        state=payload.ufmState or "Texas",
    )
    reporter = ReporterCredentials(
        officer_name=payload.ufmCSRName,
        csr_license=payload.ufmCSRLicense,
        firm_registration=payload.ufmFirmReg,
        license_expiration=payload.ufmCSRCertExp,
    )
    session = DepositionSession(
        witness_name=payload.ufmWitness,
        deposition_date=payload.ufmDate,
        start_time=payload.ufmStartTime,
        end_time=payload.ufmEndTime,
        location_type=lt,
        location_address=payload.ufmAddress,
    )

    keyterms: list[KeyTerm] = []
    for kt in payload.keyterms:
        src = kt.get("source", "manual")
        if src not in ("nod_parser", "text_parser", "learned", "manual"):
            src = "manual"
        term = (kt.get("term") or "").strip()
        if not term:
            continue
        keyterms.append(KeyTerm(
            term=term,
            boost=float(kt.get("boost", 1.0) or 1.0),
            category=kt.get("category", "Term"),
            source=src,
        ))

    case_packet = CaseWorkspacePacket(
        case_id=payload.case_id,
        identity=identity,
        reporter=reporter,
        keyterms=keyterms,
    )
    session_packet = SessionPacket(
        session_id=payload.session_id,
        case_id=payload.case_id,
        session=session,
    )

    try:
        result = workspace_svc.initialize_case_workspace(
            case_packet, session_packet, reporter_name=payload.reporter_name,
        )
        # Write the Deepgram keyterms file into the session's raw/ folder
        keyterms_payload = {
            "case_id": payload.case_id,
            "case_caption": identity.caption_full,
            "cause_number": identity.case_number_value,
            "generated_at": case_packet.created_at,
            "keyterms": [k.model_dump(mode="json") for k in keyterms],
        }
        kt_path = workspace_svc.write_keyterms_file(
            result["session_dir"], keyterms_payload,
        )
        result["keyterms_path"] = kt_path
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to initialize workspace: {type(exc).__name__}: {exc}",
        ) from exc

    return result
