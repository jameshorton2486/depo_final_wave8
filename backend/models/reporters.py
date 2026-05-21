"""Pydantic models for the /api/reporters router."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReporterCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(..., min_length=1, max_length=200)
    csr_number: Optional[str] = Field(default=None, max_length=40)
    csr_state: str = Field(default="TX", max_length=4)
    csr_expiration: Optional[str] = Field(default=None, description="ISO date")
    firm_registration_number: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)


class ReporterUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    csr_number: Optional[str] = Field(default=None, max_length=40)
    csr_state: Optional[str] = Field(default=None, max_length=4)
    csr_expiration: Optional[str] = None
    firm_registration_number: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)


class ReporterRead(BaseModel):
    reporter_id: str
    full_name: str
    csr_number: Optional[str] = None
    csr_state: Optional[str] = None
    csr_expiration: Optional[str] = None
    default_reporting_firm_id: Optional[str] = None
    firm_registration_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: str


class ReporterList(BaseModel):
    reporters: list[ReporterRead]
    count: int
