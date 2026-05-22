"""Repository layer for the `deposition_metadata` table (schema_v9).

Stores job-level certificate fields: examination disposition, officer
charges, time per party, volume, and other reporter-recorded facts.
"""
from __future__ import annotations

from backend.db.repository import get_connection

_COLUMNS = (
    "job_id",
    "volume",
    "examination_disposition",
    "officer_charges_amount",
    "charges_party",
    "certificate_service_date",
    "time_per_party_json",
    "also_present_json",
    "created_at",
    "updated_at",
)

_UPDATABLE = {
    "volume",
    "examination_disposition",
    "officer_charges_amount",
    "charges_party",
    "certificate_service_date",
    "time_per_party_json",
    "also_present_json",
}


def _row_to_dict(row) -> dict:
    return {col: row[col] for col in _COLUMNS}


def get_depo_meta(job_id: str) -> dict | None:
    """Return the deposition_metadata row for a job, or None if absent."""
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM deposition_metadata "
            "WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def upsert_depo_meta(job_id: str, payload: dict) -> dict:
    """Create or update the deposition_metadata row for job_id.

    Only columns in `_UPDATABLE` are written; unknown keys are ignored.
    Returns the full row after the upsert.
    """
    filtered = {k: v for k, v in payload.items() if k in _UPDATABLE}

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM deposition_metadata WHERE job_id = ?", (job_id,)
        ).fetchone()

        if existing is None:
            cols = ["job_id"] + list(filtered.keys())
            vals = [job_id] + list(filtered.values())
            placeholders = ", ".join(["?"] * len(cols))
            conn.execute(
                f"INSERT INTO deposition_metadata ({', '.join(cols)}) "
                f"VALUES ({placeholders})",
                vals,
            )
        else:
            if filtered:
                set_clause = ", ".join(f"{k} = ?" for k in filtered)
                conn.execute(
                    f"UPDATE deposition_metadata "
                    f"SET {set_clause}, updated_at = datetime('now') "
                    f"WHERE job_id = ?",
                    [*filtered.values(), job_id],
                )
            else:
                conn.execute(
                    "UPDATE deposition_metadata "
                    "SET updated_at = datetime('now') WHERE job_id = ?",
                    (job_id,),
                )

        row = conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM deposition_metadata "
            "WHERE job_id = ?",
            (job_id,),
        ).fetchone()

    return _row_to_dict(row)
