"""Authoritative Stage 1 intake artifact storage.

This module keeps Stage 1 persistence additive and local to the existing
architecture:

  - SQLite remains the source of truth for cases / sessions / reporters.
  - Case-scoped intake artifacts live under data/cases/{case_id}/.
  - Deepgram reads a normalized list[str] keyterms.json from that folder.
  - Rich keyterm metadata and parser output are preserved in companion files.

The goal is determinism and interoperability, not a new architecture.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from backend.config import settings
from backend.models.canonical import (
    CaseIdentity,
    CaseWorkspacePacket,
    DepositionSession,
    KeyTerm,
    ReporterCredentials,
    SessionPacket,
)
from backend.services import workspace as workspace_svc

_SOURCE_ALIASES = {
    "notice_parser": "nod_parser",
}
_VALID_SOURCES = {"nod_parser", "text_parser", "learned", "manual"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def case_artifacts_dir(case_id: str) -> Path:
    return settings.data_root / "cases" / case_id


def intake_metadata_path(case_id: str) -> Path:
    return case_artifacts_dir(case_id) / "stage1_intake.json"


def keyterms_path(case_id: str) -> Path:
    return case_artifacts_dir(case_id) / "keyterms.json"


def keyterms_meta_path(case_id: str) -> Path:
    return case_artifacts_dir(case_id) / "keyterms.meta.json"


def normalize_keyterm_source(source: str | None) -> str:
    src = (source or "manual").strip().lower()
    src = _SOURCE_ALIASES.get(src, src)
    return src if src in _VALID_SOURCES else "manual"


def normalize_keyterm_entries(raw_terms: list[Any] | None) -> list[dict]:
    """Return canonical keyterm entry dicts.

    Accepts legacy strings, rich dicts, or mixed input. Duplicates are merged
    case-insensitively with the highest boost retained.
    """
    merged: dict[str, dict] = {}
    order: list[str] = []

    for raw in raw_terms or []:
        if isinstance(raw, str):
            term = raw.strip()
            entry = {
                "term": term,
                "boost": 1.0,
                "category": "Term",
                "source": "manual",
            }
        elif isinstance(raw, dict):
            term = str(raw.get("term") or "").strip()
            entry = {
                "term": term,
                "boost": float(raw.get("boost", 1.0) or 1.0),
                "category": str(raw.get("category") or "Term").strip() or "Term",
                "source": normalize_keyterm_source(raw.get("source")),
            }
        else:
            continue

        if not entry["term"]:
            continue

        key = entry["term"].casefold()
        existing = merged.get(key)
        if existing is None:
            merged[key] = entry
            order.append(key)
            continue

        if entry["boost"] > existing["boost"]:
            existing["boost"] = entry["boost"]
        if existing.get("category") in ("", "Term") and entry["category"]:
            existing["category"] = entry["category"]
        if existing.get("source") == "manual" and entry["source"] != "manual":
            existing["source"] = entry["source"]

    return [merged[key] for key in order]


def keyterm_strings(raw_terms: list[Any] | None) -> list[str]:
    return [entry["term"] for entry in normalize_keyterm_entries(raw_terms)]


def _default_record(case_id: str) -> dict:
    now = _utc_now_iso()
    return {
        "case_id": case_id,
        "raw_intake_notes": "",
        "parser_metadata": {
            "appearances": [],
            "speaker_hints": [],
            "deepgram_config": {},
            "jurisdiction_type": "texas_state",
            "location_type": "unknown",
            "detected_types": [],
            "warnings": [],
            "field_sources": {},
        },
        "keyterms": [],
        "workspace": {
            "sessions": {},
        },
        "created_at": now,
        "updated_at": now,
    }


def read_stage1_record(case_id: str) -> dict:
    path = intake_metadata_path(case_id)
    if not path.exists():
        return _default_record(case_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Stage 1 intake metadata unreadable for case {case_id}: {exc}")
        return _default_record(case_id)

    record = _default_record(case_id)
    record.update({k: v for k, v in data.items() if k in record})
    record["parser_metadata"] = {
        **record["parser_metadata"],
        **(data.get("parser_metadata") or {}),
    }
    record["workspace"] = {
        "sessions": {},
        **(data.get("workspace") or {}),
    }
    record["workspace"]["sessions"] = dict(
        (data.get("workspace") or {}).get("sessions") or {}
    )
    record["keyterms"] = normalize_keyterm_entries(data.get("keyterms") or [])
    return record


def write_stage1_record(case_id: str, record: dict) -> dict:
    base = _default_record(case_id)
    base.update(record or {})
    base["case_id"] = case_id
    base["keyterms"] = normalize_keyterm_entries(base.get("keyterms") or [])
    base["workspace"] = {
        "sessions": {},
        **(base.get("workspace") or {}),
    }
    base["workspace"]["sessions"] = dict(base["workspace"].get("sessions") or {})
    base["updated_at"] = _utc_now_iso()

    path = intake_metadata_path(case_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")
    return base


def persist_case_keyterms(
    case_id: str,
    *,
    case_caption: str | None,
    cause_number: str | None,
    entries: list[dict] | None,
) -> dict:
    normalized_entries = normalize_keyterm_entries(entries or [])
    strings = [entry["term"] for entry in normalized_entries]
    now = _utc_now_iso()

    kp = keyterms_path(case_id)
    km = keyterms_meta_path(case_id)
    kp.parent.mkdir(parents=True, exist_ok=True)
    kp.write_text(json.dumps(strings, indent=2, ensure_ascii=False), encoding="utf-8")
    km.write_text(
        json.dumps(
            {
                "case_id": case_id,
                "case_caption": case_caption,
                "cause_number": cause_number,
                "generated_at": now,
                "keyterms": normalized_entries,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    logger.info(
        f"Persisted {len(strings)} Stage 1 keyterms for case {case_id} to {kp}"
    )
    return {
        "keyterms_path": str(kp),
        "keyterms_meta_path": str(km),
        "keyterm_count": len(strings),
    }


def _build_workspace_packets(payload: dict) -> tuple[CaseWorkspacePacket, SessionPacket]:
    jt = payload.get("jurisdiction_type")
    if jt not in ("federal", "texas_state", "other"):
        jt = "texas_state"
    lt = payload.get("location_type")
    if lt not in ("zoom", "in_person", "hybrid", "phone", "unknown"):
        lt = "unknown"

    identity = CaseIdentity(
        case_number_value=payload.get("ufmCause"),
        jurisdiction_type=jt,
        caption_full=payload.get("ufmStyle"),
        judicial_district=payload.get("ufmCourt") if jt != "federal" else None,
        court_district=payload.get("ufmCourt") if jt == "federal" else None,
        county=payload.get("ufmCounty"),
        state=payload.get("ufmState") or "Texas",
    )
    reporter = ReporterCredentials(
        officer_name=payload.get("ufmCSRName"),
        csr_license=payload.get("ufmCSRLicense"),
        firm_registration=payload.get("ufmFirmReg"),
        license_expiration=payload.get("ufmCSRCertExp"),
    )
    session = DepositionSession(
        witness_name=payload.get("ufmWitness"),
        deposition_date=payload.get("ufmDate"),
        start_time=payload.get("ufmStartTime"),
        end_time=payload.get("ufmEndTime"),
        location_type=lt,
        location_address=payload.get("ufmAddress"),
    )
    keyterms = [KeyTerm(**entry) for entry in normalize_keyterm_entries(payload.get("keyterms"))]

    case_packet = CaseWorkspacePacket(
        case_id=payload.get("case_id"),
        identity=identity,
        reporter=reporter,
        keyterms=keyterms,
    )
    session_packet = SessionPacket(
        session_id=payload.get("session_id"),
        case_id=payload.get("case_id"),
        session=session,
    )
    return case_packet, session_packet


def sync_stage1_artifacts(payload: dict) -> dict:
    """Persist authoritative Stage 1 artifacts and initialize workspace safely."""
    case_id = str(payload.get("case_id") or "").strip()
    if not case_id:
        raise ValueError("case_id is required for Stage 1 artifact sync")

    record = read_stage1_record(case_id)
    parser_metadata = {
        **record.get("parser_metadata", {}),
        **(payload.get("parser_metadata") or {}),
    }
    keyterms = normalize_keyterm_entries(payload.get("keyterms") or record.get("keyterms"))

    record["raw_intake_notes"] = payload.get("raw_intake_notes") or ""
    record["parser_metadata"] = parser_metadata
    record["keyterms"] = keyterms

    persisted_keyterms = persist_case_keyterms(
        case_id,
        case_caption=payload.get("ufmStyle"),
        cause_number=payload.get("ufmCause"),
        entries=keyterms,
    )

    session_id = str(payload.get("session_id") or "").strip()
    workspace_result: dict[str, Any] = {"workspace_state": "pending_session"}
    if session_id:
        session_map = record["workspace"].setdefault("sessions", {})
        existing = session_map.get(session_id)
        if existing and Path(existing.get("session_dir") or "").exists():
            workspace_result = dict(existing)
            logger.info(
                f"Reusing existing Stage 1 workspace for case {case_id}, session {session_id}"
            )
        else:
            case_packet, session_packet = _build_workspace_packets(
                {**payload, "keyterms": keyterms}
            )
            workspace_result = workspace_svc.initialize_case_workspace(
                case_packet,
                session_packet,
                reporter_name=payload.get("reporter_name"),
            )
            session_map[session_id] = workspace_result
            logger.info(
                f"Initialized Stage 1 workspace for case {case_id}, session {session_id}"
            )

        # Backwards-compatible mirror for session-local inspection only.
        mirror_payload = {
            "case_id": case_id,
            "case_caption": payload.get("ufmStyle"),
            "cause_number": payload.get("ufmCause"),
            "generated_at": _utc_now_iso(),
            "keyterms": keyterms,
        }
        workspace_result["workspace_keyterms_path"] = workspace_svc.write_keyterms_file(
            workspace_result["session_dir"], mirror_payload
        )

    record = write_stage1_record(case_id, record)
    logger.info(
        f"Stage 1 sync complete for case {case_id}: "
        f"{len(keyterms)} keyterm(s), session={'bound' if session_id else 'pending'}"
    )
    return {
        **workspace_result,
        **persisted_keyterms,
        "case_id": case_id,
        "session_id": session_id or None,
        "metadata_path": str(intake_metadata_path(case_id)),
        "keyterms": record["keyterms"],
        "parser_metadata": record["parser_metadata"],
        "raw_intake_notes": record["raw_intake_notes"],
        "workspace": record["workspace"],
    }
