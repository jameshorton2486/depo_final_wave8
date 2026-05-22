"""Administrative page generators — Wave 20.

The five administrative pages, each a template-driven generator. Every
generator consumes *structured metadata* — never parsed transcript text
(review item 14). Each produces an AdministrativePage of semantic text
lines; physical geometry is applied later by the shared Wave 19
Geometry Layer.

Template wording below is the proposed standard Texas-UFM phrasing,
pending James's confirmation (plan Q20-2). It is data-driven so the
exact wording can be set precisely without touching assembly logic.

See docs/wave20_packaging.md section 6.
"""
from __future__ import annotations

from backend.packaging.model import (
    DEFAULT_TEMPLATE_VERSION,
    AdministrativePage,
    TranscriptIndex,
)


def _meta(metadata: dict, key: str, default: str = "") -> str:
    """A trimmed string metadata value, or the default when blank."""
    value = (metadata or {}).get(key)
    if value is None:
        return default
    return str(value).strip() or default


# --- Title / Caption page -------------------------------------------

def build_caption_page(metadata: dict) -> AdministrativePage:
    """The Title / Caption page — case style, cause number, court, date,
    location."""
    cause = _meta(metadata, "cause_number", "[CAUSE NUMBER]")
    caption = _meta(metadata, "caption", "[CASE STYLE]")
    court = _meta(metadata, "court", "[COURT]")
    witness = _meta(metadata, "witness_name", "[WITNESS]")
    date = _meta(metadata, "proceedings_date", "[DATE]")
    location = _meta(metadata, "location", "[LOCATION]")

    lines = [
        f"CAUSE NO. {cause}",
        "",
        caption.upper(),
        "",
        f"IN THE {court.upper()}",
        "",
        "ORAL AND VIDEOTAPED DEPOSITION OF",
        witness.upper(),
        date.upper(),
        "",
        f"Taken at {location}." if location else "",
    ]
    return AdministrativePage(
        kind="caption",
        title="Title Page",
        lines=[ln for ln in lines if ln != "" or True],
    )


# --- Appearances page -----------------------------------------------

def build_appearances_page(metadata: dict) -> AdministrativePage:
    """The Appearances page — attorneys, firms, parties represented.

    `appearances` is a list of dicts: {role, attorney, firm, party}.
    """
    lines = ["APPEARANCES", ""]
    appearances = (metadata or {}).get("appearances") or []

    if not appearances:
        lines.append("[No appearances recorded.]")
    for ap in appearances:
        role = str(ap.get("role", "")).strip().upper()
        attorney = str(ap.get("attorney", "")).strip()
        firm = str(ap.get("firm", "")).strip()
        party = str(ap.get("party", "")).strip()
        if role:
            lines.append(f"FOR THE {role}:")
        if attorney:
            lines.append(f"    {attorney}")
        if firm:
            lines.append(f"    {firm}")
        if party:
            lines.append(f"    On behalf of {party}")
        lines.append("")

    return AdministrativePage(
        kind="appearances", title="Appearances", lines=lines)


# --- Index pages ----------------------------------------------------

def _format_index(index: TranscriptIndex, heading: str) -> list[str]:
    """Render one TranscriptIndex into aligned text lines."""
    lines = [heading, ""]
    if not index.entries:
        lines.append("[No entries.]")
        return lines
    for entry in index.entries:
        ref = entry.reference or "(page pending)"
        detail = f" — {entry.detail}" if entry.detail else ""
        lines.append(f"{entry.label}{detail} .......... {ref}")
    return lines


def build_chronological_index_page(index: TranscriptIndex) -> AdministrativePage:
    """The chronological index page."""
    return AdministrativePage(
        kind="chronological_index",
        title="Chronological Index",
        lines=_format_index(index, "CHRONOLOGICAL INDEX"))


def build_witness_index_page(index: TranscriptIndex) -> AdministrativePage:
    """The alphabetical witness index page."""
    return AdministrativePage(
        kind="witness_index",
        title="Witness Index",
        lines=_format_index(index, "ALPHABETICAL INDEX OF WITNESSES"))


def build_exhibit_index_page(index: TranscriptIndex) -> AdministrativePage:
    """The exhibit index page."""
    return AdministrativePage(
        kind="exhibit_index",
        title="Exhibit Index",
        lines=_format_index(index, "INDEX OF EXHIBITS"))


# --- Corrections / Signature page -----------------------------------

def build_corrections_signature_page(metadata: dict) -> AdministrativePage:
    """The Corrections / Signature page — for freelance depositions; where
    the witness records changes and signs."""
    witness = _meta(metadata, "witness_name", "the witness")
    lines = [
        "CHANGES AND SIGNATURE",
        "",
        f"Witness: {witness}",
        "",
        "PAGE    LINE    CHANGE                          REASON",
        "____    ____    ______________________________  ____________",
        "____    ____    ______________________________  ____________",
        "____    ____    ______________________________  ____________",
        "",
        "I have read the foregoing deposition and hereby affix my",
        "signature that same is true and correct, except as noted above.",
        "",
        "                         ______________________________",
        f"                         {witness.upper()}",
    ]
    return AdministrativePage(
        kind="corrections_signature",
        title="Corrections and Signature",
        lines=lines)


# --- Reporter's Certificate page ------------------------------------

def build_certificate_page(
    metadata: dict,
    *,
    package_id: str = "",
    snapshot_id: str = "",
    state_hash: str = "",
    certification_id: str = "",
) -> AdministrativePage:
    """The Reporter's Certificate page — always the final page.

    The certificate binds to the package it certifies (review item 8 —
    Certificate Binding): it carries the package id, the transcript
    snapshot id, the state hash, and the certification id, so the
    certificate cannot be detached from the record it certifies.
    """
    reporter = _meta(metadata, "reporter_name", "[REPORTER NAME]")
    csr = _meta(metadata, "reporter_csr_number", "[CSR NUMBER]")
    csr_state = _meta(metadata, "reporter_csr_state", "Texas")
    witness = _meta(metadata, "witness_name", "the witness")

    lines = [
        "REPORTER'S CERTIFICATE",
        "",
        f"I, {reporter}, Certified Shorthand Reporter in and for the",
        f"State of {csr_state}, do hereby certify that the foregoing is a",
        f"true and correct transcript of the testimony of {witness},",
        "taken at the time and place set forth herein.",
        "",
        "I further certify that I am neither counsel for, related to,",
        "nor employed by any of the parties in this action, and have no",
        "financial interest in its outcome.",
        "",
        f"                         ______________________________",
        f"                         {reporter.upper()}, CSR No. {csr}",
        "",
        "— Certificate binding —",
        f"Package ID:        {package_id or '(assigned at certification)'}",
        f"Certification ID:  {certification_id or '(assigned at certification)'}",
        f"Snapshot ID:       {snapshot_id or '(unbound)'}",
        f"State hash:        {state_hash[:16] + '…' if state_hash else '(unbound)'}",
    ]
    return AdministrativePage(
        kind="certificate",
        title="Reporter's Certificate",
        lines=lines)


# A map for the template-versioning seam (review item 12). One version
# now; later UFM revisions register additional versions here.
ADMIN_TEMPLATE_VERSIONS: dict[str, str] = {
    "caption": DEFAULT_TEMPLATE_VERSION,
    "appearances": DEFAULT_TEMPLATE_VERSION,
    "chronological_index": DEFAULT_TEMPLATE_VERSION,
    "witness_index": DEFAULT_TEMPLATE_VERSION,
    "exhibit_index": DEFAULT_TEMPLATE_VERSION,
    "corrections_signature": DEFAULT_TEMPLATE_VERSION,
    "certificate": DEFAULT_TEMPLATE_VERSION,
}
