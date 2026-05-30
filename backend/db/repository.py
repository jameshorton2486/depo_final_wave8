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
_MANAGED_APPEARANCE_ROLE_LABEL = "Parsed NOD appearance"


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


# ====================================================================
# TARGETED APPEARANCES PERSISTENCE
# ====================================================================

def _split_caption_sides(caption_full: str | None) -> dict[str, str]:
    caption = (caption_full or "").strip()
    if not caption:
        return {}
    for needle in (" vs. ", " VS. ", " v. ", " V. ", " vs ", " v "):
        if needle in caption:
            plaintiff, defendant = caption.split(needle, 1)
            out = {}
            if plaintiff.strip():
                out["plaintiff"] = plaintiff.strip()
            if defendant.strip():
                out["defendant"] = defendant.strip()
            return out
    return {}


def _normalize_appearance_side(raw: str | None) -> str | None:
    side = str(raw or "").strip().lower()
    return side if side in {"plaintiff", "defendant"} else None


def _speaker_label_from_name(full_name: str) -> str:
    parts = [part.strip(".,") for part in (full_name or "").split() if part.strip(".,")]
    if not parts:
        return ""
    honorific_map = {
        "mr": "MR.",
        "mrs": "MRS.",
        "ms": "MS.",
        "miss": "MISS",
        "dr": "DR.",
    }
    first = parts[0].lower()
    surname = parts[-1].upper()
    honorific = honorific_map.get(first)
    return f"{honorific} {surname}" if honorific else surname


def _ensure_case_party(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    role: str,
    preferred_name: str,
) -> str:
    row = conn.execute(
        "SELECT party_id FROM parties WHERE case_id = ? AND role = ? "
        "ORDER BY sort_order, rowid LIMIT 1",
        (case_id, role),
    ).fetchone()
    if row:
        return row["party_id"]

    party_id = str(uuid.uuid4())
    entity_type = "corporation" if any(
        token in preferred_name.upper()
        for token in (" INC", " LLC", " LLP", " PLLC", " CORP", " COMPANY", " CO.", " LP")
    ) else "other"
    sort_order = 0 if role == "plaintiff" else 1
    conn.execute(
        "INSERT INTO parties (party_id, case_id, role, name, entity_type, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (party_id, case_id, role, preferred_name, entity_type, sort_order),
    )
    return party_id


def _ensure_attorney(
    conn: sqlite3.Connection,
    *,
    full_name: str,
    bar_number: str | None,
) -> str:
    normalized_bar = (bar_number or "").strip() or None
    normalized_name = full_name.strip()

    row = None
    if normalized_bar:
        row = conn.execute(
            "SELECT attorney_id, bar_number, bar_state FROM attorneys "
            "WHERE bar_number = ? ORDER BY rowid LIMIT 1",
            (normalized_bar,),
        ).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT attorney_id, bar_number, bar_state FROM attorneys "
            "WHERE lower(full_name) = lower(?) ORDER BY rowid LIMIT 1",
            (normalized_name,),
        ).fetchone()
    if row:
        if normalized_bar and (not row["bar_number"] or not row["bar_state"]):
            conn.execute(
                "UPDATE attorneys SET bar_number = COALESCE(bar_number, ?), "
                "bar_state = COALESCE(bar_state, 'TX') WHERE attorney_id = ?",
                (normalized_bar, row["attorney_id"]),
            )
        return row["attorney_id"]

    attorney_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO attorneys (attorney_id, full_name, bar_state, bar_number) "
        "VALUES (?, ?, ?, ?)",
        (attorney_id, normalized_name, "TX" if normalized_bar else None, normalized_bar),
    )
    return attorney_id


def sync_case_attorney_appearances(
    case_id: str,
    *,
    caption_full: str | None,
    appearances: list[dict] | None,
) -> dict[str, int]:
    """Persist parser-derived appearances into parties/attorneys/case_attorneys.

    This is deliberately narrow: it wires the existing normalized read path that
    packaging already uses, without expanding the broader 16->50 field rollout.
    Only parser-managed case_attorneys rows are replaced; unrelated/manual rows
    are preserved.
    """
    side_names = _split_caption_sides(caption_full)
    normalized: list[dict] = []
    for appearance in appearances or []:
        if not isinstance(appearance, dict):
            continue
        side = _normalize_appearance_side(appearance.get("side"))
        name = str(appearance.get("name") or "").strip()
        if not side or not name:
            continue
        normalized.append({
            "side": side,
            "name": name,
            "firm": str(appearance.get("firm") or "").strip() or None,
            "bar_number": str(appearance.get("bar_number") or "").strip() or None,
        })

    if not normalized:
        return {"parties_written": 0, "attorneys_written": 0, "case_attorneys_written": 0}

    parties_written = 0
    attorneys_written = 0
    case_attorneys_written = 0

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM case_attorneys WHERE case_id = ? AND role_label = ?",
            (case_id, _MANAGED_APPEARANCE_ROLE_LABEL),
        )

        for item in normalized:
            preferred_name = side_names.get(item["side"]) or item["side"].title()
            before_party = conn.total_changes
            party_id = _ensure_case_party(
                conn,
                case_id=case_id,
                role=item["side"],
                preferred_name=preferred_name,
            )
            if conn.total_changes > before_party:
                parties_written += 1

            before_attorney = conn.total_changes
            attorney_id = _ensure_attorney(
                conn,
                full_name=item["name"],
                bar_number=item["bar_number"],
            )
            if conn.total_changes > before_attorney:
                attorneys_written += 1

            existing = conn.execute(
                "SELECT case_attorney_id FROM case_attorneys "
                "WHERE case_id = ? AND attorney_id = ? AND represents_party_id = ? "
                "ORDER BY rowid LIMIT 1",
                (case_id, attorney_id, party_id),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE case_attorneys SET "
                    "firm_name = COALESCE(firm_name, ?), "
                    "speaker_label = COALESCE(speaker_label, ?) "
                    "WHERE case_attorney_id = ?",
                    (item["firm"], _speaker_label_from_name(item["name"]), existing["case_attorney_id"]),
                )
                continue

            conn.execute(
                "INSERT INTO case_attorneys "
                "(case_attorney_id, case_id, attorney_id, represents_party_id, "
                "firm_name, role_label, speaker_label, is_noticing_party) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    case_id,
                    attorney_id,
                    party_id,
                    item["firm"],
                    _MANAGED_APPEARANCE_ROLE_LABEL,
                    _speaker_label_from_name(item["name"]),
                    1 if item["side"] == "plaintiff" else 0,
                ),
            )
            case_attorneys_written += 1

    return {
        "parties_written": parties_written,
        "attorneys_written": attorneys_written,
        "case_attorneys_written": case_attorneys_written,
    }
