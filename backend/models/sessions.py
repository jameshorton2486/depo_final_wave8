"""Pydantic models for the /api/sessions router.

A session is one deposition event tied to a case. Schema columns from
backend/db/schema_v1.sql, plus the additive columns from
backend/db/migrations.py (scheduled_end_at, custodial_attorney_name,
requesting_party_name).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

WitnessType = Literal[
    "individual", "corporate_rep_30b6", "expert", "custodian", "other"
]
LocationType = Literal["zoom", "in_person", "hybrid", "phone"]
ServiceType = Literal["CR_only", "Zoom_only", "CR_plus_Zoom", "video_only", "other"]
SessionOutcome = Literal[
    "pending", "transcript_proceeding", "certified_non_appearance", "cancelled", "rescheduled"
]


class SessionCreate(BaseModel):
    """Payload for POST /api/sessions."""

    model_config = ConfigDict(str_strip_whitespace=True)

    case_id: str = Field(..., min_length=1)
    scheduled_at: str = Field(..., min_length=1, description="ISO 8601 start datetime")
    scheduled_end_at: Optional[str] = Field(default=None, description="ISO 8601 end datetime")
    timezone: str = Field(default="America/Chicago")
    witness_name: str = Field(..., min_length=1, max_length=300)
    witness_type: WitnessType = "individual"
    location_type: LocationType = "in_person"
    location_address: Optional[str] = Field(default=None, max_length=500)
    service_type: ServiceType = "CR_only"
    csr_required: int = Field(default=1, ge=0, le=1)
    reporter_id: Optional[str] = None
    ordered_by: Optional[str] = None
    notes: Optional[str] = None
    custodial_attorney_name: Optional[str] = Field(default=None, max_length=300)
    requesting_party_name: Optional[str] = Field(default=None, max_length=300)


class SessionUpdate(BaseModel):
    """Payload for PUT /api/sessions/{session_id}. All fields optional."""

    model_config = ConfigDict(str_strip_whitespace=True)

    scheduled_at: Optional[str] = None
    scheduled_end_at: Optional[str] = None
    timezone: Optional[str] = None
    witness_name: Optional[str] = Field(default=None, min_length=1, max_length=300)
    witness_type: Optional[WitnessType] = None
    location_type: Optional[LocationType] = None
    location_address: Optional[str] = Field(default=None, max_length=500)
    service_type: Optional[ServiceType] = None
    csr_required: Optional[int] = Field(default=None, ge=0, le=1)
    reporter_id: Optional[str] = None
    ordered_by: Optional[str] = None
    outcome: Optional[SessionOutcome] = None
    notes: Optional[str] = None
    custodial_attorney_name: Optional[str] = Field(default=None, max_length=300)
    requesting_party_name: Optional[str] = Field(default=None, max_length=300)


class SessionRead(BaseModel):
    """Response shape for read/list endpoints."""

    session_id: str
    case_id: str
    scheduled_at: str
    scheduled_end_at: Optional[str] = None
    timezone: str
    witness_name: str
    witness_type: WitnessType
    location_type: LocationType
    location_address: Optional[str] = None
    service_type: ServiceType
    csr_required: int
    reporter_id: Optional[str] = None
    reporting_firm_id: Optional[str] = None
    ordered_by: Optional[str] = None
    outcome: SessionOutcome
    notes: Optional[str] = None
    custodial_attorney_name: Optional[str] = None
    requesting_party_name: Optional[str] = None
    created_at: str
    updated_at: str


class SessionList(BaseModel):
    sessions: list[SessionRead]
    count: int
