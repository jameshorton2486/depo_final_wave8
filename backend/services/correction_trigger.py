"""Correction-engine trigger service.

Wave 11 section 7.1: the deterministic correction engine runs
automatically — in the background, no user click — as soon as the
Speaker Mapping is *confirmed*. The engine's role-scoped stages need
confirmed roles, so "transcription finished" is not a sufficient
trigger; "speaker mapping confirmed" is.

This module is the single bridge between the participant mapping and
`backend.corrections.pipeline`. It builds the engine's `Utterance`
inputs (each carrying its confirmed Wave 9 role) from the stored
utterances + participants, runs the pipeline, and returns the result.

It is deliberately defensive: the correction engine is optional
infrastructure. If it is absent or raises, this service logs and
returns None — a missing engine never breaks speaker mapping.
"""
from __future__ import annotations

from typing import Optional

from loguru import logger

from backend.transcript.render import build_index_map
from backend.transcript import working_state as working_state_mod


def run_correction_engine_for_job(
    job_id: str,
    *,
    job_config: Optional[dict] = None,
) -> Optional[dict]:
    """Run the deterministic correction engine for one job.

    Builds role-tagged Utterance inputs from the confirmed participant
    mapping and runs the pipeline. Returns a small summary dict, or None
    if the engine is unavailable or the job has no confirmed mapping.

    This is safe to call in a background task and safe to call twice —
    the engine is idempotent.
    """
    try:
        from backend.corrections import pipeline as corrections_pipeline
        from backend.corrections.model import Utterance
    except Exception as exc:
        logger.info(f"Correction engine not present; skipping for {job_id}: {exc}")
        return None

    from backend.transcript import repository as trepo

    participants = trepo.get_participants(job_id)
    if not participants:
        logger.info(f"No confirmed mapping for {job_id}; correction engine not run.")
        return None

    utterances = working_state_mod.get_working_utterances(job_id)
    index_map = build_index_map(participants)

    engine_input: list = []
    for utt in sorted(
        utterances,
        key=lambda u: (u.get("utterance_index") if u.get("utterance_index") is not None else 0),
    ):
        idx = utt.get("speaker_index")
        info = index_map.get(idx) if idx is not None else None
        role = info["role"] if info else "other"  # unmapped -> 'other'
        engine_input.append(Utterance(
            utterance_id=utt.get("utterance_id") or "",
            speaker_index=idx,
            role=role,
            text=utt.get("text") or "",
            participant_name=(info["label"] if info else None),
            start_time=utt.get("start_time") or 0.0,
            end_time=utt.get("end_time") or 0.0,
        ))

    try:
        result = corrections_pipeline.run(
            engine_input,
            job_config=job_config or {},
            speaker_map_confirmed=True,
        )
    except Exception as exc:
        logger.warning(f"Correction engine run failed for {job_id}: {exc}")
        return None

    summary = {
        "job_id": job_id,
        "line_count": len(result.lines),
        "correction_count": len(result.log),
        "flag_count": len(result.flags),
        "parity_mode": result.parity_mode,
    }
    logger.info(
        f"Correction engine ran for {job_id}: "
        f"{summary['correction_count']} correction(s), {summary['flag_count']} flag(s)"
    )
    return summary
