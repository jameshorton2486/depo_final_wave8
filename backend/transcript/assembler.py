"""Transcript assembler.

Takes a RAW provider response (real Deepgram batch JSON, or the offline
fallback's Deepgram-shaped equivalent) and normalizes it into the
canonical DEPO-PRO object model:

    words[]       -- one dict per spoken token (the canonical layer)
    utterances[]  -- speaker-turn blocks, each owning a slice of words
    speakers[]    -- the speaker map

This module performs ONLY structural assembly: continuity, ordering,
speaker grouping. It does NOT do punctuation rewriting, cleanup, or
legal formatting -- those belong to later stages, per the build plan's
"faithful transcript acquisition, not transformation" rule.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

# Hesitation / filler tokens preserved verbatim in the raw layer but
# flagged so the export stage can optionally suppress them.
_FILLER_TOKENS = {"um", "uh", "uh-huh", "huh-uh", "mm-hmm", "er", "ah"}


@dataclass
class NormalizedTranscript:
    """Canonical, provider-agnostic transcript produced by the assembler."""

    words: list[dict] = field(default_factory=list)
    utterances: list[dict] = field(default_factory=list)
    speakers: list[dict] = field(default_factory=list)
    duration_seconds: float = 0.0
    full_text: str = ""

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def utterance_count(self) -> int:
        return len(self.utterances)

    @property
    def speaker_count(self) -> int:
        return len(self.speakers)

    @property
    def avg_confidence(self) -> float:
        if not self.words:
            return 0.0
        return round(sum(w["confidence"] for w in self.words) / len(self.words), 4)


def _is_filler(token: str) -> bool:
    return token.strip().strip(".,?;:!").lower() in _FILLER_TOKENS


def _word_text(raw_word: dict) -> str:
    """Prefer the punctuated form Deepgram returns; fall back to the bare word."""
    return (
        raw_word.get("punctuated_word")
        or raw_word.get("word")
        or ""
    ).strip()


def normalize(raw_response: dict) -> NormalizedTranscript:
    """Normalize a Deepgram-shaped batch response into canonical objects.

    Robust to both the real API response and the offline fallback, and
    degrades gracefully if `utterances` is absent (falls back to grouping
    the flat word list by consecutive speaker index).
    """
    results = (raw_response or {}).get("results", {}) or {}
    metadata = (raw_response or {}).get("metadata", {}) or {}

    channels = results.get("channels") or []
    alternatives = (channels[0].get("alternatives") if channels else []) or []
    primary = alternatives[0] if alternatives else {}
    flat_words = primary.get("words") or []

    raw_utterances = results.get("utterances")
    if not raw_utterances:
        raw_utterances = _group_words_by_speaker(flat_words)

    # Deepgram utterances are persisted one-to-one as canonical utterances.
    # No same-speaker merging occurs at ingest: the canonical/raw layer must
    # faithfully mirror the provider response. Speaker-run grouping for the
    # Playground-style display is a render-layer concern (Stage 3), not a
    # transcript transformation.

    transcript = NormalizedTranscript()
    word_index = 0
    speaker_word_counts: dict[int, int] = {}

    for utt_index, raw_utt in enumerate(raw_utterances):
        utterance_id = str(uuid.uuid4())
        speaker_index = _safe_int(raw_utt.get("speaker"))
        utt_words_raw = raw_utt.get("words") or []

        canonical_words: list[dict] = []
        for raw_word in utt_words_raw:
            text = _word_text(raw_word)
            if not text:
                continue
            confidence = _safe_float(raw_word.get("confidence"), default=1.0)
            word_speaker = _safe_int(raw_word.get("speaker"), default=speaker_index)
            word_obj = {
                "word_id": str(uuid.uuid4()),
                "utterance_id": utterance_id,
                "word_index": word_index,
                "raw_text": text,
                "working_text": None,
                "speaker_index": word_speaker,
                "start_time": _safe_float(raw_word.get("start")),
                "end_time": _safe_float(raw_word.get("end")),
                "confidence": round(confidence, 4),
                "is_filler": 1 if _is_filler(text) else 0,
                "reviewed": 0,
            }
            canonical_words.append(word_obj)
            transcript.words.append(word_obj)
            word_index += 1
            if word_speaker is not None:
                speaker_word_counts[word_speaker] = (
                    speaker_word_counts.get(word_speaker, 0) + 1
                )

        if not canonical_words:
            continue

        utt_text = (raw_utt.get("transcript") or "").strip() or " ".join(
            w["raw_text"] for w in canonical_words
        )
        utt_confidence = _safe_float(raw_utt.get("confidence"), default=None)
        if utt_confidence is None:
            utt_confidence = round(
                sum(w["confidence"] for w in canonical_words) / len(canonical_words), 4
            )

        transcript.utterances.append(
            {
                "utterance_id": utterance_id,
                "utterance_index": utt_index,
                "speaker_index": speaker_index,
                "speaker_label": _speaker_label(speaker_index),
                "start_time": _safe_float(raw_utt.get("start")),
                "end_time": _safe_float(raw_utt.get("end")),
                "text": utt_text,
                "avg_confidence": round(utt_confidence, 4),
            }
        )

    # Speaker map.
    for speaker_index in sorted(speaker_word_counts):
        transcript.speakers.append(
            {
                "speaker_row_id": str(uuid.uuid4()),
                "speaker_index": speaker_index,
                "speaker_label": _speaker_label(speaker_index),
                "assigned_name": None,
                "speaker_role": None,
                "word_count": speaker_word_counts[speaker_index],
            }
        )

    # Duration: trust the ASR metadata, else use the last word's end time.
    duration = _safe_float(metadata.get("duration"), default=None)
    if duration is None and transcript.words:
        duration = max(w["end_time"] for w in transcript.words)
    transcript.duration_seconds = round(duration or 0.0, 3)

    transcript.full_text = (primary.get("transcript") or "").strip() or " ".join(
        u["text"] for u in transcript.utterances
    )
    return transcript

def _group_words_by_speaker(flat_words: list[dict]) -> list[dict]:
    """Fallback grouping when the response has no `utterances` array.

    Splits the flat word list on speaker-index changes so we still get
    sensible speaker-turn blocks.
    """
    if not flat_words:
        return []

    grouped: list[dict] = []
    current: list[dict] = []
    current_speaker = _safe_int(flat_words[0].get("speaker"))

    def _flush() -> None:
        if not current:
            return
        grouped.append(
            {
                "speaker": current_speaker,
                "start": current[0].get("start"),
                "end": current[-1].get("end"),
                "transcript": " ".join(_word_text(w) for w in current),
                "words": list(current),
            }
        )

    for word in flat_words:
        speaker = _safe_int(word.get("speaker"))
        if speaker != current_speaker and current:
            _flush()
            current = []
            current_speaker = speaker
        current.append(word)
    _flush()
    return grouped


def _speaker_label(speaker_index: int | None) -> str:
    if speaker_index is None:
        return "Speaker ?"
    return f"Speaker {speaker_index}"


def _safe_int(value, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
