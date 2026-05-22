"""Snapshot persistence — Wave 18.5.

CRUD over the transcript_snapshots table (schema_v7), enforcing the
Append-Only Audit Principle: snapshots are inserted and read, never
updated or deleted. The ONLY mutation permitted is setting the `locked`
flag (certification locking), and a locked snapshot can never be
unlocked or altered thereafter.
"""
from __future__ import annotations

import json

from backend.db.repository import get_connection
from backend.transcript_state.model import ExportReference, Snapshot


def _row_to_snapshot(row) -> Snapshot:
    return Snapshot(
        snapshot_id=row["snapshot_id"],
        job_id=row["job_id"],
        category=row["category"],
        state_hash=row["state_hash"],
        state=json.loads(row["state_json"]) if row["state_json"] else {},
        ai_trace=(json.loads(row["ai_trace_json"])
                  if row["ai_trace_json"] else []),
        export_refs=(json.loads(row["export_refs_json"])
                     if row["export_refs_json"] else []),
        locked=bool(row["locked"]),
        note=row["note"] or "",
        created_by=row["created_by"] or "",
        created_at=row["created_at"],
    )


def save_snapshot(snapshot: Snapshot) -> Snapshot:
    """Insert a new snapshot. Append-only -- never overwrites."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO transcript_snapshots "
            "(snapshot_id, job_id, category, state_hash, state_json, "
            " ai_trace_json, export_refs_json, locked, note, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot.snapshot_id, snapshot.job_id, snapshot.category,
                snapshot.state_hash, json.dumps(snapshot.state),
                json.dumps(snapshot.ai_trace) if snapshot.ai_trace else None,
                json.dumps(snapshot.export_refs)
                if snapshot.export_refs else None,
                1 if snapshot.locked else 0,
                snapshot.note or None, snapshot.created_by or None,
            ),
        )
    return get_snapshot(snapshot.snapshot_id)


def get_snapshot(snapshot_id: str) -> Snapshot | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM transcript_snapshots WHERE snapshot_id = ?",
            (snapshot_id,)).fetchone()
    return _row_to_snapshot(row) if row else None


def list_snapshots(job_id: str) -> list[Snapshot]:
    """All snapshots for a job, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM transcript_snapshots WHERE job_id = ? "
            "ORDER BY created_at DESC, snapshot_id DESC",
            (job_id,)).fetchall()
    return [_row_to_snapshot(r) for r in rows]


def lock_snapshot(snapshot_id: str) -> bool:
    """Mark a snapshot as a Certification Snapshot (immutable).

    This is the only permitted mutation. A snapshot that is already
    locked stays locked -- locking is one-way.
    """
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE transcript_snapshots SET locked = 1 "
            "WHERE snapshot_id = ?", (snapshot_id,))
        return cur.rowcount > 0


def add_export_reference(snapshot_id: str, ref: ExportReference) -> bool:
    """Append an export reference to a snapshot.

    Appending an export reference is additive provenance, not a state
    mutation -- it records that an export was produced FROM this state.
    Permitted even on a locked Certification Snapshot.
    """
    snap = get_snapshot(snapshot_id)
    if snap is None:
        return False
    refs = list(snap.export_refs)
    refs.append(ref.to_dict())
    with get_connection() as conn:
        conn.execute(
            "UPDATE transcript_snapshots SET export_refs_json = ? "
            "WHERE snapshot_id = ?",
            (json.dumps(refs), snapshot_id))
    return True
