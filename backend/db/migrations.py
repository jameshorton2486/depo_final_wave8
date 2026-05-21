"""Hand-rolled SQLite migrations for Depo-Pro.

Why hand-rolled instead of Alembic: this is a local-first single-user
desktop app. Hand-rolled migrations are easier to audit, ship with no
extra dependencies, and don't require a migration metadata table beyond
the schema_version table we own.

Migration files live next to this module as schema_v{N}.sql. Each
migration is idempotent - re-running apply() on an up-to-date database
is a no-op.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

from backend.config import settings

DB_PATH = settings.database_path
MIGRATIONS_DIR = Path(__file__).parent


def _connect() -> sqlite3.Connection:
    """Open a connection with foreign keys enabled."""
    settings.sqlite_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def current_version(conn: sqlite3.Connection) -> int:
    """Return the highest applied schema version, or 0 if none."""
    try:
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def _ensure_column(conn, table: str, column: str, ddl_type: str) -> None:
    """Idempotently add a column to an existing table if missing.

    Used for additive migrations between named schema_vN.sql files. Real
    Alembic-style migrations can come later if we ever need destructive
    or non-trivial changes.
    """
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if cols and column not in cols:
        logger.info(f"Adding missing column {table}.{column}")
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")
        conn.commit()


def apply() -> int:
    """Apply all pending migrations. Returns the final schema version."""
    conn = _connect()
    try:
        version_before = current_version(conn)
        logger.info(f"DB schema version before apply: {version_before}")

        for sql_file in sorted(MIGRATIONS_DIR.glob("schema_v*.sql")):
            sql = sql_file.read_text(encoding="utf-8")
            logger.info(f"Applying {sql_file.name}")
            conn.executescript(sql)
            conn.commit()

        # Additive columns (Wave 2 Step 2). Each is idempotent.
        _ensure_column(conn, "case_attorneys", "speaker_label", "TEXT")
        _ensure_column(conn, "sessions", "scheduled_end_at", "TEXT")
        _ensure_column(conn, "sessions", "custodial_attorney_name", "TEXT")
        _ensure_column(conn, "sessions", "requesting_party_name", "TEXT")
        _ensure_column(conn, "reporters", "firm_registration_number", "TEXT")

        version_after = current_version(conn)
        logger.info(f"DB schema version after apply: {version_after}")
        return version_after
    finally:
        conn.close()


def list_tables() -> list[str]:
    """Return all user tables (excluding sqlite_* internal tables)."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()
