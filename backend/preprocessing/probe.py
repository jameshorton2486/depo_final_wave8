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
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


def ffprobe_available() -> bool:
    """True when the ffprobe binary can be found on PATH."""
    return shutil.which("ffprobe") is not None


def ffmpeg_available() -> bool:
    """True when the ffmpeg binary can be found on PATH."""
    return shutil.which("ffmpeg") is not None


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


# ---------------------------------------------------------------------------
# Audio profiling (Stage 2 preset library)
# ---------------------------------------------------------------------------
# A measured acoustic profile of one media file, used by
# backend/preprocessing/presets.classify_audio to pick Deepgram batch
# parameters. Every field is Optional so a partial probe (e.g. ffmpeg
# present but one analysis pass failing) never crashes consumers; callers
# treat a fully-None / None profile as "unknown -> safe default preset".
#
# Tunables (documented so future audits can adjust):
#   - Silence detection: noise floor -30 dBFS, min silence 0.2 s. Gaps
#     shorter than that are treated as speech, not pauses.
#   - Analysis window: only the first ANALYSIS_WINDOW_SECONDS are decoded
#     for the content passes (silence/volume), so a multi-hour deposition
#     cannot hang ingestion. Duration / sample-rate / channels come from
#     ffprobe over the whole file (instant).
#   - Channel distinctness: the L-R difference signal is measured over the
#     first CHANNEL_WINDOW_SECONDS; if it is >= DOWNMIX_DIFF_DB quieter than
#     the programme, the two channels are treated as a mono downmix.

SILENCE_NOISE_DB = "-30dB"
SILENCE_MIN_DURATION_S = "0.2"
ANALYSIS_WINDOW_SECONDS = 180
CHANNEL_WINDOW_SECONDS = 10
DOWNMIX_DIFF_DB = -34.0  # ~2% RMS ratio expressed in dB
FFMPEG_TIMEOUT_SECONDS = 30


@dataclass
class ProbedAudioProfile:
    duration_seconds: float | None = None
    sample_rate_hz: int | None = None
    channel_count: int | None = None
    channels_distinct: bool | None = None
    peak_dbfs: float | None = None
    rms_dbfs: float | None = None
    voice_activity_ratio: float | None = None
    mean_silence_gap_ms: float | None = None
    p75_silence_gap_ms: float | None = None


def _ffprobe_audio_stream(media_path: Path) -> dict:
    """Return the first audio stream's format/stream dict, or {} on failure."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", "-select_streams", "a:0",
        str(media_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=FFMPEG_TIMEOUT_SECONDS)
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout or "{}")
    except (subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        logger.debug(f"ffprobe stream probe failed for {media_path.name}: {exc}")
        return {}


def _run_ffmpeg_filter(media_path: Path, af: str, window_s: int,
                       start_s: float = 0.0) -> str:
    """Run ffmpeg with an audio filter over a bounded window, return stderr.

    ffmpeg's detector filters (silencedetect, volumedetect) emit their
    findings to stderr. Output is discarded via the null muxer. `start_s`
    seeks past unrepresentative lead-in (e.g. pre-roll silence / mic
    checks) before measuring. Returns "" on any failure so the caller
    degrades to None fields.
    """
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if start_s > 0:
        cmd += ["-ss", str(start_s)]
    cmd += [
        "-t", str(window_s), "-i", str(media_path),
        "-af", af, "-f", "null", "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=FFMPEG_TIMEOUT_SECONDS)
        return result.stderr or ""
    except subprocess.SubprocessError as exc:
        logger.debug(f"ffmpeg filter pass failed for {media_path.name}: {exc}")
        return ""


_SILENCE_DUR_RE = re.compile(r"silence_duration:\s*([0-9.]+)")
_MEAN_VOL_RE = re.compile(r"mean_volume:\s*(-?[0-9.]+)\s*dB")
_MAX_VOL_RE = re.compile(r"max_volume:\s*(-?[0-9.]+)\s*dB")


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = max(0, min(len(sorted_values) - 1,
                     math.ceil(pct * len(sorted_values)) - 1))
    return sorted_values[idx]


def probe_audio_profile(media_path: str | Path) -> ProbedAudioProfile | None:
    """Measure an acoustic profile for preset classification.

    Returns None when ffmpeg is unavailable or the file is missing, so
    ingestion proceeds with base Deepgram params. Never raises; any single
    failed analysis pass leaves its fields None rather than aborting.
    """
    media_path = Path(media_path)
    if not media_path.exists():
        return None
    if not ffmpeg_available():
        logger.debug("ffmpeg not found; audio profiling skipped (base params will be used).")
        return None

    profile = ProbedAudioProfile()

    # --- whole-file structural facts (ffprobe, instant) ---
    info = _ffprobe_audio_stream(media_path)
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    astream = streams[0] if streams else {}
    raw_dur = fmt.get("duration") or astream.get("duration")
    if raw_dur is not None:
        try:
            profile.duration_seconds = round(float(raw_dur), 3)
        except (TypeError, ValueError):
            pass
    if astream.get("sample_rate") is not None:
        try:
            profile.sample_rate_hz = int(astream["sample_rate"])
        except (TypeError, ValueError):
            pass
    if astream.get("channels") is not None:
        try:
            profile.channel_count = int(astream["channels"])
        except (TypeError, ValueError):
            pass

    # For long recordings, skip the lead-in (depositions routinely open with
    # silence + mic checks) and measure a representative interior window, so
    # the gap / voice-activity stats reflect the testimony, not the pre-roll.
    offset_s = 0.0
    if profile.duration_seconds and profile.duration_seconds > 2 * ANALYSIS_WINDOW_SECONDS:
        offset_s = round(profile.duration_seconds * 0.25, 1)

    analyzed_s = ANALYSIS_WINDOW_SECONDS
    if profile.duration_seconds:
        analyzed_s = min(ANALYSIS_WINDOW_SECONDS,
                         max(0.0, profile.duration_seconds - offset_s))

    # --- content pass: silence intervals + loudness (one ffmpeg run) ---
    af = (f"silencedetect=noise={SILENCE_NOISE_DB}:d={SILENCE_MIN_DURATION_S},"
          f"volumedetect")
    stderr = _run_ffmpeg_filter(media_path, af, ANALYSIS_WINDOW_SECONDS, offset_s)
    if stderr:
        mean_m = _MEAN_VOL_RE.search(stderr)
        max_m = _MAX_VOL_RE.search(stderr)
        if mean_m:
            profile.rms_dbfs = float(mean_m.group(1))
        if max_m:
            profile.peak_dbfs = float(max_m.group(1))

        gaps_s = [float(x) for x in _SILENCE_DUR_RE.findall(stderr)]
        if gaps_s:
            gaps_ms = sorted(g * 1000.0 for g in gaps_s)
            profile.mean_silence_gap_ms = round(sum(gaps_ms) / len(gaps_ms), 1)
            p75 = _percentile(gaps_ms, 0.75)
            profile.p75_silence_gap_ms = round(p75, 1) if p75 is not None else None
        if analyzed_s and analyzed_s > 0:
            total_silence_s = sum(gaps_s)
            var = 1.0 - (total_silence_s / analyzed_s)
            profile.voice_activity_ratio = round(min(1.0, max(0.0, var)), 3)

    # --- channel distinctness (only meaningful for stereo) ---
    if profile.channel_count == 2 and profile.rms_dbfs is not None:
        diff_stderr = _run_ffmpeg_filter(
            media_path, "pan=mono|c0=0.5*c0-0.5*c1,volumedetect",
            CHANNEL_WINDOW_SECONDS, offset_s)
        diff_m = _MEAN_VOL_RE.search(diff_stderr)
        if diff_m:
            diff_mean = float(diff_m.group(1))
            # If the L-R difference is much quieter than the programme, the
            # channels carry the same content -> a downmix, not distinct.
            profile.channels_distinct = (diff_mean - profile.rms_dbfs) > DOWNMIX_DIFF_DB
    elif profile.channel_count == 1:
        profile.channels_distinct = None  # not applicable to mono

    return profile
