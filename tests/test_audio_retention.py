from __future__ import annotations

import os
import time
from pathlib import Path

from backend.transcript.audio_retention import prune_audio


def _make_audio_file(directory: Path, name: str, *, size: int = 4096) -> Path:
    path = directory / name
    path.write_bytes(b"a" * size)
    return path


def _age_file(path: Path, *, days_old: float) -> None:
    now = time.time()
    modified = now - (days_old * 86400)
    os.utime(path, (modified, modified))


def test_old_file_is_pruned_live_run(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    old_file = _make_audio_file(audio_dir, "old.mp3")
    _age_file(old_file, days_old=10)

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=False)

    assert not old_file.exists()
    assert result["deleted"] == 1
    assert result["eligible"] == 1
    assert result["reclaimed_mb"] > 0


def test_fresh_file_is_kept_live_run(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    fresh_file = _make_audio_file(audio_dir, "fresh.mp3")

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=False)

    assert fresh_file.exists()
    assert result["deleted"] == 0
    assert result["eligible"] == 0


def test_dry_run_deletes_nothing(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    old_file = _make_audio_file(audio_dir, "old.mp3")
    _age_file(old_file, days_old=10)

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=True)

    assert old_file.exists()
    assert result["deleted"] == 0
    assert result["eligible"] == 1
    assert result["reclaimed_mb"] == 0.0


def test_retention_window_is_honoured(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    aged_file = _make_audio_file(audio_dir, "aged.mp3")
    _age_file(aged_file, days_old=5)

    kept = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=False)
    assert aged_file.exists()
    assert kept["eligible"] == 0

    eligible = prune_audio(audio_dir=audio_dir, retention_days=3, dry_run=True)
    assert aged_file.exists()
    assert eligible["eligible"] == 1


def test_missing_audio_dir_is_safe(tmp_path: Path):
    audio_dir = tmp_path / "missing-audio"

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=False)

    assert result["scanned"] == 0
    assert result["eligible"] == 0
    assert result["deleted"] == 0
    assert result["errors"] == []


def test_boundary_exactly_at_window(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    eligible_file = _make_audio_file(audio_dir, "eligible.mp3")
    ineligible_file = _make_audio_file(audio_dir, "ineligible.mp3")
    _age_file(eligible_file, days_old=7.25)
    _age_file(ineligible_file, days_old=6.75)

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=True)

    assert eligible_file.exists()
    assert ineligible_file.exists()
    assert result["eligible"] == 1
    assert result["deleted"] == 0
