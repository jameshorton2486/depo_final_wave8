"""Administrative page generators -- Wave 20.

The five administrative pages, each a template-driven generator. Every
generator consumes *structured metadata* -- never parsed transcript
text. Each produces an AdministrativePage of semantic text lines;
physical geometry (the format box, line numbering) is applied later by
the shared Wave 19 Geometry Layer.

BLOCKER-3 RESOLVED: the caption, appearances, and certificate wording
below is the exact Texas statutory language (Tex. R. Civ. P. 203.2 /
203.3 and UFM Figures 3, 4, 8, 8A for freelance deposition records).

Data note: several statutory fields (time used per party, the officer's
charges, custodial attorney, SBOT numbers, firm registration, CSR
expiration) are not yet captured anywhere in the pipeline. Where a field
has no metadata value the generator renders a [BRACKETED] placeholder,
and the package is correctly held at DRAFT until the data is supplied.

See docs/wave20_packaging.md section 6.
"""
from __future__ import annotations

from backend.packaging.model import (
    DEFAULT_TEMPLATE_VERSION,
    AdministrativePage,
    TranscriptIndex,
)

_RULE = "-" * 60


def _meta(metadata: dict, key: str, default: str = "") -> str:
    """A trimmed string metadata value, or the default when blank."""
    value = (metadata or {}).get(key)
    if value is None:
        return default
    return str(value).strip() or default


# --- Title / Caption page -------------------------------------------

def _caption_row(left: str, right: str = "") -> str:
    """One row of the caption box: left text, the ')' boundary, right text."""
    return f"{left:<34})   {right}".rstrip()


def build_caption_page(metadata: dict) -> AdministrativePage:
    """The Title / Caption page -- Tex. R. Civ. P. 203 / UFM Figure 3."""
    cause = _meta(metadata, "cause_number", "[CAUSE NUMBER]")
    plaintiff = _meta(metadata, "plaintiff_names", "[PLAINTIFF NAME(S)]")
    defendant = _meta(metadata, "defendant_names", "[DEFENDANT NAME(S)]")
    county = _meta(metadata, "county", "[COUNTY]")
    district = _meta(metadata, "judicial_district", "[JUDICIAL DISTRICT]")
    witness = _meta(metadata, "witness_name", "[WITNESS NAME]")
    date = _meta(metadata, "proceedings_date", "[DATE OF DEPOSITION]")
    volume = _meta(metadata, "volume", "1")
    party = _meta(metadata, "party_at_instance", "[PARTY]")
    start_time = _meta(metadata, "start_time", "[START TIME]")
    end_time = _meta(metadata, "end_time", "[END TIME]")
    method = _meta(metadata, "deposition_method", "[METHOD]")
    reporter = _meta(metadata, "reporter_name", "[REPORTER NAME]")
    month = _meta(metadata, "proceedings_month", "[MONTH]")
    day = _meta(metadata, "proceedings_day", "[DAY]")
    year = _meta(metadata, "proceedings_year", "[YEAR]")

    lines = [
        f"CAUSE NO. {cause}",
        "",
        _caption_row(f"{plaintiff},", "IN THE DISTRICT COURT OF"),
        _caption_row(""),
        _caption_row("    Plaintiff,"),
        _caption_row(""),
        _caption_row("VS.", f"{county} COUNTY, TEXAS"),
        _caption_row(""),
        _caption_row(f"{defendant},"),
        _caption_row(""),
        _caption_row("    Defendant.", district),
        _RULE,
        "ORAL AND VIDEOTAPED DEPOSITION OF",
        witness.upper(),
        date,
        f"Volume {volume}",
        _RULE,
        "",
        (f"ORAL AND VIDEOTAPED DEPOSITION OF {witness.upper()}, produced "
         f"as a witness at the instance of the {party}, and duly sworn, "
         f"was taken in the above-styled and numbered cause on the {day} "
         f"of {month}, {year}, from {start_time} to {end_time}, via "
         f"{method}, before {reporter}, CSR in and for the State of "
         "Texas, reported/recorded by the aforementioned method, "
         "pursuant to the Texas Rules of Civil Procedure and the "
         "provisions stated on the record or attached hereto."),
    ]
    return AdministrativePage(
        kind="caption", title="Title Page", lines=lines)


# --- Appearances page -----------------------------------------------

def _appearance_block(ap: dict) -> list[str]:
    """One attorney appearance block in UFM order."""
    out: list[str] = []
    name = str(ap.get("attorney", "")).strip()
    firm = str(ap.get("firm", "")).strip()
    sbot = str(ap.get("sbot_no", "")).strip()
    address = str(ap.get("address", "")).strip()
    city = str(ap.get("city_state_zip", "")).strip()
    phone = str(ap.get("phone", "")).strip()
    party = str(ap.get("party", "")).strip()
    if name:
        out.append(f"    {name}")
    if firm:
        out.append(f"    {firm}")
    out.append(f"    SBOT NO. {sbot or '[########]'}")
    if address:
        out.append(f"    {address}")
    if city:
        out.append(f"    {city}")
    if phone:
        out.append(f"    Phone: {phone}")
    if party:
        out.append(f"    ATTORNEY FOR {party.upper()}")
    return out


def build_appearances_page(metadata: dict) -> AdministrativePage:
    """The Appearances page -- UFM Figure 4. Attorneys grouped by side,
    each block in statutory order (name, firm, SBOT, address, phone)."""
    lines = ["A P P E A R A N C E S", ""]
    appearances = (metadata or {}).get("appearances") or []

    if not appearances:
        lines.append("[No appearances recorded.]")
    else:
        for side, heading in (("plaintiff", "FOR THE PLAINTIFF(S):"),
                              ("defendant", "FOR THE DEFENDANT(S):")):
            side_aps = [a for a in appearances
                        if side in str(a.get("role", "")).lower()
                        or side in str(a.get("party", "")).lower()]
            if side_aps:
                lines.append(heading)
                for ap in side_aps:
                    lines.extend(_appearance_block(ap))
                    lines.append("")
        # Any appearance not classified to a side.
        other = [a for a in appearances
                 if not any(s in (str(a.get("role", "")) + str(
                     a.get("party", ""))).lower()
                     for s in ("plaintiff", "defendant"))]
        for ap in other:
            lines.append("FOR THE PARTY:")
            lines.extend(_appearance_block(ap))
            lines.append("")

    also_present = (metadata or {}).get("also_present") or []
    if also_present:
        lines.append("ALSO PRESENT:")
        for person in also_present:
            name = str(person.get("name", "")).strip()
            role = str(person.get("role", "")).strip()
            lines.append(f"    {name}, {role}" if role else f"    {name}")

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
        detail = f" - {entry.detail}" if entry.detail else ""
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
    """The Corrections / Signature page -- for freelance depositions."""
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
    """The Reporter's Certificate page -- Tex. R. Civ. P. 203.3 / UFM
    Figure 8. Always the final page.

    The certificate also binds to the package it certifies (package id,
    snapshot id, state hash, certification id) so it cannot be detached
    from the record it certifies.
    """
    reporter = _meta(metadata, "reporter_name", "[REPORTER NAME]")
    csr = _meta(metadata, "reporter_csr_number", "[CSR NUMBER]")
    witness = _meta(metadata, "witness_name", "[WITNESS NAME]")
    date = _meta(metadata, "proceedings_date", "[DATE]")
    disposition = _meta(metadata, "examination_disposition", "[waived/retained]")
    custodian = _meta(metadata, "custodial_attorney", "[CUSTODIAL ATTORNEY]")
    charges = _meta(metadata, "officer_charges_amount", "[AMOUNT]")
    charges_party = _meta(metadata, "charges_party", "[PARTY]")
    service_date = _meta(metadata, "certificate_service_date", "[DATE]")
    cert_day = _meta(metadata, "certified_day", "[DAY]")
    cert_month = _meta(metadata, "certified_month", "[MONTH]")
    cert_year = _meta(metadata, "certified_year", "[YEAR]")
    expiration = _meta(metadata, "reporter_csr_expiration", "[##/##/####]")
    firm_reg = _meta(metadata, "firm_registration_no", "[####]")
    firm_addr = _meta(metadata, "firm_address", "[FIRM ADDRESS]")
    firm_city = _meta(metadata, "firm_city_state_zip", "[CITY, STATE, ZIP]")

    lines = [
        "REPORTER'S CERTIFICATE",
        f"DEPOSITION OF {witness.upper()}",
        date,
        "",
        (f"I, {reporter}, Certified Shorthand Reporter in and for the "
         "State of Texas, hereby certify to the following:"),
        "",
        (f"That the witness, {witness.upper()}, was duly sworn by the "
         "officer and that the transcript of the oral deposition is a "
         "true record of the testimony given by the witness;"),
        "",
        ("That examination and signature of the witness to the "
         f"deposition transcript was {disposition} by the witness and "
         "agreement of the parties at the time of the deposition;"),
        "",
        ("That the original deposition was delivered to "
         f"{custodian};"),
        "",
        ("That the amount of time used by each party at the deposition "
         "is as follows:"),
    ]

    time_per_party = (metadata or {}).get("time_per_party") or []
    if time_per_party:
        for entry in time_per_party:
            who = str(entry.get("party", "")).strip()
            dur = str(entry.get("duration", "")).strip()
            lines.append(f"     {who} - {dur}")
    else:
        lines.append("     [TIME USED PER PARTY -- not yet captured]")

    lines += [
        "",
        (f"That ${charges} is the deposition officer's charges to the "
         f"{charges_party} for preparing the original deposition "
         "transcript and any copies of exhibits;"),
        "",
        ("That pursuant to information given to the deposition officer "
         "at the time said testimony was taken, the following includes "
         "counsel for all parties of record:"),
    ]

    counsel = (metadata or {}).get("counsel_of_record") or []
    if counsel:
        for c in counsel:
            name = str(c.get("name", "")).strip()
            role = str(c.get("role", "")).strip()
            lines.append(f"     {name}, {role}" if role else f"     {name}")
    else:
        lines.append("     [COUNSEL OF RECORD -- not yet captured]")

    lines += [
        "",
        ("That a copy of this certificate was served on all parties "
         f"shown herein on {service_date} and filed with the Clerk "
         "pursuant to Rule 203.3."),
        "",
        ("I further certify that I am neither counsel for, related to, "
         "nor employed by any of the parties or attorneys in the action "
         "in which this proceeding was taken, and further that I am not "
         "financially or otherwise interested in the outcome of the "
         "action."),
        "",
        f"Certified to by me this {cert_day} day of {cert_month}, {cert_year}.",
        "",
        "______________________________________",
        f"{reporter.upper()}, Texas CSR No. {csr}",
        f"Expiration Date: {expiration}",
        f"Firm Registration No. {firm_reg}",
        firm_addr,
        firm_city,
        "",
        "-- Certificate binding --",
        f"Package ID:        {package_id or '(assigned at certification)'}",
        f"Certification ID:  {certification_id or '(assigned at certification)'}",
        f"Snapshot ID:       {snapshot_id or '(unbound)'}",
        f"State hash:        {state_hash[:16] + '...' if state_hash else '(unbound)'}",
    ]
    return AdministrativePage(
        kind="certificate",
        title="Reporter's Certificate",
        lines=lines)


# A map for the template-versioning seam. One version now; later UFM
# revisions register additional versions here.
ADMIN_TEMPLATE_VERSIONS: dict[str, str] = {
    "caption": DEFAULT_TEMPLATE_VERSION,
    "appearances": DEFAULT_TEMPLATE_VERSION,
    "chronological_index": DEFAULT_TEMPLATE_VERSION,
    "witness_index": DEFAULT_TEMPLATE_VERSION,
    "exhibit_index": DEFAULT_TEMPLATE_VERSION,
    "corrections_signature": DEFAULT_TEMPLATE_VERSION,
    "certificate": DEFAULT_TEMPLATE_VERSION,
}
