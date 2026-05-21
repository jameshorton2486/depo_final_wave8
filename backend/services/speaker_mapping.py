"""Speaker mapping: raw diarization indices -> canonical participants.

THE PROBLEM THIS SOLVES
    Deepgram returns speaker indices (0, 1, 2, ...). They are acoustic
    clusters, not people. One witness on a failing microphone is routinely
    split across two or three indices; an attorney's objections may cluster
    separately from their examination. No request parameter fixes this --
    it is intrinsic to all ASR diarization.

    The fix is a human-confirmed identity layer. This module provides the
    two deterministic pieces around that human step:

      1. prefill_participants() -- a deterministic FIRST GUESS the reporter
         can accept or override. It uses only counting and string matching
         on the transcript text. There is NO AI here and NO model call.

      2. build_speaker_directory() -- collapses the confirmed participant
         list into a {speaker_index -> role/label} lookup the renderer uses
         to assign Q. / A. / colloquy. Pure table lookup.

    The certified transcript therefore depends on exactly two things, both
    auditable: Deepgram's verbatim words, and the reporter's own speaker
    assignments. A language model never touches either one.
"""
from __future__ import annotations

import json
from typing import Optional

# --------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------
# The full deposition role set offered in the Speaker Mapping UI.
ROLES: tuple[str, ...] = (
    "examining_attorney",
    "witness",
    "defending_attorney",
    "co_counsel",
    "court_reporter",
    "videographer",
    "interpreter",
    "off_record",
    "other",
)

ROLE_LABELS: dict[str, str] = {
    "examining_attorney": "Examining Attorney",
    "witness": "Witness",
    "defending_attorney": "Defending Attorney",
    "co_counsel": "Co-Counsel",
    "court_reporter": "Court Reporter",
    "videographer": "Videographer",
    "interpreter": "Interpreter",
    "off_record": "Off the Record",
    "other": "Other",
}

# How each role renders in the transcript body.
#   Q       -- examining attorney's questions  -> "Q."
#   A       -- the witness's testimony         -> "A."
#   COLLOQUY-- everyone else; rendered as named colloquy ("MS. ZAHN:", etc.)
_QA_BY_ROLE: dict[str, str] = {
    "examining_attorney": "Q",
    "witness": "A",
}


def role_to_qa(role: Optional[str]) -> str:
    """Map a participant role to its transcript rendering mode."""
    return _QA_BY_ROLE.get((role or "").strip(), "COLLOQUY")


def is_valid_role(role: Optional[str]) -> bool:
    return (role or "").strip() in ROLES


# --------------------------------------------------------------------
# Text signals for the deterministic prefill
# --------------------------------------------------------------------
# Phrases only the court reporter says when going on/off the record and
# swearing the witness. Matched case-insensitively as substrings.
_REPORTER_PHRASES: tuple[str, ...] = (
    "on the record",
    "off the record",
    "the time is",
    "court reporter",
    "raise your right hand",
    "solemnly swear",
    "the beginning of the deposition",
    "continuation of the deposition",
    "licensed in texas",
    "we are on the record",
    "back on the record",
)

# Leading tokens of a spoken objection. An objecting speaker is almost
# always defending counsel.
_OBJECTION_MARKERS: tuple[str, ...] = (
    "objection",
    "object to",
    "form, vague",
    "vague and ambiguous",
    "calls for speculation",
    "misstates",
)


def _count_phrase_hits(texts: list[str], phrases: tuple[str, ...]) -> int:
    hits = 0
    for t in texts:
        low = t.lower()
        for p in phrases:
            if p in low:
                hits += 1
                break
    return hits


def _speaker_stats(speaker_index: int, utterances: list[dict]) -> dict:
    """Counting-only profile of one raw speaker index."""
    texts = [
        (u.get("text") or "").strip()
        for u in utterances
        if u.get("speaker_index") == speaker_index and (u.get("text") or "").strip()
    ]
    questions = sum(1 for t in texts if t.endswith("?"))
    objections = _count_phrase_hits(texts, _OBJECTION_MARKERS)
    reporter = _count_phrase_hits(texts, _REPORTER_PHRASES)
    words = sum(len(t.split()) for t in texts)
    return {
        "speaker_index": speaker_index,
        "utterance_count": len(texts),
        "word_count": words,
        "question_count": questions,
        "objection_count": objections,
        "reporter_score": reporter,
        "sample": texts[0] if texts else "",
    }


def _guess_role(stats: dict) -> str:
    """Classify a single speaker from its stats. Deterministic.

    Used as a fallback for leftover speakers after the primary role
    holders are picked, so that fragmented indices fold onto a sensible
    role instead of all landing in 'other'.
    """
    if stats["reporter_score"] >= 2:
        return "court_reporter"
    if stats["objection_count"] >= 2 and stats["objection_count"] >= stats["question_count"]:
        return "defending_attorney"
    if stats["question_count"] >= 3 and stats["question_count"] > stats["objection_count"]:
        return "examining_attorney"
    if stats["word_count"] > 0:
        # Speaks, but not question- or objection-heavy: most likely the witness.
        return "witness"
    return "other"


def prefill_participants(speakers: list[dict], utterances: list[dict]) -> list[dict]:
    """Produce a deterministic first-guess participant list for a job.

    `speakers`    -- transcript_speakers rows (speaker_index, word_count, ...)
    `utterances`  -- transcript_utterances rows (speaker_index, text, ...)

    Returns a list of participant dicts (name=None, is_prefill=1). Every
    detected speaker index is assigned to exactly one participant. The
    reporter confirms or overrides this in the Speaker Mapping step.

    The strategy: pick the single best index for each primary role
    (reporter, examiner, witness, defender), then fold every remaining
    index onto the role it most resembles. Multiple indices collapsing
    onto one participant is the expected, correct outcome.
    """
    indices = sorted({s["speaker_index"] for s in speakers if s.get("speaker_index") is not None})
    if not indices:
        return []

    stats = {i: _speaker_stats(i, utterances) for i in indices}
    assigned: dict[int, str] = {}

    # 1. Court reporter: strongest reporter-phrase score (must be convincing).
    reporter_pool = [i for i in indices if stats[i]["reporter_score"] >= 2]
    if reporter_pool:
        pick = max(reporter_pool, key=lambda i: stats[i]["reporter_score"])
        assigned[pick] = "court_reporter"

    # 2. Examining attorney: most question-shaped utterances among the rest.
    examiner_pool = [
        i for i in indices if i not in assigned and stats[i]["question_count"] >= 3
    ]
    if examiner_pool:
        pick = max(examiner_pool, key=lambda i: stats[i]["question_count"])
        assigned[pick] = "examining_attorney"

    # 3. Witness: most words among the remaining speakers (long narrative answers).
    witness_pool = [i for i in indices if i not in assigned and stats[i]["word_count"] > 0]
    if witness_pool:
        pick = max(witness_pool, key=lambda i: stats[i]["word_count"])
        assigned[pick] = "witness"

    # 4. Defending attorney: most objections among whoever is still unassigned.
    defender_pool = [
        i for i in indices if i not in assigned and stats[i]["objection_count"] >= 2
    ]
    if defender_pool:
        pick = max(defender_pool, key=lambda i: stats[i]["objection_count"])
        assigned[pick] = "defending_attorney"

    # 5. Fold every leftover index onto the role it most resembles.
    for i in indices:
        if i not in assigned:
            assigned[i] = _guess_role(stats[i])

    # Group indices by assigned role into one participant per role.
    by_role: dict[str, list[int]] = {}
    for idx, role in assigned.items():
        by_role.setdefault(role, []).append(idx)

    participants: list[dict] = []
    for sort_order, role in enumerate(r for r in ROLES if r in by_role):
        idx_list = sorted(by_role[role])
        participants.append(
            {
                "name": None,
                "role": role,
                "speaker_indices": idx_list,
                "is_prefill": 1,
                "sort_order": sort_order,
            }
        )
    return participants


# --------------------------------------------------------------------
# Render directory
# --------------------------------------------------------------------

def build_speaker_directory(participants: list[dict]) -> dict[int, dict]:
    """Collapse a participant list into a {speaker_index -> render info} map.

    Each value carries the participant's name, role, and qa mode ('Q',
    'A', or 'COLLOQUY'). This is the lookup the transcript renderer uses
    to label every utterance. Pure table lookup -- no inference.
    """
    directory: dict[int, dict] = {}
    for p in participants:
        role = p.get("role") or "other"
        info = {
            "participant_id": p.get("participant_id"),
            "name": p.get("name"),
            "role": role,
            "role_label": ROLE_LABELS.get(role, "Other"),
            "qa": role_to_qa(role),
        }
        for idx in _coerce_indices(p.get("speaker_indices")):
            directory[idx] = info
    return directory


def _coerce_indices(value) -> list[int]:
    """Accept a JSON string or a list; return a clean list[int]."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    out: list[int] = []
    for v in value or []:
        try:
            out.append(int(v))
        except (ValueError, TypeError):
            continue
    return out
