"""Router for /api/ai-review -- the AI review layer (Wave 15b).

Endpoints:
    GET  /api/ai-review/status                          is the AI layer live?
    POST /api/ai-review/jobs/{job_id}/speaker-map        generate map suggestion
    GET  /api/ai-review/jobs/{job_id}/suggestions        list the review queue
    POST /api/ai-review/suggestions/{id}/approve         approve one
    POST /api/ai-review/suggestions/{id}/apply           explicitly apply one approved edit
    POST /api/ai-review/suggestions/{id}/reject          reject one

AI suggestions remain advisory. Approval alone never mutates the
transcript. A second, explicit apply action is required before the
WORKING transcript changes.
"""
from __future__ import annotations

import datetime

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from backend.ai_review import client as ai_client
from backend.ai_review import cross_speaker_flags
from backend.ai_review import generators as ai_generators
from backend.ai_review import review_queue
from backend.ai_review.speaker_map import generate_speaker_map_suggestion
from backend.ai_review.suggestions import STATUS_APPROVED, STATUS_REJECTED
from backend.transcript import provenance as provenance_mod
from backend.transcript import repository as trepo
from backend.transcript import working_state as working_state_mod

router = APIRouter(prefix="/api/ai-review", tags=["ai-review"])


@router.get("/status")
def ai_status() -> dict:
    """Report whether the AI review layer is live (API key configured)."""
    available = ai_client.is_available()
    return {
        "available": available,
        "model": ai_client.DEFAULT_MODEL if available else None,
        "note": ("AI review layer is live."
                 if available else
                 "AI review layer is inert -- ANTHROPIC_API_KEY not set. "
                 "The app and the deterministic engine are unaffected."),
    }


@router.post("/jobs/{job_id}/speaker-map")
def generate_speaker_map(job_id: str) -> dict:
    """Generate an AI speaker-map SUGGESTION for a job.

    The suggestion enters the review queue; it is not applied. If the AI
    layer is inert, this returns available=False and creates nothing.
    """
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found")

    if not ai_client.is_available():
        return {
            "available": False,
            "suggestion": None,
            "note": "AI review layer is inert -- no suggestion generated.",
        }

    utterances = trepo.get_utterances(job_id)
    witness_name = ""
    case_id = row.get("case_id")
    session_id = row.get("session_id")
    if case_id:
        try:
            from backend.db import repository as case_repo
            session = case_repo.get_session(session_id) if session_id else None
            if session:
                witness_name = session.get("witness_name") or ""
        except Exception as exc:
            logger.warning(f"witness lookup failed: {exc}")

    suggestion = generate_speaker_map_suggestion(
        job_id, utterances, witness_name)
    if suggestion is None:
        return {
            "available": True,
            "suggestion": None,
            "note": "AI did not return a usable speaker map.",
        }

    review_queue.save_suggestions([suggestion])
    return {"available": True, "suggestion": suggestion.to_dict()}


# Generator registry: maps an analysis name to its generator function.
_GENERATORS = {
    "boundaries": ai_generators.generate_boundary_suggestions,
    "garbles": ai_generators.generate_garble_suggestions,
    "flags": ai_generators.generate_flag_suggestions,
}


@router.post("/jobs/{job_id}/analyze")
def analyze_job(job_id: str, kinds: str | None = None) -> dict:
    """Run the AI generators over a job and queue their suggestions.

    `kinds` is an optional comma-separated subset of
    boundaries,garbles,flags. Omitted -> all three run. Each suggestion
    enters the review queue; nothing is applied. Inert without a key.
    """
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found")

    if not ai_client.is_available():
        return {
            "available": False,
            "generated": 0,
            "note": "AI review layer is inert -- nothing generated.",
        }

    requested = (
        [k.strip() for k in kinds.split(",") if k.strip()]
        if kinds else list(_GENERATORS.keys())
    )
    unknown = [k for k in requested if k not in _GENERATORS]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown analysis kind(s): {', '.join(unknown)}")

    utterances = trepo.get_utterances(job_id)
    all_suggestions = []
    counts: dict[str, int] = {}
    for name in requested:
        try:
            produced = _GENERATORS[name](job_id, utterances)
        except Exception as exc:
            logger.warning(f"AI generator '{name}' failed for {job_id}: {exc}")
            produced = []
        counts[name] = len(produced)
        all_suggestions.extend(produced)

    if all_suggestions:
        review_queue.save_suggestions(all_suggestions)
    logger.info(f"AI analyze {job_id}: {counts}")
    return {
        "available": True,
        "generated": len(all_suggestions),
        "by_kind": counts,
    }


@router.get("/jobs/{job_id}/suggestions")
def list_suggestions(job_id: str, status_filter: str | None = None) -> dict:
    """List a job's AI suggestions, optionally filtered by status."""
    suggestions = review_queue.list_suggestions(job_id, status_filter)
    suggestions = [
        s for s in suggestions
        if not cross_speaker_flags._is_marker_payload(s.payload)
    ]
    return {
        "job_id": job_id,
        "suggestions": [s.to_dict() for s in suggestions],
        "count": len(suggestions),
    }


@router.post("/suggestions/{suggestion_id}/approve")
def approve_suggestion(suggestion_id: str) -> dict:
    """Approve one suggestion. Approval does not mutate transcript text."""
    suggestion = review_queue.get_suggestion(suggestion_id)
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion {suggestion_id} not found")
    try:
        review_queue.set_status(suggestion_id, STATUS_APPROVED)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    logger.info(f"AI suggestion {suggestion_id} approved by reporter.")
    return {"suggestion_id": suggestion_id, "status": STATUS_APPROVED}


@router.post("/suggestions/{suggestion_id}/reject")
def reject_suggestion(suggestion_id: str) -> dict:
    """Reject one suggestion -- it never reaches the transcript."""
    suggestion = review_queue.get_suggestion(suggestion_id)
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion {suggestion_id} not found")
    try:
        review_queue.set_status(suggestion_id, STATUS_REJECTED)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {"suggestion_id": suggestion_id, "status": STATUS_REJECTED}


@router.post("/suggestions/{suggestion_id}/apply")
def apply_suggestion(suggestion_id: str) -> dict:
    """Explicitly apply one APPROVED AI edit to the WORKING transcript.

    Approval alone never mutates transcript text. This endpoint is the
    second, explicit human action. RAW transcript state remains untouched.
    """
    suggestion = review_queue.get_suggestion(suggestion_id)
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion {suggestion_id} not found")
    if suggestion.status != STATUS_APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suggestion must be approved before it can be applied.")
    if not suggestion.is_applicable_edit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This AI suggestion is advisory only and cannot be applied.")
    if not suggestion.target_utterance_id or not suggestion.after_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suggestion does not identify a usable transcript edit.")

    utterances = trepo.get_utterances(suggestion.job_id, layer="working")
    target = next(
        (u for u in utterances if u["utterance_id"] == suggestion.target_utterance_id),
        None,
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Target utterance {suggestion.target_utterance_id} does not "
                f"belong to transcript job {suggestion.job_id}."
            ),
        )

    result = working_state_mod.persist_working_transcript(
        suggestion.job_id,
        [{
            "utterance_id": suggestion.target_utterance_id,
            "working_text": suggestion.after_text,
        }],
        source="ai_apply",
    )
    review_queue.update_payload(
        suggestion_id,
        {
            "applied_to_transcript": True,
            "applied_at": datetime.datetime.utcnow().isoformat(),
            "applied_text": suggestion.after_text,
        },
    )
    try:
        provenance_mod.record_event(
            suggestion.job_id,
            event_type="ai_suggestion_applied",
            title="AI Suggestion Applied",
            detail=(
                f"Applied approved AI {suggestion.kind} suggestion to "
                f"utterance {suggestion.target_utterance_id}."
            ),
            actor_type="user",
            source="ai_review",
            metadata={
                "kind": suggestion.kind,
                "before_text": suggestion.before_text,
                "after_text": suggestion.after_text,
            },
            related_suggestion_id=suggestion_id,
        )
    except Exception as exc:
        logger.warning(f"AI apply provenance record failed: {exc}")
    logger.info(
        f"AI suggestion {suggestion_id} applied to job {suggestion.job_id} "
        f"utterance {suggestion.target_utterance_id}"
    )
    return {
        "suggestion_id": suggestion_id,
        "status": suggestion.status,
        "applied": True,
        "job_id": suggestion.job_id,
        "target_utterance_id": suggestion.target_utterance_id,
        "working_transcript": result,
    }
