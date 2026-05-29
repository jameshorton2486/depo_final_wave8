"""Router for /api/transcripts -- the Stage 2 transcripts engine.

Endpoints:
    POST   /api/transcripts/upload                 upload media, queue a job
    GET    /api/transcripts/jobs                    list jobs (?case_id=...)
    GET    /api/transcripts/jobs/{job_id}           job status + metadata
    GET    /api/transcripts/jobs/{job_id}/content   full canonical content
    GET    /api/transcripts/jobs/{job_id}/packet    working transcript packet
    GET    /api/transcripts/jobs/{job_id}/raw       immutable raw packet
    DELETE /api/transcripts/jobs/{job_id}           delete a job
    POST   /api/transcripts/readback                search persisted transcripts

Processing model: upload saves the file and creates a 'queued' job, then
the ingestion pipeline runs as a FastAPI BackgroundTask. The frontend
polls GET /jobs/{job_id} for status. This keeps the local-first desktop
build simple -- no external queue/worker infrastructure.
"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from backend.config import settings
from backend.ai_review import cross_speaker_flags
from backend.models.transcripts import (
    DetectedSpeaker,
    ReadbackMatch,
    ReadbackResult,
    RoleOption,
    SpeakerMappingApplyResponse,
    SpeakerMappingSaveRequest,
    SpeakerMappingView,
    TranscriptContent,
    TranscriptExhibit,
    TranscriptJob,
    TranscriptJobList,
    TranscriptJobUpdateRequest,
    TranscriptParticipant,
    TranscriptProvenanceCreateRequest,
    TranscriptProvenanceEvent,
    TranscriptProvenanceListResponse,
    TranscriptSpeaker,
    TranscriptUtterance,
    TranscriptWord,
    WorkingTranscriptSaveRequest,
    WorkingTranscriptSaveResponse,
)
from backend.services import correction_trigger, intake_store, speaker_mapping
from backend.transcript import export_render as export_render_mod
from backend.transcript import ingest
from backend.transcript import integrity as integrity_mod
from backend.transcript import packet as packet_mod
from backend.transcript import provenance as provenance_mod
from backend.transcript import render as render_mod
from backend.transcript import repository as trepo
from backend.transcript import working_state as working_state_mod
from backend.transcript_state import snapshot_repo

router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])

# Upload guard. The standard-library Deepgram uploader has its own
# 250 MB cap; this is the server-side accept limit.
MAX_UPLOAD_BYTES = 300 * 1024 * 1024  # 300 MB

ALLOWED_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".mp4",
    ".mov",
    ".aac",
    ".ogg",
    ".flac",
    ".webm",
}


def _safe_filename(name: str) -> str:
    """Strip path components and unsafe characters from an upload filename."""
    name = Path(name or "upload").name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name or "upload"


def _audio_dir() -> Path:
    path = settings.data_root / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _media_content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _iter_file_range(path: Path, start: int, end: int, chunk_size: int = 64 * 1024):
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _resolve_media_range(range_header: str | None, file_size: int) -> tuple[int, int, bool]:
    if not range_header:
        return 0, max(0, file_size - 1), False
    match = re.match(r"^bytes=(\d*)-(\d*)$", range_header.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Invalid Range header.",
        )
    start_raw, end_raw = match.groups()
    if start_raw == "" and end_raw == "":
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Invalid Range header.",
        )
    if start_raw == "":
        length = int(end_raw)
        if length <= 0:
            raise HTTPException(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                detail="Invalid Range header.",
            )
        start = max(0, file_size - length)
        end = max(0, file_size - 1)
        return start, end, True

    start = int(start_raw)
    end = int(end_raw) if end_raw else max(0, file_size - 1)
    if start >= file_size or start < 0 or end < start:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Requested range not satisfiable.",
        )
    end = min(end, max(0, file_size - 1))
    return start, end, True


def _assert_raw_integrity_or_409(job_row: dict) -> None:
    raw_packet_path = (job_row or {}).get("raw_packet_path")
    if not raw_packet_path:
        return
    try:
        integrity_mod.verify_raw_packet(raw_packet_path)
    except integrity_mod.RawTranscriptIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Raw transcript integrity verification failed. The immutable raw "
                f"record for job {job_row.get('job_id')} appears to have been tampered with: {exc}"
            ),
        ) from exc


# ====================================================================
# Upload + queue
# ====================================================================


@router.post("/upload", response_model=TranscriptJob, status_code=status.HTTP_201_CREATED)
async def upload_transcript(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    case_id: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
    sequence_index: int = Form(default=0),
) -> TranscriptJob:
    """Accept one media file, persist it, and queue a transcription job.

    Returns the created job immediately with status='queued'. The
    ingestion pipeline runs in the background; poll GET /jobs/{job_id}.
    """
    filename = _safe_filename(file.filename or "upload")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            ),
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(contents)} bytes; max {MAX_UPLOAD_BYTES}).",
        )

    # Stage 2 requires a bound case + session so transcript ingestion always
    # carries authoritative Stage 1 metadata.
    if not case_id or not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Save Stage 1 Intake before uploading transcripts. "
                "A valid case and session are required."
            ),
        )

    from backend.db import repository as l1_repo

    if l1_repo.get_case(case_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Case {case_id} does not exist.",
        )
    session_row = l1_repo.get_session(session_id)
    if session_row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session {session_id} does not exist.",
        )
    if session_row.get("case_id") != case_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Session {session_id} does not belong to case {case_id}."),
        )
    logger.info(f"Transcript upload bound to case {case_id}, session {session_id}, file {filename}")

    # Create the job row first so we have the job_id for the audio path.
    job = trepo.create_job(
        {
            "case_id": case_id,
            "session_id": session_id,
            "source_filename": filename,
            "source_size_bytes": len(contents),
            "media_kind": "prerecorded",
            "sequence_index": sequence_index,
            "engine": "deepgram-nova-3",
        }
    )
    job_id = job["job_id"]

    # Persist the media file alongside its job id.
    audio_path = _audio_dir() / f"{job_id}__{filename}"
    audio_path.write_bytes(contents)
    job = trepo.update_job(job_id, {"audio_path": str(audio_path)})

    logger.info(f"Queued transcript job {job_id}: {filename} ({len(contents)} bytes)")

    # Kick off ingestion after the response is sent.
    background.add_task(ingest.process_job, job_id)

    return TranscriptJob(**job)


# ====================================================================
# Jobs
# ====================================================================


@router.get("/jobs", response_model=TranscriptJobList)
def list_jobs(
    case_id: str | None = Query(default=None, description="Filter to one case"),
) -> TranscriptJobList:
    rows = trepo.list_jobs(case_id=case_id)
    return TranscriptJobList(
        jobs=[
            TranscriptJob(
                **{
                    **r,
                    "case_bound": bool(r.get("case_id")),
                    "authoritative_transcript": r.get("transcription_source")
                    != "offline-fallback",
                }
            )
            for r in rows
        ],
        count=len(rows),
    )


@router.get("/jobs/{job_id}", response_model=TranscriptJob)
def get_job(job_id: str) -> TranscriptJob:
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    return TranscriptJob(
        **{
            **row,
            "case_bound": bool(row.get("case_id")),
            "authoritative_transcript": row.get("transcription_source")
            != "offline-fallback",
        }
    )


@router.put("/jobs/{job_id}", response_model=TranscriptJob)
def update_job(job_id: str, payload: TranscriptJobUpdateRequest) -> TranscriptJob:
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )

    patch: dict[str, str | None] = {}
    if payload.case_id is not None:
        from backend.db import repository as l1_repo

        case_row = l1_repo.get_case(payload.case_id)
        if case_row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Case {payload.case_id} does not exist.",
            )
        if row.get("session_id"):
            session_row = l1_repo.get_session(row["session_id"])
            if session_row and session_row.get("case_id") != payload.case_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Transcript job {job_id} is already attached to session "
                        f"{row['session_id']}, which belongs to a different case."
                    ),
                )
        patch["case_id"] = payload.case_id

    updated = trepo.update_job(job_id, patch)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )

    if payload.case_id is not None and payload.case_id != row.get("case_id"):
        provenance_mod.record_event(
            job_id,
            event_type="job_case_bound",
            title="Transcript Job Bound to Case",
            detail=f"Transcript job {job_id} bound to case {payload.case_id}.",
            actor_type="system",
            source="stage2_transcripts",
            metadata={
                "previous_case_id": row.get("case_id") or "",
                "case_id": payload.case_id,
                "session_id": row.get("session_id") or "",
            },
        )

    return TranscriptJob(
        **{
            **updated,
            "case_bound": bool(updated.get("case_id")),
            "authoritative_transcript": updated.get("transcription_source")
            != "offline-fallback",
        }
    )


@router.get("/jobs/{job_id}/content", response_model=TranscriptContent)
def get_job_content(job_id: str) -> TranscriptContent:
    """Return the full canonical content: job + speakers + utterances + words.

    `participants` carries the confirmed speaker-identity mapping when the
    Speaker Mapping step has been completed; it is empty otherwise.
    """
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    _assert_raw_integrity_or_409(row)
    raw_utterances = trepo.get_utterances(job_id, layer="raw")
    working_utterances = trepo.get_utterances(job_id, layer="working")
    raw_map = {u["utterance_id"]: u for u in raw_utterances}
    merged_utterances = []
    for utt in working_utterances:
        raw = raw_map.get(utt["utterance_id"], {})
        payload = dict(utt)
        payload["raw_text"] = raw.get("text") or utt.get("raw_text")
        payload["working_text"] = utt.get("working_text")
        payload["is_working_override"] = bool(utt.get("is_working_override"))
        merged_utterances.append(TranscriptUtterance(**payload))
    logger.info(
        f"Transcript state load for {job_id}: "
        f"{len(merged_utterances)} utterance(s), "
        f"{sum(1 for u in merged_utterances if u.is_working_override)} working override(s)"
    )
    return TranscriptContent(
        job=TranscriptJob(**row),
        speakers=[TranscriptSpeaker(**s) for s in trepo.get_speakers(job_id)],
        utterances=merged_utterances,
        words=[TranscriptWord(**w) for w in trepo.get_words(job_id)],
        participants=[TranscriptParticipant(**p) for p in trepo.get_participants(job_id)],
        exhibits=[TranscriptExhibit(**e) for e in trepo.list_exhibits(job_id)],
    )


@router.get("/jobs/{job_id}/media")
def stream_job_media(
    job_id: str,
    request: Request,
    range_header: str | None = Header(default=None, alias="Range"),
):
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    audio_path_value = row.get("audio_path")
    media_path = Path(audio_path_value) if audio_path_value else None
    if media_path is None or not media_path.exists() or not media_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio no longer retained for this job",
        )

    file_size = media_path.stat().st_size
    try:
        start, end, partial = _resolve_media_range(range_header, file_size)
    except HTTPException as exc:
        exc.headers = {"Content-Range": f"bytes */{file_size}"}
        raise exc

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
    }
    if partial:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    if request.method == "HEAD":
        return StreamingResponse(
            iter(()),
            status_code=status.HTTP_206_PARTIAL_CONTENT if partial else status.HTTP_200_OK,
            media_type=_media_content_type(media_path),
            headers=headers,
        )
    return StreamingResponse(
        _iter_file_range(media_path, start, end),
        status_code=status.HTTP_206_PARTIAL_CONTENT if partial else status.HTTP_200_OK,
        media_type=_media_content_type(media_path),
        headers=headers,
    )


@router.put(
    "/jobs/{job_id}/working-transcript",
    response_model=WorkingTranscriptSaveResponse,
)
def save_working_transcript(
    job_id: str,
    payload: WorkingTranscriptSaveRequest,
) -> WorkingTranscriptSaveResponse:
    """Persist the authoritative Stage 3 working transcript text.

    RAW transcript content remains immutable. Only working-layer utterance
    overrides are written, and only when their text differs from RAW.
    """
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    _assert_raw_integrity_or_409(row)
    try:
        result = working_state_mod.persist_working_transcript(
            job_id,
            [
                {"utterance_id": u.utterance_id, "working_text": u.working_text}
                for u in payload.utterances
            ],
            source=payload.source or "stage3_workspace",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    try:
        provenance_mod.record_event(
            job_id,
            event_type="working_transcript_saved",
            title="Working Transcript Saved",
            detail=(
                f"Saved {result['saved']} override(s); " f"cleared {result['removed']} override(s)."
            ),
            actor_type="system",
            source="workspace",
            metadata={
                "source": payload.source or "stage3_workspace",
                "saved": result["saved"],
                "removed": result["removed"],
                "override_count": result["override_count"],
            },
        )
    except Exception as exc:
        logger.warning(f"working transcript provenance record failed: {exc}")
    return WorkingTranscriptSaveResponse(**result)


@router.get(
    "/jobs/{job_id}/provenance",
    response_model=TranscriptProvenanceListResponse,
)
def list_transcript_provenance(job_id: str) -> TranscriptProvenanceListResponse:
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    events = provenance_mod.list_events(job_id)
    return TranscriptProvenanceListResponse(
        job_id=job_id,
        events=[TranscriptProvenanceEvent(**e) for e in events],
        count=len(events),
    )


@router.post(
    "/jobs/{job_id}/provenance",
    response_model=TranscriptProvenanceEvent,
    status_code=status.HTTP_201_CREATED,
)
def create_transcript_provenance(
    job_id: str,
    payload: TranscriptProvenanceCreateRequest,
) -> TranscriptProvenanceEvent:
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    event = provenance_mod.record_event(
        job_id,
        event_type=payload.event_type,
        title=payload.title,
        detail=payload.detail,
        actor_type=payload.actor_type,
        source=payload.source,
        metadata=payload.metadata,
        related_snapshot_id=payload.related_snapshot_id or None,
        related_suggestion_id=payload.related_suggestion_id or None,
        related_package_id=payload.related_package_id or None,
    )
    return TranscriptProvenanceEvent(**event)


# ====================================================================
# Speaker Mapping  -- raw diarization indices -> canonical participants
# ====================================================================


def _speaker_sample(speaker_index: int, utterances: list[dict]) -> str:
    """Pick a representative transcript snippet for one raw speaker."""
    own = [
        (u.get("text") or "").strip()
        for u in utterances
        if u.get("speaker_index") == speaker_index and (u.get("text") or "").strip()
    ]
    if not own:
        return ""
    # Prefer the first reasonably substantial line; fall back to the first.
    sample = next((t for t in own if len(t.split()) >= 4), own[0])
    return sample if len(sample) <= 160 else sample[:157].rstrip() + "..."


@router.get("/jobs/{job_id}/speaker-mapping", response_model=SpeakerMappingView)
def get_speaker_mapping(job_id: str) -> SpeakerMappingView:
    """Return the Speaker Mapping step payload for one job.

    If the reporter has not yet saved a mapping, a deterministic first
    guess is computed (no AI) and returned with is_prefill=True so the UI
    can show it as an editable suggestion.
    """
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )

    speakers = trepo.get_speakers(job_id)
    utterances = trepo.get_utterances(job_id, layer="raw")

    detected = [
        DetectedSpeaker(
            speaker_index=s["speaker_index"],
            speaker_label=s["speaker_label"],
            word_count=s.get("word_count", 0),
            utterance_count=sum(
                1 for u in utterances if u.get("speaker_index") == s["speaker_index"]
            ),
            sample=_speaker_sample(s["speaker_index"], utterances),
        )
        for s in speakers
    ]

    saved = trepo.get_participants(job_id)
    if saved:
        participants = saved
        is_prefill = any(p.get("is_prefill") for p in saved)
    else:
        participants = speaker_mapping.prefill_participants(speakers, utterances)
        is_prefill = True
    logger.info(
        f"Speaker mapping load for {job_id}: "
        f"{len(detected)} raw speaker(s), {len(participants)} participant row(s), "
        f"prefill={is_prefill}"
    )
    cross_speaker_summary = cross_speaker_flags.ensure_persisted(job_id)

    # Wave 11: deterministic candidate-name dropdown. Built from case
    # metadata when available; always includes the fixed court-officer
    # labels so the dropdown is useful even with no parsed NOD.
    candidate_names = _build_candidate_names_for_job(row)

    return SpeakerMappingView(
        job_id=job_id,
        source_filename=row["source_filename"],
        detected_speakers=detected,
        participants=[TranscriptParticipant(**p) for p in participants],
        roles=[
            RoleOption(value=r, label=speaker_mapping.ROLE_LABELS[r]) for r in speaker_mapping.ROLES
        ],
        is_prefill=is_prefill,
        candidate_names=candidate_names,
        cross_speaker_flags=cross_speaker_summary,
    )


def _build_candidate_names_for_job(job_row: dict) -> list[str]:
    """Assemble the Wave 11 candidate-name list for a job.

    Reads case-level NOD metadata when the job is linked to a case. Falls
    back gracefully to just the fixed court-officer labels. Deterministic;
    no model call.
    """
    nod_metadata: dict = {}
    reporter_name = None
    case_id = job_row.get("case_id")
    session_id = job_row.get("session_id")
    if case_id:
        try:
            from backend.db import repository as case_repo

            case = case_repo.get_case(case_id)
            session = case_repo.get_session(session_id) if session_id else None
            intake = intake_store.read_stage1_record(case_id)
            parser_meta = intake.get("parser_metadata") or {}
            appearances = parser_meta.get("appearances") or []
            attorneys = []
            for a in appearances:
                role = "examining_attorney"
                if a.get("side") == "defendant":
                    role = "defending_attorney"
                attorneys.append(
                    {
                        "name": a.get("name"),
                        "honorific": a.get("honorific"),
                        "role": role,
                    }
                )
            witness_name = ""
            if session:
                witness_name = session.get("witness_name") or ""
                reporter_id = session.get("reporter_id")
                if reporter_id:
                    reporter = case_repo.get_reporter(reporter_id)
                    if reporter:
                        reporter_name = reporter.get("full_name")
            if not witness_name:
                witness_name = parser_meta.get("witness_name") or ""
            nod_metadata = {
                "attorneys": attorneys,
                "witness": {"name": witness_name},
            }
        except Exception as exc:  # never let metadata lookup break the page
            logger.warning(f"candidate-names metadata lookup failed: {exc}")
    return speaker_mapping.build_candidate_names(nod_metadata, reporter_name)


@router.put("/jobs/{job_id}/speaker-mapping", response_model=SpeakerMappingView)
def save_speaker_mapping(
    job_id: str,
    payload: SpeakerMappingSaveRequest,
    background_tasks: BackgroundTasks,
) -> SpeakerMappingView:
    """Persist the reporter-confirmed speaker mapping for a job.

    Saved participants are marked is_prefill=0 -- the reporter has taken
    ownership of the mapping. Roles are validated against the fixed set.

    Wave 11 section 7.1: confirming the mapping auto-triggers the
    deterministic correction engine in the background -- no user click.
    """
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )

    to_save: list[dict] = []
    for p in payload.participants:
        if not speaker_mapping.is_valid_role(p.role):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown participant role '{p.role}'.",
            )
        to_save.append(
            {
                "participant_id": p.participant_id,
                "name": p.name,
                "role": p.role,
                "speaker_indices": p.speaker_indices,
                "is_prefill": 0,  # reporter-confirmed
                "sort_order": p.sort_order,
                "name_source": p.name_source,
                "honorific": p.honorific,
            }
        )

    trepo.save_participants(job_id, to_save)
    cross_speaker_flags.invalidate_for_job(job_id)
    logger.info(f"Saved speaker mapping for job {job_id}: {len(to_save)} participant(s)")

    # Wave 11 section 7.1: a confirmed mapping auto-triggers the
    # deterministic correction engine in the background. It is fast,
    # idempotent, and makes no API calls -- no reason to gate it behind
    # a click. A missing engine is a no-op (correction_trigger is
    # defensive).
    background_tasks.add_task(correction_trigger.run_correction_engine_for_job, job_id)

    return get_speaker_mapping(job_id)


@router.post(
    "/jobs/{job_id}/speaker-mapping/apply",
    response_model=SpeakerMappingApplyResponse,
)
def apply_speaker_mapping(
    job_id: str, payload: SpeakerMappingSaveRequest
) -> SpeakerMappingApplyResponse:
    """Wave 11 'Assign Speakers' action.

    1. Persist the participant list (same as PUT).
    2. Re-render the WORKING transcript from utterances + the new mapping
       via the canonical backend renderer.
    3. Re-run the deterministic correction engine if it is present
       (idempotent -- running it twice equals running it once).

    Returns the re-rendered lines so the Workspace can refresh in place.
    """
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )

    # --- 1. Persist (validates roles, same rules as PUT) --------------
    to_save: list[dict] = []
    for p in payload.participants:
        if not speaker_mapping.is_valid_role(p.role):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown participant role '{p.role}'.",
            )
        to_save.append(
            {
                "participant_id": p.participant_id,
                "name": p.name,
                "role": p.role,
                "speaker_indices": p.speaker_indices,
                "is_prefill": 0,
                "sort_order": p.sort_order,
                "name_source": p.name_source,
                "honorific": p.honorific,
            }
        )
    trepo.save_participants(job_id, to_save)
    cross_speaker_flags.invalidate_for_job(job_id)

    # --- 2. Re-render WORKING from the canonical renderer -------------
    utterances = working_state_mod.get_working_utterances(job_id)
    participants = trepo.get_participants(job_id)
    lines = render_mod.render_working_transcript(utterances, participants)
    unmapped = sum(1 for ln in lines if ln.flagged)

    # --- 3. Re-run the correction engine if present (idempotent) ------
    engine_ran = False
    try:
        summary = correction_trigger.run_correction_engine_for_job(job_id)
        engine_ran = summary is not None
    except Exception as exc:
        logger.info(f"Correction engine not run for {job_id}: {exc}")
        engine_ran = False

    logger.info(
        f"Applied speaker mapping for job {job_id}: "
        f"{len(to_save)} participant(s), {len(lines)} line(s), "
        f"{unmapped} unmapped cluster(s)"
    )
    return SpeakerMappingApplyResponse(
        job_id=job_id,
        participant_count=len(to_save),
        lines=[ln.to_dict() for ln in lines],
        unmapped_cluster_count=unmapped,
        correction_engine_ran=engine_ran,
    )


@router.get("/jobs/{job_id}/packet")
def get_working_packet(job_id: str) -> dict:
    """Return the editable WORKING transcript packet."""
    return _read_packet_or_404(job_id, layer="working")


@router.get("/jobs/{job_id}/raw")
def get_raw_packet(job_id: str) -> dict:
    """Return the IMMUTABLE raw transcript packet."""
    return _read_packet_or_404(job_id, layer="raw")


def _read_packet_or_404(job_id: str, layer: str) -> dict:
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    path_field = "raw_packet_path" if layer == "raw" else "working_packet_path"
    packet_path = row.get(path_field)
    if not packet_path or not Path(packet_path).exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No {layer} packet for job {job_id} yet " f"(current status: {row['status']})."
            ),
        )
    if layer == "raw":
        _assert_raw_integrity_or_409(row)
    return packet_mod.read_packet(packet_path)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str) -> None:
    """Delete a job, its DB content, and its on-disk artifacts."""
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )

    # Best-effort cleanup of on-disk artifacts.
    for path_value in (row.get("audio_path"), row.get("raw_packet_path")):
        if path_value:
            try:
                Path(path_value).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(f"Could not remove {path_value}: {exc}")
    transcripts_dir = settings.data_root / "transcripts" / job_id
    if transcripts_dir.exists():
        import shutil

        shutil.rmtree(transcripts_dir, ignore_errors=True)

    trepo.delete_job(job_id)


# ====================================================================
# Readback search
# ====================================================================


class ReadbackRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    case_id: str | None = None
    limit: int = Field(default=50, ge=1, le=200)


@router.post("/readback", response_model=ReadbackResult)
def readback_search(payload: ReadbackRequest) -> ReadbackResult:
    """Search persisted transcripts for a phrase.

    Backs the Stage 2 Live Read-Back Terminal. Matches against structured
    utterance rows (not a transcript blob), so it stays fast and returns
    speaker + timing + source-file context for each hit.
    """
    rows = trepo.search_utterances(
        query=payload.query,
        case_id=payload.case_id,
        limit=payload.limit,
    )
    return ReadbackResult(
        query=payload.query,
        matches=[ReadbackMatch(**r) for r in rows],
        count=len(rows),
    )


def _lexicon_config_for_job(job_row: dict) -> dict:
    """Assemble the Stage X lexicon config for a job (Wave 14).

    Reads the case's keyterms when available. Deterministic; never
    raises -- a missing source simply contributes nothing.
    """
    cfg: dict = {}
    case_id = job_row.get("case_id")
    if not case_id:
        return cfg
    try:
        from backend.db import repository as case_repo

        case = case_repo.get_case(case_id)
        intake = intake_store.read_stage1_record(case_id)
        if case:
            cfg["confirmed_spellings"] = case.get("confirmed_spellings") or {}
        cfg["intake_keyterms"] = intake_store.keyterm_strings(intake.get("keyterms") or [])
    except Exception as exc:
        logger.warning(f"lexicon config lookup failed: {exc}")
    return cfg


# ====================================================================
# Export preview  (Wave 12) -- canonical "what will export" rendering
# ====================================================================


def _build_export_document(job_id: str):
    """Build the canonical ExportDocument for a job.

    This is the SAME pipeline the real DOCX/PDF export uses:

        RAW -> participant mapping -> render.py (WORKING lines)
            -> regex + Stage X corrections -> Stage S structural render
            -> export_render.py (paginated layout)

    Returns (ExportDocument, PaginatedDocument). PaginatedDocument is
    None only when the transcript body is empty.
    Shared by the export-preview endpoint and the Wave 18 export
    endpoint so preview and export can never diverge.
    """
    row = trepo.get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )

    utterances = working_state_mod.get_working_utterances(job_id)
    participants = trepo.get_participants(job_id)

    # Wave 14: deterministic corrections run BEFORE structural render.
    #   1. per-case persisted regex rules
    #   2. Stage X merged lexicon (whole-word, possessive-aware)
    # Both operate on a working copy -- RAW utterances are never mutated.
    case_id_for_corr = row.get("case_id")
    if case_id_for_corr:
        try:
            from backend.corrections.regex_rules import apply_regex_rules
            from backend.db import regex_rules_repo

            rules = regex_rules_repo.list_rules(case_id_for_corr)
            if rules:
                utterances, _ = apply_regex_rules(utterances, rules)
        except Exception as exc:
            logger.warning(f"export-preview regex step skipped: {exc}")
    try:
        from backend.lexicon.merge import merge_from_job_config
        from backend.lexicon.stage_x import apply_stage_x

        lexicon = merge_from_job_config(_lexicon_config_for_job(row))
        if len(lexicon) > 0:
            utterances, _ = apply_stage_x(utterances, lexicon)
    except Exception as exc:
        logger.warning(f"export-preview Stage X step skipped: {exc}")

    # Stage S (Wave 13): the structural renderer. Produces Q/A
    # segmentation, isolated objections, off-record tagging, and
    # procedural parentheticals. The export layer consumes its output.
    from backend.stage_s.renderer import render_stage_s

    stage_s = render_stage_s(utterances, participants)

    # Map Stage S RenderLines into the shape export_render expects.
    # Off-record lines are suppressed from the export body (their
    # recess/resume parentheticals already mark the gap); RAW retains
    # everything, and the Workspace can still surface them.
    working: list[dict] = []
    for ln in stage_s.lines:
        if ln.render_state == "OFF_RECORD" and not ln.procedural:
            continue
        if ln.line_type == "parenthetical":
            lt = "colloquy"
        elif ln.line_type in ("by_line", "examination"):
            # Carry structural ritual headers through unflattened so the
            # export renders them as proper headers, not colloquy.
            lt = ln.line_type
        elif ln.line_type in ("Q", "A", "colloquy", "flagged"):
            lt = ln.line_type
        else:
            lt = "colloquy"
        working.append(
            {
                "line_type": lt,
                "speaker_label": ln.speaker_label,
                "text": ln.text,
            }
        )

    # Case identity for the header block -- best-effort, blank if absent.
    caption = cause_number = witness = proceedings_date = ""
    examining_label = ""
    case_id = row.get("case_id")
    if case_id:
        try:
            from backend.db import repository as case_repo

            case = case_repo.get_case(case_id)
            if case:
                caption = case.get("caption_full") or ""
                cause_number = case.get("case_number_value") or ""
        except Exception as exc:
            logger.warning(f"export-preview case lookup failed: {exc}")

    # Examining attorney label from the confirmed participants.
    for p in participants:
        if p.get("role") == "examining_attorney":
            examining_label = speaker_mapping.participant_label(
                "examining_attorney", p.get("name"), p.get("honorific")
            )
            break
    # Witness name from the confirmed participants.
    for p in participants:
        if p.get("role") == "witness" and p.get("name"):
            witness = p.get("name")
            break
    logger.info(
        f"Export speaker resolution for {job_id}: "
        f"{len(participants)} participant(s), witness='{witness or 'unset'}', "
        f"examining='{examining_label or 'unset'}'"
    )

    # BLOCKER-5 fix: use the layout-aware render so the live export
    # path receives the PaginatedDocument the Geometry Layer needs.
    doc, paginated = export_render_mod.render_export_with_layout(
        working,
        caption=caption,
        cause_number=cause_number,
        witness=witness,
        proceedings_date=proceedings_date,
        examining_attorney_label=examining_label,
        is_approximate=False,
    )
    return doc, paginated


def _build_export_document_from_snapshot(snapshot_state: dict, *, snapshot_id: str = ""):
    """Build the canonical export document from a locked snapshot state."""
    from backend.stage_s.renderer import render_stage_s

    working_utterances = snapshot_state.get("working_utterances") or []
    utterances = [
        {
            "utterance_id": u.get("utterance_id"),
            "utterance_index": u.get("utterance_index"),
            "speaker_index": u.get("speaker_index"),
            "speaker_label": u.get("speaker_label") or "",
            "start_time": u.get("start_time") or 0.0,
            "end_time": u.get("end_time") or 0.0,
            "text": u.get("text") or u.get("raw_text") or "",
            "avg_confidence": None,
        }
        for u in working_utterances
    ]
    participants = [
        {
            "participant_id": p.get("participant_id"),
            "name": p.get("name"),
            "role": p.get("role") or "other",
            "speaker_indices": p.get("speaker_indices") or [],
            "sort_order": idx,
            "name_source": p.get("name_source"),
            "honorific": p.get("honorific"),
        }
        for idx, p in enumerate(snapshot_state.get("speaker_mapping") or [])
    ]

    try:
        from backend.corrections.regex_rules import RegexRule, apply_regex_rules

        rules = [
            RegexRule(
                rule_id=r.get("rule_id", ""),
                find_pattern=r.get("find_pattern", ""),
                replace_with=r.get("replace_with", ""),
                rule_order=r.get("rule_order", 0),
                enabled=r.get("enabled", True),
                description=r.get("description", ""),
            )
            for r in (snapshot_state.get("regex_rule_state") or [])
        ]
        if rules:
            utterances, _ = apply_regex_rules(utterances, rules)
    except Exception as exc:
        logger.warning(f"snapshot export regex step skipped for {snapshot_id}: {exc}")

    try:
        from backend.lexicon.merge import merge_from_job_config
        from backend.lexicon.stage_x import apply_stage_x

        lexicon_cfg = snapshot_state.get("lexicon_state") or {}
        lexicon = merge_from_job_config(
            {
                "confirmed_spellings": lexicon_cfg.get("confirmed_spellings") or {},
                "intake_keyterms": lexicon_cfg.get("intake_keyterms") or [],
            }
        )
        if len(lexicon) > 0:
            utterances, _ = apply_stage_x(utterances, lexicon)
    except Exception as exc:
        logger.warning(f"snapshot export Stage X step skipped for {snapshot_id}: {exc}")

    stage_s = render_stage_s(utterances, participants)
    working_lines: list[dict] = []
    for ln in stage_s.lines:
        if ln.render_state == "OFF_RECORD" and not ln.procedural:
            continue
        if ln.line_type == "parenthetical":
            lt = "colloquy"
        elif ln.line_type in ("by_line", "examination"):
            # Carry structural ritual headers through unflattened so the
            # export renders them as proper headers, not colloquy.
            lt = ln.line_type
        elif ln.line_type in ("Q", "A", "colloquy", "flagged"):
            lt = ln.line_type
        else:
            lt = "colloquy"
        working_lines.append(
            {
                "line_type": lt,
                "speaker_label": ln.speaker_label,
                "text": ln.text,
            }
        )

    export_meta = snapshot_state.get("export_metadata") or {}
    caption = export_meta.get("caption") or ""
    cause_number = export_meta.get("cause_number") or ""
    witness = export_meta.get("witness_name") or ""
    proceedings_date = export_meta.get("proceedings_date") or ""
    examining_label = export_meta.get("examining_attorney_label") or ""
    for p in participants:
        if p.get("role") == "examining_attorney":
            examining_label = speaker_mapping.participant_label(
                "examining_attorney", p.get("name"), p.get("honorific")
            )
            break
    for p in participants:
        if p.get("role") == "witness" and p.get("name"):
            witness = p.get("name")
            break

    doc, paginated = export_render_mod.render_export_with_layout(
        working_lines,
        caption=caption,
        cause_number=cause_number,
        witness=witness,
        proceedings_date=proceedings_date,
        examining_attorney_label=examining_label,
        is_approximate=False,
    )
    return doc, paginated


@router.get("/jobs/{job_id}/export-preview")
def get_export_preview(job_id: str) -> dict:
    """Render the canonical paginated export document for one job.

    The Export screen's "Refresh Preview" button calls this. It is the
    authoritative "this is what would export right now" view -- it and
    the real export share `_build_export_document`, so they cannot
    diverge.
    """
    doc, _ = _build_export_document(job_id)
    return doc.to_dict()


@router.get("/jobs/{job_id}/engine-status")
def get_engine_status(job_id: str) -> dict:
    """Last correction-engine run for a job (auto or manual regex).

    Drives the Stage 3 engine-status badge. Reads the most recent
    `correction_engine_auto_run` / `regex_apply_manual` provenance event;
    returns nulls when the engine has never run for this job.
    """
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    events = provenance_mod.list_events(job_id, limit=200)
    for ev in events:  # list_events is newest-first
        et = ev.get("event_type")
        if et in ("correction_engine_auto_run", "regex_apply_manual"):
            meta = ev.get("metadata") or {}
            subs = meta.get("substitution_count")
            if subs is None:
                subs = meta.get("substitutions")
            return {
                "last_run_at": ev.get("created_at"),
                "last_run_substitutions": subs,
                "last_run_event_id": ev.get("event_id"),
                "last_run_source": "manual_regex" if et == "regex_apply_manual" else "auto",
            }
    return {
        "last_run_at": None,
        "last_run_substitutions": None,
        "last_run_event_id": None,
        "last_run_source": None,
    }


@router.get("/jobs/{job_id}/correction-log")
def get_correction_log(job_id: str) -> dict:
    """Entries from the most recent correction run (auto or manual regex).

    Reads the per-job correction-log JSONL sidecar. Drives the Stage 3
    correction-log viewer. Empty list when no run has produced corrections.
    """
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    from backend.corrections import correction_log_store
    return {"entries": correction_log_store.read_latest_run(job_id)}


class ExportRequest(BaseModel):
    fmt: str = "txt"
    destination: str = "downloads"  # downloads | case_folder | path
    explicit_path: str | None = None
    snapshot_id: str | None = None


@router.post("/jobs/{job_id}/export")
def export_transcript(job_id: str, payload: ExportRequest) -> dict:
    """Wave 18 -- render the job and write a real file to disk.

    The backend writes the file (fixing the PyWebView blob-download
    failure). Uses the SAME canonical document as the preview. Returns
    the absolute path written.
    """
    from backend.export import export_service

    export_state = "working"
    snapshot_id = payload.snapshot_id or None
    if snapshot_id:
        snap = snapshot_repo.get_snapshot(snapshot_id)
        if snap is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot {snapshot_id} not found",
            )
        if snap.job_id != job_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Snapshot {snapshot_id} does not belong to job {job_id}",
            )
        if not snap.locked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only locked certification snapshots may drive certified export.",
            )
        doc, paginated = _build_export_document_from_snapshot(
            snap.state or {},
            snapshot_id=snap.snapshot_id,
        )
        export_state = "certified_snapshot"
        logger.info(f"Export render source for {job_id}: locked snapshot {snap.snapshot_id}")
    else:
        doc, paginated = _build_export_document(job_id)  # 404s on unknown job
        logger.info(f"Export render source for {job_id}: live working transcript")

    # Resolve the case's workspace directory, if any.
    case_dir = None
    row = trepo.get_job(job_id)
    case_id = row.get("case_id") if row else None
    if case_id:
        try:
            from backend.db import repository as case_repo

            case = case_repo.get_case(case_id)
            if case and case.get("workspace_dir"):
                case_dir = case["workspace_dir"]
            if not case_dir:
                intake = intake_store.read_stage1_record(case_id)
                sessions = (intake.get("workspace") or {}).get("sessions") or {}
                if sessions:
                    any_binding = next(iter(sessions.values()))
                    case_dir = any_binding.get("case_dir")
        except Exception as exc:
            logger.warning(f"export case-dir lookup failed: {exc}")

    try:
        result = export_service.export_document(
            doc,
            payload.fmt,
            payload.destination,
            explicit_path=payload.explicit_path,
            case_dir=case_dir,
            paginated_document=paginated,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Export failed for {job_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Export failed: {exc}"
        )

    # Wave 18.5: every export captures an EXPORT snapshot and records
    # an export reference, so "which transcript state did this file
    # come from" is always answerable. Defensive -- a snapshot failure
    # never fails the export itself.
    recorded_snapshot_id = None
    try:
        import datetime

        from backend.transcript_state import snapshot_service

        if snapshot_id:
            snapshot_service.record_export(
                snapshot_id,
                export_id=result["filename"],
                export_format=result["format"],
                export_timestamp=datetime.datetime.now().isoformat(),
            )
            recorded_snapshot_id = snapshot_id
        else:
            snap = snapshot_service.create_snapshot(
                job_id,
                category="EXPORT",
                note=f"Auto-snapshot on {result['format'].upper()} export",
            )
            snapshot_service.record_export(
                snap.snapshot_id,
                export_id=result["filename"],
                export_format=result["format"],
                export_timestamp=datetime.datetime.now().isoformat(),
            )
            recorded_snapshot_id = snap.snapshot_id
    except Exception as exc:
        logger.warning(f"export snapshot skipped for {job_id}: {exc}")

    try:
        provenance_mod.record_event(
            job_id,
            event_type="export_rendered",
            title="Transcript Exported",
            detail=(
                f"Rendered {result['format'].upper()} export from "
                f"{'locked certification snapshot' if export_state == 'certified_snapshot' else 'current working transcript'}."
            ),
            actor_type="system",
            source="export",
            metadata={
                "format": result["format"],
                "destination": payload.destination,
                "path": result["path"],
                "export_state": export_state,
            },
            related_snapshot_id=recorded_snapshot_id or "",
        )
    except Exception as exc:
        logger.warning(f"export provenance record failed for {job_id}: {exc}")

    return {
        "job_id": job_id,
        "snapshot_id": recorded_snapshot_id,
        "export_state": export_state,
        **result,
    }


class ExportPreviewFallbackRequest(BaseModel):
    """Frontend-fallback payload: render an export preview from
    transient WORKING lines that are not yet saved to a job."""

    lines: list[dict] = Field(default_factory=list)
    caption: str = ""
    cause_number: str = ""
    witness: str = ""
    proceedings_date: str = ""
    examining_attorney_label: str = ""


@router.post("/export-preview/fallback")
def post_export_preview_fallback(payload: ExportPreviewFallbackRequest) -> dict:
    """Render an export preview from frontend-supplied WORKING lines.

    Used only when the transcript is not yet a saved job. The result is
    marked is_approximate=True so the UI can label it clearly. The
    long-term authority is the job-based endpoint above.
    """
    doc = export_render_mod.render_export_document(
        payload.lines,
        caption=payload.caption,
        cause_number=payload.cause_number,
        witness=payload.witness,
        proceedings_date=payload.proceedings_date,
        examining_attorney_label=payload.examining_attorney_label,
        is_approximate=True,
    )
    return doc.to_dict()
