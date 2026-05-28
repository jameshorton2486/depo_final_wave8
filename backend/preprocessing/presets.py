"""Audio-profile-driven Deepgram preset library.

Each preset is a deterministic, named bundle of Deepgram batch
parameters tuned for a class of audio. Selection is a pure function
of the measured ProbedAudioProfile. Presets are minimal deltas
against DEEPGRAM_PARAMS in deepgram.client -- they only override the
keys that materially vary by audio class.

Invariants (CLAUDE.md SS5, SS5A):
  - No preset sets ``filler_words`` or ``model``. Those live in the base
    DEEPGRAM_PARAMS; verbatim-first requires ``filler_words=true`` on
    every path, so presets never touch it.
  - classify_audio is deterministic and total: a given profile always
    maps to exactly one preset, and every possible profile (including
    None) maps to one.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.preprocessing.probe import ProbedAudioProfile


@dataclass(frozen=True)
class AudioPreset:
    name: str
    deepgram_params: dict[str, str] = field(default_factory=dict)
    rationale: str = ""


# Deltas only -- merged onto DEEPGRAM_PARAMS at request time, override
# winning. utt_split and multichannel are NOT in the base param set, so
# these add them; no preset overrides filler_words or model. Values are
# starting points and are intended to be tunable as real-audio evidence
# accumulates.
_STUDIO = AudioPreset(
    name="studio",
    deepgram_params={"utt_split": "1.4"},
    rationale="Clean, close-mic speech: wider utterance split tolerates natural pauses.",
)
_COURTROOM = AudioPreset(
    name="courtroom",
    deepgram_params={"utt_split": "1.0"},
    rationale="Room mic, moderate reverb/cross-talk: balanced split (safe default).",
)
_ZOOM_MIXED = AudioPreset(
    name="zoom_mixed",
    deepgram_params={"utt_split": "0.8", "multichannel": "false"},
    rationale="Remote/Zoom stereo downmix: tighter split, treat as one mixed channel.",
)
_PHONE = AudioPreset(
    name="phone",
    deepgram_params={"utt_split": "0.6"},
    rationale="Narrowband telephony: tight utterance split for clipped, low-bandwidth speech.",
)

PRESETS: dict[str, AudioPreset] = {
    p.name: p for p in (_STUDIO, _COURTROOM, _ZOOM_MIXED, _PHONE)
}

# The safe default when no profile is available (ffmpeg missing, probe
# failed). Courtroom is the most conservative, room-tolerant setting.
DEFAULT_PRESET = _COURTROOM


def classify_audio(profile: ProbedAudioProfile | None) -> AudioPreset:
    """Map a measured audio profile to exactly one preset (pure, total).

    Rules are ordered by signal reliability, refined from a live trace of
    a real (Zoom) deposition:
      1. ``phone`` -- narrowband sample rate (<=16 kHz) is the one
         unambiguous telephony marker.
      2. ``zoom_mixed`` -- a stereo pair whose channels are a downmix
         (channels_distinct is False) is the remote/Zoom signature. This
         is checked BEFORE the quiet-audio phone fallback because a quiet
         Zoom call is not a phone call -- RMS alone mis-classifies it.
      3. ``studio`` -- very high voice-activity AND loud level: clean,
         close-mic source.
      4. ``phone`` (fallback) -- extremely quiet level, retained from the
         brief but ordered after the structural zoom signal.
      5. ``courtroom`` -- everything else; the conservative default.

    A None profile (probe unavailable) returns the courtroom default.
    """
    if profile is None:
        return DEFAULT_PRESET

    if profile.sample_rate_hz is not None and profile.sample_rate_hz <= 16000:
        return _PHONE

    if profile.channel_count == 2 and profile.channels_distinct is False:
        return _ZOOM_MIXED

    if (profile.voice_activity_ratio is not None
            and profile.voice_activity_ratio > 0.85
            and profile.rms_dbfs is not None
            and profile.rms_dbfs > -18):
        return _STUDIO

    if profile.rms_dbfs is not None and profile.rms_dbfs < -32:
        return _PHONE

    return _COURTROOM
