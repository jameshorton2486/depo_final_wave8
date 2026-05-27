"""Transcript ingestion orchestrator.

`process_job(job_id)` runs one queued media file through the full
Wave 1 pipeline:

    probe          -- cheap media probe (duration)
    transcribe     -- Deepgram batch ASR (or deterministic offline fallback)
    assemble       -- normalize the raw response into canonical objects
    packet         -- write the immutable raw.json + editable working.json
    persist        -- write speakers / utterances / words to SQLite
    finalize       -- mark the job completed with summary metrics

This function is designed to be called from a FastAPI BackgroundTask:
it is synchronous, does its own DB connections, and never raises -- any
failure is caught and recorded on the job row as status='failed'.

The RAW layer (raw.json + the words' raw_text) is written exactly once
and never modified afterwards. The build plan's immutability rule.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from backend.ai_review import cross_speaker_flags
from backend.config import settings
from backend.deepgram import client as deepgram_client
from backend.services import intake_store
from backend.preprocessing import probe
from backend.transcript import assembler, packet
from backend.transcript import repository as trepo


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _transcripts_dir(job_id: str) -> Path:
    """Per-job output folder: data/transcripts/{job_id}/."""
    path = settings.data_root / "transcripts" / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_keyterms(case_id: str | None) -> list[str]:
    """Load the case's Deepgram keyterms if a keyterms.json exists.

    Stage 1 writes the authoritative keyterms file under
    data/cases/{case_id}/keyterms.json. Missing file is fine -- ingestion
    just runs without vocabulary boosting.
    """
    if not case_id:
        return []
    path = intake_store.keyterms_path(case_id)
    if not path.exists():
        logger.info(f"No Stage 1 keyterms file found for case {case_id}; continuing without keyterms")
        return []
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        terms = intake_store.keyterm_strings(
            data.get("keyterms") if isinstance(data, dict) else data
        )
        logger.info(
            f"Loaded {len(terms)} Stage 1 keyterm(s) for case {case_id} from {path}"
        )
        return terms
    except Exception as exc:  # best-effort; never block ingestion
        logger.warning(f"Could not read keyterms for case {case_id}: {exc}")
    return []


def process_job(job_id: str) -> None:
    """Run the full ingestion pipeline for one job. Never raises."""
    job = trepo.get_job(job_id)
    if job is None:
        logger.error(f"process_job: job {job_id} not found")
        return

    logger.info(f"Ingesting transcript job {job_id} ({job['source_filename']})")
    try:
        _run_pipeline(job)
    except Exception as exc:  # noqa: BLE001 -- intentional catch-all
        logger.exception(f"Transcript job {job_id} failed")
        trepo.update_job(
            job_id,
            {
                "status": "failed",
                "error_message": f"{type(exc).__name__}: {exc}",
            },
        )


def _run_pipeline(job: dict) -> None:
    job_id = job["job_id"]
    audio_path = job.get("audio_path")

    # ---- 1. Preprocessing probe -------------------------------------
    trepo.update_job(job_id, {"status": "preprocessing"})
    probed_duration = probe.probe_duration_seconds(audio_path) if audio_path else None

    # ---- 2. Deepgram batch ASR (or offline fallback) ----------------
    trepo.update_job(job_id, {"status": "transcribing"})
    keyterms = load_keyterms(job.get("case_id"))
    result = deepgram_client.transcribe_file(audio_path, keyterms)
    transcription_source = result["source"]
    raw_response = result["response"]

    # ---- 3. Assemble canonical objects ------------------------------
    trepo.update_job(job_id, {"status": "assembling"})
    normalized = assembler.normalize(raw_response)
    if probed_duration and not normalized.duration_seconds:
        normalized.duration_seconds = probed_duration
    logger.info(
        f"Diarization complete for {job_id}: "
        f"{normalized.speaker_count} speaker(s), "
        f"{normalized.utterance_count} utterance(s), "
        f"source={transcription_source}"
    )

    # ---- 4. Write packets -------------------------------------------
    out_dir = _transcripts_dir(job_id)

    # The raw provider response is itself archived, immutable.
    import json

    (out_dir / "asr_response.json").write_text(
        json.dumps(raw_response, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    common_packet_args = dict(
        job_id=job_id,
        source_filename=job["source_filename"],
        source_size_bytes=job.get("source_size_bytes", 0),
        transcription_source=transcription_source,
        engine_name=job.get("engine", "deepgram-nova-3"),
        normalized=normalized,
        keyterms=keyterms,
        audio_path=audio_path,
    )
    raw_packet = packet.build_packet(layer="raw", **common_packet_args)
    working_packet = packet.build_packet(layer="working", **common_packet_args)

    raw_path = packet.write_raw_packet(raw_packet, out_dir / "raw.json")
    working_path = packet.write_packet(working_packet, out_dir / "working.json")

    # ---- 5. Persist canonical content to SQLite ---------------------
    trepo.save_transcript_content(
        job_id,
        speakers=normalized.speakers,
        utterances=normalized.utterances,
        words=normalized.words,
    )
    # Cross-speaker contamination flags are derived review metadata keyed
    # to canonical utterances. Canonical regeneration can replace the
    # utterance set, so stale rows are intentionally cleared here. This is
    # metadata cleanup only; it does not alter transcript content or ingest
    # behavior.
    cross_speaker_flags.invalidate_for_job(job_id)

    # ---- 6. Finalize ------------------------------------------------
    trepo.update_job(
        job_id,
        {
            "status": "completed",
            "transcription_source": transcription_source,
            "duration_seconds": normalized.duration_seconds,
            "word_count": normalized.word_count,
            "utterance_count": normalized.utterance_count,
            "speaker_count": normalized.speaker_count,
            "avg_confidence": normalized.avg_confidence,
            "raw_packet_path": str(raw_path),
            "working_packet_path": str(working_path),
            "completed_at": _utc_now(),
            "error_message": None,
        },
    )
    logger.success(
        f"Transcript job {job_id} completed: {normalized.word_count} words, "
        f"{normalized.utterance_count} utterances, "
        f"{normalized.speaker_count} speakers ({transcription_source})."
    )
