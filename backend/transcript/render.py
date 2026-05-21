"""Canonical WORKING transcript renderer.

THE SINGLE RENDER AUTHORITY.

Before Wave 11 the only thing that joined participants to utterances and
decided Q. / A. / colloquy was a JavaScript function in the frontend
(`stage_2.js :: loadTranscriptResultsIntoWorkspace`). That made the
frontend the de-facto source of truth for what the transcript says.

This module moves that authority to the backend. It is deterministic,
RAW is never touched, and the WORKING transcript is *regenerated* from
utterances + the participant mapping every time -- it is never edited
in place.

Pipeline position:

    RAW (immutable)
        -> participant mapping (transcript_participants)
        -> render_working_transcript()        <-- this module
        -> correction pipeline (backend/corrections)
        -> formatted / export transcript

The output `RenderedLine` shape matches `backend.corrections.model`
so the correction pipeline can consume this directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from backend.services.speaker_mapping import participant_label, role_to_qa


@dataclass
class WorkingLine:
    """One rendered line of the WORKING transcript.

    Deliberately shaped to match backend.corrections.model.RenderedLine
    so the correction pipeline consumes the renderer output directly.
    """

    line_type: str            # Q | A | colloquy | flagged | divider
    text: str
    speaker_label: str        # "MR. NUNEZ", "THE REPORTER", "Speaker 3", ""
    role: Optional[str] = None
    speaker_index: Optional[int] = None
    utterance_ids: list[str] = field(default_factory=list)
    flagged: bool = False     # True for unmapped clusters
    start_time: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "line_type": self.line_type,
            "text": self.text,
            "speaker_label": self.speaker_label,
            "role": self.role,
            "speaker_index": self.speaker_index,
            "utterance_ids": list(self.utterance_ids),
            "flagged": self.flagged,
            "start_time": self.start_time,
        }


def _coerce_indices(value) -> list[int]:
    """Parse a participant's speaker_indices (stored as a JSON string)."""
    if value is None:
        return []
    if isinstance(value, list):
        out = []
        for v in value:
            try:
                out.append(int(v))
            except (TypeError, ValueError):
                continue
        return out
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return _coerce_indices(parsed) if isinstance(parsed, list) else []


def build_index_map(participants: list[dict]) -> dict[int, dict]:
    """Collapse the participant list into {speaker_index -> participant info}.

    Each raw diarization index maps to exactly one participant. If two
    participants claim the same index (should not happen via the UI), the
    earlier one in sort order wins -- deterministic, not arbitrary.
    """
    ordered = sorted(
        participants,
        key=lambda p: (p.get("sort_order", 0), p.get("created_at", "")),
    )
    index_map: dict[int, dict] = {}
    for p in ordered:
        role = (p.get("role") or "other").strip()
        label = participant_label(role, p.get("name"), p.get("honorific"))
        info = {
            "participant_id": p.get("participant_id"),
            "role": role,
            "name": p.get("name"),
            "honorific": p.get("honorific"),
            "label": label,
            "qa": role_to_qa(role),
        }
        for idx in _coerce_indices(p.get("speaker_indices")):
            index_map.setdefault(idx, info)
    return index_map


def render_working_transcript(
    utterances: list[dict],
    participants: list[dict],
) -> list[WorkingLine]:
    """Render the canonical WORKING transcript.

    Deterministic. RAW utterances are read, never written. Every call
    rebuilds the full line list from scratch from (utterances + mapping).

    Rules (spec wave11 section 6):
      - examining attorney utterances  -> line_type 'Q'
      - witness utterances             -> line_type 'A'
      - any other mapped role          -> line_type 'colloquy', named label
      - an utterance whose speaker_index is not claimed by any participant
        (an UNMAPPED cluster) -> line_type 'flagged', raw "Speaker N" label.
        The text is NOT dropped -- testimony is never lost; it renders with
        a raw label so the reporter can see and fix it.
    """
    index_map = build_index_map(participants)
    lines: list[WorkingLine] = []

    # Stable ordering: by utterance_index when present, else input order.
    ordered = sorted(
        utterances,
        key=lambda u: (u.get("utterance_index") if u.get("utterance_index") is not None else 0),
    )

    for utt in ordered:
        text = (utt.get("text") or "").strip()
        idx = utt.get("speaker_index")
        utt_id = utt.get("utterance_id")
        start = utt.get("start_time")
        info = index_map.get(idx) if idx is not None else None

        if info is None:
            # UNMAPPED cluster -- never drop the text, render flagged.
            raw_label = (utt.get("speaker_label") or "").strip()
            if not raw_label:
                raw_label = f"Speaker {idx}" if idx is not None else "Speaker ?"
            lines.append(WorkingLine(
                line_type="flagged",
                text=text,
                speaker_label=raw_label,
                role=None,
                speaker_index=idx,
                utterance_ids=[utt_id] if utt_id else [],
                flagged=True,
                start_time=start,
            ))
            continue

        qa = info["qa"]
        if qa == "Q":
            line_type = "Q"
        elif qa == "A":
            line_type = "A"
        else:
            line_type = "colloquy"

        lines.append(WorkingLine(
            line_type=line_type,
            text=text,
            speaker_label=info["label"],
            role=info["role"],
            speaker_index=idx,
            utterance_ids=[utt_id] if utt_id else [],
            flagged=False,
            start_time=start,
        ))

    return lines


def render_to_dicts(
    utterances: list[dict],
    participants: list[dict],
) -> list[dict]:
    """Convenience: render and return plain dicts for a JSON API response."""
    return [ln.to_dict() for ln in render_working_transcript(utterances, participants)]
