"""Intake text parser.

Parses free-text scheduling notes (the kind a court reporter types or
pastes from a scheduling email) into UFM fields. This is the engine
behind the "Run Text Parser on Pasted Notes" button on Stage 1.

It is deliberately complementary to the NOD PDF parser:
  - The NOD parser reads a formal Notice of Deposition PDF.
  - This parser reads informal labelled notes ("Court Reporter: ...",
    "Deposition location: ...", "Acoustic spellings to sync: ...").

A parser can only extract what is actually present in the text. Fields
not mentioned in the notes are simply left blank — the parser fills
gaps, it never invents data.

Output shape matches the NOD parser's `to_frontend_dict()` so the
frontend can reuse the same field-application code.
"""
from __future__ import annotations

import re
from typing import Optional

from backend.services import keyterms as keyterms_mod

# --- Label → field mapping -------------------------------------------

# Each entry: list of label spellings → the UFM field id it populates.
# Labels are matched case-insensitively at the start of a line or after
# a sentence boundary.
_LABEL_MAP: dict[str, tuple[str, ...]] = {
    "ufmCause": ("cause number", "cause no", "cause"),
    "ufmCourt": ("court", "judicial district"),
    "ufmCounty": ("county of venue", "county"),
    "ufmState": ("state",),
    "ufmStyle": ("case style", "case caption", "caption", "style"),
    "ufmWitness": ("deponent name", "witness name", "deponent", "witness"),
    "ufmDate": ("deposition date", "date"),
    "ufmStartTime": ("start time", "time"),
    "ufmEndTime": ("end time",),
    "ufmAddress": ("deposition location", "deposition address", "location", "address"),
    "ufmCustodialName": ("custodial attorney", "ordering attorney"),
    "ufmRequestingParty": ("requesting party", "requesting firm"),
    "ufmCSRName": ("court reporter", "csr officer", "reporter"),
}

_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december")
_MONTH_TO_NUM = {m: i for i, m in enumerate(_MONTHS, 1)}


def _normalize_date(raw: str) -> Optional[str]:
    """Convert a date string to ISO YYYY-MM-DD. Accepts several formats."""
    raw = raw.strip()
    # Already ISO
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw):
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # M/D/YYYY or M/D/YY
    if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", raw):
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        return f"{year:04d}-{month:02d}-{day:02d}"
    # Month D, YYYY
    if m := re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", raw):
        month = _MONTH_TO_NUM.get(m.group(1).lower())
        if month:
            return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(2)):02d}"
    return None


def _normalize_time(raw: str) -> Optional[str]:
    """Convert a time string to 'H:MM AM/PM'."""
    raw = raw.strip()
    if m := re.match(r"(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?", raw, re.IGNORECASE):
        return f"{int(m.group(1))}:{m.group(2)} {m.group(3).upper()}M"
    if m := re.match(r"(\d{1,2})\s*([ap])\.?\s*m\.?", raw, re.IGNORECASE):
        return f"{int(m.group(1))}:00 {m.group(2).upper()}M"
    return None


def _split_into_segments(text: str) -> list[str]:
    """Split notes into labelled segments. Each line is one segment, but a
    single line may also contain several 'Label: value' pairs."""
    segments: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            segments.append(line)
    return segments


def _find_label(segment: str) -> Optional[tuple[str, str]]:
    """If a segment starts with a known label, return (field_id, value)."""
    m = re.match(r"\s*([A-Za-z][A-Za-z /]+?)\s*:\s*(.+)$", segment)
    if not m:
        return None
    label_raw = m.group(1).strip().lower()
    value = m.group(2).strip().rstrip(".")
    for field_id, spellings in _LABEL_MAP.items():
        if label_raw in spellings:
            return (field_id, value)
    return None


# --- Embedded sub-field extractors -----------------------------------

_RE_CSR_LICENSE = re.compile(
    r"(?:CSR\s+)?License\s*#?\s*:?\s*([A-Z0-9\-]+)", re.IGNORECASE
)
_RE_FIRM_REG = re.compile(
    r"Firm\s+Registration\s*#?\s*:?\s*([A-Z0-9\-]+)", re.IGNORECASE
)
_RE_EXPIRATION = re.compile(
    r"(?:expiration|expires?|cert\.?\s*exp\.?)\s*:?\s*"
    r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)
_RE_REPRESENTING = re.compile(
    r"representing\s+(?:Plaintiff|Defendant|Petitioner|Respondent)?\s*(.+)$",
    re.IGNORECASE,
)


def _parse_court_reporter_line(value: str) -> dict:
    """The 'Court Reporter:' line often packs name + license + expiration
    + firm registration into one comma-separated string."""
    out: dict = {}

    # CSR name: everything before the first comma or before 'CSR License'
    name_part = re.split(r",|\bCSR\s+License\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
    name_part = name_part.strip().rstrip(",")
    if name_part:
        out["ufmCSRName"] = name_part

    if m := _RE_CSR_LICENSE.search(value):
        out["ufmCSRLicense"] = m.group(1).strip()
    if m := _RE_FIRM_REG.search(value):
        out["ufmFirmReg"] = m.group(1).strip()
    if m := _RE_EXPIRATION.search(value):
        iso = _normalize_date(m.group(1))
        if iso:
            out["ufmCSRCertExp"] = iso
    return out


def _parse_custodial_attorney_line(value: str) -> dict:
    """The 'Custodial Attorney:' line may include 'representing Plaintiff X'."""
    out: dict = {}
    # Attorney name: everything before 'representing'
    name_part = re.split(r"\brepresenting\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
    name_part = name_part.strip().rstrip(",")
    if name_part:
        out["ufmCustodialName"] = name_part
    # The represented party — captured as a keyterm candidate, not a field
    if m := _RE_REPRESENTING.search(value):
        party = m.group(1).strip().rstrip(".")
        if party:
            out["_represented_party"] = _titlecase_name(party)
    return out


def _titlecase_name(s: str) -> str:
    """Title-case a name while leaving all-caps acronyms alone."""
    parts = []
    for p in s.split():
        if len(p) <= 3 and p.isupper():
            parts.append(p)
        else:
            parts.append(p[:1].upper() + p[1:] if p else p)
    return " ".join(parts)


# --- Acoustic spellings / explicit keyterm lines ---------------------

_RE_ACOUSTIC_LINE = re.compile(
    r"(?:acoustic\s+spellings?(?:\s+to\s+sync)?|terms?\s+to\s+sync|"
    r"keyterms?|terminology)\s*:\s*(.+)$",
    re.IGNORECASE,
)


def _extract_explicit_keyterms(text: str) -> list[str]:
    """Pull terms from an explicit 'Acoustic spellings to sync: a, b, c' line."""
    found: list[str] = []
    for line in text.splitlines():
        if m := _RE_ACOUSTIC_LINE.search(line.strip()):
            raw = m.group(1).strip().rstrip(".")
            for term in re.split(r"[,;]", raw):
                term = term.strip()
                if term:
                    found.append(term)
    return found


# --- Main entry point ------------------------------------------------

def parse_intake_text(text: str) -> dict:
    """Parse pasted intake notes. Returns {fields, metadata, keyterms}."""
    fields: dict[str, str] = {}
    field_sources: dict[str, str] = {}
    warnings: list[str] = []

    if not text or not text.strip():
        return {
            "fields": {},
            "metadata": {"detected_types": [], "warnings": ["No text provided."],
                         "field_sources": {}},
            "keyterms": [],
        }

    explicit_terms = _extract_explicit_keyterms(text)
    represented_party: Optional[str] = None

    for segment in _split_into_segments(text):
        labelled = _find_label(segment)
        if not labelled:
            continue
        field_id, value = labelled

        # Special handling for packed lines
        if field_id == "ufmCSRName":
            for k, v in _parse_court_reporter_line(value).items():
                fields.setdefault(k, v)
                field_sources.setdefault(k, "text_parser")
            continue
        if field_id == "ufmCustodialName":
            parsed = _parse_custodial_attorney_line(value)
            if "_represented_party" in parsed:
                represented_party = parsed.pop("_represented_party")
            for k, v in parsed.items():
                fields.setdefault(k, v)
                field_sources.setdefault(k, "text_parser")
            continue

        # Normalize specific field types
        if field_id == "ufmDate":
            iso = _normalize_date(value)
            if iso:
                fields.setdefault(field_id, iso)
                field_sources.setdefault(field_id, "text_parser")
            continue
        if field_id in ("ufmStartTime", "ufmEndTime"):
            t = _normalize_time(value)
            if t:
                fields.setdefault(field_id, t)
                field_sources.setdefault(field_id, "text_parser")
            continue

        # Generic: take the value as-is
        fields.setdefault(field_id, value)
        field_sources.setdefault(field_id, "text_parser")

    # --- Build keyterms -------------------------------------------------
    keyterm_objs: list[dict] = []
    seen: set[str] = set()

    def add_term(term: str, boost: float, category: str, source: str):
        term = (term or "").strip()
        if not term or term.lower() in seen:
            return
        seen.add(term.lower())
        keyterm_objs.append({
            "term": term, "boost": boost, "category": category, "source": source,
        })

    # Explicit acoustic spellings — highest intent, boost 1.5
    for term in keyterms_mod.clean_keyterms(explicit_terms):
        add_term(term, 1.5, "Term", "text_parser")

    # Named entities pulled from field values
    if fields.get("ufmCSRName"):
        add_term(fields["ufmCSRName"], 1.2, "Reporter", "text_parser")
    if fields.get("ufmCustodialName"):
        add_term(fields["ufmCustodialName"], 1.2, "Attorney", "text_parser")
    if fields.get("ufmRequestingParty"):
        add_term(fields["ufmRequestingParty"], 1.0, "Firm", "text_parser")
    if fields.get("ufmWitness"):
        add_term(fields["ufmWitness"], 1.5, "Deponent", "text_parser")
    if represented_party:
        add_term(represented_party, 1.0, "Party", "text_parser")

    detected = ["intake_notes"] if fields or keyterm_objs else []
    if not fields:
        warnings.append(
            "No recognizable labelled fields were found. Use labels like "
            "'Cause No:', 'Deponent:', 'Court Reporter:', 'Deposition location:'."
        )

    return {
        "fields": fields,
        "metadata": {
            "detected_types": detected,
            "warnings": warnings,
            "field_sources": field_sources,
        },
        "keyterms": keyterm_objs,
    }
