"""Router for /api/sessions — CRUD on the sessions table.

Endpoints:
    GET    /api/sessions?case_id=...     list sessions for a case
    POST   /api/sessions                 create
    GET    /api/sessions/{session_id}    read one
    PUT    /api/sessions/{session_id}    update (partial)
    DELETE /api/sessions/{session_id}    delete
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger

from backend.db import repository
from backend.models.sessions import (
    SessionCreate,
    SessionList,
    SessionRead,
    SessionUpdate,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=SessionList)
def list_sessions(case_id: str = Query(..., description="Case to list sessions for")) -> SessionList:
    rows = repository.list_sessions_for_case(case_id)
    return SessionList(sessions=[SessionRead(**r) for r in rows], count=len(rows))


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate) -> SessionRead:
    # Verify the case exists so we get a clean 400 rather than a FK error
    if repository.get_case(payload.case_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Case {payload.case_id} does not exist",
        )
    try:
        row = repository.create_session(payload.model_dump())
    except sqlite3.IntegrityError as exc:
        logger.warning(f"Integrity error creating session: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database constraint violated: {exc}",
        ) from exc
    return SessionRead(**row)


@router.get("/{session_id}", response_model=SessionRead)
def read_session(session_id: str) -> SessionRead:
    row = repository.get_session(session_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return SessionRead(**row)


@router.put("/{session_id}", response_model=SessionRead)
def update_session(session_id: str, payload: SessionUpdate) -> SessionRead:
    patch = payload.model_dump(exclude_unset=True)
    try:
        row = repository.update_session(session_id, patch)
    except sqlite3.IntegrityError as exc:
        logger.warning(f"Integrity error updating session {session_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database constraint violated: {exc}",
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return SessionRead(**row)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str) -> None:
    if not repository.delete_session(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
