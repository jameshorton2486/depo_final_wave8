"""Tests for backend.preprocessing.probe audio profiling (Stage 2).

The unit tests use a tiny synthesized WAV (stdlib `wave`, no third-party
fixtures). The end-to-end probe is skipped when ffmpeg/ffprobe are not on
PATH, so the suite stays green on machines without them.
"""
from __future__ import annotations

import dataclasses
import math
import struct
import wave
from pathlib import Path

import pytest

from backend.preprocessing import probe

EXPECTED_FIELDS = [
    "duration_seconds", "sample_rate_hz", "channel_count", "channels_distinct",
    "peak_dbfs", "rms_dbfs", "voice_activity_ratio",
    "mean_silence_gap_ms", "p75_silence_gap_ms",
]


def _write_sine_wav(path: Path, *, seconds: float = 1.0,
                    rate: int = 16000, freq: float = 440.0) -> Path:
    n = int(seconds * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        amp = 0.6 * 32767
        for i in range(n):
            sample = int(amp * math.sin(2 * math.pi * freq * (i / rate)))
            frames += struct.pack("<h", sample)
        w.writeframes(bytes(frames))
    return path


def test_profile_dataclass_shape_is_stable():
    fields = [f.name for f in dataclasses.fields(probe.ProbedAudioProfile)]
    assert fields == EXPECTED_FIELDS


def test_profile_defaults_all_none():
    p = probe.ProbedAudioProfile()
    assert all(getattr(p, f) is None for f in EXPECTED_FIELDS)


def test_probe_returns_none_when_ffmpeg_unavailable(tmp_path, monkeypatch):
    f = tmp_path / "x.wav"
    f.write_bytes(b"not really audio")
    monkeypatch.setattr(probe, "ffmpeg_available", lambda: False)
    assert probe.probe_audio_profile(f) is None


def test_probe_returns_none_for_missing_file(tmp_path):
    assert probe.probe_audio_profile(tmp_path / "nope.wav") is None


def test_probe_never_raises_on_garbage(tmp_path):
    # ffmpeg may be present but the bytes are not decodable -> a profile
    # object with None fields (or None), never an exception.
    f = tmp_path / "garbage.mp3"
    f.write_bytes(b"fake-media-bytes" * 50)
    result = probe.probe_audio_profile(f)
    assert result is None or isinstance(result, probe.ProbedAudioProfile)


@pytest.mark.skipif(
    not (probe.ffmpeg_available() and probe.ffprobe_available()),
    reason="ffmpeg/ffprobe not on PATH",
)
def test_probe_real_synth_wav_end_to_end(tmp_path):
    wav = _write_sine_wav(tmp_path / "tone.wav", seconds=1.0, rate=16000)
    profile = probe.probe_audio_profile(wav)
    assert isinstance(profile, probe.ProbedAudioProfile)
    # Structural facts come from ffprobe and must be populated for a real WAV.
    assert profile.sample_rate_hz == 16000
    assert profile.channel_count == 1
    # A continuous tone has no silence gaps -> high voice-activity ratio.
    assert profile.voice_activity_ratio is not None
    assert profile.voice_activity_ratio > 0.5
    # Mono is not applicable to channel distinctness.
    assert profile.channels_distinct is None
