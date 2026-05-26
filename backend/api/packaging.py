"""Router for /api/packages -- the Transcript Packaging Engine (Wave 20).

Endpoints:
    POST /api/packages/jobs/{job_id}          assemble a DRAFT package
    GET  /api/packages/jobs/{job_id}          list a job's packages
    GET  /api/packages/{package_id}           get one package (full)
    POST /api/packages/{package_id}/certify   certify (one-way finalization)

Packages are assembled from a locked Certification Snapshot (Wave 18.5)
using the Packaging Engine (Wave 20). Once certified a package is
immutable -- any change requires assembling a new package version.
"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel

from backend.packaging import (
    ExhibitEvent,
    IndexInputs,
    assemble_package,
    certify_package,
)
from backend.packaging.package_repo import (
    get_package,
    get_package_for_update,
    get_package_summary,
    list_packages,
    save_package,
    update_package_state,
)
from backend.transcript import repository as trepo
from backend.transcript import provenance as provenance_mod
from backend.transcript_state import snapshot_repo
from backend.services import intake_store

router = APIRouter(prefix="/api/packages", tags=["packages"])


# ---------------------------------------------------------------------------
# Metadata auto-population helpers
# ---------------------------------------------------------------------------

def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    suffixes = {1: "st", 2: "nd", 3: "rd"}
    return f"{n}{suffixes.get(n % 10, 'th')}"


def _format_time_12h(dt: datetime) -> str:
    ampm = "a.m." if dt.hour < 12 else "p.m."
    hour12 = dt.hour % 12 or 12
    return f"{hour12}:{dt.minute:02d} {ampm}"


def _parse_iso_dt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _get_firm_address(firm_id: str) -> tuple[str, str]:
    from backend.db.repository import get_connection
    with get_connection() as conn:
        row = conn.execute(
            "SELECT address_line, city, state, zip "
            "FROM reporting_firm_offices "
            "WHERE reporting_firm_id = ? AND is_default = 1 LIMIT 1",
            (firm_id,),
        ).fetchone()
    if not row:
        return "", ""
    addr = row["address_line"] or ""
    city = row["city"] or ""
    state = row["state"] or ""
    zip_ = row["zip"] or ""
    if city and state:
        city_state_zip = f"{city}, {state} {zip_}".strip()
    elif city:
        city_state_zip = f"{city} {zip_}".strip()
    else:
        city_state_zip = zip_
    return addr, city_state_zip


def _build_metadata_for_job(job_id: str, override: dict) -> dict:
    """Build a complete metadata dict by pulling all persisted fields for job_id.

    Draws from: cases, sessions, reporters, reporting_firm_offices, parties,
    case_attorneys, and deposition_metadata. The caller-supplied `override`
    dict wins on every key, so explicit request-body values always take
    priority over auto-populated values.
    """
    from backend.db import repository as dbrepo
    from backend.db.depo_meta_repo import get_depo_meta

    override = override or {}
    meta: dict = {}

    job = trepo.get_job(job_id)
    if not job:
        meta.update(override)
        return meta

    session_id = job.get("session_id")
    case_id = job.get("case_id")
    intake = intake_store.read_stage1_record(case_id) if case_id else {}
    parser_meta = intake.get("parser_metadata") or {}

    # --- Case -----------------------------------------------------------
    if case_id:
        case = dbrepo.get_case(case_id)
        if case:
            meta["cause_number"] = case.get("case_number_value") or ""
            meta["caption"] = case.get("caption_full") or ""
            meta["county"] = case.get("county") or ""
            meta["judicial_district"] = case.get("judicial_district") or ""

            jd = case.get("judicial_district") or ""
            county = case.get("county") or ""
            state = case.get("state") or "Texas"
            court_parts = []
            if jd:
                court_parts.append(f"{jd} Court")
            if county:
                court_parts.append(county)
            if state:
                court_parts.append(state)
            meta["court"] = ", ".join(court_parts)

            # Plaintiff / defendant names from parties
            _populate_party_names(meta, case_id)
            if not meta.get("plaintiff_names") and not meta.get("defendant_names"):
                _populate_parties_from_caption(meta)

            # Appearances and counsel of record from case_attorneys
            _populate_appearances(meta, case_id)
            if not meta.get("appearances"):
                _populate_appearances_from_intake(meta, parser_meta)

    # --- Session --------------------------------------------------------
    if session_id:
        session = dbrepo.get_session(session_id)
        if session:
            meta["witness_name"] = session.get("witness_name") or ""
            meta["party_at_instance"] = session.get("requesting_party_name") or ""
            meta["custodial_attorney"] = session.get("custodial_attorney_name") or ""
            meta["location"] = session.get("location_address") or ""

            dt_start = _parse_iso_dt(session.get("scheduled_at") or "")
            if dt_start:
                meta["proceedings_date"] = (
                    f"{dt_start.strftime('%B')} {dt_start.day}, {dt_start.year}")
                meta["start_time"] = _format_time_12h(dt_start)
                meta["proceedings_month"] = dt_start.strftime("%B")
                meta["proceedings_day"] = _ordinal(dt_start.day)
                meta["proceedings_year"] = str(dt_start.year)

            dt_end = _parse_iso_dt(session.get("scheduled_end_at") or "")
            if dt_end:
                meta["end_time"] = _format_time_12h(dt_end)

            loc_type = session.get("location_type") or ""
            method_map = {
                "zoom": "Zoom videoconference",
                "in_person": "stenographic",
                "hybrid": "hybrid Zoom/in-person",
                "phone": "telephone",
            }
            if loc_type in method_map:
                meta["deposition_method"] = method_map[loc_type]

            reporter_id = session.get("reporter_id")
            if reporter_id:
                reporter = dbrepo.get_reporter(reporter_id)
                if reporter:
                    meta["reporter_name"] = reporter.get("full_name") or ""
                    meta["reporter_csr_number"] = reporter.get("csr_number") or ""
                    meta["reporter_csr_expiration"] = reporter.get("csr_expiration") or ""
                    meta["firm_registration_no"] = (
                        reporter.get("firm_registration_number") or "")
                    firm_id = reporter.get("default_reporting_firm_id")
                    if firm_id:
                        addr, csz = _get_firm_address(firm_id)
                        if addr:
                            meta["firm_address"] = addr
                        if csz:
                            meta["firm_city_state_zip"] = csz

    if not meta.get("deposition_method"):
        loc_type = parser_meta.get("location_type") or ""
        method_map = {
            "zoom": "Zoom videoconference",
            "in_person": "stenographic",
            "hybrid": "hybrid Zoom/in-person",
            "phone": "telephone",
        }
        if loc_type in method_map:
            meta["deposition_method"] = method_map[loc_type]

    # --- Job-specific deposition metadata --------------------------------
    depo = get_depo_meta(job_id)
    if depo:
        meta["volume"] = depo.get("volume") or "1"
        for key in ("examination_disposition", "officer_charges_amount",
                    "charges_party", "certificate_service_date"):
            v = depo.get(key)
            if v is not None and str(v).strip():
                meta[key] = v
        tpp_json = depo.get("time_per_party_json")
        if tpp_json:
            try:
                meta["time_per_party"] = json.loads(tpp_json)
            except Exception:
                pass
        ap_json = depo.get("also_present_json")
        if ap_json:
            try:
                meta["also_present"] = json.loads(ap_json)
            except Exception:
                pass

    # --- Certification date (computed) ----------------------------------
    now = datetime.utcnow()
    meta.setdefault("certified_day", _ordinal(now.day))
    meta.setdefault("certified_month", now.strftime("%B"))
    meta.setdefault("certified_year", str(now.year))

    # Caller override wins on every key.
    meta.update(override)
    return meta


def _populate_party_names(meta: dict, case_id: str) -> None:
    from backend.db.repository import get_connection
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT name, role FROM parties "
            "WHERE case_id = ? ORDER BY sort_order, rowid",
            (case_id,),
        ).fetchall()
    plaintiffs = [r["name"] for r in rows if r["role"] == "plaintiff"]
    defendants = [r["name"] for r in rows if r["role"] == "defendant"]
    if plaintiffs:
        meta["plaintiff_names"] = ", ".join(plaintiffs)
    if defendants:
        meta["defendant_names"] = ", ".join(defendants)


def _populate_parties_from_caption(meta: dict) -> None:
    caption = (meta.get("caption") or "").strip()
    if not caption:
        return
    parts = None
    for needle in (" vs. ", " VS. ", " v. ", " V. ", " vs ", " v "):
        if needle in caption:
            parts = caption.split(needle, 1)
            break
    if not parts or len(parts) != 2:
        return
    plaintiff, defendant = parts[0].strip(), parts[1].strip()
    if plaintiff and not meta.get("plaintiff_names"):
        meta["plaintiff_names"] = plaintiff
    if defendant and not meta.get("defendant_names"):
        meta["defendant_names"] = defendant


def _populate_appearances(meta: dict, case_id: str) -> None:
    from backend.db.repository import get_connection
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT a.full_name, a.bar_number, a.phone,
                   ca.firm_name, ca.firm_address, ca.firm_city,
                   ca.firm_state, ca.firm_zip,
                   p.name AS party_name, p.role
            FROM case_attorneys ca
            JOIN attorneys a ON ca.attorney_id = a.attorney_id
            JOIN parties p ON ca.represents_party_id = p.party_id
            WHERE ca.case_id = ?
            ORDER BY p.sort_order, p.rowid, ca.rowid
            """,
            (case_id,),
        ).fetchall()
    appearances = []
    counsel = []
    for row in rows:
        city_parts = [row["firm_city"] or "", row["firm_state"] or "",
                      row["firm_zip"] or ""]
        city_state_zip = " ".join(p for p in city_parts if p).strip()
        appearances.append({
            "attorney": row["full_name"] or "",
            "sbot_no": row["bar_number"] or "",
            "firm": row["firm_name"] or "",
            "address": row["firm_address"] or "",
            "city_state_zip": city_state_zip,
            "phone": row["phone"] or "",
            "party": row["party_name"] or "",
            "role": row["role"] or "",
        })
        counsel.append({
            "name": row["full_name"] or "",
            "role": (f"Attorney for {row['party_name']}"
                     if row["party_name"] else ""),
        })
    if appearances:
        meta["appearances"] = appearances
    if counsel:
        meta["counsel_of_record"] = counsel


def _populate_appearances_from_intake(meta: dict, parser_meta: dict) -> None:
    appearances = []
    counsel = []
    for ap in parser_meta.get("appearances") or []:
        side = str(ap.get("side") or "").lower()
        party = "Plaintiff" if side == "plaintiff" else "Defendant" if side == "defendant" else ""
        appearances.append({
            "attorney": ap.get("name") or "",
            "sbot_no": ap.get("bar_number") or "",
            "firm": ap.get("firm") or "",
            "address": "",
            "city_state_zip": "",
            "phone": "",
            "party": party,
            "role": side,
        })
        counsel.append({
            "name": ap.get("name") or "",
            "role": f"Attorney for {party}" if party else "Attorney",
        })
    if appearances and not meta.get("appearances"):
        meta["appearances"] = appearances
    if counsel and not meta.get("counsel_of_record"):
        meta["counsel_of_record"] = counsel


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AssembleRequest(BaseModel):
    snapshot_id: str
    metadata: dict = {}
    freelance: bool = True


class CertifyRequest(BaseModel):
    metadata: dict = {}


# ---------------------------------------------------------------------------
# Helper: build a paginated document for a job
# ---------------------------------------------------------------------------

def _build_paginated_and_index_inputs_from_snapshot_state(snapshot_state: dict):
    """Return frozen pagination + index inputs from locked snapshot state.

    Certification and packaging must freeze from the snapshot state, not
    from the current mutable live database rows.
    """
    from backend.stage_s.renderer import render_stage_s
    from backend.transcript.export_render import render_export_with_layout

    working = snapshot_state.get("working_utterances") or []
    utterances = [
        {
            "utterance_id": u.get("utterance_id"),
            "utterance_index": u.get("utterance_index"),
            "speaker_index": u.get("speaker_index"),
            "speaker_label": u.get("speaker_label") or "",
            "start_time": u.get("start_time") or 0.0,
            "end_time": u.get("end_time") or 0.0,
            "text": u.get("text") or u.get("raw_text") or "",
            "avg_confidence": None,
        }
        for u in working
    ]
    try:
        from backend.corrections.regex_rules import RegexRule, apply_regex_rules

        rules = [
            RegexRule(
                rule_id=r.get("rule_id", ""),
                find_pattern=r.get("find_pattern", ""),
                replace_with=r.get("replace_with", ""),
                rule_order=r.get("rule_order", 0),
                enabled=r.get("enabled", True),
                description=r.get("description", ""),
            )
            for r in (snapshot_state.get("regex_rule_state") or [])
        ]
        if rules:
            utterances, _ = apply_regex_rules(utterances, rules)
    except Exception:
        pass
    try:
        from backend.lexicon.merge import merge_from_job_config
        from backend.lexicon.stage_x import apply_stage_x

        lexicon_cfg = snapshot_state.get("lexicon_state") or {}
        lexicon = merge_from_job_config({
            "confirmed_spellings": lexicon_cfg.get("confirmed_spellings") or {},
            "intake_keyterms": lexicon_cfg.get("intake_keyterms") or [],
        })
        if len(lexicon) > 0:
            utterances, _ = apply_stage_x(utterances, lexicon)
    except Exception:
        pass
    participants = [
        {
            "participant_id": p.get("participant_id"),
            "name": p.get("name"),
            "role": p.get("role") or "other",
            "speaker_indices": p.get("speaker_indices") or [],
            "sort_order": idx,
            "name_source": p.get("name_source"),
            "honorific": p.get("honorific"),
        }
        for idx, p in enumerate(snapshot_state.get("speaker_mapping") or [])
    ]

    # Stage S structural render
    stage_s = render_stage_s(utterances, participants)
    utterance_to_render_line: dict[str, str] = {}
    for ln in stage_s.lines:
        for utt_id in ln.source_utterance_ids or []:
            if utt_id and utt_id not in utterance_to_render_line:
                utterance_to_render_line[utt_id] = ln.line_id

    # Map to working line dicts (same mapping as export-preview)
    working: list[dict] = []
    for ln in stage_s.lines:
        if ln.render_state == "OFF_RECORD" and not ln.procedural:
            continue
        if ln.line_type == "parenthetical":
            lt = "colloquy"
        elif ln.line_type == "by_line":
            lt = "colloquy"
        elif ln.line_type in ("Q", "A", "colloquy", "flagged"):
            lt = ln.line_type
        else:
            lt = "colloquy"
        working.append({
            "line_type": lt,
            "speaker_label": ln.speaker_label,
            "text": ln.text,
        })

    _, paginated = render_export_with_layout(working)

    exhibit_events = []
    for ex in snapshot_state.get("exhibits") or []:
        render_line_id = utterance_to_render_line.get(ex.get("anchor_utterance_id") or "")
        exhibit_events.append(
            ExhibitEvent(
                exhibit_number=str(ex.get("exhibit_number") or ""),
                exhibit_title=str(ex.get("exhibit_title") or ""),
                render_line_id=render_line_id or "",
            )
        )
    return paginated, IndexInputs(exhibit_events=exhibit_events)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/jobs/{job_id}")
def assemble(job_id: str, payload: AssembleRequest) -> dict:
    """Assemble a Certified Transcript Package in the DRAFT state.

    The package is built from the provided locked Certification Snapshot.
    Metadata (caption, cause number, court, witness, reporter) must
    accompany the request; required fields are validated and any missing
    ones generate warnings in the Generation Report.
    """
    job = trepo.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found")
    if job.get("transcription_source") == "offline-fallback":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Offline validation transcripts are non-authoritative and cannot "
                "enter the certification/package chain. Re-transcribe with the "
                "Deepgram provider before certification."
            ),
        )

    snap = snapshot_repo.get_snapshot(payload.snapshot_id)
    if snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {payload.snapshot_id} not found")
    if snap.job_id != job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Snapshot {payload.snapshot_id} does not belong to job {job_id}")
    if not snap.locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Snapshot {payload.snapshot_id} is not locked. "
                    "Lock the snapshot first (POST /api/snapshots/{id}/lock) "
                    "before assembling a package."))

    # Build the paginated body from the LOCKED snapshot state.
    try:
        paginated, index_inputs = _build_paginated_and_index_inputs_from_snapshot_state(
            snap.state or {}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to paginate transcript for packaging: {exc}")
    logger.info(
        f"Packaging assemble for {job_id} frozen to snapshot {snap.snapshot_id} "
        f"(locked={snap.locked}, hash={snap.state_hash[:12]}, "
        f"exhibits={len(index_inputs.exhibit_events)})"
    )

    # Auto-populate metadata from DB; explicit payload fields win.
    metadata = _build_metadata_for_job(job_id, payload.metadata or {})

    # Assemble the package using the Wave 20 engine.
    package = assemble_package(
        snapshot_id=snap.snapshot_id,
        state_hash=snap.state_hash,
        metadata=metadata,
        index_inputs=index_inputs,
        paginated_document=paginated,
        freelance=payload.freelance,
    )

    # Persist and return.
    summary = save_package(package, job_id)
    try:
        provenance_mod.record_event(
            job_id,
            event_type="package_assembled",
            title="Certified Package Draft Assembled",
            detail=(
                f"Draft package {summary.get('package_id') or package.package_id} "
                f"assembled from locked snapshot {snap.snapshot_id}."
            ),
            actor_type="system",
            source="packaging",
            metadata={
                "snapshot_id": snap.snapshot_id,
                "state_hash": snap.state_hash,
                "included_exhibits": package.manifest.included_exhibits or [],
            },
            related_snapshot_id=snap.snapshot_id,
            related_package_id=summary.get("package_id") or package.package_id,
        )
    except Exception as exc:
        logger.warning(f"package assemble provenance record failed: {exc}")
    return {
        **summary,
        "generation_report": package.generation_report.to_dict(),
        "section_order": package.section_order,
    }


@router.get("/jobs/{job_id}")
def list_job_packages(job_id: str) -> dict:
    """List all packages for a job, newest first."""
    packages = list_packages(job_id)
    return {
        "job_id": job_id,
        "packages": packages,
        "count": len(packages),
    }


@router.get("/{package_id}")
def get_one_package(package_id: str) -> dict:
    """Retrieve one package including the full stored package JSON."""
    pkg = get_package(package_id)
    if pkg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Package {package_id} not found")
    return pkg


@router.post("/{package_id}/certify")
def certify(package_id: str, payload: CertifyRequest) -> dict:
    """Certify a DRAFT/REVIEW package — the one-way finalization step.

    Runs the full pre-certification validation. If validation fails, the
    package is NOT certified and the blocking errors are returned as a
    422. On success the package transitions to CERTIFIED and becomes
    immutable.
    """
    summary = get_package_summary(package_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Package {package_id} not found")

    if summary["package_state"] not in ("DRAFT", "REVIEW"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Package {package_id} is {summary['package_state']} "
                    "and cannot be certified again."))

    package = get_package_for_update(package_id)
    if package is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reconstruct package {package_id} for certification")

    # Auto-populate metadata from DB; explicit payload fields win.
    job_id = summary["job_id"]
    metadata = _build_metadata_for_job(job_id, payload.metadata or {})

    try:
        certified = certify_package(package, metadata)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc))

    update_package_state(package_id, "CERTIFIED", certified)

    result = get_package(package_id) or {}
    prior_certified = [
        pkg for pkg in list_packages(job_id)
        if pkg["package_state"] == "CERTIFIED" and pkg["package_id"] != package_id
    ]

    try:
        provenance_mod.record_event(
            job_id,
            event_type="certification_frozen",
            title="Certification Frozen",
            detail=f"Package {package_id} certified from locked snapshot.",
            actor_type="system",
            source="packaging",
            metadata={
                "snapshot_id": result.get("snapshot_id") or summary.get("snapshot_id"),
                "manifest_hash": result.get("manifest_hash") or "",
                "included_exhibits": (
                    ((result.get("package") or {}).get("manifest") or {}).get("included_exhibits") or []
                ),
                "prior_certified_package_ids": [pkg["package_id"] for pkg in prior_certified],
            },
            related_snapshot_id=result.get("snapshot_id") or summary.get("snapshot_id") or "",
            related_package_id=package_id,
        )
        if prior_certified:
            provenance_mod.record_event(
                job_id,
                event_type="recertification_created",
                title="Recertification Created",
                detail=(
                    f"Certified new package {package_id} while preserving "
                    f"{len(prior_certified)} prior certified package(s)."
                ),
                actor_type="system",
                source="packaging",
                metadata={
                    "new_package_id": package_id,
                    "prior_certified_package_ids": [pkg["package_id"] for pkg in prior_certified],
                },
                related_snapshot_id=result.get("snapshot_id") or summary.get("snapshot_id") or "",
                related_package_id=package_id,
            )
    except Exception as exc:
        logger.warning(f"certification provenance record failed: {exc}")
    logger.info(
        f"Package {package_id} certified from snapshot "
        f"{result.get('snapshot_id') or summary.get('snapshot_id')}"
    )
    return {
        **result,
        "certified": True,
        "generation_report": certified.generation_report.to_dict(),
    }
