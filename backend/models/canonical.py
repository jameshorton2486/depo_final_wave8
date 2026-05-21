"""Canonical data models for DEPO-PRO.

This module is the single source of truth for the shapes of the core
domain entities. Parsers, the workspace service, and (over time) the
API layer all speak these models instead of loose dicts.

Design notes:
  - These are deliberately small and composable — no giant nested
    mega-objects. A `CaseWorkspacePacket` is assembled FROM these
    pieces; the pieces are not derived from it.
  - Field names are the canonical vocabulary. Where the frontend or
    an existing router uses different names (the UI's `ufmCause`,
    the `cases` table's `case_number_value`), translation happens at
    that boundary — not here.
  - Every model is JSON-serializable via `.model_dump()` so it can be
    written straight into `case_packet.json` / `session.json`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

JurisdictionType = Literal["federal", "texas_state", "other"]
LocationType = Literal["zoom", "in_person", "hybrid", "phone", "unknown"]
KeytermSource = Literal["nod_parser", "text_parser", "learned", "manual"]


class WorkspaceState(str, Enum):
    """Lifecycle state of a case/session workspace on disk.

    draft      — created on first Save; intake captured, not yet processing
    active     — user clicked 'Proceed to Transcripts Engine'
    processing — transcription in progress
    review     — transcript under proofreading review
    certified  — final transcript certified and exported
    archived   — soft-deleted / retired (never hard-deleted)
    """

    DRAFT = "draft"
    ACTIVE = "active"
    PROCESSING = "processing"
    REVIEW = "review"
    CERTIFIED = "certified"
    ARCHIVED = "archived"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CanonicalModel(BaseModel):
    """Base: strips whitespace, forbids unknown fields to catch drift early."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


# ---------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------

class CaseIdentity(CanonicalModel):
    """Who/where a case is — the Block 1 'Case & Court Parameters' data."""

    case_number_value: Optional[str] = Field(default=None, max_length=64)
    case_number_label: str = "cause_no"
    jurisdiction_type: JurisdictionType = "texas_state"
    caption_full: Optional[str] = Field(default=None, max_length=2000)
    court_district: Optional[str] = Field(default=None, max_length=200)
    court_division: Optional[str] = Field(default=None, max_length=200)
    judicial_district: Optional[str] = Field(default=None, max_length=200)
    county: Optional[str] = Field(default=None, max_length=120)
    state: str = "Texas"


class Participant(CanonicalModel):
    """A person attached to a deposition — attorney, deponent, or firm rep."""

    role: Literal[
        "deponent", "custodial_attorney", "copy_attorney",
        "requesting_party", "other",
    ] = "other"
    name: Optional[str] = Field(default=None, max_length=200)
    firm: Optional[str] = Field(default=None, max_length=200)
    bar_number: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=400)


class ReporterCredentials(CanonicalModel):
    """The Block 3 'Court Reporter (CSR) Credentials' data."""

    officer_name: Optional[str] = Field(default=None, max_length=200)
    csr_license: Optional[str] = Field(default=None, max_length=40)
    firm_registration: Optional[str] = Field(default=None, max_length=40)
    license_expiration: Optional[str] = Field(default=None, max_length=20)
    agency: Optional[str] = Field(default=None, max_length=200)


class DepositionSession(CanonicalModel):
    """One deposition — a witness deposed on a date. A case has 1..n of these."""

    witness_name: Optional[str] = Field(default=None, max_length=200)
    deposition_date: Optional[str] = Field(default=None, max_length=20)  # ISO YYYY-MM-DD
    start_time: Optional[str] = Field(default=None, max_length=20)
    end_time: Optional[str] = Field(default=None, max_length=20)
    location_type: LocationType = "unknown"
    location_address: Optional[str] = Field(default=None, max_length=400)


class KeyTerm(CanonicalModel):
    """One Deepgram keyterm with a boost weight and provenance."""

    term: str = Field(..., min_length=1, max_length=200)
    boost: float = Field(default=1.0, ge=0.0, le=10.0)
    category: str = Field(default="Term", max_length=40)
    source: KeytermSource = "manual"


# ---------------------------------------------------------------------
# Composite: the workspace packet
# ---------------------------------------------------------------------

class CaseWorkspacePacket(CanonicalModel):
    """The canonical snapshot written to `case_packet.json`.

    Assembled from the small models above — intentionally NOT a place
    to invent new nested structures. New data belongs in one of the
    component models or a new sibling model, not buried here.
    """

    schema_version: int = 1
    case_id: Optional[str] = None
    workspace_state: WorkspaceState = WorkspaceState.DRAFT
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)

    identity: CaseIdentity = Field(default_factory=CaseIdentity)
    reporter: ReporterCredentials = Field(default_factory=ReporterCredentials)
    participants: list[Participant] = Field(default_factory=list)
    keyterms: list[KeyTerm] = Field(default_factory=list)


class SessionPacket(CanonicalModel):
    """The canonical snapshot written to a session's `session.json`."""

    schema_version: int = 1
    session_id: Optional[str] = None
    case_id: Optional[str] = None
    workspace_state: WorkspaceState = WorkspaceState.DRAFT
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)

    session: DepositionSession = Field(default_factory=DepositionSession)
