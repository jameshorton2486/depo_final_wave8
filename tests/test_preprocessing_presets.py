"""Tests for backend.preprocessing.presets (Stage 2 preset library).

Verifies the preset params are stable, verbatim-first is never violated,
and classify_audio is deterministic and total.
"""
from __future__ import annotations

import itertools

import pytest

from backend.preprocessing import presets
from backend.preprocessing.probe import ProbedAudioProfile

ALL_NAMES = {"studio", "courtroom", "zoom_mixed", "phone"}


def test_all_four_presets_present():
    assert set(presets.PRESETS) == ALL_NAMES


def test_preset_params_are_stable():
    assert presets.PRESETS["studio"].deepgram_params == {"utt_split": "1.4"}
    assert presets.PRESETS["courtroom"].deepgram_params == {"utt_split": "1.0"}
    assert presets.PRESETS["zoom_mixed"].deepgram_params == {
        "utt_split": "0.8", "multichannel": "false"}
    assert presets.PRESETS["phone"].deepgram_params == {"utt_split": "0.6"}


def test_no_preset_violates_verbatim_first():
    # CLAUDE.md SS5A: filler_words must never be turned off, and model is
    # owned by the base params -- no preset may override either.
    for name, p in presets.PRESETS.items():
        assert p.deepgram_params.get("filler_words") != "false", name
        assert "filler_words" not in p.deepgram_params, name
        assert "model" not in p.deepgram_params, name


def test_every_preset_has_a_rationale():
    for name, p in presets.PRESETS.items():
        assert p.rationale.strip(), name


def test_classify_none_returns_courtroom_default():
    assert presets.classify_audio(None).name == "courtroom"
    assert presets.DEFAULT_PRESET.name == "courtroom"


# Table-driven: one representative profile per class -> that preset.
@pytest.mark.parametrize("profile, expected", [
    (ProbedAudioProfile(sample_rate_hz=8000), "phone"),
    (ProbedAudioProfile(sample_rate_hz=16000, channel_count=1), "phone"),
    (ProbedAudioProfile(sample_rate_hz=44100, channel_count=2,
                        channels_distinct=False), "zoom_mixed"),
    (ProbedAudioProfile(sample_rate_hz=48000, channel_count=1,
                        voice_activity_ratio=0.92, rms_dbfs=-12.0), "studio"),
    (ProbedAudioProfile(sample_rate_hz=44100, channel_count=1,
                        rms_dbfs=-40.0), "phone"),  # quiet fallback
    (ProbedAudioProfile(sample_rate_hz=44100, channel_count=1,
                        voice_activity_ratio=0.5, rms_dbfs=-22.0), "courtroom"),
    (ProbedAudioProfile(), "courtroom"),  # all-None profile -> default
])
def test_classify_table(profile, expected):
    assert presets.classify_audio(profile).name == expected


def test_classify_is_deterministic():
    p = ProbedAudioProfile(sample_rate_hz=44100, channel_count=2,
                           channels_distinct=False, rms_dbfs=-24.0,
                           voice_activity_ratio=0.5)
    assert presets.classify_audio(p).name == presets.classify_audio(p).name == "zoom_mixed"


def test_classify_is_total_over_a_grid():
    # Every plausible profile must map to exactly one known preset and
    # never raise.
    rates = [None, 8000, 16000, 22050, 44100, 48000]
    chans = [None, 1, 2]
    distinct = [None, True, False]
    rms = [None, -45.0, -33.0, -24.0, -16.0, -5.0]
    var = [None, 0.1, 0.5, 0.9]
    for sr, ch, di, rm, va in itertools.product(rates, chans, distinct, rms, var):
        prof = ProbedAudioProfile(
            sample_rate_hz=sr, channel_count=ch, channels_distinct=di,
            rms_dbfs=rm, voice_activity_ratio=va)
        preset = presets.classify_audio(prof)
        assert preset.name in ALL_NAMES
