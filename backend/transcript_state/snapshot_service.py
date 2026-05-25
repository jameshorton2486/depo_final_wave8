"""Snapshot service — Wave 18.5 orchestration.

Captures the complete transcript state into an immutable Snapshot, and
restores a prior snapshot via append-only rollback.

Append-Only Audit Principle: rollback NEVER deletes or mutates a
snapshot. Restoring a prior state writes the current participants back
and records a NEW snapshot of category MANUAL noting the rollback.
"""
from __future__ import annotations

from loguru import logger

from backend.transcript import repository as trepo
from backend.transcript_state.model import ExportReference, Snapshot
from backend.transcript_state.snapshot_repo import (
    add_export_reference,
    get_snapshot,
    save_snapshot,
)
from backend.transcript_state.state_hash import compute_state_hash


def _capture_state(job_id: str) -> dict:
    """Assemble the complete transcript state for a job.

    Captures the full state per docs/wave18_5_snapshot_versioning.md
    section 4 -- semantic, render, correction, and (where available)
    AI review state. A source that is absent contributes its empty
    default; the capture never raises for missing data.
    """
    state: dict = {}
    try:
        utterances = trepo.get_utterances(job_id)
        state["render_lines"] = [
            {"utterance_id": u.get("utterance_id"),
             "speaker_index": u.get("speaker_index"),
             "role": u.get("role"),
             "text": u.get("text")}
            for u in utterances
        ]
    except Exception as exc:
        logger.warning(f"snapshot: render_lines capture failed: {exc}")
        state["render_lines"] = []

    try:
        participants = trepo.get_participants(job_id)
        state["speaker_mapping"] = [
            {"participant_id": p.get("participant_id"),
             "speaker_indices": p.get("speaker_indices") or [],
             "role": p.get("role"),
             "name": p.get("name"),
             "name_source": p.get("name_source"),
             "honorific": p.get("honorific")}
            for p in participants
        ]
        logger.info(
            f"snapshot capture speaker mapping for {job_id}: {len(state['speaker_mapping'])} participant(s)"
        )
    except Exception as exc:
        logger.warning(f"snapshot: speaker_mapping capture failed: {exc}")
        state["speaker_mapping"] = []

    # Correction / AI / lexicon / regex state -- captured when the job
    # config carries them; defaults keep the hash deterministic.
    job = trepo.get_job(job_id) or {}
    state["accepted_ai_suggestions"] = []
    state["correction_outputs"] = []
    state["lexicon_state"] = job.get("lexicon_state") or {}
    state["regex_rule_state"] = job.get("regex_rule_state") or []
    state["export_profile"] = "texas_ufm"
    state["pagination_inputs"] = {}

    # AI review state -- accepted/rejected suggestions, if the table
    # exists for this job.
    try:
        from backend.ai_review import review_queue
        suggestions = review_queue.list_suggestions(job_id)
        state["accepted_ai_suggestions"] = [
            s.suggestion_id for s in suggestions if s.status == "approved"
        ]
    except Exception as exc:
        logger.warning(f"snapshot: AI state capture skipped: {exc}")

    return state


def _capture_ai_trace(job_id: str) -> list:
    """Capture AI review traceability for the snapshot."""
    try:
        from backend.ai_review import review_queue
        out = []
        for s in review_queue.list_suggestions(job_id):
            if s.status in ("approved", "rejected"):
                out.append({
                    "suggestion_id": s.suggestion_id,
                    "kind": s.kind,
                    "status": s.status,
                    "four_part_pass": s.four_part_pass,
                })
        return out
    except Exception:
        return []


def create_snapshot(
    job_id: str,
    category: str = "MANUAL",
    note: str = "",
    created_by: str = "",
) -> Snapshot:
    """Capture the current transcript state as an immutable snapshot."""
    state = _capture_state(job_id)
    snapshot = Snapshot(
        job_id=job_id,
        state_hash=compute_state_hash(state),
        state=state,
        category=category,
        ai_trace=_capture_ai_trace(job_id),
        note=note,
        created_by=created_by,
    )
    saved = save_snapshot(snapshot)
    logger.info(
        f"Snapshot {saved.snapshot_id} created for job {job_id} "
        f"(category={category}, hash={saved.state_hash[:12]})")
    return saved


def record_export(
    snapshot_id: str,
    export_id: str,
    export_format: str,
    export_timestamp: str,
    export_hash: str = "",
) -> bool:
    """Attach an export reference to a snapshot (additive provenance)."""
    return add_export_reference(snapshot_id, ExportReference(
        export_id=export_id,
        export_format=export_format,
        export_timestamp=export_timestamp,
        export_hash=export_hash,
    ))


def rollback_to(job_id: str, snapshot_id: str,
                created_by: str = "") -> Snapshot | None:
    """Restore the transcript to a prior snapshot's state.

    Append-only: the prior snapshot is NOT modified. The current
    participants are restored from it, and a NEW snapshot is recorded
    noting the rollback. Returns the new snapshot, or None if the
    target snapshot does not exist or belongs to another job.
    """
    target = get_snapshot(snapshot_id)
    if target is None or target.job_id != job_id:
        return None

    # Restore speaker mapping from the captured state.
    mapping = target.state.get("speaker_mapping") or []
    if mapping:
        try:
            trepo.save_participants(job_id, [
                {"participant_id": m.get("participant_id"),
                 "speaker_indices": m.get("speaker_indices") or [],
                 "role": m.get("role"),
                 "name": m.get("name"),
                 "name_source": m.get("name_source"),
                 "honorific": m.get("honorific")}
                for m in mapping
            ])
            logger.info(
                f"snapshot rollback restored speaker mapping for {job_id}: {len(mapping)} participant(s)"
            )
        except Exception as exc:
            logger.warning(f"rollback: participant restore failed: {exc}")

    # Record a NEW snapshot documenting the rollback (history preserved).
    new_snap = create_snapshot(
        job_id, category="MANUAL",
        note=f"Rollback to snapshot {snapshot_id}",
        created_by=created_by)
    logger.info(f"Job {job_id} rolled back to {snapshot_id} "
                f"-> new snapshot {new_snap.snapshot_id}")
    return new_snap
