"""Router for /api/ai-review -- the AI review layer (Wave 15b).

Endpoints:
    GET  /api/ai-review/status                          is the AI layer live?
    POST /api/ai-review/jobs/{job_id}/speaker-map        generate map suggestion
    GET  /api/ai-review/jobs/{job_id}/suggestions        list the review queue
    POST /api/ai-review/suggestions/{id}/approve         approve one
    POST /api/ai-review/suggestions/{id}/reject          reject one

Approval is the only path from a suggestion to the transcript. The AI
layer never writes the WORKING transcript directly.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from backend.ai_review import client as ai_client
from backend.ai_review import generators as ai_generators
from backend.ai_review import review_queue
from backend.ai_review.speaker_map import generate_speaker_map_suggestion
from backend.ai_review.suggestions import STATUS_APPROVED, STATUS_REJECTED
from backend.transcript import repository as trepo

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
    if case_id:
        try:
            from backend.db import repository as case_repo
            case = case_repo.get_case(case_id)
            if case:
                witness_name = case.get("witness_name") or ""
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
    return {
        "job_id": job_id,
        "suggestions": [s.to_dict() for s in suggestions],
        "count": len(suggestions),
    }


@router.post("/suggestions/{suggestion_id}/approve")
def approve_suggestion(suggestion_id: str) -> dict:
    """Approve one suggestion. Approval is the gate to the transcript."""
    suggestion = review_queue.get_suggestion(suggestion_id)
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion {suggestion_id} not found")
    review_queue.set_status(suggestion_id, STATUS_APPROVED)
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
    review_queue.set_status(suggestion_id, STATUS_REJECTED)
    return {"suggestion_id": suggestion_id, "status": STATUS_REJECTED}
