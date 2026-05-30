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
from backend.db import repository as dbrepo
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
_VALID_ORIGINS = {"parse", "operator"}
_PARSER_OWNED_SOURCES = {"nod_parser", "text_parser"}

# Canonical UFM field IDs. Keep aligned with frontend UFM_FIELD_IDS in
# stage_1.js — these are the only keys accepted in field_confirmations.
UFM_FIELD_IDS = (
    "ufmCause", "ufmStyle", "ufmCourt", "ufmCounty", "ufmState",
    "ufmWitness", "ufmDate", "ufmStartTime", "ufmEndTime", "ufmAddress",
    "ufmCSRName", "ufmCSRLicense", "ufmFirmReg", "ufmCSRCertExp",
    "ufmCustodialName", "ufmRequestingParty",
)


def filter_field_confirmations(raw: dict | None) -> dict[str, str]:
    """Return a sanitized field_confirmations dict.

    Only known UFM field IDs (UFM_FIELD_IDS) are kept; the only valid value
    is the literal "confirmed". Anything else is dropped.
    """
    out: dict[str, str] = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if key in UFM_FIELD_IDS and value == "confirmed":
            out[key] = "confirmed"
    return out


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
        if entry["source"] == "manual":
            existing["source"] = "manual"

    return [merged[key] for key in order]


def normalize_sync_origin(origin: Any) -> str:
    raw = str(origin or "").strip().lower()
    return raw if raw in _VALID_ORIGINS else "parse"


def _normalize_warning_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _append_warning(warnings: list[str], message: str) -> None:
    text = str(message or "").strip()
    if text and text not in warnings:
        warnings.append(text)


def _merge_parser_metadata(existing: dict | None, incoming: dict | None) -> dict:
    merged = {
        **(existing if isinstance(existing, dict) else {}),
        **(incoming if isinstance(incoming, dict) else {}),
    }
    warnings = _normalize_warning_list((existing or {}).get("warnings"))
    for message in _normalize_warning_list((incoming or {}).get("warnings")):
        _append_warning(warnings, message)
    merged["warnings"] = warnings
    return merged


def merge_stage1_keyterms(
    stored_terms: list[Any] | None,
    incoming_terms: list[Any] | None,
    origin: str,
) -> list[dict]:
    stored = normalize_keyterm_entries(stored_terms)
    incoming = normalize_keyterm_entries(incoming_terms)
    if origin != "parse":
        return normalize_keyterm_entries(stored + incoming)

    incoming_sources = {
        entry["source"]
        for entry in incoming
        if entry.get("source") in _PARSER_OWNED_SOURCES
    }
    retained = [
        entry for entry in stored
        if entry.get("source") not in incoming_sources
    ]
    return normalize_keyterm_entries(retained + incoming)


def merge_stage1_ufm_fields(
    stored_fields: dict[str, str] | None,
    incoming_fields: dict[str, str] | None,
    *,
    origin: str,
    field_confirmations: dict[str, str] | None,
    field_sources: dict[str, str] | None,
    warnings: list[str],
) -> tuple[dict[str, str], set[str]]:
    stored = filter_ufm_fields(stored_fields)
    incoming = filter_ufm_fields(incoming_fields)
    if origin != "parse":
        merged = dict(stored)
        for field_id in UFM_FIELD_IDS:
            if field_id in incoming:
                merged[field_id] = incoming[field_id]
            elif isinstance(incoming_fields, dict) and field_id in incoming_fields:
                merged.pop(field_id, None)
        return merged, set()

    confirmations = filter_field_confirmations(field_confirmations)
    sources = reconcile_field_sources(stored, field_sources)
    merged = dict(stored)
    adopted: set[str] = set()
    for field_id, next_value in incoming.items():
        current_value = stored.get(field_id, "")
        if not next_value:
            continue
        is_confirmed = confirmations.get(field_id) == "confirmed"
        is_manual = sources.get(field_id) == "manual"
        if current_value and next_value != current_value and (is_confirmed or is_manual):
            reason = "confirmed" if is_confirmed else "manual"
            _append_warning(
                warnings,
                f"Preserved {reason} value for {field_id}; incoming parser value did not replace it.",
            )
            continue
        merged[field_id] = next_value
        adopted.add(field_id)
    return merged, adopted


def merge_stage1_field_sources(
    stored_fields: dict[str, str] | None,
    merged_fields: dict[str, str] | None,
    *,
    origin: str,
    existing_sources: dict[str, Any] | None,
    incoming_sources: dict[str, Any] | None,
    adopted_parser_fields: set[str] | None = None,
) -> dict[str, str]:
    if origin != "parse":
        return reconcile_field_sources(merged_fields, existing_sources)

    merged: dict[str, str] = reconcile_field_sources(stored_fields, existing_sources)
    adopted_payload = {
        field_id: filter_ufm_fields(merged_fields).get(field_id, "")
        for field_id in (adopted_parser_fields or set())
    }
    merged.update(reconcile_field_sources(adopted_payload, incoming_sources))
    return reconcile_field_sources(merged_fields, merged)


def keyterm_strings(raw_terms: list[Any] | None) -> list[str]:
    return [entry["term"] for entry in normalize_keyterm_entries(raw_terms)]


def reconcile_field_sources(
    ufm_fields: dict[str, str] | None,
    raw_sources: dict[str, Any] | None,
) -> dict[str, str]:
    """Project field_sources onto the current non-empty UFM field set.

    field_sources is never authoritative on its own: it must be a subset of the
    current non-empty ufm_fields, and any populated field without an explicit
    parser/learned source is treated as operator-entered manual data.
    """
    fields = filter_ufm_fields(ufm_fields)
    incoming = raw_sources if isinstance(raw_sources, dict) else {}
    out: dict[str, str] = {}

    for key, value in fields.items():
        if not value:
            continue
        source = normalize_keyterm_source(incoming.get(key))
        if key not in incoming:
            source = "manual"
        out[key] = source
    return out


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
        "field_confirmations": {},
        "ufm_fields": {},
        "keyterms": [],
        "workspace": {
            "sessions": {},
        },
        "created_at": now,
        "updated_at": now,
    }


def filter_ufm_fields(raw: dict | None) -> dict[str, str]:
    """Return only known UFM field IDs as string values."""
    out: dict[str, str] = {}
    if not isinstance(raw, dict):
        return out
    for key in UFM_FIELD_IDS:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            out[key] = text
    return out


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
    record["field_confirmations"] = filter_field_confirmations(
        data.get("field_confirmations")
    )
    record["ufm_fields"] = filter_ufm_fields(data.get("ufm_fields"))
    record["parser_metadata"]["field_sources"] = reconcile_field_sources(
        record["ufm_fields"],
        record["parser_metadata"].get("field_sources"),
    )
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
    base["field_confirmations"] = filter_field_confirmations(
        base.get("field_confirmations")
    )
    base["ufm_fields"] = filter_ufm_fields(base.get("ufm_fields"))
    base["parser_metadata"] = {
        **base.get("parser_metadata", {}),
        "field_sources": reconcile_field_sources(
            base.get("ufm_fields"),
            (base.get("parser_metadata") or {}).get("field_sources"),
        ),
    }
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
    origin = normalize_sync_origin(payload.get("origin"))
    existing_parser_metadata = record.get("parser_metadata") or {}
    incoming_parser_metadata = payload.get("parser_metadata") or {}
    parser_metadata = _merge_parser_metadata(
        existing_parser_metadata,
        incoming_parser_metadata,
    )
    warnings = _normalize_warning_list(parser_metadata.get("warnings"))

    raw_incoming = payload.get("field_confirmations")
    if raw_incoming is None:
        raw_incoming = {}
    if not isinstance(raw_incoming, dict):
        raise ValueError("field_confirmations must be an object")
    if origin == "operator":
        merged_confirmations = filter_field_confirmations(raw_incoming)
    else:
        merged_confirmations = filter_field_confirmations(record.get("field_confirmations"))
        for key, value in raw_incoming.items():
            if key not in UFM_FIELD_IDS:
                # API layer should reject this; defensive guard here.
                raise ValueError(f"Unknown field_confirmations key: {key}")
            if value == "confirmed":
                merged_confirmations[key] = "confirmed"
            else:
                merged_confirmations.pop(key, None)

    if origin == "operator":
        for key in raw_incoming:
            if key not in UFM_FIELD_IDS:
                raise ValueError(f"Unknown field_confirmations key: {key}")

    incoming_ufm_raw = {k: payload.get(k) for k in UFM_FIELD_IDS}
    incoming_ufm = filter_ufm_fields(incoming_ufm_raw)

    record["raw_intake_notes"] = payload.get("raw_intake_notes") or ""
    # Re-parse is non-destructive to human data and never blanks on absence.
    # Operator-origin syncs honor deliberate edits and clears.
    merged_ufm, adopted_parser_fields = merge_stage1_ufm_fields(
        record.get("ufm_fields"),
        incoming_ufm_raw,
        origin=origin,
        field_confirmations=merged_confirmations,
        field_sources=existing_parser_metadata.get("field_sources"),
        warnings=warnings,
    )
    keyterms = merge_stage1_keyterms(
        record.get("keyterms"),
        payload.get("keyterms"),
        origin,
    )
    parser_metadata["warnings"] = warnings
    parser_metadata["field_sources"] = merge_stage1_field_sources(
        record.get("ufm_fields"),
        merged_ufm,
        origin=origin,
        existing_sources=existing_parser_metadata.get("field_sources"),
        incoming_sources=incoming_parser_metadata.get("field_sources"),
        adopted_parser_fields=adopted_parser_fields,
    )

    record["parser_metadata"] = parser_metadata
    record["keyterms"] = keyterms
    record["field_confirmations"] = merged_confirmations
    record["ufm_fields"] = merged_ufm

    appearance_sync: dict[str, int] | None = None
    if parser_metadata.get("appearances") and dbrepo.get_case(case_id) is not None:
        appearance_sync = dbrepo.sync_case_attorney_appearances(
            case_id,
            caption_full=merged_ufm.get("ufmStyle"),
            appearances=parser_metadata.get("appearances") or [],
        )

    persisted_keyterms = persist_case_keyterms(
        case_id,
        case_caption=merged_ufm.get("ufmStyle"),
        cause_number=merged_ufm.get("ufmCause"),
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
                {**payload, **merged_ufm, "keyterms": keyterms}
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
            "case_caption": merged_ufm.get("ufmStyle"),
            "cause_number": merged_ufm.get("ufmCause"),
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
        "appearance_sync": appearance_sync,
        "field_confirmations": record["field_confirmations"],
        "raw_intake_notes": record["raw_intake_notes"],
        "workspace": record["workspace"],
    }
