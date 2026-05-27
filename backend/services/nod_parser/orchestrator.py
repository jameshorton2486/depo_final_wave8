"""Top-level NOD parser.

Combines Type A (firm scheduling form) + Type B (legal pleading) extractions
into a single canonical record matching the UFM field names the frontend uses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

import re
from backend.services.nod_parser import (
    intelligence,
    pdf_text,
    type_a_form,
    type_b_pleading,
)


@dataclass
class ParsedNOD:
    """Result of parsing one NOD packet."""

    # UFM-shaped flat fields (match the frontend's existing docFields keys)
    ufm_cause: Optional[str] = None
    ufm_style: Optional[str] = None
    ufm_court: Optional[str] = None
    ufm_county: Optional[str] = None
    ufm_state: str = "Texas"
    ufm_witness: Optional[str] = None
    ufm_date: Optional[str] = None
    ufm_start_time: Optional[str] = None
    ufm_end_time: Optional[str] = None
    ufm_address: Optional[str] = None
    ufm_custodial_name: Optional[str] = None
    ufm_requesting_party: Optional[str] = None

    # CSR fields stay blank — these aren't in the NOD itself
    ufm_csr_name: Optional[str] = None
    ufm_csr_license: Optional[str] = None
    ufm_firm_reg: Optional[str] = None
    ufm_csr_cert_exp: Optional[str] = None

    # Metadata
    detected_types: list[str] = field(default_factory=list)
    jurisdiction_type: str = "texas_state"
    location_type: str = "in_person"
    additional_sessions: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # --- Deepgram intelligence layer (kept separate from UFM metadata) ---
    # keyterms:        categorized ASR priming terms
    # speaker_hints:   name + role, for diarization / review labeling
    # deepgram_config: recommended Deepgram request settings
    keyterms: list[dict] = field(default_factory=list)
    speaker_hints: list[dict] = field(default_factory=list)
    deepgram_config: dict = field(default_factory=dict)

    # --- UFM metadata layer ---
    # appearances: structured attorney appearances for the UFM appearance page
    appearances: list[dict] = field(default_factory=list)

    def to_frontend_dict(self) -> dict:
        """Return the dict shape the frontend's existing field-population code expects."""
        fields = {
            "ufmCause": self.ufm_cause or "",
            "ufmStyle": self.ufm_style or "",
            "ufmCourt": self.ufm_court or "",
            "ufmCounty": self.ufm_county or "",
            "ufmState": self.ufm_state,
            "ufmWitness": self.ufm_witness or "",
            "ufmDate": self.ufm_date or "",
            "ufmStartTime": self.ufm_start_time or "",
            "ufmEndTime": self.ufm_end_time or "",
            "ufmAddress": self.ufm_address or "",
            "ufmCustodialName": self.ufm_custodial_name or "",
            "ufmRequestingParty": self.ufm_requesting_party or "",
            "ufmCSRName": self.ufm_csr_name or "",
            "ufmCSRLicense": self.ufm_csr_license or "",
            "ufmFirmReg": self.ufm_firm_reg or "",
            "ufmCSRCertExp": self.ufm_csr_cert_exp or "",
        }
        field_sources = {k: "nod_parser" for k, v in fields.items() if v}
        return {
            "fields": fields,
            "metadata": {
                "detected_types": self.detected_types,
                "jurisdiction_type": self.jurisdiction_type,
                "location_type": self.location_type,
                "additional_sessions": self.additional_sessions,
                "warnings": self.warnings,
                "field_sources": field_sources,
            },
            # --- Deepgram intelligence list ---
            "keyterms": self.keyterms,
            "speaker_hints": self.speaker_hints,
            "deepgram_config": self.deepgram_config,
            # --- UFM metadata list ---
            "appearances": self.appearances,
        }

    def to_canonical(self):
        """Return this parse result as canonical models.

        The parsing logic is unchanged — this is purely a serializer that
        re-shapes the already-extracted fields into the canonical vocabulary
        (CaseIdentity / DepositionSession / ReporterCredentials / Participant
        / KeyTerm). Callers that want typed, validated output use this;
        callers that want the legacy flat dict keep using to_frontend_dict().
        """
        from backend.models.canonical import (
            CaseIdentity,
            DepositionSession,
            KeyTerm,
            Participant,
            ReporterCredentials,
        )

        identity = CaseIdentity(
            case_number_value=self.ufm_cause,
            jurisdiction_type=self.jurisdiction_type
            if self.jurisdiction_type in ("federal", "texas_state", "other")
            else "other",
            caption_full=self.ufm_style,
            judicial_district=self.ufm_court if self.jurisdiction_type != "federal" else None,
            court_district=self.ufm_court if self.jurisdiction_type == "federal" else None,
            county=self.ufm_county,
            state=self.ufm_state or "Texas",
        )
        session = DepositionSession(
            witness_name=self.ufm_witness,
            deposition_date=self.ufm_date,
            start_time=self.ufm_start_time,
            end_time=self.ufm_end_time,
            location_type=self.location_type
            if self.location_type in ("zoom", "in_person", "hybrid", "phone", "unknown")
            else "unknown",
            location_address=self.ufm_address,
        )
        reporter = ReporterCredentials(
            officer_name=self.ufm_csr_name,
            csr_license=self.ufm_csr_license,
            firm_registration=self.ufm_firm_reg,
            license_expiration=self.ufm_csr_cert_exp,
        )
        participants: list[Participant] = []
        if self.ufm_custodial_name:
            participants.append(Participant(
                role="custodial_attorney",
                name=self.ufm_custodial_name,
                firm=self.ufm_requesting_party,
            ))
        if self.ufm_witness:
            participants.append(Participant(role="deponent", name=self.ufm_witness))

        keyterms: list[KeyTerm] = []
        for kt in self.keyterms:
            src = kt.get("source", "nod_parser")
            if src not in ("nod_parser", "text_parser", "learned", "manual"):
                src = "nod_parser"
            keyterms.append(KeyTerm(
                term=kt.get("term", ""),
                boost=kt.get("boost", 1.0),
                category=kt.get("category", "Term"),
                source=src,
            ))

        return {
            "identity": identity,
            "session": session,
            "reporter": reporter,
            "participants": participants,
            "keyterms": keyterms,
        }


def parse(source: Union[str, bytes]) -> ParsedNOD:
    """Parse a NOD packet (path or bytes).

    Strategy:
      1. Extract text per page.
      2. Run Type A form parser on each page (the form is usually page 1).
      3. Run Type B legal-pleading parser on the full text (pleading spans pages).
      4. Merge with Type B winning for canonical case fields.
      5. Build keyterms list from extracted names.
    """
    pages = pdf_text.extract_pages(source)
    full_text = "\n\n".join(pages)
    parsed = ParsedNOD()

    # --- Type A: try each page; merge results (last non-empty wins) ---
    type_a_data: dict = {}
    for page_text in pages:
        if type_a_form.looks_like_type_a(page_text):
            parsed.detected_types.append("s_a_legal_form")
            type_a_data = type_a_form.parse(page_text)
            break

    # --- Type B: parse full text (one or many depositions) ---
    type_b_records = type_b_pleading.parse(full_text)
    if type_b_records and any(r.get("case_number_value") for r in type_b_records):
        parsed.detected_types.append("legal_pleading")

    # Use the FIRST notice as the primary record; flag additional ones
    primary: dict = type_b_records[0] if type_b_records else {}
    if len(type_b_records) > 1:
        for extra in type_b_records[1:]:
            parsed.additional_sessions.append({
                "witness_name": extra.get("witness_name"),
                "date_iso": extra.get("date_iso"),
                "start_time": extra.get("start_time"),
            })
        parsed.warnings.append(
            f"This packet contains {len(type_b_records)} depositions. "
            f"Imported the first ({primary.get('witness_name') or 'unknown deponent'}); "
            f"others can be added as additional sessions on this case."
        )

    # --- Build the canonical field set (Type B wins, Type A fills gaps) ---
    parsed.ufm_cause = primary.get("case_number_value") or None
    parsed.ufm_style = primary.get("caption_full") or _build_caption_from_form(type_a_data)
    parsed.jurisdiction_type = primary.get("jurisdiction_type", "texas_state")
    parsed.ufm_state = primary.get("state", "Texas")

    # Court / district / county wording differs by jurisdiction
    if parsed.jurisdiction_type == "federal":
        district = primary.get("court_district") or ""
        division = primary.get("court_division") or _extract_division(full_text) or ""
        court_parts = ["United States District Court"]
        if district:
            court_parts.append(district)
        if division:
            court_parts.append(division)
        parsed.ufm_court = ", ".join(court_parts)
        parsed.ufm_county = None  # Federal has no county of venue
    else:
        parsed.ufm_court = primary.get("judicial_district") or None
        parsed.ufm_county = primary.get("county") or None

    parsed.ufm_witness = primary.get("witness_name") or type_a_data.get("deponent")
    parsed.ufm_date = primary.get("date_iso") or _form_date_to_iso(type_a_data.get("form_date_raw"))
    parsed.ufm_start_time = primary.get("start_time") or type_a_data.get("form_start_time")

    loc_type = primary.get("location_type") or "in_person"

    # If Type A says Zoom (CSR Yes + 'via Zoom' in location_raw), inherit that
    if loc_type == "in_person":
        ta_loc = (type_a_data.get("location_raw") or "").lower()
        if "zoom" in ta_loc or "remote" in ta_loc:
            loc_type = "zoom"

    parsed.location_type = loc_type

    # Address: prefer Type B's authoritative location. Fall back to Type A
    # ONLY if it's a non-date, non-empty value.
    ta_addr = type_a_data.get("location_raw") or ""
    ta_addr_is_date = bool(re.fullmatch(r"\s*\d{1,2}/\d{1,2}/\d{2,4}\s*", ta_addr))
    parsed.ufm_address = primary.get("location_raw") or (ta_addr if not ta_addr_is_date else None)

    # Custodial attorney and firm: prefer Type B signature block, fall back to Type A
    signing = type_b_pleading.extract_signing_attorney(full_text)
    parsed.ufm_custodial_name = (
        signing.get("custodial_name")
        or type_a_data.get("ordering_attorney")
    )
    parsed.ufm_requesting_party = (
        signing.get("requesting_party")
        or type_a_data.get("ordering_firm")
    )

    # --- Deepgram intelligence layer ----------------------------------
    # All attorney appearances from the pleading (signature block + the
    # "TO: ... attorney of record" line) -- the reliable source for
    # names and firms, since the scheduling form's column layout makes
    # its copy-attorney fields unreliable.
    parsed.appearances = type_b_pleading.extract_appearances(full_text)
    firms = type_b_pleading.extract_all_firms(full_text)
    plaintiff = type_b_pleading._extract_plaintiff(full_text)
    defendant_block = type_b_pleading._extract_defendant(full_text)
    cities = _extract_cities(full_text)
    division = primary.get("court_division") or _extract_division(full_text)

    parsed.keyterms = intelligence.build_keyterms(
        deponent=parsed.ufm_witness,
        plaintiff=plaintiff,
        defendant_block=defendant_block,
        appearances=parsed.appearances,
        firms=firms,
        ordered_by=type_a_data.get("ordered_by"),
        cities=cities,
        court_district=primary.get("court_district"),
        court_division=division,
        cause_number=parsed.ufm_cause,
    )
    parsed.speaker_hints = intelligence.build_speaker_hints(
        deponent=parsed.ufm_witness,
        appearances=parsed.appearances,
    )
    parsed.deepgram_config = dict(intelligence.RECOMMENDED_DEEPGRAM_CONFIG)

    return parsed


def _extract_division(text: str) -> Optional[str]:
    """Find a federal court division name (e.g. 'San Antonio Division').

    Anchored to a single line so it cannot span the multi-line court
    header ('UNITED STATES DISTRICT COURT / WESTERN DISTRICT OF TEXAS').
    """
    m = re.search(
        r"^[ \t]*([A-Z][A-Za-z. ]+?)[ \t]+DIVISION[ \t]*$", text, re.MULTILINE
    )
    if not m:
        return None
    name = m.group(1).strip()
    if name.upper() in ("JUDICIAL", "STATES", "THE", "DISTRICT"):
        return None
    if name.isupper():
        name = name.title()
    return f"{name} Division"


def _extract_cities(text: str) -> list[str]:
    """Texas cities mentioned in the document, for geographic keyterms."""
    cities: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(
        r"\b([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)?)[ \t]*,?[ \t]+(?:TX|Texas)\b", text
    ):
        city = m.group(1).strip()
        if city.lower() not in seen and len(city) > 2:
            seen.add(city.lower())
            cities.append(city)
    return cities


def _build_caption_from_form(type_a_data: dict) -> Optional[str]:
    """Fallback: use Type A's 'Case/Style:' field if Type B couldn't parse the header."""
    cs = type_a_data.get("case_style")
    if not cs:
        return None
    # Form often has 'Foo v. Bar' lowercase — pleading uses 'FOO vs. BAR'
    return cs


def _form_date_to_iso(raw: Optional[str]) -> Optional[str]:
    """Convert '4/30/2026' to '2026-04-30'."""
    if not raw:
        return None
    parts = raw.strip().split("/")
    if len(parts) != 3:
        return None
    try:
        month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
        if year < 100:
            year += 2000
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
        return None

