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
# Wave 11: speaker label formatting
# --------------------------------------------------------------------
# A speaker label is the exact string printed in the transcript for a
# participant. Two forms (spec wave11 section 6.1):
#   - attorneys / witness : "{HONORIFIC}. {SURNAME}"  e.g. "MR. NUNEZ"
#       all-caps, exactly one space after the honorific period.
#   - court officers      : a fixed "THE ..." label, no name.
# This builder is the single authority for both the candidate-name
# dropdown and the transcript renderer, so the two cannot diverge.

VALID_HONORIFICS: tuple[str, ...] = ("MR", "MS", "MRS", "DR")

# Roles that take a "{HONORIFIC}. {SURNAME}" label.
_NAMED_LABEL_ROLES: frozenset[str] = frozenset({
    "examining_attorney", "witness", "defending_attorney", "co_counsel",
})

# Roles that take a fixed court-officer label, no name.
_COURT_OFFICER_LABELS: dict[str, str] = {
    "court_reporter": "THE REPORTER",       # never "THE COURT REPORTER"
    "videographer": "THE VIDEOGRAPHER",
    "interpreter": "THE INTERPRETER",
}


def _surname_of(name: Optional[str]) -> str:
    """Extract the surname (last whitespace-delimited token) from a name."""
    if not name:
        return ""
    cleaned = name.strip().rstrip(",.").strip()
    if not cleaned:
        return ""
    # If already an all-caps single token, take it as the surname.
    return cleaned.split()[-1]


def participant_label(
    role: Optional[str],
    name: Optional[str],
    honorific: Optional[str] = None,
) -> str:
    """Build the deterministic speaker label for a participant.

    Returns the finished, transcript-ready label string. Empty string when
    there is not enough information yet (e.g. a named role with no surname,
    or a named role missing its honorific) -- the caller treats an empty
    label as "not finalised".

    This is spec wave11 section 6.1 and the engine's STD-SPK-01/02.
    """
    role = (role or "").strip()

    # Court officers -- fixed label, ignore name/honorific entirely.
    if role in _COURT_OFFICER_LABELS:
        return _COURT_OFFICER_LABELS[role]

    # Named roles -- "{HONORIFIC}. {SURNAME}", all-caps, one space.
    if role in _NAMED_LABEL_ROLES:
        surname = _surname_of(name).upper()
        hon = (honorific or "").strip().upper().rstrip(".")
        if not surname:
            return ""
        if hon not in VALID_HONORIFICS:
            return ""  # not finalised until honorific is set
        return f"{hon}. {surname}"

    # off_record / other -- no standardized label form.
    if name:
        return name.strip().upper()
    return ""


def build_candidate_names(
    nod_metadata: Optional[dict] = None,
    reporter_name: Optional[str] = None,
    confirmed_spellings: Optional[dict] = None,
) -> list[str]:
    """Build the deterministic dropdown of finished speaker labels.

    Reads parsed NOD metadata (attorneys + witness) and the assigned
    reporter, passes each through participant_label(), and returns the
    de-duplicated list of label strings the Workspace name dropdown offers.

    No model call -- this is a read of already-parsed data plus the
    role-to-label rule. spec wave11 section 4.3 / 10.3.
    """
    labels: list[str] = []
    seen: set[str] = set()

    def _add(label: str) -> None:
        if label and label not in seen:
            seen.add(label)
            labels.append(label)

    meta = nod_metadata or {}

    # Attorneys from the NOD parser. Each entry may carry name + honorific.
    for atty in (meta.get("attorneys") or []):
        role = atty.get("role") or "examining_attorney"
        if role not in _NAMED_LABEL_ROLES:
            role = "examining_attorney"
        _add(participant_label(role, atty.get("name"), atty.get("honorific")))

    # Witness from the NOD parser.
    witness = meta.get("witness") or {}
    if witness.get("name"):
        _add(participant_label("witness", witness.get("name"),
                               witness.get("honorific")))

    # Court officers -- always offered; fixed labels.
    _add(participant_label("court_reporter", reporter_name))
    _add(participant_label("videographer", None))
    _add(participant_label("interpreter", None))

    return labels


# --------------------------------------------------------------------
# Wave 11: deterministic name prefill from appearance statements
# --------------------------------------------------------------------
# Appearance statements follow a recognisable pattern at the top of a
# deposition: "{NAME} for the {defendant|plaintiff}...". A deterministic
# regex can read the first utterance of a cluster and, on a match,
# pre-select a name. Best-effort only -- never overrides a user choice,
# never guesses outside the pattern. spec wave11 section 4.4.

import re as _re

_APPEARANCE_RE = _re.compile(
    r"^\s*(?P<name>[A-Z][A-Za-z.''\-]+(?:\s+[A-Z][A-Za-z.''\-]+){0,3})\s+"
    r"for\s+the\s+(?:defendant|plaintiff|deponent|witness)",
    _re.IGNORECASE,
)


def prefill_name_from_appearance(first_utterance_text: Optional[str]) -> Optional[str]:
    """Return a name parsed from an appearance-statement utterance, or None.

    Deterministic and best-effort: matches only the well-known
    '{name} for the {party}' pattern. Anything else returns None and the
    dropdown opens unselected.
    """
    if not first_utterance_text:
        return None
    m = _APPEARANCE_RE.match(first_utterance_text.strip())
    if not m:
        return None
    name = m.group("name").strip()
    # Reject single-token false positives like "Appearing for the..."
    if len(name.split()) < 2:
        return None
    return name


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
