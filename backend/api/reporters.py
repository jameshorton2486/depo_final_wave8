"""Router for /api/reporters — CRUD on the reporters table.

Endpoints:
    GET    /api/reporters              list reporters, newest first
    POST   /api/reporters              create
    GET    /api/reporters/{id}         read one
    PUT    /api/reporters/{id}         update (partial)
    DELETE /api/reporters/{id}         delete
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from backend.db import repository
from backend.models.reporters import (
    ReporterCreate,
    ReporterList,
    ReporterRead,
    ReporterUpdate,
)

router = APIRouter(prefix="/api/reporters", tags=["reporters"])


@router.get("", response_model=ReporterList)
def list_reporters() -> ReporterList:
    rows = repository.list_reporters()
    return ReporterList(reporters=[ReporterRead(**r) for r in rows], count=len(rows))


@router.post("", response_model=ReporterRead, status_code=status.HTTP_201_CREATED)
def create_reporter(payload: ReporterCreate) -> ReporterRead:
    try:
        row = repository.create_reporter(payload.model_dump())
    except sqlite3.IntegrityError as exc:
        logger.warning(f"Integrity error creating reporter: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database constraint violated: {exc}",
        ) from exc
    return ReporterRead(**row)


@router.get("/{reporter_id}", response_model=ReporterRead)
def read_reporter(reporter_id: str) -> ReporterRead:
    row = repository.get_reporter(reporter_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporter {reporter_id} not found",
        )
    return ReporterRead(**row)


@router.put("/{reporter_id}", response_model=ReporterRead)
def update_reporter(reporter_id: str, payload: ReporterUpdate) -> ReporterRead:
    patch = payload.model_dump(exclude_unset=True)
    try:
        row = repository.update_reporter(reporter_id, patch)
    except sqlite3.IntegrityError as exc:
        logger.warning(f"Integrity error updating reporter {reporter_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database constraint violated: {exc}",
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporter {reporter_id} not found",
        )
    return ReporterRead(**row)


@router.delete("/{reporter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reporter(reporter_id: str) -> None:
    if not repository.delete_reporter(reporter_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporter {reporter_id} not found",
        )
