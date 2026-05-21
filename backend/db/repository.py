"""SQL access layer for the `cases` table.

Keeping SQL out of the router so:
- Routes stay readable.
- Tests can exercise the repository in isolation if needed.
- A future Postgres / SQLAlchemy migration touches only this file.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from backend.config import settings


_CASE_COLUMNS = (
    "case_id",
    "case_number_value",
    "jurisdiction_type",
    "case_number_label",
    "caption_full",
    "court_district",
    "court_division",
    "judicial_district",
    "county",
    "state",
    "intake_timestamp",
    "created_at",
    "updated_at",
)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a sqlite connection with sensible defaults and ensure it closes."""
    settings.sqlite_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {col: row[col] for col in _CASE_COLUMNS}


def new_case_id() -> str:
    return str(uuid.uuid4())


def create_case(payload: dict) -> dict:
    """Insert one case row. `payload` must contain at least case_number_value.

    Returns the full row as a dict (matching CaseRead).
    """
    case_id = new_case_id()
    columns = [
        "case_id",
        "case_number_value",
        "jurisdiction_type",
        "case_number_label",
        "caption_full",
        "court_district",
        "court_division",
        "judicial_district",
        "county",
        "state",
    ]
    values = [
        case_id,
        payload["case_number_value"],
        payload.get("jurisdiction_type", "texas_state"),
        payload.get("case_number_label", "cause_no"),
        payload.get("caption_full"),
        payload.get("court_district"),
        payload.get("court_division"),
        payload.get("judicial_district"),
        payload.get("county"),
        payload.get("state", "Texas"),
    ]
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO cases ({', '.join(columns)}) VALUES ({placeholders})"

    with get_connection() as conn:
        conn.execute(sql, values)
        row = conn.execute(
            f"SELECT {', '.join(_CASE_COLUMNS)} FROM cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()

    return _row_to_dict(row)


def get_case(case_id: str) -> Optional[dict]:
    """Fetch one case by id. Returns None if missing."""
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {', '.join(_CASE_COLUMNS)} FROM cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_cases(limit: int = 50) -> list[dict]:
    """Return cases newest-first. Used by the frontend to find a 'last edited' case."""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_CASE_COLUMNS)} FROM cases "
            "ORDER BY updated_at DESC, created_at DESC, rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_case(case_id: str, patch: dict) -> Optional[dict]:
    """Update only the columns present in `patch`. Returns the new row, or None if not found.

    Always bumps updated_at to now. Empty patch is a no-op except for the timestamp bump.
    """
    allowed = {
        "case_number_value",
        "jurisdiction_type",
        "case_number_label",
        "caption_full",
        "court_district",
        "court_division",
        "judicial_district",
        "county",
        "state",
    }
    filtered = {k: v for k, v in patch.items() if k in allowed}

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if existing is None:
            return None

        if filtered:
            set_clause = ", ".join(f"{k} = ?" for k in filtered)
            sql = (
                f"UPDATE cases SET {set_clause}, updated_at = datetime('now') "
                "WHERE case_id = ?"
            )
            conn.execute(sql, [*filtered.values(), case_id])
        else:
            conn.execute(
                "UPDATE cases SET updated_at = datetime('now') WHERE case_id = ?",
                (case_id,),
            )

        row = conn.execute(
            f"SELECT {', '.join(_CASE_COLUMNS)} FROM cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()

    return _row_to_dict(row)


def delete_case(case_id: str) -> bool:
    """Delete one case. Returns True if a row was removed."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))
    return cur.rowcount > 0


# ====================================================================
# SESSIONS
# ====================================================================

_SESSION_COLUMNS = (
    "session_id",
    "case_id",
    "scheduled_at",
    "scheduled_end_at",
    "timezone",
    "witness_name",
    "witness_type",
    "location_type",
    "location_address",
    "service_type",
    "csr_required",
    "reporter_id",
    "reporting_firm_id",
    "ordered_by",
    "outcome",
    "notes",
    "custodial_attorney_name",
    "requesting_party_name",
    "created_at",
    "updated_at",
)


def _session_row_to_dict(row: sqlite3.Row) -> dict:
    return {col: row[col] for col in _SESSION_COLUMNS}


def new_session_id() -> str:
    return str(uuid.uuid4())


def create_session(payload: dict) -> dict:
    """Insert one session row. Requires case_id, scheduled_at, witness_name."""
    session_id = new_session_id()
    columns = [
        "session_id",
        "case_id",
        "scheduled_at",
        "scheduled_end_at",
        "timezone",
        "witness_name",
        "witness_type",
        "location_type",
        "location_address",
        "service_type",
        "csr_required",
        "reporter_id",
        "ordered_by",
        "notes",
        "custodial_attorney_name",
        "requesting_party_name",
    ]
    values = [
        session_id,
        payload["case_id"],
        payload["scheduled_at"],
        payload.get("scheduled_end_at"),
        payload.get("timezone", "America/Chicago"),
        payload["witness_name"],
        payload.get("witness_type", "individual"),
        payload.get("location_type", "in_person"),
        payload.get("location_address"),
        payload.get("service_type", "CR_only"),
        payload.get("csr_required", 1),
        payload.get("reporter_id"),
        payload.get("ordered_by"),
        payload.get("notes"),
        payload.get("custodial_attorney_name"),
        payload.get("requesting_party_name"),
    ]
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO sessions ({', '.join(columns)}) VALUES ({placeholders})"

    with get_connection() as conn:
        conn.execute(sql, values)
        row = conn.execute(
            f"SELECT {', '.join(_SESSION_COLUMNS)} FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return _session_row_to_dict(row)


def get_session(session_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {', '.join(_SESSION_COLUMNS)} FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return _session_row_to_dict(row) if row else None


def list_sessions_for_case(case_id: str) -> list[dict]:
    """Return all sessions for a case, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_SESSION_COLUMNS)} FROM sessions WHERE case_id = ? "
            "ORDER BY updated_at DESC, created_at DESC, rowid DESC",
            (case_id,),
        ).fetchall()
    return [_session_row_to_dict(r) for r in rows]


def update_session(session_id: str, patch: dict) -> dict | None:
    allowed = {
        "scheduled_at",
        "scheduled_end_at",
        "timezone",
        "witness_name",
        "witness_type",
        "location_type",
        "location_address",
        "service_type",
        "csr_required",
        "reporter_id",
        "ordered_by",
        "outcome",
        "notes",
        "custodial_attorney_name",
        "requesting_party_name",
    }
    filtered = {k: v for k, v in patch.items() if k in allowed}

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if existing is None:
            return None

        if filtered:
            set_clause = ", ".join(f"{k} = ?" for k in filtered)
            conn.execute(
                f"UPDATE sessions SET {set_clause}, updated_at = datetime('now') "
                "WHERE session_id = ?",
                [*filtered.values(), session_id],
            )
        else:
            conn.execute(
                "UPDATE sessions SET updated_at = datetime('now') WHERE session_id = ?",
                (session_id,),
            )

        row = conn.execute(
            f"SELECT {', '.join(_SESSION_COLUMNS)} FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return _session_row_to_dict(row)


def delete_session(session_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    return cur.rowcount > 0


# ====================================================================
# REPORTERS
# ====================================================================

_REPORTER_COLUMNS = (
    "reporter_id",
    "full_name",
    "csr_number",
    "csr_state",
    "csr_expiration",
    "default_reporting_firm_id",
    "firm_registration_number",
    "email",
    "phone",
    "created_at",
)


def _reporter_row_to_dict(row: sqlite3.Row) -> dict:
    return {col: row[col] for col in _REPORTER_COLUMNS}


def new_reporter_id() -> str:
    return str(uuid.uuid4())


def create_reporter(payload: dict) -> dict:
    """Insert one reporter row. Requires full_name."""
    reporter_id = new_reporter_id()
    columns = [
        "reporter_id",
        "full_name",
        "csr_number",
        "csr_state",
        "csr_expiration",
        "firm_registration_number",
        "email",
        "phone",
    ]
    values = [
        reporter_id,
        payload["full_name"],
        payload.get("csr_number"),
        payload.get("csr_state", "TX"),
        payload.get("csr_expiration"),
        payload.get("firm_registration_number"),
        payload.get("email"),
        payload.get("phone"),
    ]
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO reporters ({', '.join(columns)}) VALUES ({placeholders})"

    with get_connection() as conn:
        conn.execute(sql, values)
        row = conn.execute(
            f"SELECT {', '.join(_REPORTER_COLUMNS)} FROM reporters WHERE reporter_id = ?",
            (reporter_id,),
        ).fetchone()
    return _reporter_row_to_dict(row)


def get_reporter(reporter_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {', '.join(_REPORTER_COLUMNS)} FROM reporters WHERE reporter_id = ?",
            (reporter_id,),
        ).fetchone()
    return _reporter_row_to_dict(row) if row else None


def list_reporters(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_REPORTER_COLUMNS)} FROM reporters "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_reporter_row_to_dict(r) for r in rows]


def update_reporter(reporter_id: str, patch: dict) -> dict | None:
    allowed = {
        "full_name",
        "csr_number",
        "csr_state",
        "csr_expiration",
        "default_reporting_firm_id",
        "firm_registration_number",
        "email",
        "phone",
    }
    filtered = {k: v for k, v in patch.items() if k in allowed}

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM reporters WHERE reporter_id = ?", (reporter_id,)
        ).fetchone()
        if existing is None:
            return None

        if filtered:
            set_clause = ", ".join(f"{k} = ?" for k in filtered)
            conn.execute(
                f"UPDATE reporters SET {set_clause} WHERE reporter_id = ?",
                [*filtered.values(), reporter_id],
            )

        row = conn.execute(
            f"SELECT {', '.join(_REPORTER_COLUMNS)} FROM reporters WHERE reporter_id = ?",
            (reporter_id,),
        ).fetchone()
    return _reporter_row_to_dict(row)


def delete_reporter(reporter_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM reporters WHERE reporter_id = ?", (reporter_id,))
    return cur.rowcount > 0
