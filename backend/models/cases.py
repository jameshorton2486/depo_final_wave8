"""Pydantic models for the /api/cases router.

These match the `cases` table in backend/db/schema_v1.sql. Field
names mirror the SQL column names so the API surface stays close to
the canonical data model. The frontend translates UI field names
(cause, caption, court, ...) to these names in assets/js/api.js.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

JurisdictionType = Literal["federal", "texas_state", "other"]
CaseNumberLabel = Literal["civil_action_no", "cause_no", "docket_no", "other"]


class CaseCreate(BaseModel):
    """Payload accepted by POST /api/cases."""

    model_config = ConfigDict(str_strip_whitespace=True)

    case_number_value: str = Field(..., min_length=1, max_length=64)
    jurisdiction_type: JurisdictionType = "texas_state"
    case_number_label: CaseNumberLabel = "cause_no"
    caption_full: Optional[str] = Field(default=None, max_length=2000)
    court_district: Optional[str] = Field(default=None, max_length=200)
    court_division: Optional[str] = Field(default=None, max_length=200)
    judicial_district: Optional[str] = Field(default=None, max_length=200)
    county: Optional[str] = Field(default=None, max_length=120)
    state: str = Field(default="Texas", max_length=60)


class CaseUpdate(BaseModel):
    """Payload accepted by PUT /api/cases/{case_id}. All fields optional.

    Only fields present in the request body are updated. A field set
    to null explicitly clears the column (except for required ones).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    case_number_value: Optional[str] = Field(default=None, min_length=1, max_length=64)
    jurisdiction_type: Optional[JurisdictionType] = None
    case_number_label: Optional[CaseNumberLabel] = None
    caption_full: Optional[str] = Field(default=None, max_length=2000)
    court_district: Optional[str] = Field(default=None, max_length=200)
    court_division: Optional[str] = Field(default=None, max_length=200)
    judicial_district: Optional[str] = Field(default=None, max_length=200)
    county: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, max_length=60)


class CaseRead(BaseModel):
    """Response shape for GET / POST / PUT."""

    case_id: str
    case_number_value: str
    jurisdiction_type: JurisdictionType
    case_number_label: CaseNumberLabel
    caption_full: Optional[str] = None
    court_district: Optional[str] = None
    court_division: Optional[str] = None
    judicial_district: Optional[str] = None
    county: Optional[str] = None
    state: str
    intake_timestamp: str
    created_at: str
    updated_at: str


class CaseList(BaseModel):
    """Response shape for GET /api/cases (list endpoint)."""

    cases: list[CaseRead]
    count: int
