from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from backend.config import settings


def _age_days(now_ts: float, modified_ts: float) -> float:
    return max(0.0, (now_ts - modified_ts) / 86400.0)


def _size_mb(size_bytes: int) -> float:
    return size_bytes / (1024 * 1024)


def prune_audio(
    *,
    audio_dir: Path | None = None,
    retention_days: int | None = None,
    dry_run: bool | None = None,
) -> dict:
    audio_dir = audio_dir or (settings.data_root / "audio")
    retention_days = settings.audio_retention_days if retention_days is None else retention_days
    dry_run = settings.audio_retention_dry_run if dry_run is None else dry_run

    summary = {
        "audio_dir": str(audio_dir),
        "retention_days": retention_days,
        "dry_run": dry_run,
        "scanned": 0,
        "eligible": 0,
        "deleted": 0,
        "reclaimed_mb": 0.0,
        "errors": [],
    }

    try:
        if not audio_dir.exists():
            logger.info(
                "audio retention sweep: scanned 0, eligible 0, deleted 0, reclaimed 0.0 MB "
                f"(dry_run={dry_run})"
            )
            return summary

        now_ts = time.time()
        cutoff_ts = now_ts - (retention_days * 86400)

        for path in audio_dir.iterdir():
            if not path.is_file():
                continue

            summary["scanned"] += 1

            try:
                stat = path.stat()
            except Exception as exc:  # noqa: BLE001
                message = f"Could not stat audio file {path.name}: {exc}"
                summary["errors"].append(message)
                logger.warning(message)
                continue

            if stat.st_mtime > cutoff_ts:
                continue

            summary["eligible"] += 1
            age_days = _age_days(now_ts, stat.st_mtime)
            size_mb = _size_mb(stat.st_size)

            if dry_run:
                logger.info(
                    f"[dry-run] would prune audio {path.name} ({age_days:.1f} days, {size_mb:.2f} MB)"
                )
                continue

            try:
                path.unlink()
                summary["deleted"] += 1
                summary["reclaimed_mb"] += size_mb
                logger.info(f"pruned audio {path.name} ({age_days:.1f} days, {size_mb:.2f} MB)")
            except Exception as exc:  # noqa: BLE001
                message = f"Failed to prune audio {path.name}: {exc}"
                summary["errors"].append(message)
                logger.warning(message)

        summary["reclaimed_mb"] = round(summary["reclaimed_mb"], 4)
        logger.info(
            "audio retention sweep: "
            f"scanned {summary['scanned']}, eligible {summary['eligible']}, "
            f"deleted {summary['deleted']}, reclaimed {summary['reclaimed_mb']} MB "
            f"(dry_run={dry_run})"
        )
        return summary
    except Exception as exc:  # noqa: BLE001
        message = f"Audio retention sweep failed unexpectedly: {exc}"
        summary["errors"].append(message)
        logger.warning(message)
        return summary
