"""Cross-speaker contamination flag detector.

Read-only analysis over canonical utterances + per-word diarization.
The detector never rewrites transcript text or speaker attribution; it
produces review-only Suggestion rows for human review in Stage 3.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import uuid

from backend.ai_review import review_queue
from backend.ai_review.suggestions import (
    KIND_FLAG,
    STATUS_INFORMATIONAL,
    STATUS_PENDING,
    STATUS_REJECTED,
    Suggestion,
)
from backend.models.transcripts import CrossSpeakerFlagSummary
from backend.transcript import repository as trepo
from backend.transcript_state import snapshot_repo


SOURCE = "cross_speaker_detector"
FLAG_MID_UTTERANCE_CHANGE = "mid_utterance_change"
FLAG_FLICKER = "flicker"
FLAG_SHORT_TURN = "short_turn"
_MARKER_ID = "__cross_speaker_detector__"
SHORT_TURN_MAX_WORDS = 3
FLICKER_RATIO_THRESHOLD = 0.15


@dataclass
class ClassifiedFlag:
    utterance_id: str
    utterance_text: str
    utterance_speaker_index: int | None
    word_speaker_counts: dict[int, int]
    speaker_runs: list[dict]
    flag_category: str
    severity: str
    word_excerpt: list[str]


def _stable_suggestion_id(job_id: str, utterance_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://depo-pro.local/{SOURCE}/{job_id}/{utterance_id}"))


def _marker_suggestion_id(job_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://depo-pro.local/{SOURCE}/{job_id}/{_MARKER_ID}"))


def _is_cross_speaker_payload(payload: dict | None) -> bool:
    return bool(payload and payload.get("source") == SOURCE)


def _is_marker_payload(payload: dict | None) -> bool:
    return _is_cross_speaker_payload(payload) and bool(payload.get("detector_marker"))


def _severity_for(category: str) -> str:
    if category == FLAG_MID_UTTERANCE_CHANGE:
        return "high"
    if category == FLAG_SHORT_TURN:
        return "medium"
    return "low"


def _build_speaker_runs(speakers: list[int | None]) -> list[dict]:
    runs: list[dict] = []
    if not speakers:
        return runs
    current = speakers[0]
    start = 0
    length = 1
    for idx, speaker in enumerate(speakers[1:], start=1):
        if speaker == current:
            length += 1
            continue
        runs.append({"speaker_index": current, "start_word": start, "length": length})
        current = speaker
        start = idx
        length = 1
    runs.append({"speaker_index": current, "start_word": start, "length": length})
    return runs


def _classify_flag(
    *,
    utterance_speaker: int | None,
    word_speakers: list[int | None],
) -> str | None:
    filtered = [s for s in word_speakers if s is not None]
    if not filtered:
        return None
    distinct = sorted(set(filtered))
    if len(distinct) == 1 and distinct[0] == utterance_speaker:
        return None

    total_words = len(filtered)
    minority_words = sum(1 for s in filtered if s != utterance_speaker)
    ratio = minority_words / total_words if total_words else 0.0
    runs = _build_speaker_runs(filtered)
    off_runs = [r for r in runs if r["speaker_index"] != utterance_speaker]
    max_off_run = max((r["length"] for r in off_runs), default=0)

    # Investigation-phase thresholds, retained for review prioritization only.
    if total_words <= SHORT_TURN_MAX_WORDS:
        return FLAG_SHORT_TURN
    if minority_words == 1 or ratio < FLICKER_RATIO_THRESHOLD or max_off_run == 1:
        return FLAG_FLICKER
    return FLAG_MID_UTTERANCE_CHANGE


def detect_for_job(job_id: str) -> list[ClassifiedFlag]:
    utterances = trepo.get_utterances(job_id, layer="raw")
    words = trepo.get_words(job_id)
    by_utterance: dict[str, list[dict]] = defaultdict(list)
    for word in words:
        by_utterance[word.get("utterance_id")].append(word)

    flags: list[ClassifiedFlag] = []
    for utt in utterances:
        utt_id = utt.get("utterance_id") or ""
        utt_words = by_utterance.get(utt_id, [])
        word_speakers = [w.get("speaker_index") for w in utt_words]
        category = _classify_flag(
            utterance_speaker=utt.get("speaker_index"),
            word_speakers=word_speakers,
        )
        if not category:
            continue
        counts = Counter(s for s in word_speakers if s is not None)
        excerpt = []
        for word in utt_words[:18]:
            token = word.get("punctuated_word") or word.get("word") or word.get("raw_text") or ""
            excerpt.append(f"{word.get('speaker_index')}:{token}")
        flags.append(
            ClassifiedFlag(
                utterance_id=utt_id,
                utterance_text=utt.get("text") or "",
                utterance_speaker_index=utt.get("speaker_index"),
                word_speaker_counts=dict(counts),
                speaker_runs=_build_speaker_runs(word_speakers),
                flag_category=category,
                severity=_severity_for(category),
                word_excerpt=excerpt,
            )
        )
    return flags


def _flag_reason(category: str, utterance_speaker_index: int | None, counts: dict[int, int]) -> str:
    if category == FLAG_MID_UTTERANCE_CHANGE:
        prefix = "High-confidence cross-speaker turn"
    elif category == FLAG_SHORT_TURN:
        prefix = "Short cross-speaker turn"
    else:
        prefix = "Possible speaker flicker"
    return (
        f"{prefix}: utterance speaker {utterance_speaker_index} contains words "
        f"from multiple speaker clusters {counts}. Review before confirming mapping."
    )


def _to_suggestions(
    job_id: str,
    flags: list[ClassifiedFlag],
    *,
    certified_locked: bool,
) -> list[Suggestion]:
    status = STATUS_INFORMATIONAL if certified_locked else STATUS_PENDING
    suggestions: list[Suggestion] = []
    for flag in flags:
        payload = {
            "source": SOURCE,
            "flag_category": flag.flag_category,
            "utterance_speaker_index": flag.utterance_speaker_index,
            "word_speaker_counts": flag.word_speaker_counts,
            "speaker_runs": flag.speaker_runs,
            "severity": flag.severity,
            "word_excerpt": flag.word_excerpt,
            "locked_informational": certified_locked,
        }
        suggestions.append(
            Suggestion(
                suggestion_id=_stable_suggestion_id(job_id, flag.utterance_id),
                job_id=job_id,
                kind=KIND_FLAG,
                reason=_flag_reason(
                    flag.flag_category,
                    flag.utterance_speaker_index,
                    flag.word_speaker_counts,
                ),
                target_utterance_id=flag.utterance_id,
                before_text=flag.utterance_text,
                after_text=flag.utterance_text,
                four_part_pass=False,
                status=status,
                payload=payload,
            )
        )
    marker_payload = {
        "source": SOURCE,
        # Internal computation sentinel: distinguishes "already computed"
        # from "not yet computed" even when a job yields zero visible flags.
        # Excluded from all user-facing lists and counts.
        "detector_marker": True,
        "summary": build_summary(flags, certified_locked=certified_locked).model_dump(),
        "locked_informational": certified_locked,
    }
    suggestions.append(
        Suggestion(
            suggestion_id=_marker_suggestion_id(job_id),
            job_id=job_id,
            kind=KIND_FLAG,
            reason="Cross-speaker detector marker.",
            four_part_pass=False,
            status=status,
            payload=marker_payload,
        )
    )
    return suggestions


def build_summary(
    flags: list[ClassifiedFlag] | list[Suggestion],
    *,
    certified_locked: bool,
) -> CrossSpeakerFlagSummary:
    if flags and isinstance(flags[0], Suggestion):
        items = []
        for s in flags:  # type: ignore[assignment]
            payload = s.payload or {}
            if _is_marker_payload(payload):
                continue
            items.append(payload.get("flag_category"))
        counts = Counter(items)
    else:
        counts = Counter(getattr(flag, "flag_category", None) for flag in flags)
    return CrossSpeakerFlagSummary(
        total=sum(counts.values()),
        mid_utterance_change=counts.get(FLAG_MID_UTTERANCE_CHANGE, 0),
        flicker=counts.get(FLAG_FLICKER, 0),
        short_turn=counts.get(FLAG_SHORT_TURN, 0),
        certified_locked=certified_locked,
        informational_only=certified_locked,
    )


def list_persisted(job_id: str) -> list[Suggestion]:
    return [
        s for s in review_queue.list_suggestions(job_id)
        if _is_cross_speaker_payload(s.payload)
    ]


def invalidate_for_job(job_id: str) -> int:
    return review_queue.delete_suggestions(
        job_id,
        predicate=lambda s: _is_cross_speaker_payload(s.payload),
    )


def ensure_persisted(job_id: str) -> CrossSpeakerFlagSummary:
    certified_locked = snapshot_repo.has_locked_snapshot(job_id)
    existing = list_persisted(job_id)
    if existing:
        if certified_locked:
            for suggestion in existing:
                if suggestion.status == STATUS_PENDING:
                    review_queue.set_status(
                        suggestion.suggestion_id,
                        STATUS_INFORMATIONAL,
                    )
                if not suggestion.payload.get("locked_informational"):
                    review_queue.update_payload(
                        suggestion.suggestion_id,
                        {"locked_informational": True},
                    )
        active = [
            s for s in list_persisted(job_id)
            if s.status != STATUS_REJECTED or _is_marker_payload(s.payload)
        ]
        return build_summary(active, certified_locked=certified_locked)

    flags = detect_for_job(job_id)
    review_queue.save_suggestions(_to_suggestions(job_id, flags, certified_locked=certified_locked))
    return build_summary(flags, certified_locked=certified_locked)
