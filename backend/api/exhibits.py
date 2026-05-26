"""Router for /api/exhibits -- authoritative Stage 4 exhibit records."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from backend.models.transcripts import (
    TranscriptExhibit,
    TranscriptExhibitCreateRequest,
    TranscriptExhibitListResponse,
    TranscriptExhibitUpdateRequest,
)
from backend.transcript import provenance as provenance_mod
from backend.transcript import repository as trepo

router = APIRouter(prefix="/api/exhibits", tags=["exhibits"])


def _anchor_context(job_id: str, anchor_utterance_id: str) -> dict:
    utterance = next(
        (
            u for u in trepo.get_utterances(job_id, layer="working")
            if u["utterance_id"] == anchor_utterance_id
        ),
        None,
    )
    if not utterance:
        return {}
    text = (utterance.get("text") or "").strip()
    return {
        "anchor_preview": text[:160],
        "anchor_speaker_label": utterance.get("speaker_label") or "",
        "anchor_utterance_index": utterance.get("utterance_index"),
    }


def _serialize_exhibit(row: dict) -> dict:
    return {
        **TranscriptExhibit(**row).model_dump(),
        **_anchor_context(row["job_id"], row["anchor_utterance_id"]),
    }


@router.get("/jobs/{job_id}", response_model=TranscriptExhibitListResponse)
def list_job_exhibits(job_id: str) -> TranscriptExhibitListResponse:
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    rows = trepo.list_exhibits(job_id)
    return TranscriptExhibitListResponse(
        job_id=job_id,
        exhibits=[TranscriptExhibit(**row) for row in rows],
        count=len(rows),
    )


@router.post("/jobs/{job_id}", response_model=TranscriptExhibit, status_code=status.HTTP_201_CREATED)
def create_job_exhibit(
    job_id: str,
    payload: TranscriptExhibitCreateRequest,
) -> TranscriptExhibit:
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    try:
        row = trepo.create_exhibit(job_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        detail = str(exc)
        if "UNIQUE constraint failed" in detail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Exhibit number {payload.exhibit_number} already exists for this job.",
            )
        raise
    try:
        provenance_mod.record_event(
            job_id,
            event_type="exhibit_created",
            title="Exhibit Created",
            detail=f"Exhibit {row['exhibit_number']} anchored to utterance {row['anchor_utterance_id']}.",
            actor_type="user",
            source="exhibits",
            metadata={
                "exhibit_id": row["exhibit_id"],
                "exhibit_number": row["exhibit_number"],
                "anchor_utterance_id": row["anchor_utterance_id"],
            },
        )
    except Exception as exc:
        logger.warning(f"exhibit provenance record failed: {exc}")
    logger.info(
        f"Exhibit created for {job_id}: {row['exhibit_number']} -> {row['anchor_utterance_id']}"
    )
    return TranscriptExhibit(**row)


@router.put("/{exhibit_id}", response_model=TranscriptExhibit)
def update_exhibit(
    exhibit_id: str,
    payload: TranscriptExhibitUpdateRequest,
) -> TranscriptExhibit:
    existing = trepo.get_exhibit(exhibit_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit {exhibit_id} not found",
        )
    try:
        row = trepo.update_exhibit(exhibit_id, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        detail = str(exc)
        if "UNIQUE constraint failed" in detail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That exhibit number already exists for this transcript job.",
            )
        raise
    assert row is not None
    try:
        provenance_mod.record_event(
            row["job_id"],
            event_type="exhibit_updated",
            title="Exhibit Updated",
            detail=f"Exhibit {row['exhibit_number']} updated.",
            actor_type="user",
            source="exhibits",
            metadata={
                "exhibit_id": row["exhibit_id"],
                "anchor_utterance_id": row["anchor_utterance_id"],
            },
        )
    except Exception as exc:
        logger.warning(f"exhibit update provenance record failed: {exc}")
    logger.info(
        f"Exhibit updated for {row['job_id']}: {row['exhibit_number']} -> {row['anchor_utterance_id']}"
    )
    return TranscriptExhibit(**row)


@router.delete("/{exhibit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exhibit(exhibit_id: str) -> None:
    existing = trepo.get_exhibit(exhibit_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit {exhibit_id} not found",
        )
    if not trepo.delete_exhibit(exhibit_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete exhibit {exhibit_id}",
        )
    try:
        provenance_mod.record_event(
            existing["job_id"],
            event_type="exhibit_deleted",
            title="Exhibit Deleted",
            detail=f"Deleted exhibit {existing['exhibit_number']}.",
            actor_type="user",
            source="exhibits",
            metadata={
                "exhibit_id": existing["exhibit_id"],
                "exhibit_number": existing["exhibit_number"],
                "anchor_utterance_id": existing["anchor_utterance_id"],
            },
        )
    except Exception as exc:
        logger.warning(f"exhibit delete provenance record failed: {exc}")
    logger.info(f"Exhibit deleted for {existing['job_id']}: {existing['exhibit_number']}")
