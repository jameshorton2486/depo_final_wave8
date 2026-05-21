"""Lightweight media probe for the transcripts ingestion pipeline.

Stage 2 (per the Screen 2 build plan) should focus on *faithful
transcript acquisition*, not heavy DSP. The full deterministic
preprocessing pipeline from the technical spec (FFmpeg resample,
85 Hz high-pass, -16 LUFS normalization, Silero VAD, blind SNR) is a
later wave.

For now this module does one cheap, safe thing: probe the media file
for its duration. If `ffprobe` is on PATH it is used; otherwise the
probe degrades gracefully and the duration is filled in later from the
ASR response. No third-party Python dependency is required.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from loguru import logger


def ffprobe_available() -> bool:
    """True when the ffprobe binary can be found on PATH."""
    return shutil.which("ffprobe") is not None


def probe_duration_seconds(media_path: str | Path) -> float | None:
    """Return media duration in seconds, or None when it cannot be determined.

    Uses ffprobe when present. Any failure is swallowed and returns None
    so ingestion never breaks just because ffprobe is missing.
    """
    media_path = Path(media_path)
    if not media_path.exists():
        return None
    if not ffprobe_available():
        logger.debug("ffprobe not found; duration will be taken from the ASR response.")
        return None

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(media_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return None
        info = json.loads(result.stdout or "{}")
        raw = info.get("format", {}).get("duration")
        return round(float(raw), 3) if raw is not None else None
    except (subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        logger.debug(f"ffprobe duration probe failed for {media_path.name}: {exc}")
        return None
