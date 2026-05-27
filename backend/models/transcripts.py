"""Pydantic models for the /api/transcripts router.

Response shapes for the Stage 2 transcripts engine. Request bodies for
the upload endpoint arrive as multipart form data, so they are declared
inline in the router rather than here.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

# --------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------


class TranscriptJob(BaseModel):
    """One transcript ingestion job (one media file)."""

    job_id: str
    case_id: Optional[str] = None
    session_id: Optional[str] = None
    case_bound: bool = False
    authoritative_transcript: bool = True
    source_filename: str
    source_size_bytes: int
    media_kind: str
    sequence_index: int
    status: str
    engine: str
    transcription_source: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    word_count: int
    utterance_count: int
    speaker_count: int
    avg_confidence: Optional[float] = None
    audio_path: Optional[str] = None
    raw_packet_path: Optional[str] = None
    working_packet_path: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


class TranscriptJobList(BaseModel):
    jobs: list[TranscriptJob]
    count: int


class TranscriptJobUpdateRequest(BaseModel):
    case_id: Optional[str] = None


# --------------------------------------------------------------------
# Canonical content
# --------------------------------------------------------------------


class TranscriptSpeaker(BaseModel):
    speaker_row_id: str
    speaker_index: int
    speaker_label: str
    assigned_name: Optional[str] = None
    speaker_role: Optional[str] = None
    word_count: int


class TranscriptUtterance(BaseModel):
    utterance_id: str
    utterance_index: int
    speaker_index: Optional[int] = None
    speaker_label: str
    start_time: float
    end_time: float
    text: str
    raw_text: Optional[str] = None
    working_text: Optional[str] = None
    is_working_override: bool = False
    working_source: Optional[str] = None
    working_updated_at: Optional[str] = None
    avg_confidence: Optional[float] = None


class TranscriptWord(BaseModel):
    word_id: str
    utterance_id: str
    word_index: int
    raw_text: str
    working_text: Optional[str] = None
    speaker_index: Optional[int] = None
    start_time: float
    end_time: float
    confidence: float
    is_filler: int
    reviewed: int


# --------------------------------------------------------------------
# Canonical participants (speaker-identity layer)
# --------------------------------------------------------------------


class TranscriptParticipant(BaseModel):
    """One real person/role. speaker_indices lists every raw diarization
    index that collapses onto this participant."""

    participant_id: Optional[str] = None
    name: Optional[str] = None
    role: str = "other"
    speaker_indices: list[int] = []
    is_prefill: int = 0
    sort_order: int = 0
    # Wave 11
    name_source: Optional[str] = None  # prefill_deterministic | ai_suggested | user_confirmed
    honorific: Optional[str] = None  # MR | MS | MRS | DR | None


class TranscriptExhibit(BaseModel):
    exhibit_id: str
    job_id: str
    case_id: Optional[str] = None
    session_id: Optional[str] = None
    exhibit_number: str
    exhibit_title: str = ""
    offering_attorney: str = ""
    description: str = ""
    anchor_utterance_id: str
    anchor_note: str = ""
    sort_order: int = 0
    created_at: str
    updated_at: str


class TranscriptContent(BaseModel):
    """The full canonical content for a job: speakers + utterances + words.

    `participants` is the confirmed speaker-identity mapping; it is empty
    until the reporter completes the Speaker Mapping step.
    """

    job: TranscriptJob
    speakers: list[TranscriptSpeaker]
    utterances: list[TranscriptUtterance]
    words: list[TranscriptWord]
    participants: list[TranscriptParticipant] = []
    exhibits: list[TranscriptExhibit] = []


# --------------------------------------------------------------------
# Speaker Mapping step
# --------------------------------------------------------------------


class DetectedSpeaker(BaseModel):
    """A raw diarization speaker with enough context for the reporter to
    recognize who it is: a transcript sample and how much they spoke."""

    speaker_index: int
    speaker_label: str
    word_count: int
    utterance_count: int
    sample: str


class RoleOption(BaseModel):
    value: str
    label: str


class CrossSpeakerFlagSummary(BaseModel):
    total: int = 0
    mid_utterance_change: int = 0
    flicker: int = 0
    short_turn: int = 0
    certified_locked: bool = False
    informational_only: bool = False


class SpeakerMappingView(BaseModel):
    """GET payload for the Speaker Mapping step."""

    job_id: str
    source_filename: str
    detected_speakers: list[DetectedSpeaker]
    participants: list[TranscriptParticipant]
    roles: list[RoleOption]
    is_prefill: bool  # True when `participants` is an unconfirmed first guess
    candidate_names: list[str] = []  # Wave 11: finished speaker-label dropdown
    cross_speaker_flags: CrossSpeakerFlagSummary | None = None


class SpeakerMappingSaveRequest(BaseModel):
    participants: list[TranscriptParticipant]


class SpeakerMappingApplyResponse(BaseModel):
    """Wave 11: response from POST .../speaker-mapping/apply.

    Carries the re-rendered WORKING transcript so the Workspace can
    refresh in place without a second fetch.
    """

    job_id: str
    participant_count: int
    lines: list[dict]  # rendered WorkingLine dicts
    unmapped_cluster_count: int
    correction_engine_ran: bool


# --------------------------------------------------------------------
# Stage 3 authoritative working transcript state
# --------------------------------------------------------------------


class WorkingTranscriptUtterance(BaseModel):
    utterance_id: str
    working_text: str


class WorkingTranscriptSaveRequest(BaseModel):
    utterances: list[WorkingTranscriptUtterance]
    source: str = "stage3_workspace"


class WorkingTranscriptSaveResponse(BaseModel):
    job_id: str
    saved: int
    removed: int
    override_count: int
    working_packet_path: Optional[str] = None


class TranscriptExhibitCreateRequest(BaseModel):
    exhibit_number: str
    exhibit_title: str = ""
    offering_attorney: str = ""
    description: str = ""
    anchor_utterance_id: str
    anchor_note: str = ""
    sort_order: Optional[int] = None


class TranscriptExhibitUpdateRequest(BaseModel):
    exhibit_number: Optional[str] = None
    exhibit_title: Optional[str] = None
    offering_attorney: Optional[str] = None
    description: Optional[str] = None
    anchor_utterance_id: Optional[str] = None
    anchor_note: Optional[str] = None
    sort_order: Optional[int] = None


class TranscriptExhibitListResponse(BaseModel):
    job_id: str
    exhibits: list[TranscriptExhibit]
    count: int


class TranscriptProvenanceEvent(BaseModel):
    event_id: str
    job_id: str
    event_type: str
    title: str
    detail: str = ""
    actor_type: str = "system"
    source: str = ""
    metadata: dict = {}
    related_snapshot_id: str = ""
    related_suggestion_id: str = ""
    related_package_id: str = ""
    created_at: str


class TranscriptProvenanceListResponse(BaseModel):
    job_id: str
    events: list[TranscriptProvenanceEvent]
    count: int


class TranscriptProvenanceCreateRequest(BaseModel):
    event_type: str
    title: str
    detail: str = ""
    actor_type: str = "system"
    source: str = "workspace"
    metadata: dict = {}
    related_snapshot_id: str = ""
    related_suggestion_id: str = ""
    related_package_id: str = ""


# --------------------------------------------------------------------
# Readback search
# --------------------------------------------------------------------


class ReadbackMatch(BaseModel):
    utterance_id: str
    job_id: str
    utterance_index: int
    speaker_label: str
    start_time: float
    end_time: float
    text: str
    avg_confidence: Optional[float] = None
    source_filename: str
    sequence_index: int


class ReadbackResult(BaseModel):
    query: str
    matches: list[ReadbackMatch]
    count: int
