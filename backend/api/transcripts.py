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

import re
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from loguru import logger
from pydantic import BaseModel, Field

from backend.config import settings
from backend.models.transcripts import (
    DetectedSpeaker,
    ReadbackMatch,
    ReadbackResult,
    RoleOption,
    SpeakerMappingApplyResponse,
    SpeakerMappingSaveRequest,
    SpeakerMappingView,
    TranscriptContent,
    TranscriptJob,
    TranscriptJobList,
    TranscriptParticipant,
    TranscriptSpeaker,
    TranscriptUtterance,
    TranscriptWord,
)
from backend.services import intake_store
from backend.services import speaker_mapping
from backend.services import correction_trigger
from backend.transcript import ingest
from backend.transcript import packet as packet_mod
from backend.transcript import render as render_mod
from backend.transcript import export_render as export_render_mod
from backend.transcript import repository as trepo

router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])

# Upload guard. The standard-library Deepgram uploader has its own
# 250 MB cap; this is the server-side accept limit.
MAX_UPLOAD_BYTES = 300 * 1024 * 1024  # 300 MB

ALLOWED_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".aac", ".ogg", ".flac", ".webm",
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
            detail=(
                f"Session {session_id} does not belong to case {case_id}."
            ),
        )
    logger.info(
        f"Transcript upload bound to case {case_id}, session {session_id}, file {filename}"
    )

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
        jobs=[TranscriptJob(**r) for r in rows],
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
    return TranscriptJob(**row)


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
    return TranscriptContent(
        job=TranscriptJob(**row),
        speakers=[TranscriptSpeaker(**s) for s in trepo.get_speakers(job_id)],
        utterances=[TranscriptUtterance(**u) for u in trepo.get_utterances(job_id)],
        words=[TranscriptWord(**w) for w in trepo.get_words(job_id)],
        participants=[
            TranscriptParticipant(**p) for p in trepo.get_participants(job_id)
        ],
    )


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
    utterances = trepo.get_utterances(job_id)

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
            RoleOption(value=r, label=speaker_mapping.ROLE_LABELS[r])
            for r in speaker_mapping.ROLES
        ],
        is_prefill=is_prefill,
        candidate_names=candidate_names,
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
                attorneys.append({
                    "name": a.get("name"),
                    "honorific": a.get("honorific"),
                    "role": role,
                })
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
    logger.info(f"Saved speaker mapping for job {job_id}: {len(to_save)} participant(s)")

    # Wave 11 section 7.1: a confirmed mapping auto-triggers the
    # deterministic correction engine in the background. It is fast,
    # idempotent, and makes no API calls -- no reason to gate it behind
    # a click. A missing engine is a no-op (correction_trigger is
    # defensive).
    background_tasks.add_task(
        correction_trigger.run_correction_engine_for_job, job_id
    )

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
        to_save.append({
            "participant_id": p.participant_id,
            "name": p.name,
            "role": p.role,
            "speaker_indices": p.speaker_indices,
            "is_prefill": 0,
            "sort_order": p.sort_order,
            "name_source": p.name_source,
            "honorific": p.honorific,
        })
    trepo.save_participants(job_id, to_save)

    # --- 2. Re-render WORKING from the canonical renderer -------------
    utterances = trepo.get_utterances(job_id)
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
                f"No {layer} packet for job {job_id} yet "
                f"(current status: {row['status']})."
            ),
        )
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
        cfg["intake_keyterms"] = intake_store.keyterm_strings(
            intake.get("keyterms") or []
        )
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

    utterances = trepo.get_utterances(job_id)
    participants = trepo.get_participants(job_id)

    # Wave 14: deterministic corrections run BEFORE structural render.
    #   1. per-case persisted regex rules
    #   2. Stage X merged lexicon (whole-word, possessive-aware)
    # Both operate on a working copy -- RAW utterances are never mutated.
    case_id_for_corr = row.get("case_id")
    if case_id_for_corr:
        try:
            from backend.db import regex_rules_repo
            from backend.corrections.regex_rules import apply_regex_rules
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
        elif ln.line_type == "by_line":
            lt = "colloquy"
        elif ln.line_type in ("Q", "A", "colloquy", "flagged"):
            lt = ln.line_type
        else:
            lt = "colloquy"
        working.append({
            "line_type": lt,
            "speaker_label": ln.speaker_label,
            "text": ln.text,
        })

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
                "examining_attorney", p.get("name"), p.get("honorific"))
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


class ExportRequest(BaseModel):
    fmt: str = "txt"
    destination: str = "downloads"   # downloads | case_folder | path
    explicit_path: str | None = None


@router.post("/jobs/{job_id}/export")
def export_transcript(job_id: str, payload: ExportRequest) -> dict:
    """Wave 18 -- render the job and write a real file to disk.

    The backend writes the file (fixing the PyWebView blob-download
    failure). Uses the SAME canonical document as the preview. Returns
    the absolute path written.
    """
    from backend.export import export_service

    doc, paginated = _build_export_document(job_id)   # 404s on unknown job

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
            doc, payload.fmt, payload.destination,
            explicit_path=payload.explicit_path, case_dir=case_dir,
            paginated_document=paginated)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Export failed for {job_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {exc}")

    # Wave 18.5: every export captures an EXPORT snapshot and records
    # an export reference, so "which transcript state did this file
    # come from" is always answerable. Defensive -- a snapshot failure
    # never fails the export itself.
    snapshot_id = None
    try:
        import datetime
        from backend.transcript_state import snapshot_service
        snap = snapshot_service.create_snapshot(
            job_id, category="EXPORT",
            note=f"Auto-snapshot on {result['format'].upper()} export")
        snapshot_service.record_export(
            snap.snapshot_id,
            export_id=result["filename"],
            export_format=result["format"],
            export_timestamp=datetime.datetime.now().isoformat(),
        )
        snapshot_id = snap.snapshot_id
    except Exception as exc:
        logger.warning(f"export snapshot skipped for {job_id}: {exc}")

    return {"job_id": job_id, "snapshot_id": snapshot_id, **result}


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
