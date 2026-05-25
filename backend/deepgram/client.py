"""Deepgram ASR client for the DEPO-PRO transcripts engine.

Two transcription paths:

1. REAL  -- POST the media file to Deepgram's batch REST API
            (https://api.deepgram.com/v1/listen). Used when DEEPGRAM_API_KEY
            is set in the environment. No third-party SDK required; this
            uses only the Python standard library so the desktop build
            stays dependency-light.

2. OFFLINE FALLBACK -- when no API key is configured, a deterministic
            synthetic deposition transcript is generated instead. This lets
            the entire Stage 2 pipeline, persistence layer, and UI run and
            be tested end-to-end with no network and no API key.

Both paths return a RAW provider-style response dict. The shape is then
normalized by backend/transcript/assembler.py so the rest of the system
never has to care which path produced it.

The RAW response is treated as immutable once written to disk.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path

from loguru import logger

DEEPGRAM_ENDPOINT = "https://api.deepgram.com/v1/listen"

# Batch parameters. Kept aligned with the DEPO-PRO technical spec and
# verified against current Deepgram pre-recorded docs (May 2026):
#   - model nova-3, punctuation + paragraphs + utterances on.
#   - filler_words on: legal transcripts require verbatim hesitations
#     ("um", "uh") -- with filler_words off Deepgram strips them.
#   - diarize_model=latest: the modern batch diarization parameter. It
#     both enables diarization and selects Deepgram's v2 diarizer (much
#     better speaker separation than the legacy diarize=true, which
#     stays pinned to v1). NOTE: a future live/streaming path must use
#     diarize=true instead -- diarize_model is rejected on streaming.
#   - smart_format/paragraphs are presentation flags that affect the
#     rendered text. That is acceptable here because the full Deepgram
#     JSON is persisted verbatim as the immutable raw packet; all
#     downstream text is derived from it and never overwrites it.
DEEPGRAM_PARAMS = {
    "model": "nova-3",
    "punctuate": "true",
    "paragraphs": "true",
    "diarize_model": "latest",
    "filler_words": "true",
    "utterances": "true",
    "smart_format": "true",
}

# Network guard for the standard-library uploader. Large depositions
# should eventually use chunked/streaming upload; flagged in the build plan.
MAX_UPLOAD_BYTES = 250 * 1024 * 1024  # 250 MB

# Audio/video extension -> Content-Type for the REST upload header.
_CONTENT_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


def _content_type_for(path: Path) -> str:
    return _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


# Deepgram Nova-3 Keyterm Prompting accepts up to 100 important terms or
# phrases per request. Anything beyond that is silently ignored, so the
# list is normalized once: whitespace collapsed, case-insensitive
# duplicates dropped, then capped.
KEYTERM_LIMIT = 100


def normalize_keyterms(terms: list[str] | list[dict] | None) -> list[str]:
    """Clean, de-duplicate, and cap a keyterm list for Deepgram Nova-3."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in terms or []:
        if isinstance(raw, Mapping):
            raw = raw.get("term")
        term = " ".join(str(raw).split()).strip()
        if not term:
            continue
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(term)
        if len(out) >= KEYTERM_LIMIT:
            break
    return out


def api_key_present() -> bool:
    """True when a usable Deepgram API key is configured."""
    return bool((os.getenv("DEEPGRAM_API_KEY") or "").strip())


def transcribe_file(audio_path: str | Path, keyterms: list[str] | None = None) -> dict:
    """Transcribe one media file.

    Returns a dict with:
        source    -- 'deepgram' or 'offline-fallback'
        response  -- the raw provider response (Deepgram JSON, or the
                     synthetic equivalent)

    Never raises for the offline path. The real path raises
    DeepgramError on network/API failure so the caller can mark the job
    failed and surface a message.
    """
    audio_path = Path(audio_path)
    keyterms = normalize_keyterms(keyterms or [])
    logger.info(
        f"Preparing Deepgram request for {audio_path.name} with {len(keyterms)} keyterm(s)"
    )

    if api_key_present():
        logger.info(f"Deepgram: transcribing {audio_path.name} via REST API")
        response = _transcribe_via_rest(audio_path, keyterms)
        return {"source": "deepgram", "response": response}

    logger.warning(
        "DEEPGRAM_API_KEY not set -- using deterministic offline fallback "
        f"transcript for {audio_path.name}. Set the key in .env for real ASR."
    )
    response = _synthetic_response(audio_path)
    return {"source": "offline-fallback", "response": response}


class DeepgramError(RuntimeError):
    """Raised when the real Deepgram REST call fails."""


# --------------------------------------------------------------------
# Real path: Deepgram batch REST API (standard library only)
# --------------------------------------------------------------------
def _transcribe_via_rest(audio_path: Path, keyterms: list[str]) -> dict:
    api_key = (os.getenv("DEEPGRAM_API_KEY") or "").strip()
    if not audio_path.exists():
        raise DeepgramError(f"Audio file not found: {audio_path}")

    size = audio_path.stat().st_size
    if size == 0:
        raise DeepgramError("Audio file is empty.")
    if size > MAX_UPLOAD_BYTES:
        raise DeepgramError(
            f"Audio file is {size} bytes; the standard-library uploader caps "
            f"at {MAX_UPLOAD_BYTES} bytes. Split the file or pre-compress it."
        )

    # Build the query string. keyterm may be repeated for nova-3 in-context
    # vocabulary boosting; normalize_keyterms() handles the 100-term cap.
    query_pairs = list(DEEPGRAM_PARAMS.items())
    for term in normalize_keyterms(keyterms):
        query_pairs.append(("keyterm", term))
    url = f"{DEEPGRAM_ENDPOINT}?{urllib.parse.urlencode(query_pairs)}"

    audio_bytes = audio_path.read_bytes()
    request = urllib.request.Request(
        url,
        data=audio_bytes,
        method="POST",
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": _content_type_for(audio_path),
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=600) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise DeepgramError(f"Deepgram API HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise DeepgramError(f"Deepgram API unreachable: {exc.reason}") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DeepgramError(f"Deepgram returned non-JSON response: {exc}") from exc


# --------------------------------------------------------------------
# Offline fallback: deterministic synthetic deposition transcript
# --------------------------------------------------------------------
# A short scripted deposition. Each tuple is (speaker_index, text). The
# offline generator lays these out with realistic word-level timestamps
# and confidence scores so the review / readback features have real data
# to work against. A couple of words carry low confidence on purpose to
# exercise the low-confidence highlighting path downstream.
_SCRIPT: list[tuple[int, str]] = [
    (0, "Please state your full name and occupation for the record."),
    (1, "Doctor Donald Leifer. I am a board certified neurosurgeon with Houston Neurological."),
    (0, "And did you have occasion to review the MRI scans for Miss Sarah Jenkins?"),
    (1, "Yes. We took detailed brain scans and identified an acoustic neuroma."),
    (0, "Let the record reflect the MRI scans are marked as Exhibit 1 for identification."),
    (1, "The mass was approximately, um, two point four centimeters on the largest axis."),
    (0, "And was that mass compromising the adjacent cranial nerve structures?"),
    (1, "Yes. It was compressing the seventh cranial nerve pathway."),
    (0, "Thank you, Doctor. We will take a short recess and resume the afternoon session."),
]

# Words that should land with deliberately low confidence in the fallback.
_LOW_CONFIDENCE_TOKENS = {"acoustic", "neuroma", "Leifer.", "um,"}


def _synthetic_response(audio_path: Path) -> dict:
    """Build a deterministic Deepgram-shaped response from the script.

    Determinism: confidence jitter is seeded from a hash of the filename,
    so the same file always yields the same transcript. Different files
    yield slightly different confidences, which keeps multi-file batches
    visually distinct without changing the words.
    """
    seed = int(hashlib.sha256(audio_path.name.encode("utf-8")).hexdigest(), 16)

    words: list[dict] = []
    utterances: list[dict] = []
    cursor = 0.0  # running audio offset in seconds

    for utt_idx, (speaker, sentence) in enumerate(_SCRIPT):
        tokens = sentence.split()
        utt_start = cursor
        utt_words: list[dict] = []

        for tok_idx, token in enumerate(tokens):
            # ~0.34s per word with light deterministic variation.
            jitter = ((seed >> ((tok_idx + utt_idx) % 24)) & 0x7) / 100.0
            duration = 0.30 + jitter
            start = cursor
            end = cursor + duration
            cursor = end + 0.04  # tiny inter-word gap

            if token in _LOW_CONFIDENCE_TOKENS:
                confidence = 0.62 + (((seed >> tok_idx) & 0xF) / 100.0)
            else:
                confidence = 0.94 + (((seed >> tok_idx) & 0x7) / 100.0)
            confidence = round(min(confidence, 0.999), 3)

            bare = token.strip(".,?;:")
            word_obj = {
                "word": bare.lower(),
                "punctuated_word": token,
                "start": round(start, 3),
                "end": round(end, 3),
                "confidence": confidence,
                "speaker": speaker,
            }
            words.append(word_obj)
            utt_words.append(word_obj)

        cursor += 0.45  # speaker-turn gap
        utterances.append(
            {
                "speaker": speaker,
                "start": round(utt_start, 3),
                "end": round(utt_words[-1]["end"], 3),
                "transcript": sentence,
                "confidence": round(
                    sum(w["confidence"] for w in utt_words) / len(utt_words), 3
                ),
                "words": utt_words,
            }
        )

    transcript_text = " ".join(u["transcript"] for u in utterances)

    # Mirror the parts of the Deepgram batch response shape that the
    # assembler reads: results.utterances and results.channels[0]...words.
    return {
        "metadata": {
            "transcription_source": "offline-fallback",
            "duration": round(cursor, 3),
            "model_info": {"name": "offline-fallback"},
        },
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "transcript": transcript_text,
                            "confidence": round(
                                sum(w["confidence"] for w in words) / len(words), 3
                            ),
                            "words": words,
                        }
                    ]
                }
            ],
            "utterances": utterances,
        },
    }
