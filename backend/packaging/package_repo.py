"""Transcript Package repository — Wave 20.

CRUD over the transcript_packages table (schema_v8). Append-only for
DRAFT and REVIEW packages; the only permitted mutation is transitioning
to CERTIFIED (one-way, sets certified_at) or later immutable states
(EXPORTED, SEALED, AMENDED, SUPERSEDED).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.db.repository import get_connection
from backend.packaging.model import (
    GenerationReport,
    IndexEntry,
    PackageIdentity,
    PackageManifest,
    TranscriptIndex,
    TranscriptPackage,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_summary(row) -> dict:
    """Return a lightweight summary dict from a DB row (no full JSON)."""
    return {
        "package_id": row["package_id"],
        "job_id": row["job_id"],
        "snapshot_id": row["snapshot_id"],
        "state_hash": row["state_hash"],
        "package_state": row["package_state"],
        "manifest_hash": row["manifest_hash"] or "",
        "created_at": row["created_at"],
        "certified_at": row["certified_at"] or "",
    }


def _reconstruct_package(row) -> TranscriptPackage:
    """Reconstruct a TranscriptPackage from a DB row.

    Rebuilds only the fields required by `certify_package()`:
    indices, body_page_count, state, and identity/manifest for
    transition tracking. All other fields come from the stored JSON.
    """
    pkg_dict = json.loads(row["package_json"])
    manifest_dict = json.loads(row["manifest_json"])

    # Reconstruct identity
    ident_d = pkg_dict.get("identity", {})
    identity = PackageIdentity(
        package_id=ident_d.get("package_id", ""),
        transcript_snapshot_id=ident_d.get("transcript_snapshot_id", ""),
        state_hash=ident_d.get("state_hash", ""),
        package_version=ident_d.get("package_version", 1),
        certification_id=ident_d.get("certification_id", ""),
        export_id=ident_d.get("export_id", ""),
    )

    # Reconstruct manifest
    manifest = PackageManifest(
        identity=identity,
        certification_state=manifest_dict.get("certification_state", "DRAFT"),
        package_timestamp=manifest_dict.get("package_timestamp", ""),
        included_exhibits=list(manifest_dict.get("included_exhibits", [])),
        generated_indices=list(manifest_dict.get("generated_indices", [])),
        template_versions=dict(manifest_dict.get("template_versions", {})),
        geometry_profile=manifest_dict.get("geometry_profile", "texas_ufm"),
        packaging_engine_version=manifest_dict.get("packaging_engine_version", ""),
        manifest_hash=manifest_dict.get("manifest_hash", ""),
    )

    # Reconstruct generation report
    rpt_d = pkg_dict.get("generation_report", {})
    report = GenerationReport(
        body_pages=rpt_d.get("body_pages", 0),
        administrative_pages=rpt_d.get("administrative_pages", 0),
        exhibits_indexed=rpt_d.get("exhibits_indexed", 0),
        witnesses_indexed=rpt_d.get("witnesses_indexed", 0),
        unresolved_flags=rpt_d.get("unresolved_flags", 0),
        warnings=list(rpt_d.get("warnings", [])),
        ai_review_summary=dict(rpt_d.get("ai_review_summary", {})),
        certification_status=rpt_d.get("certification_status", "DRAFT"),
        validation_passed=bool(rpt_d.get("validation_passed", False)),
    )

    # Reconstruct indices
    indices: dict[str, TranscriptIndex] = {}
    for kind, idx_d in pkg_dict.get("indices", {}).items():
        entries = [
            IndexEntry(
                label=e.get("label", ""),
                page=e.get("page"),
                line=e.get("line"),
                detail=e.get("detail", ""),
            )
            for e in idx_d.get("entries", [])
        ]
        indices[kind] = TranscriptIndex(kind=kind, entries=entries)

    return TranscriptPackage(
        identity=identity,
        manifest=manifest,
        generation_report=report,
        administrative_pages={},   # not needed for certify
        section_order=list(pkg_dict.get("section_order", [])),
        body_page_count=pkg_dict.get("body_page_count", 0),
        indices=indices,
        state=row["package_state"],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_package(package: TranscriptPackage, job_id: str) -> dict:
    """Persist a new TranscriptPackage. Append-only; never overwrites."""
    pkg_dict = package.to_dict()
    manifest_dict = package.manifest.to_dict()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO transcript_packages "
            "(package_id, job_id, snapshot_id, state_hash, package_state, "
            " manifest_hash, manifest_json, package_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                package.package_id,
                job_id,
                package.manifest.identity.transcript_snapshot_id,
                package.manifest.identity.state_hash,
                package.state,
                package.manifest.manifest_hash,
                json.dumps(manifest_dict),
                json.dumps(pkg_dict),
            ),
        )
    return get_package_summary(package.package_id) or {}


def get_package(package_id: str) -> dict | None:
    """Return the full stored package JSON as a dict, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM transcript_packages WHERE package_id = ?",
            (package_id,)).fetchone()
    if row is None:
        return None
    result = _row_to_summary(row)
    result["package"] = json.loads(row["package_json"])
    return result


def get_package_summary(package_id: str) -> dict | None:
    """Return a lightweight summary row without the full JSON blob."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM transcript_packages WHERE package_id = ?",
            (package_id,)).fetchone()
    return _row_to_summary(row) if row else None


def get_package_for_update(package_id: str) -> TranscriptPackage | None:
    """Retrieve and reconstruct a TranscriptPackage for transition ops."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM transcript_packages WHERE package_id = ?",
            (package_id,)).fetchone()
    return _reconstruct_package(row) if row else None


def list_packages(job_id: str) -> list[dict]:
    """List all packages for a job, newest first (summary form)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM transcript_packages WHERE job_id = ? "
            "ORDER BY created_at DESC, package_id DESC",
            (job_id,)).fetchall()
    return [_row_to_summary(r) for r in rows]


def has_certified_package(job_id: str) -> bool:
    """True when immutable certified package lineage exists for `job_id`."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM transcript_packages "
            "WHERE job_id = ? AND package_state = 'CERTIFIED' LIMIT 1",
            (job_id,),
        ).fetchone()
    return row is not None


# Any state past DRAFT carries real downstream weight (an EXPORTED package
# has been served, a SEALED one finalized), so deletion protection uses the
# full non-DRAFT set, not just CERTIFIED.
_NON_DRAFT_STATES = ("CERTIFIED", "EXPORTED", "SEALED", "AMENDED", "SUPERSEDED")


def list_non_draft_package_ids(job_id: str) -> list[str]:
    """Package IDs for `job_id` in any non-DRAFT state (newest first)."""
    placeholders = ", ".join("?" for _ in _NON_DRAFT_STATES)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT package_id FROM transcript_packages "
            f"WHERE job_id = ? AND package_state IN ({placeholders}) "
            f"ORDER BY created_at DESC, package_id DESC",
            (job_id, *_NON_DRAFT_STATES),
        ).fetchall()
    return [r["package_id"] for r in rows]


def has_non_draft_package(job_id: str) -> bool:
    """True when `job_id` has any package past DRAFT (the deletion guard)."""
    return bool(list_non_draft_package_ids(job_id))


def update_package_state(
    package_id: str,
    new_state: str,
    updated_package: TranscriptPackage,
) -> bool:
    """Update a package's state in the DB after a transition."""
    certified_at = None
    if new_state == "CERTIFIED":
        certified_at = datetime.now(tz=timezone.utc).isoformat()
    pkg_dict = updated_package.to_dict()
    manifest_dict = updated_package.manifest.to_dict()
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE transcript_packages "
            "SET package_state = ?, manifest_hash = ?, "
            "    manifest_json = ?, package_json = ?, certified_at = ? "
            "WHERE package_id = ?",
            (
                new_state,
                updated_package.manifest.manifest_hash,
                json.dumps(manifest_dict),
                json.dumps(pkg_dict),
                certified_at,
                package_id,
            ),
        )
        return cur.rowcount > 0
