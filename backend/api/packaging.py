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
from pydantic import BaseModel

from backend.packaging import (
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
from backend.transcript_state import snapshot_repo

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

            # Appearances and counsel of record from case_attorneys
            _populate_appearances(meta, case_id)

    # --- Session --------------------------------------------------------
    if session_id:
        session = dbrepo.get_session(session_id)
        if session:
            meta["witness_name"] = session.get("witness_name") or ""
            meta["party_at_instance"] = session.get("requesting_party_name") or ""
            meta["custodial_attorney"] = session.get("custodial_attorney_name") or ""

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

def _build_paginated_for_job(job_id: str, job_row: dict):
    """Return a PaginatedDocument for a job's current working state.

    Runs the same Stage S pipeline as the export-preview endpoint so the
    packaging engine receives the same body the exporter would write.
    Returns None when the transcript body is empty (no utterances).
    """
    from backend.stage_s.renderer import render_stage_s
    from backend.transcript.export_render import render_export_with_layout

    utterances = trepo.get_utterances(job_id) or []
    participants = trepo.get_participants(job_id) or []

    # Stage S structural render
    stage_s = render_stage_s(utterances, participants)

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
    return paginated


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
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found")

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

    job_row = trepo.get_job(job_id) or {}

    # Build the paginated body from the job's working lines.
    try:
        paginated = _build_paginated_for_job(job_id, job_row)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to paginate transcript for packaging: {exc}")

    # Auto-populate metadata from DB; explicit payload fields win.
    metadata = _build_metadata_for_job(job_id, payload.metadata or {})

    # Assemble the package using the Wave 20 engine.
    package = assemble_package(
        snapshot_id=snap.snapshot_id,
        state_hash=snap.state_hash,
        metadata=metadata,
        index_inputs=IndexInputs(),  # empty by default; caller may extend
        paginated_document=paginated,
        freelance=payload.freelance,
    )

    # Persist and return.
    summary = save_package(package, job_id)
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
    return {
        **result,
        "certified": True,
        "generation_report": certified.generation_report.to_dict(),
    }
