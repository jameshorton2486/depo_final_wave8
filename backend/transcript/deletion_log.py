"""Append-only JSONL audit trail for transcript-job deletions.

A deletion record MUST outlive the deletion it describes. Deleting a
`transcript_jobs` row CASCADEs through every child table -- including
`transcript_provenance_events` -- so the audit trail cannot live in the
database; it would vanish with the job. This sidecar at
`data/transcript_deletions.jsonl` is append-only, lives outside the cascade,
and survives even a crash mid-delete (the record is written BEFORE the
destructive sequence runs). No schema migration.

One JSON object per line; never rewritten or truncated.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from backend.config import settings


def _log_path() -> Path:
    # Resolved lazily so test fixtures can swap settings.data_root.
    return Path(settings.data_root) / "transcript_deletions.jsonl"


def append_deletion_event(
    job_row: dict,
    *,
    actor: str = "operator",
    force: bool = False,
    reason: str | None = None,
    package_ids: list[str] | None = None,
    fsync: bool = True,
) -> dict:
    """Append one deletion record and return it.

    Written before the job's destructive sequence so the trail survives a
    crash mid-delete. `fsync` defaults on for durability.
    """
    job_row = job_row or {}
    event = {
        "event_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "job_id": job_row.get("job_id"),
        "case_id": job_row.get("case_id"),
        "session_id": job_row.get("session_id"),
        "source_filename": job_row.get("source_filename"),
        "actor": actor,
        "force": bool(force),
        "reason": reason,
        "package_ids": list(package_ids or []),
        "metrics": {
            "word_count": job_row.get("word_count"),
            "utterance_count": job_row.get("utterance_count"),
            "duration_seconds": job_row.get("duration_seconds"),
            "transcription_source": job_row.get("transcription_source"),
        },
    }
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        fh.flush()
        if fsync:
            os.fsync(fh.fileno())
    logger.info(
        f"Deletion logged for job {event['job_id']} "
        f"(force={event['force']}, packages={len(event['package_ids'])})."
    )
    return event


def list_deletion_events(limit: int = 100) -> list[dict]:
    """Return up to `limit` deletion records, newest-first ([] if none)."""
    path = _log_path()
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed line in transcript_deletions.jsonl")
            continue
    rows.reverse()  # file is append-order (oldest first) -> newest-first
    return rows[:limit]
