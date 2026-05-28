"""SQL access layer for the Layer 2/3 transcript tables.

Mirrors the structure of backend/db/repository.py (the Layer 1 access
layer): connections are short-lived, SQL is kept out of the routers, and
rows come back as plain dicts.

Tables (see backend/db/schema_v2.sql):
    transcript_jobs        -- one ingestion job per media file
    transcript_speakers    -- speaker map per job
    transcript_utterances  -- speaker-turn blocks
    transcript_words       -- the canonical word objects
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from backend.config import settings
from backend.transcript.integrity import RawTranscriptImmutableError

# ====================================================================
# Connection helper (same conventions as the Layer 1 repository)
# ====================================================================


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
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


def new_id() -> str:
    return str(uuid.uuid4())


# ====================================================================
# transcript_jobs
# ====================================================================

_JOB_COLUMNS = (
    "job_id",
    "case_id",
    "session_id",
    "source_filename",
    "source_size_bytes",
    "media_kind",
    "sequence_index",
    "status",
    "engine",
    "transcription_source",
    "error_message",
    "duration_seconds",
    "word_count",
    "utterance_count",
    "speaker_count",
    "avg_confidence",
    "audio_path",
    "raw_packet_path",
    "working_packet_path",
    "created_at",
    "updated_at",
    "completed_at",
)


def _job_row_to_dict(row: sqlite3.Row) -> dict:
    return {col: row[col] for col in _JOB_COLUMNS}


def create_job(payload: dict) -> dict:
    """Insert a queued transcript job. Requires source_filename.

    Optional: case_id, session_id, source_size_bytes, media_kind,
    sequence_index, engine, audio_path.
    """
    job_id = new_id()
    columns = [
        "job_id",
        "case_id",
        "session_id",
        "source_filename",
        "source_size_bytes",
        "media_kind",
        "sequence_index",
        "status",
        "engine",
        "audio_path",
    ]
    values = [
        job_id,
        payload.get("case_id"),
        payload.get("session_id"),
        payload["source_filename"],
        payload.get("source_size_bytes", 0),
        payload.get("media_kind", "prerecorded"),
        payload.get("sequence_index", 0),
        "queued",
        payload.get("engine", "deepgram-nova-3"),
        payload.get("audio_path"),
    ]
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO transcript_jobs ({', '.join(columns)}) VALUES ({placeholders})"

    with get_connection() as conn:
        conn.execute(sql, values)
        row = conn.execute(
            f"SELECT {', '.join(_JOB_COLUMNS)} FROM transcript_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    return _job_row_to_dict(row)


def get_job(job_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {', '.join(_JOB_COLUMNS)} FROM transcript_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    return _job_row_to_dict(row) if row else None


def find_jobs_by_audio_path(audio_path: str) -> list[dict]:
    """Return every job whose persisted audio_path exactly matches `audio_path`."""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_JOB_COLUMNS)} FROM transcript_jobs WHERE audio_path = ?",
            (audio_path,),
        ).fetchall()
    return [_job_row_to_dict(r) for r in rows]


def list_jobs(case_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    """List jobs newest-first, optionally filtered to one case."""
    with get_connection() as conn:
        if case_id:
            rows = conn.execute(
                f"SELECT {', '.join(_JOB_COLUMNS)} FROM transcript_jobs "
                "WHERE case_id = ? "
                "ORDER BY sequence_index ASC, created_at DESC, rowid DESC LIMIT ?",
                (case_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {', '.join(_JOB_COLUMNS)} FROM transcript_jobs "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_job_row_to_dict(r) for r in rows]


def update_job(job_id: str, patch: dict) -> Optional[dict]:
    """Update only the columns present in `patch`. Bumps updated_at."""
    allowed = {
        "case_id",
        "session_id",
        "status",
        "engine",
        "transcription_source",
        "error_message",
        "duration_seconds",
        "word_count",
        "utterance_count",
        "speaker_count",
        "avg_confidence",
        "audio_path",
        "raw_packet_path",
        "working_packet_path",
        "completed_at",
    }
    filtered = {k: v for k, v in patch.items() if k in allowed}

    with get_connection() as conn:
        existing_row = conn.execute(
            f"SELECT {', '.join(_JOB_COLUMNS)} FROM transcript_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        existing = _job_row_to_dict(existing_row) if existing_row else None
        if existing is None:
            return None

        if (
            "raw_packet_path" in filtered
            and existing.get("raw_packet_path")
            and filtered["raw_packet_path"] != existing.get("raw_packet_path")
        ):
            raise RawTranscriptImmutableError(
                f"Transcript job {job_id} already has an immutable raw packet path."
            )

        if filtered:
            set_clause = ", ".join(f"{k} = ?" for k in filtered)
            conn.execute(
                f"UPDATE transcript_jobs SET {set_clause}, updated_at = datetime('now') "
                "WHERE job_id = ?",
                [*filtered.values(), job_id],
            )
        else:
            conn.execute(
                "UPDATE transcript_jobs SET updated_at = datetime('now') WHERE job_id = ?",
                (job_id,),
            )

        row = conn.execute(
            f"SELECT {', '.join(_JOB_COLUMNS)} FROM transcript_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    return _job_row_to_dict(row)


def delete_job(job_id: str) -> bool:
    """Delete a job. Cascades to its speakers / utterances / words."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM transcript_jobs WHERE job_id = ?", (job_id,))
    return cur.rowcount > 0


# ====================================================================
# Content persistence (speakers + utterances + words, one transaction)
# ====================================================================

_UTTERANCE_COLUMNS = (
    "utterance_id",
    "job_id",
    "utterance_index",
    "speaker_index",
    "speaker_label",
    "start_time",
    "end_time",
    "text",
    "avg_confidence",
)

_WORD_COLUMNS = (
    "word_id",
    "job_id",
    "utterance_id",
    "word_index",
    "raw_text",
    "working_text",
    "speaker_index",
    "start_time",
    "end_time",
    "confidence",
    "is_filler",
    "reviewed",
)

_SPEAKER_COLUMNS = (
    "speaker_row_id",
    "job_id",
    "speaker_index",
    "speaker_label",
    "assigned_name",
    "speaker_role",
    "word_count",
)

_WORKING_UTTERANCE_COLUMNS = (
    "working_row_id",
    "job_id",
    "utterance_id",
    "working_text",
    "source",
    "updated_at",
)

_EXHIBIT_COLUMNS = (
    "exhibit_id",
    "job_id",
    "case_id",
    "session_id",
    "exhibit_number",
    "exhibit_title",
    "offering_attorney",
    "description",
    "anchor_utterance_id",
    "anchor_note",
    "sort_order",
    "created_at",
    "updated_at",
)


def save_transcript_content(
    job_id: str,
    speakers: list[dict],
    utterances: list[dict],
    words: list[dict],
) -> None:
    """Persist a job's full canonical content in one transaction.

    The raw transcript layer is immutable once captured. Attempting to
    persist canonical raw content a second time for the same job raises
    RawTranscriptImmutableError.
    """
    with get_connection() as conn:
        existing_raw = conn.execute(
            "SELECT COUNT(1) AS count FROM transcript_utterances WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if existing_raw and int(existing_raw["count"] or 0) > 0:
            raise RawTranscriptImmutableError(
                f"Transcript job {job_id} already has immutable raw utterances."
            )
        conn.execute("DELETE FROM transcript_words WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM transcript_utterances WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM transcript_speakers WHERE job_id = ?", (job_id,))

        if speakers:
            conn.executemany(
                f"INSERT INTO transcript_speakers ({', '.join(_SPEAKER_COLUMNS)}) "
                f"VALUES ({', '.join(['?'] * len(_SPEAKER_COLUMNS))})",
                [
                    (
                        s["speaker_row_id"],
                        job_id,
                        s["speaker_index"],
                        s["speaker_label"],
                        s.get("assigned_name"),
                        s.get("speaker_role"),
                        s.get("word_count", 0),
                    )
                    for s in speakers
                ],
            )

        if utterances:
            conn.executemany(
                f"INSERT INTO transcript_utterances ({', '.join(_UTTERANCE_COLUMNS)}) "
                f"VALUES ({', '.join(['?'] * len(_UTTERANCE_COLUMNS))})",
                [
                    (
                        u["utterance_id"],
                        job_id,
                        u["utterance_index"],
                        u.get("speaker_index"),
                        u["speaker_label"],
                        u["start_time"],
                        u["end_time"],
                        u["text"],
                        u.get("avg_confidence"),
                    )
                    for u in utterances
                ],
            )

        if words:
            conn.executemany(
                f"INSERT INTO transcript_words ({', '.join(_WORD_COLUMNS)}) "
                f"VALUES ({', '.join(['?'] * len(_WORD_COLUMNS))})",
                [
                    (
                        w["word_id"],
                        job_id,
                        w["utterance_id"],
                        w["word_index"],
                        w["raw_text"],
                        w.get("working_text"),
                        w.get("speaker_index"),
                        w["start_time"],
                        w["end_time"],
                        w["confidence"],
                        w.get("is_filler", 0),
                        w.get("reviewed", 0),
                    )
                    for w in words
                ],
            )


def get_utterances(job_id: str, layer: str = "raw") -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_UTTERANCE_COLUMNS)} FROM transcript_utterances "
            "WHERE job_id = ? ORDER BY utterance_index ASC",
            (job_id,),
        ).fetchall()
    utterances = [{col: r[col] for col in _UTTERANCE_COLUMNS} for r in rows]
    if layer == "raw":
        return utterances
    if layer != "working":
        raise ValueError(f"Unknown utterance layer '{layer}'")

    overrides = get_working_utterance_map(job_id)
    for utt in utterances:
        raw_text = utt.get("text") or ""
        override = overrides.get(utt["utterance_id"])
        utt["raw_text"] = raw_text
        utt["working_text"] = override.get("working_text") if override else None
        utt["is_working_override"] = bool(override)
        utt["working_source"] = override.get("source") if override else None
        utt["working_updated_at"] = override.get("updated_at") if override else None
        if override:
            utt["text"] = override.get("working_text") or ""
    return utterances


def get_words(job_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_WORD_COLUMNS)} FROM transcript_words "
            "WHERE job_id = ? ORDER BY word_index ASC",
            (job_id,),
        ).fetchall()
    return [{col: r[col] for col in _WORD_COLUMNS} for r in rows]


def get_speakers(job_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_SPEAKER_COLUMNS)} FROM transcript_speakers "
            "WHERE job_id = ? ORDER BY speaker_index ASC",
            (job_id,),
        ).fetchall()
    return [{col: r[col] for col in _SPEAKER_COLUMNS} for r in rows]


def get_working_utterance_overrides(job_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_WORKING_UTTERANCE_COLUMNS)} "
            "FROM transcript_working_utterances "
            "WHERE job_id = ? ORDER BY updated_at ASC, rowid ASC",
            (job_id,),
        ).fetchall()
    return [{col: r[col] for col in _WORKING_UTTERANCE_COLUMNS} for r in rows]


def get_working_utterance_map(job_id: str) -> dict[str, dict]:
    return {
        row["utterance_id"]: row
        for row in get_working_utterance_overrides(job_id)
    }


def save_working_utterance_overrides(
    job_id: str,
    overrides: list[dict],
    *,
    source: str = "stage3_workspace",
) -> dict:
    """Persist utterance-level working transcript overrides.

    Only utterances whose working text differs from RAW are stored. If a
    working text equals RAW again, its override row is removed so the raw
    layer continues to be the default source of truth.
    """
    raw_rows = get_utterances(job_id, layer="raw")
    raw_map = {u["utterance_id"]: u for u in raw_rows}

    saved = 0
    removed = 0
    with get_connection() as conn:
        for item in overrides or []:
            utterance_id = item.get("utterance_id")
            if utterance_id not in raw_map:
                raise ValueError(
                    f"Utterance {utterance_id} does not belong to job {job_id}"
                )
            raw_text = raw_map[utterance_id].get("text") or ""
            working_text = (item.get("working_text") or "").strip()
            if working_text == raw_text:
                cur = conn.execute(
                    "DELETE FROM transcript_working_utterances "
                    "WHERE utterance_id = ?",
                    (utterance_id,),
                )
                removed += cur.rowcount
                continue

            existing = conn.execute(
                "SELECT working_row_id FROM transcript_working_utterances "
                "WHERE utterance_id = ?",
                (utterance_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE transcript_working_utterances "
                    "SET working_text = ?, source = ?, updated_at = datetime('now') "
                    "WHERE utterance_id = ?",
                    (working_text, source, utterance_id),
                )
            else:
                conn.execute(
                    "INSERT INTO transcript_working_utterances "
                    "(working_row_id, job_id, utterance_id, working_text, source) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (new_id(), job_id, utterance_id, working_text, source),
                )
            saved += 1

    return {
        "job_id": job_id,
        "saved": saved,
        "removed": removed,
        "override_count": len(get_working_utterance_overrides(job_id)),
    }


def replace_working_utterance_overrides(
    job_id: str,
    working_utterances: list[dict],
    *,
    source: str = "snapshot_rollback",
) -> dict:
    """Replace a job's full working transcript state from snapshot data."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM transcript_working_utterances WHERE job_id = ?",
            (job_id,),
        )
    return save_working_utterance_overrides(job_id, working_utterances, source=source)


# ====================================================================
# transcript_participants  -- the canonical speaker-identity layer
# ====================================================================

_PARTICIPANT_COLUMNS = (
    "participant_id",
    "job_id",
    "name",
    "role",
    "speaker_indices",
    "is_prefill",
    "sort_order",
    "created_at",
    "updated_at",
)


def _participant_row_to_dict(row: sqlite3.Row) -> dict:
    """Row -> dict, with speaker_indices decoded from its JSON text column."""
    import json

    out = {col: row[col] for col in _PARTICIPANT_COLUMNS}
    raw = out.get("speaker_indices")
    try:
        decoded = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (ValueError, TypeError):
        decoded = []
    out["speaker_indices"] = [int(v) for v in decoded if str(v).lstrip("-").isdigit()]
    return out


def get_participants(job_id: str) -> list[dict]:
    """Return the saved canonical participants for a job, ordered for display."""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_PARTICIPANT_COLUMNS)} FROM transcript_participants "
            "WHERE job_id = ? ORDER BY sort_order ASC, rowid ASC",
            (job_id,),
        ).fetchall()
    return [_participant_row_to_dict(r) for r in rows]


def save_participants(job_id: str, participants: list[dict]) -> None:
    """Replace the full participant list for a job in one transaction.

    Idempotent: existing rows for the job are cleared first, so saving the
    confirmed mapping (or re-saving an edited one) is a clean overwrite.
    `speaker_indices` is stored as a JSON-encoded array of ints.
    """
    import json

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM transcript_participants WHERE job_id = ?", (job_id,)
        )
        for sort_order, p in enumerate(participants or []):
            indices = [
                int(v)
                for v in (p.get("speaker_indices") or [])
                if str(v).lstrip("-").isdigit()
            ]
            conn.execute(
                "INSERT INTO transcript_participants "
                "(participant_id, job_id, name, role, speaker_indices, "
                " is_prefill, sort_order, name_source, honorific) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    p.get("participant_id") or new_id(),
                    job_id,
                    (p.get("name") or "").strip() or None,
                    p.get("role") or "other",
                    json.dumps(sorted(set(indices))),
                    1 if p.get("is_prefill") else 0,
                    p.get("sort_order", sort_order),
                    (p.get("name_source") or "").strip() or None,
                    (p.get("honorific") or "").strip().upper().rstrip(".") or None,
                ),
            )


# ====================================================================
# transcript_exhibits -- the authoritative Stage 4 exhibit layer
# ====================================================================


def _exhibit_row_to_dict(row: sqlite3.Row) -> dict:
    return {col: row[col] for col in _EXHIBIT_COLUMNS}


def list_exhibits(job_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_EXHIBIT_COLUMNS)} FROM transcript_exhibits "
            "WHERE job_id = ? "
            "ORDER BY sort_order ASC, created_at ASC, rowid ASC",
            (job_id,),
        ).fetchall()
    return [_exhibit_row_to_dict(r) for r in rows]


def get_exhibit(exhibit_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {', '.join(_EXHIBIT_COLUMNS)} FROM transcript_exhibits "
            "WHERE exhibit_id = ?",
            (exhibit_id,),
        ).fetchone()
    return _exhibit_row_to_dict(row) if row else None


def create_exhibit(job_id: str, payload: dict) -> dict:
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Transcript job {job_id} not found")
    anchor_utterance_id = (payload.get("anchor_utterance_id") or "").strip()
    if not anchor_utterance_id:
        raise ValueError("anchor_utterance_id is required")
    if not any(u["utterance_id"] == anchor_utterance_id for u in get_utterances(job_id, layer="raw")):
        raise ValueError(
            f"Utterance {anchor_utterance_id} does not belong to job {job_id}"
        )

    exhibit_number = str(payload.get("exhibit_number") or "").strip()
    if not exhibit_number:
        raise ValueError("exhibit_number is required")
    exhibit_id = new_id()
    current = list_exhibits(job_id)
    sort_order = payload.get("sort_order")
    if sort_order is None:
        sort_order = len(current)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transcript_exhibits
            (exhibit_id, job_id, case_id, session_id, exhibit_number,
             exhibit_title, offering_attorney, description,
             anchor_utterance_id, anchor_note, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exhibit_id,
                job_id,
                job.get("case_id"),
                job.get("session_id"),
                exhibit_number,
                (payload.get("exhibit_title") or "").strip(),
                (payload.get("offering_attorney") or "").strip(),
                (payload.get("description") or "").strip(),
                anchor_utterance_id,
                (payload.get("anchor_note") or "").strip(),
                int(sort_order),
            ),
        )
        row = conn.execute(
            f"SELECT {', '.join(_EXHIBIT_COLUMNS)} FROM transcript_exhibits "
            "WHERE exhibit_id = ?",
            (exhibit_id,),
        ).fetchone()
    return _exhibit_row_to_dict(row)


def update_exhibit(exhibit_id: str, patch: dict) -> Optional[dict]:
    existing = get_exhibit(exhibit_id)
    if existing is None:
        return None

    updates = {}
    if "exhibit_number" in patch and patch.get("exhibit_number") is not None:
        value = str(patch.get("exhibit_number") or "").strip()
        if not value:
            raise ValueError("exhibit_number cannot be blank")
        updates["exhibit_number"] = value
    for key in ("exhibit_title", "offering_attorney", "description", "anchor_note"):
        if key in patch and patch.get(key) is not None:
            updates[key] = str(patch.get(key) or "").strip()
    if "sort_order" in patch and patch.get("sort_order") is not None:
        updates["sort_order"] = int(patch.get("sort_order"))
    if "anchor_utterance_id" in patch and patch.get("anchor_utterance_id") is not None:
        anchor = str(patch.get("anchor_utterance_id") or "").strip()
        if not anchor:
            raise ValueError("anchor_utterance_id cannot be blank")
        if not any(u["utterance_id"] == anchor for u in get_utterances(existing["job_id"], layer="raw")):
            raise ValueError(
                f"Utterance {anchor} does not belong to job {existing['job_id']}"
            )
        updates["anchor_utterance_id"] = anchor

    with get_connection() as conn:
        if updates:
            set_clause = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE transcript_exhibits SET {set_clause}, updated_at = datetime('now') "
                "WHERE exhibit_id = ?",
                [*updates.values(), exhibit_id],
            )
        row = conn.execute(
            f"SELECT {', '.join(_EXHIBIT_COLUMNS)} FROM transcript_exhibits "
            "WHERE exhibit_id = ?",
            (exhibit_id,),
        ).fetchone()
    return _exhibit_row_to_dict(row) if row else None


def delete_exhibit(exhibit_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM transcript_exhibits WHERE exhibit_id = ?",
            (exhibit_id,),
        )
    return cur.rowcount > 0


def replace_exhibits(job_id: str, exhibits: list[dict]) -> list[dict]:
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Transcript job {job_id} not found")
    raw_ids = {u["utterance_id"] for u in get_utterances(job_id, layer="raw")}

    with get_connection() as conn:
        conn.execute("DELETE FROM transcript_exhibits WHERE job_id = ?", (job_id,))
        for idx, ex in enumerate(exhibits or []):
            anchor = (ex.get("anchor_utterance_id") or "").strip()
            if anchor not in raw_ids:
                raise ValueError(
                    f"Utterance {anchor} does not belong to job {job_id}"
                )
            conn.execute(
                """
                INSERT INTO transcript_exhibits
                (exhibit_id, job_id, case_id, session_id, exhibit_number,
                 exhibit_title, offering_attorney, description,
                 anchor_utterance_id, anchor_note, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')), COALESCE(?, datetime('now')))
                """,
                (
                    ex.get("exhibit_id") or new_id(),
                    job_id,
                    job.get("case_id"),
                    job.get("session_id"),
                    str(ex.get("exhibit_number") or "").strip(),
                    str(ex.get("exhibit_title") or "").strip(),
                    str(ex.get("offering_attorney") or "").strip(),
                    str(ex.get("description") or "").strip(),
                    anchor,
                    str(ex.get("anchor_note") or "").strip(),
                    int(ex.get("sort_order", idx)),
                    ex.get("created_at"),
                    ex.get("updated_at"),
                ),
            )
    return list_exhibits(job_id)


def search_utterances(
    query: str,
    case_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Readback search: case-insensitive substring match over utterance text.

    Per the build plan, search runs against the structured utterance
    rows, NOT a giant transcript string. Returns each match with its job
    and speaker context so the read-back terminal can show provenance.
    """
    query = (query or "").strip()
    if not query:
        return []

    like = f"%{query}%"
    with get_connection() as conn:
        if case_id:
            rows = conn.execute(
                """
                SELECT u.utterance_id, u.job_id, u.utterance_index, u.speaker_label,
                       u.start_time, u.end_time, u.text, u.avg_confidence,
                       j.source_filename, j.sequence_index
                FROM transcript_utterances u
                JOIN transcript_jobs j ON j.job_id = u.job_id
                WHERE j.case_id = ? AND u.text LIKE ? COLLATE NOCASE
                ORDER BY j.sequence_index ASC, u.utterance_index ASC
                LIMIT ?
                """,
                (case_id, like, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT u.utterance_id, u.job_id, u.utterance_index, u.speaker_label,
                       u.start_time, u.end_time, u.text, u.avg_confidence,
                       j.source_filename, j.sequence_index
                FROM transcript_utterances u
                JOIN transcript_jobs j ON j.job_id = u.job_id
                WHERE u.text LIKE ? COLLATE NOCASE
                ORDER BY j.created_at DESC, u.utterance_index ASC
                LIMIT ?
                """,
                (like, limit),
            ).fetchall()

    return [dict(r) for r in rows]
