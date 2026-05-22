"""AI review queue persistence — Wave 15b.

CRUD over the ai_suggestions table (schema_v6). Approval and rejection
are recorded here; approval is the only path from a suggestion to the
transcript.
"""
from __future__ import annotations

import json

from backend.ai_review.suggestions import (
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    Suggestion,
)
from backend.db.repository import get_connection


def _row_to_suggestion(row) -> Suggestion:
    payload = {}
    if row["payload_json"]:
        try:
            payload = json.loads(row["payload_json"])
        except (ValueError, TypeError):
            payload = {}
    return Suggestion(
        suggestion_id=row["suggestion_id"],
        job_id=row["job_id"],
        kind=row["kind"],
        reason=row["reason"] or "",
        target_utterance_id=row["target_utterance_id"] or "",
        before_text=row["before_text"] or "",
        after_text=row["after_text"] or "",
        four_part_pass=bool(row["four_part_pass"]),
        status=row["status"],
        payload=payload,
    )


def save_suggestions(suggestions: list[Suggestion]) -> int:
    """Persist a batch of suggestions. Returns the count saved."""
    with get_connection() as conn:
        for s in suggestions:
            conn.execute(
                "INSERT OR REPLACE INTO ai_suggestions "
                "(suggestion_id, job_id, kind, reason, target_utterance_id, "
                " before_text, after_text, four_part_pass, status, "
                " payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    s.suggestion_id, s.job_id, s.kind, s.reason,
                    s.target_utterance_id, s.before_text, s.after_text,
                    1 if s.four_part_pass else 0, s.status,
                    json.dumps(s.payload) if s.payload else None,
                ),
            )
    return len(suggestions)


def list_suggestions(job_id: str, status: str | None = None) -> list[Suggestion]:
    """List a job's suggestions, optionally filtered by status."""
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM ai_suggestions WHERE job_id = ? AND status = ? "
                "ORDER BY created_at ASC", (job_id, status)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ai_suggestions WHERE job_id = ? "
                "ORDER BY created_at ASC", (job_id,)).fetchall()
    return [_row_to_suggestion(r) for r in rows]


def get_suggestion(suggestion_id: str) -> Suggestion | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ai_suggestions WHERE suggestion_id = ?",
            (suggestion_id,)).fetchone()
    return _row_to_suggestion(row) if row else None


def set_status(suggestion_id: str, status: str) -> bool:
    """Approve or reject one suggestion. Returns True if a row changed."""
    if status not in (STATUS_APPROVED, STATUS_REJECTED, STATUS_PENDING):
        raise ValueError(f"Invalid suggestion status: {status}")
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE ai_suggestions SET status = ?, "
            "reviewed_at = datetime('now') WHERE suggestion_id = ?",
            (status, suggestion_id))
        return cur.rowcount > 0
