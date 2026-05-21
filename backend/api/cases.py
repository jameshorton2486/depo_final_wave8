"""Router for /api/cases — CRUD on the cases table.

Endpoints:
    GET    /api/cases             list, newest first
    POST   /api/cases             create
    GET    /api/cases/{case_id}   read one
    PUT    /api/cases/{case_id}   update (partial)
    DELETE /api/cases/{case_id}   delete

This router currently persists only the case-level UFM fields. Witness,
date, address, CSR, and attorney fields require the sessions / reporters
/ attorneys routers to be built next.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from backend.db import repository
from backend.models.cases import CaseCreate, CaseList, CaseRead, CaseUpdate

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=CaseList)
def list_cases() -> CaseList:
    rows = repository.list_cases()
    return CaseList(cases=[CaseRead(**r) for r in rows], count=len(rows))


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate) -> CaseRead:
    try:
        row = repository.create_case(payload.model_dump())
    except sqlite3.IntegrityError as exc:
        logger.warning(f"Integrity error creating case: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database constraint violated: {exc}",
        ) from exc
    return CaseRead(**row)


@router.get("/{case_id}", response_model=CaseRead)
def read_case(case_id: str) -> CaseRead:
    row = repository.get_case(case_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    return CaseRead(**row)


@router.put("/{case_id}", response_model=CaseRead)
def update_case(case_id: str, payload: CaseUpdate) -> CaseRead:
    # exclude_unset means "only the fields the client actually sent"
    patch = payload.model_dump(exclude_unset=True)
    try:
        row = repository.update_case(case_id, patch)
    except sqlite3.IntegrityError as exc:
        logger.warning(f"Integrity error updating case {case_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database constraint violated: {exc}",
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    return CaseRead(**row)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: str) -> None:
    if not repository.delete_case(case_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
