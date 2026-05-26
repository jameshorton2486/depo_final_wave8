"""Durable transcript provenance for Stage 3 auditability.

The Workspace can still mirror provenance in frontend memory for instant
feedback, but the authoritative audit trail lives here so reloads,
snapshots, certification, and export all retain the same lineage.
"""
from __future__ import annotations

import json
import uuid

from backend.db.repository import get_connection


def record_event(
    job_id: str,
    *,
    event_type: str,
    title: str,
    detail: str = "",
    actor_type: str = "system",
    source: str = "workspace",
    metadata: dict | None = None,
    related_snapshot_id: str | None = None,
    related_suggestion_id: str | None = None,
    related_package_id: str | None = None,
) -> dict:
    """Insert one immutable provenance event."""
    event_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transcript_provenance_events
            (event_id, job_id, event_type, title, detail, actor_type, source,
             metadata_json, related_snapshot_id, related_suggestion_id,
             related_package_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                job_id,
                (event_type or "event").strip(),
                (title or "Transcript Event").strip(),
                (detail or "").strip() or None,
                (actor_type or "system").strip(),
                (source or "workspace").strip(),
                json.dumps(metadata or {}) if metadata else None,
                related_snapshot_id,
                related_suggestion_id,
                related_package_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM transcript_provenance_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
    return _row_to_dict(row)


def list_events(job_id: str, limit: int = 200) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM transcript_provenance_events
            WHERE job_id = ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
            """,
            (job_id, limit),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row) -> dict:
    metadata = {}
    if row["metadata_json"]:
        try:
            metadata = json.loads(row["metadata_json"])
        except (TypeError, ValueError):
            metadata = {}
    return {
        "event_id": row["event_id"],
        "job_id": row["job_id"],
        "event_type": row["event_type"],
        "title": row["title"],
        "detail": row["detail"] or "",
        "actor_type": row["actor_type"] or "system",
        "source": row["source"] or "",
        "metadata": metadata,
        "related_snapshot_id": row["related_snapshot_id"] or "",
        "related_suggestion_id": row["related_suggestion_id"] or "",
        "related_package_id": row["related_package_id"] or "",
        "created_at": row["created_at"],
    }
