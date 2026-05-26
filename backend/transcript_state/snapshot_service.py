"""Snapshot service — Wave 18.5 orchestration.

Captures the complete transcript state into an immutable Snapshot, and
restores a prior snapshot via append-only rollback.

Append-Only Audit Principle: rollback NEVER deletes or mutates a
snapshot. Restoring a prior state writes the current participants back
and records a NEW snapshot of category MANUAL noting the rollback.
"""
from __future__ import annotations

from loguru import logger

from backend.services import intake_store
from backend.transcript import repository as trepo
from backend.transcript import provenance as provenance_mod
from backend.transcript import working_state as working_state_mod
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
        raw_utterances = trepo.get_utterances(job_id, layer="raw")
        utterances = trepo.get_utterances(job_id, layer="working")
        raw_map = {u.get("utterance_id"): u for u in raw_utterances}
        state["working_utterances"] = [
            {
                "utterance_id": u.get("utterance_id"),
                "utterance_index": u.get("utterance_index"),
                "speaker_index": u.get("speaker_index"),
                "speaker_label": u.get("speaker_label"),
                "start_time": u.get("start_time"),
                "end_time": u.get("end_time"),
                "raw_text": (raw_map.get(u.get("utterance_id")) or {}).get("text") or "",
                "working_text": u.get("working_text"),
                "text": u.get("text") or "",
                "is_working_override": bool(u.get("is_working_override")),
                "working_source": u.get("working_source") or "",
                "working_updated_at": u.get("working_updated_at") or "",
            }
            for u in utterances
        ]
        state["render_lines"] = [
            {"utterance_id": u.get("utterance_id"),
             "speaker_index": u.get("speaker_index"),
             "text": u.get("text")}
            for u in utterances
        ]
    except Exception as exc:
        logger.warning(f"snapshot: render_lines capture failed: {exc}")
        state["working_utterances"] = []
        state["render_lines"] = []

    try:
        state["exhibits"] = [
            {
                "exhibit_id": ex.get("exhibit_id"),
                "job_id": ex.get("job_id"),
                "case_id": ex.get("case_id"),
                "session_id": ex.get("session_id"),
                "exhibit_number": ex.get("exhibit_number"),
                "exhibit_title": ex.get("exhibit_title") or "",
                "offering_attorney": ex.get("offering_attorney") or "",
                "description": ex.get("description") or "",
                "anchor_utterance_id": ex.get("anchor_utterance_id"),
                "anchor_note": ex.get("anchor_note") or "",
                "sort_order": ex.get("sort_order", 0),
                "created_at": ex.get("created_at") or "",
                "updated_at": ex.get("updated_at") or "",
            }
            for ex in trepo.list_exhibits(job_id)
        ]
    except Exception as exc:
        logger.warning(f"snapshot: exhibit capture failed: {exc}")
        state["exhibits"] = []

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

    # Correction / AI / lexicon / regex state -- captured from the live
    # case configuration so snapshot-based certification/export can
    # replay the same deterministic transforms later.
    job = trepo.get_job(job_id) or {}
    state["transcript_metadata"] = {
        "job_id": job_id,
        "raw_packet_path": job.get("raw_packet_path") or "",
        "working_packet_path": job.get("working_packet_path") or "",
        "audio_path": job.get("audio_path") or "",
    }
    state["export_metadata"] = {
        "caption": "",
        "cause_number": "",
        "witness_name": "",
        "proceedings_date": "",
        "examining_attorney_label": "",
    }
    state["provenance_refs"] = {
        "raw_packet_path": job.get("raw_packet_path") or "",
        "working_packet_path": job.get("working_packet_path") or "",
    }
    state["accepted_ai_suggestions"] = []
    state["correction_outputs"] = []
    state["lexicon_state"] = {}
    state["regex_rule_state"] = []
    state["export_profile"] = "texas_ufm"
    state["pagination_inputs"] = {}

    case_id = job.get("case_id")
    if case_id:
        try:
            from backend.db import regex_rules_repo
            from backend.db import repository as case_repo

            case = case_repo.get_case(case_id) or {}
            session = case_repo.get_session(job.get("session_id")) if job.get("session_id") else {}
            intake = intake_store.read_stage1_record(case_id)
            state["regex_rule_state"] = [
                {
                    "rule_id": r.rule_id,
                    "find_pattern": r.find_pattern,
                    "replace_with": r.replace_with,
                    "rule_order": r.rule_order,
                    "enabled": r.enabled,
                    "description": r.description,
                }
                for r in regex_rules_repo.list_rules(case_id)
            ]
            state["lexicon_state"] = {
                "confirmed_spellings": case.get("confirmed_spellings") or {},
                "intake_keyterms": intake_store.keyterm_strings(
                    intake.get("keyterms") or []
                ),
            }
            state["export_metadata"] = {
                "caption": case.get("caption_full") or "",
                "cause_number": case.get("case_number_value") or "",
                "witness_name": (session or {}).get("witness_name") or "",
                "proceedings_date": ((session or {}).get("scheduled_at") or "")[:10],
                "examining_attorney_label": "",
            }
        except Exception as exc:
            logger.warning(f"snapshot: lexicon/regex state capture skipped: {exc}")

    for p in state.get("speaker_mapping") or []:
        if p.get("role") == "examining_attorney":
            name = (p.get("name") or "").strip()
            honorific = (p.get("honorific") or "").strip()
            if name:
                state["export_metadata"]["examining_attorney_label"] = (
                    f"{honorific + ' ' if honorific else ''}{name}".strip()
                )
            break
    for p in state.get("speaker_mapping") or []:
        if p.get("role") == "witness" and p.get("name"):
            state["export_metadata"]["witness_name"] = p.get("name") or ""
            break

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
    try:
        provenance_mod.record_event(
            job_id,
            event_type="snapshot_created",
            title="Snapshot Created",
            detail=f"{category} snapshot captured.",
            actor_type="system",
            source="snapshots",
            metadata={
                "category": category,
                "state_hash": saved.state_hash,
            },
            related_snapshot_id=saved.snapshot_id,
        )
    except Exception as exc:
        logger.warning(f"snapshot provenance record failed: {exc}")
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

    # Restore working transcript overrides from the captured state.
    working_utterances = target.state.get("working_utterances") or []
    try:
        working_state_mod.replace_working_transcript_from_snapshot(
            job_id,
            [
                {
                    "utterance_id": u.get("utterance_id"),
                    "working_text": u.get("text") or u.get("raw_text") or "",
                }
                for u in working_utterances
            ],
        )
        logger.info(
            f"snapshot rollback restored working transcript for {job_id}: "
            f"{len(working_utterances)} utterance(s)"
        )
    except Exception as exc:
        logger.warning(f"rollback: working transcript restore failed: {exc}")

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

    exhibits = target.state.get("exhibits") or []
    try:
        trepo.replace_exhibits(job_id, exhibits)
        logger.info(
            f"snapshot rollback restored exhibits for {job_id}: {len(exhibits)} exhibit(s)"
        )
    except Exception as exc:
        logger.warning(f"rollback: exhibit restore failed: {exc}")

    # Record a NEW snapshot documenting the rollback (history preserved).
    new_snap = create_snapshot(
        job_id, category="MANUAL",
        note=f"Rollback to snapshot {snapshot_id}",
        created_by=created_by)
    try:
        provenance_mod.record_event(
            job_id,
            event_type="snapshot_restored",
            title="Snapshot Restored",
            detail=(
                f"Restored working transcript, speaker mapping, and exhibits "
                f"from snapshot {snapshot_id}."
            ),
            actor_type="system",
            source="snapshots",
            metadata={
                "restored_from_snapshot_id": snapshot_id,
                "created_snapshot_id": new_snap.snapshot_id,
                "restored_exhibit_count": len(exhibits),
            },
            related_snapshot_id=snapshot_id,
        )
    except Exception as exc:
        logger.warning(f"rollback provenance record failed: {exc}")
    logger.info(f"Job {job_id} rolled back to {snapshot_id} "
                f"-> new snapshot {new_snap.snapshot_id}")
    return new_snap
