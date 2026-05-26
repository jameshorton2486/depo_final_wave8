"""Canonical transcript packet builder.

A "transcript packet" is the single self-describing JSON object that
represents one transcribed media file. It is the canonical source layer
the build plan mandates -- everything downstream (Workspace, Insertions,
Certify, Export, readback) reads packets, never giant transcript strings.

Two packets are written per job:

    raw.json      -- IMMUTABLE. The verbatim ASR output. Never modified
                     after ingestion.
    working.json  -- a copy of raw.json that downstream stages may edit.

Packet shape:
    {
      "packet_version": 1,
      "layer": "raw" | "working",
      "job": { ... job + media metadata ... },
      "engine": { ... ASR engine + provenance ... },
      "speakers": [ ... ],
      "utterances": [ ... ],
      "words": [ ... ],          # the canonical word objects
      "keyterms": [ ... ],
      "artifacts": { ... file paths ... }
    }
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.transcript.assembler import NormalizedTranscript
from backend.transcript.integrity import write_immutable_raw_packet

PACKET_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_packet(
    *,
    job_id: str,
    layer: str,
    source_filename: str,
    source_size_bytes: int,
    transcription_source: str,
    engine_name: str,
    normalized: NormalizedTranscript,
    keyterms: list[str],
    audio_path: str | None,
) -> dict:
    """Assemble a canonical transcript packet dict.

    `layer` is 'raw' or 'working'. The two share identical content at
    ingestion time; they diverge only once the Workspace stage edits the
    working layer.
    """
    if layer not in ("raw", "working"):
        raise ValueError(f"layer must be 'raw' or 'working', got {layer!r}")

    return {
        "packet_version": PACKET_VERSION,
        "layer": layer,
        "generated_at": _utc_now(),
        "job": {
            "job_id": job_id,
            "source_filename": source_filename,
            "source_size_bytes": source_size_bytes,
            "duration_seconds": normalized.duration_seconds,
            "word_count": normalized.word_count,
            "utterance_count": normalized.utterance_count,
            "speaker_count": normalized.speaker_count,
            "avg_confidence": normalized.avg_confidence,
        },
        "engine": {
            "name": engine_name,
            "transcription_source": transcription_source,
            "full_text": normalized.full_text,
        },
        "speakers": normalized.speakers,
        "utterances": normalized.utterances,
        "words": normalized.words,
        "keyterms": list(keyterms or []),
        "artifacts": {
            "audio_path": audio_path,
        },
    }


def write_packet(packet: dict, destination: str | Path) -> Path:
    """Write a packet to disk as pretty-printed JSON. Returns the path."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return destination


def write_raw_packet(packet: dict, destination: str | Path) -> Path:
    """Write the immutable RAW packet exactly once."""
    return write_immutable_raw_packet(packet, destination)


def read_packet(source: str | Path) -> dict:
    """Load a packet JSON file from disk."""
    return json.loads(Path(source).read_text(encoding="utf-8"))
