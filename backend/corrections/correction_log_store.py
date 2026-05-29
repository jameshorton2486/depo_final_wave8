"""Append-only JSONL sidecar for per-job correction-log entries.

Each correction run -- the deterministic engine auto-run (from the correction
trigger) or a manual Apply Rule run -- appends one batch of entries that share
a single ISO run timestamp. The Stage 3 correction-log viewer reads the most
recent run.

This is an event stream, so JSONL fits: append-only, one JSON object per line,
survives outside SQLite, no schema migration. Promote to a `transcript_corrections`
table later only if query patterns demand it. It records WHAT the engine changed;
it never touches RAW or the working transcript text.

Row shape: {timestamp, rule_id, before, after, reason, stage, source}
  source in {"auto", "manual_regex"}.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from backend.config import settings

VALID_SOURCES = ("auto", "manual_regex")


def _log_path(job_id: str) -> Path:
    return Path(settings.data_root) / "transcripts" / job_id / "correction_log.jsonl"


def append_run(job_id: str, entries: list[dict], *, source: str) -> str | None:
    """Append one run's correction entries; return the run timestamp.

    `entries` carry at least {rule_id, before, after, reason, stage}. A run
    with no entries writes nothing (the engine-status badge still reflects the
    run via its provenance event). Never raises -- a logging-sidecar failure
    must not break a correction run.
    """
    if source not in VALID_SOURCES:
        raise ValueError(f"Invalid correction-log source: {source!r}")
    if not entries:
        return None
    run_ts = datetime.now(timezone.utc).isoformat()
    try:
        path = _log_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for e in entries:
                fh.write(json.dumps({
                    "timestamp": run_ts,
                    "rule_id": e.get("rule_id", "") or "",
                    "before": e.get("before", "") or "",
                    "after": e.get("after", "") or "",
                    "reason": e.get("reason", "") or "",
                    "stage": e.get("stage", "") or "",
                    "source": source,
                }, ensure_ascii=False) + "\n")
        return run_ts
    except OSError as exc:
        logger.warning(f"Correction-log append failed for {job_id}: {exc}")
        return None


def read_latest_run(job_id: str) -> list[dict]:
    """Return the entries from the most recent run (by max timestamp), or []."""
    path = _log_path(job_id)
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError as exc:
        logger.warning(f"Correction-log read failed for {job_id}: {exc}")
        return []
    if not rows:
        return []
    latest = max(r.get("timestamp", "") for r in rows)
    return [r for r in rows if r.get("timestamp", "") == latest]
