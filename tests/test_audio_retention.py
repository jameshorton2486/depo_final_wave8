from __future__ import annotations

import json
import os
import time
from pathlib import Path

from backend.db.repository import get_connection
from backend.transcript import repository as trepo
from backend.transcript.audio_retention import prune_audio


def _make_audio_file(directory: Path, name: str, *, size: int = 4096) -> Path:
    path = directory / name
    path.write_bytes(b"a" * size)
    return path


def _age_file(path: Path, *, days_old: float) -> None:
    now = time.time()
    modified = now - (days_old * 86400)
    os.utime(path, (modified, modified))


def _register_audio_job(path: Path) -> str:
    job = trepo.create_job({"source_filename": path.name, "audio_path": str(path)})
    return job["job_id"]


def _insert_package(job_id: str, *, package_state: str) -> None:
    certified_at = "2026-05-27T12:00:00+00:00" if package_state == "CERTIFIED" else None
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transcript_packages
            (package_id, job_id, snapshot_id, state_hash, package_state,
             manifest_json, package_json, certified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"pkg-{job_id}-{package_state.lower()}",
                job_id,
                f"snap-{job_id}",
                "state-hash",
                package_state,
                json.dumps({"identity": {"package_id": f"pkg-{job_id}"}}),
                json.dumps({"identity": {"package_id": f"pkg-{job_id}"}}),
                certified_at,
            ),
        )


def test_old_file_is_pruned_live_run(tmp_path: Path, temp_db: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    old_file = _make_audio_file(audio_dir, "old.mp3")
    _age_file(old_file, days_old=10)
    _register_audio_job(old_file)

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=False)

    assert not old_file.exists()
    assert result["deleted"] == 1
    assert result["eligible"] == 1
    assert result["preserved_certified"] == 0
    assert result["preserved_unresolved"] == 0
    assert result["reclaimed_mb"] > 0


def test_fresh_file_is_kept_live_run(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    fresh_file = _make_audio_file(audio_dir, "fresh.mp3")

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=False)

    assert fresh_file.exists()
    assert result["deleted"] == 0
    assert result["eligible"] == 0


def test_dry_run_deletes_nothing(tmp_path: Path, temp_db: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    old_file = _make_audio_file(audio_dir, "old.mp3")
    _age_file(old_file, days_old=10)
    _register_audio_job(old_file)

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=True)

    assert old_file.exists()
    assert result["deleted"] == 0
    assert result["eligible"] == 1
    assert result["preserved_unresolved"] == 0
    assert result["reclaimed_mb"] == 0.0


def test_retention_window_is_honoured(tmp_path: Path, temp_db: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    aged_file = _make_audio_file(audio_dir, "aged.mp3")
    _age_file(aged_file, days_old=5)
    _register_audio_job(aged_file)

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


def test_boundary_exactly_at_window(tmp_path: Path, temp_db: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    eligible_file = _make_audio_file(audio_dir, "eligible.mp3")
    ineligible_file = _make_audio_file(audio_dir, "ineligible.mp3")
    _age_file(eligible_file, days_old=7.25)
    _age_file(ineligible_file, days_old=6.75)
    _register_audio_job(eligible_file)

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=True)

    assert eligible_file.exists()
    assert ineligible_file.exists()
    assert result["eligible"] == 1
    assert result["deleted"] == 0


def test_certified_audio_is_preserved(tmp_path: Path, temp_db: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    retained_file = _make_audio_file(audio_dir, "certified.mp3")
    _age_file(retained_file, days_old=10)
    job_id = _register_audio_job(retained_file)
    _insert_package(job_id, package_state="CERTIFIED")

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=False)

    assert retained_file.exists()
    assert result["deleted"] == 0
    assert result["eligible"] == 0
    assert result["preserved_certified"] == 1
    assert result["preserved_unresolved"] == 0


def test_missing_job_lookup_preserves_audio(tmp_path: Path, temp_db: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    orphaned_file = _make_audio_file(audio_dir, "orphaned.mp3")
    _age_file(orphaned_file, days_old=10)

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=False)

    assert orphaned_file.exists()
    assert result["deleted"] == 0
    assert result["eligible"] == 0
    assert result["preserved_unresolved"] == 1
    assert any("no transcript job owns this audio_path" in err for err in result["errors"])


def test_certification_lookup_failure_preserves_audio(
    tmp_path: Path,
    temp_db: Path,
    monkeypatch,
):
    from backend.packaging import package_repo

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    old_file = _make_audio_file(audio_dir, "lookup-failure.mp3")
    _age_file(old_file, days_old=10)
    _register_audio_job(old_file)

    def _boom(job_id: str) -> bool:
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(package_repo, "has_certified_package", _boom)

    result = prune_audio(audio_dir=audio_dir, retention_days=7, dry_run=False)

    assert old_file.exists()
    assert result["deleted"] == 0
    assert result["eligible"] == 0
    assert result["preserved_unresolved"] == 1
    assert any("certification lookup failed" in err for err in result["errors"])
