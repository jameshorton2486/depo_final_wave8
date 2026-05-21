"""Type B: the legal pleading body of the NOD.

Tightened against real-document failures from:
  01_brain_spine_federal.pdf, 02_israel_garcia_state.pdf,
  03_goldman_peterson_multi.pdf, 04_marynell_video_form.pdf
"""
from __future__ import annotations

import re
from typing import Optional

_RE_FEDERAL_HEADER = re.compile(r"UNITED\s+STATES\s+DISTRICT\s+COURT", re.IGNORECASE)


def detect_jurisdiction(text: str) -> str:
    if not text:
        return "other"
    if _RE_FEDERAL_HEADER.search(text):
        return "federal"
    if re.search(r"\bJUDICIAL\s+DISTRICT\b", text, re.IGNORECASE) and re.search(
        r"\bCOUNTY,?\s+TEXAS\b", text, re.IGNORECASE
    ):
        return "texas_state"
    return "other"


# --- Case identity ---------------------------------------------------

_RE_CIVIL_ACTION = re.compile(
    r"CIVIL\s+ACTION\s+NO\.?[:\s]+(\d{2,4}-cv-\d{3,6}(?:-[A-Z]+)?)", re.IGNORECASE
)
_RE_CAUSE_NO = re.compile(r"CAUSE\s+NO\.?\s*([A-Z0-9\-]+)", re.IGNORECASE)
_RE_JUDICIAL_DISTRICT = re.compile(
    r"(\d+)\s*(?:ST|ND|RD|TH)?\s*JUDICIAL\s+DISTRICT", re.IGNORECASE
)
_RE_COUNTY = re.compile(r"\b([A-Z][A-Z]+)\s+COUNTY,?\s+TEXAS\b", re.IGNORECASE)
_RE_FEDERAL_DISTRICT = re.compile(
    r"\b(WESTERN|EASTERN|NORTHERN|SOUTHERN)\s+DISTRICT\s+OF\s+TEXAS\b", re.IGNORECASE
)
_RE_FEDERAL_DIVISION = re.compile(r"^([A-Z][A-Z\s]+?)\s+DIVISION\s*$", re.MULTILINE)


def _ordinal_suffix(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def extract_case_identity(text: str) -> dict:
    out: dict = {}
    jurisdiction = detect_jurisdiction(text)
    out["jurisdiction_type"] = jurisdiction

    if jurisdiction == "federal":
        if m := _RE_CIVIL_ACTION.search(text):
            out["case_number_value"] = m.group(1).strip()
            out["case_number_label"] = "civil_action_no"
        if m := _RE_FEDERAL_DISTRICT.search(text):
            out["court_district"] = f"{m.group(1).title()} District of Texas"
        if m := _RE_FEDERAL_DIVISION.search(text):
            division = m.group(1).strip()
            if "JUDICIAL" not in division.upper() and "STATES" not in division.upper():
                out["court_division"] = f"{division.title()} Division"
    else:
        if m := _RE_CAUSE_NO.search(text):
            out["case_number_value"] = m.group(1).strip()
            out["case_number_label"] = "cause_no"
        if m := _RE_JUDICIAL_DISTRICT.search(text):
            num = m.group(1)
            out["judicial_district"] = f"{num}{_ordinal_suffix(int(num))} Judicial District"
        if m := _RE_COUNTY.search(text):
            out["county"] = m.group(1).title() + " County"

    out["state"] = "Texas"
    return out


# --- Caption ---------------------------------------------------------

_NOISE_LINE_RE = re.compile(
    r"^\s*(?:IN\s+THE\s+(?:UNITED\s+STATES\s+)?DISTRICT\s+COURT|"
    r"\d+(?:ST|ND|RD|TH)?\s+JUDICIAL\s+DISTRICT|"
    r"(?:OF\s+)?[A-Z]+\s+COUNTY,?\s+TEXAS|"
    r"§+|"
    r"WESTERN\s+DISTRICT\s+OF\s+TEXAS|EASTERN\s+DISTRICT\s+OF\s+TEXAS|"
    r"NORTHERN\s+DISTRICT\s+OF\s+TEXAS|SOUTHERN\s+DISTRICT\s+OF\s+TEXAS|"
    r"SAN\s+ANTONIO\s+DIVISION|HOUSTON\s+DIVISION|DALLAS\s+DIVISION|"
    r"CIVIL\s+ACTION\s+NO\.|CAUSE\s+NO\.)\s*$",
    re.IGNORECASE,
)


def _clean_party(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        line = re.sub(r"§+", "", line).strip().rstrip(",")
        if not line:
            continue
        if _NOISE_LINE_RE.match(line):
            continue
        if re.fullmatch(r"[A-Z\s.\d]+(?:cv|CV)-\d+(?:-[A-Z]+)?", line):
            continue  # federal cause number leaked in
        if re.fullmatch(r"[A-Z]+-\d+-\d+(?:-[A-Z]+)?", line):
            continue  # state cause number leaked in
        # Reject very short single-token lines (likely cause-number trailing letter, page break, etc.)
        if len(line.strip()) < 3 and not re.search(r"[A-Z]{3,}", line):
            continue
        lines.append(line)
    while lines and lines[-1].upper() in {"AND", "&", ""}:
        lines.pop()
    text = " ".join(lines)
    text = re.sub(r"\s+AND\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip().rstrip(",").strip()
    return text


def _extract_plaintiff(text: str) -> Optional[str]:
    # Include curly apostrophes (\u2019) — appear in real documents like 'WOMEN\u2019S HEALTH'
    name_chars = r"[A-Z][A-Z.,&'\u2019 \t\-]*"
    for pattern in (
        # Multi-line FIRST (so we capture full multi-plaintiff blocks like Goldman)
        re.compile(
            rf"((?:{name_chars}\n){{2,4}})\s*(?:Plaintiff[s]?,?|PLAINTIFF[S]?)\s*\n",
            re.MULTILINE,
        ),
        # Single-line fallback: 'NAME,\nPLAINTIFF\n' or 'NAME\nPlaintiff,\n'
        re.compile(rf"^({name_chars})\s*\n\s*(?:Plaintiff[s]?,?|PLAINTIFF[S]?)\s*\n", re.MULTILINE),
    ):
        for m in pattern.finditer(text):
            cleaned = _clean_party(m.group(1))
            if _is_court_noise(cleaned):
                continue
            if cleaned and len(cleaned) > 2:
                return cleaned
    return None


def _is_court_noise(s: str) -> bool:
    """True if the cleaned party value is actually court-header text."""
    if not s:
        return True
    upper = s.upper()
    for noise in (
        "DISTRICT COURT", "JUDICIAL DISTRICT", "WESTERN DISTRICT",
        "EASTERN DISTRICT", "NORTHERN DISTRICT", "SOUTHERN DISTRICT",
        "UNITED STATES", "COUNTY, TEXAS",
    ):
        if noise in upper:
            # Allow if it appears as a small fraction (e.g. company name contains 'COURT')
            if len(s) > len(noise) * 3:
                continue
            return True
    return False


def _extract_defendant(text: str) -> Optional[str]:
    name_chars = r"[A-Z][A-Z0-9.,/()&'\u2019 \t\-]*"
    for pattern in (
        # Federal/Israel Garcia: 'vs. NAME ... Defendant'
        re.compile(
            rf"(?:vs?\.[ \t]*|v\.[ \t]+)"
            r"(?:CIVIL\s+ACTION\s+NO\.[^\n]*\n)?"
            rf"((?:(?:{name_chars}|[ \t]*)\n){{1,8}})"
            r"\s*(?:Defendant|DEFENDANT)",
            re.IGNORECASE | re.MULTILINE,
        ),
        # Multi-line with possible blank lines between name lines (Marynell, Goldman)
        re.compile(
            rf"v\.?[ \t]*\n"
            rf"((?:(?:{name_chars}|[ \t]*)\n){{1,12}})"
            r"\s*(?:Defendant|DEFENDANT)",
            re.IGNORECASE | re.MULTILINE,
        ),
    ):
        if m := pattern.search(text):
            cleaned = _clean_party(m.group(1))
            if cleaned and not _is_court_noise(cleaned):
                return cleaned
    return None


def _strip_section_columns(text: str) -> str:
    """Remove '§ ...' right-column text from each line. Some PDFs render the
    caption table with the court header text on the same lines as party names,
    joined by section symbols (e.g. 'HANNAH K. CHRESTMAN, § IN THE DISTRICT COURT').
    """
    lines = []
    for line in text.split("\n"):
        # Split at the first § occurrence and keep only the left side
        if "§" in line:
            line = line.split("§")[0]
        lines.append(line.rstrip())
    return "\n".join(lines)


def extract_caption(text: str) -> Optional[str]:
    # First try with §-column stripping (Marynell-style PDFs)
    stripped = _strip_section_columns(text)
    plaintiff = _extract_plaintiff(stripped) or _extract_plaintiff(text)
    defendant = _extract_defendant(stripped) or _extract_defendant(text)
    if plaintiff and defendant:
        return f"{plaintiff} vs. {defendant}"
    return None


# --- Witness / deponent ----------------------------------------------

_RE_DEPONENT_PATTERNS = (
    re.compile(r"Deponent:\s*([^\n]+?)\s*\n", re.IGNORECASE),
    re.compile(
        r"(?:oral\s+(?:and\s+(?:video|trial)\s+)*)?deposition\s+of\s+"
        r"([A-Z][A-Z'\s.]+?(?:,?\s*M\.?D\.?)?)"
        r"(?=\s*(?:,?\s*and(?:/or)?|\s+will\s+be|\s+\(|\s+WITH\s+|\s+AND\s+DUCES))",
        re.IGNORECASE,
    ),
)


def _clean_deponent(name: str) -> str:
    if not name:
        return ""
    s = re.sub(r"\s+", " ", name).strip().rstrip(",.")
    s = re.sub(r"\s*\(\d{1,2}\s*[ap]m\)\s*", "", s, flags=re.IGNORECASE)
    if s.upper() in {"DEFENDANT", "PLAINTIFF", "DEFENDANTS", "PLAINTIFFS"}:
        return ""
    if s.isupper() or s == s.upper():
        parts = []
        for p in s.split():
            if p.upper().strip(",.") in {"MD", "M.D.", "M.D", "PHD", "ESQ", "JR", "SR", "II", "III"}:
                parts.append(p)
            else:
                parts.append(p.title())
        s = " ".join(parts)
    return s


def extract_deponents(text: str) -> list[str]:
    seen, found = set(), []
    for pattern in _RE_DEPONENT_PATTERNS:
        for m in pattern.finditer(text):
            name = _clean_deponent(m.group(1))
            if name and name.lower() not in seen and len(name) >= 3:
                seen.add(name.lower())
                found.append(name)
    return found


# --- Date / time -----------------------------------------------------

_MONTHS = ("January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December")
_MONTH_PATTERN = "|".join(_MONTHS)
_MONTH_TO_NUM = {m.lower(): i for i, m in enumerate(_MONTHS, 1)}

_RE_DATE_PATTERNS = (
    re.compile(
        rf"Date:\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?\s*"
        rf"({_MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(\d{{4}})", re.IGNORECASE),
    re.compile(
        rf"on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
        rf"({_MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(\d{{4}})", re.IGNORECASE),
    re.compile(rf"taken\s+on\s+({_MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(\d{{4}})", re.IGNORECASE),
    re.compile(rf"on\s+({_MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(\d{{4}})", re.IGNORECASE),
)


def extract_date(text: str) -> Optional[str]:
    for pattern in _RE_DATE_PATTERNS:
        if m := pattern.search(text):
            month = _MONTH_TO_NUM.get(m.group(1).lower())
            if month:
                return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(2)):02d}"
    return None


_RE_TIME_PATTERNS = (
    re.compile(r"Time:\s*(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?", re.IGNORECASE),
    re.compile(r"commencing\s+at\s+(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?", re.IGNORECASE),
    re.compile(r"at\s+(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?", re.IGNORECASE),
)


def extract_time(text: str) -> Optional[str]:
    for pattern in _RE_TIME_PATTERNS:
        if m := pattern.search(text):
            return f"{int(m.group(1))}:{m.group(2)} {m.group(3).upper()}M"
    return None


# --- Location --------------------------------------------------------

def extract_location(text: str) -> Optional[str]:
    if m := re.search(r"Location:[ \t]+([^\n]+)", text, re.IGNORECASE):
        loc = m.group(1).strip()
        # Strip trailing 'Date: ...' that lives on the same row in the form
        loc = re.sub(r"\s+Date:.*$", "", loc, flags=re.IGNORECASE)
        return loc.strip() or None
    if re.search(r"via\s+(?:remote\s+video|Zoom)", text, re.IGNORECASE):
        return "Via Zoom (remote video conference)"
    if re.search(r"\bVIA\s+ZOOM\b", text):
        return "Via Zoom"
    return None


def is_zoom_location(loc: Optional[str]) -> bool:
    if not loc:
        return False
    return bool(re.search(r"zoom|remote\s+video|video\s+conference", loc, re.IGNORECASE))


# --- Notice sectioning -----------------------------------------------

_RE_NOTICE_HEADER = re.compile(
    r"^\s*(?:[A-Z\u2019']+\s+)?(?:AMENDED\s+)?NOTICE\s+OF\s+INTENTION\s+TO\s+TAKE\s+(?:THE\s+)?"
    r"(?:ORAL|VIDEO)",
    re.MULTILINE,
)


def find_notice_sections(text: str) -> list[str]:
    splits = list(_RE_NOTICE_HEADER.finditer(text))
    if not splits:
        return [text]
    sections = []
    for i, m in enumerate(splits):
        start = m.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        sections.append(text[start:end])
    return sections


# --- Signing attorney -----------------------------------------------

_RE_SIGNING_PATTERN_1 = re.compile(
    r"/s/\s*([A-Z][A-Za-z.\s]+?)\s*\n\s*"
    r"([A-Z][A-Za-z\s.,'\-]{2,80}?)\s*[\n,]\s*"
    r"(?:State\s+Bar|Texas\s+State\s+Bar)",
)
_RE_SIGNING_PATTERN_2 = re.compile(
    r"By:\s*_{3,}[^\n]*\n\s*"
    r"([A-Z][A-Z\s.,'\-]{2,80}?)\s*\n\s*"
    r"State\s+Bar\s+No\."
)

_FIRM_LINE_RE = re.compile(
    r"^[ \t]*("
    r"LAW[ \t]+OFFICES?[ \t]+OF[ \t]+[A-Z][A-Z \t.,'&]+?(?:,?[ \t]+(?:PLLC|P\.?C\.?|LLP|L\.L\.P\.))?|"
    r"[A-Z][A-Z \t'&.,]+[ \t]+LAW[ \t]+FIRM(?:,?[ \t]+(?:PLLC|P\.?C\.?|LLP|L\.L\.P\.))?|"
    r"[A-Z][A-Z \t'&.,]+,?[ \t]+(?:PLLC|P\.?C\.?|LLP|L\.L\.P\.)"
    r")[ \t]*$",
    re.MULTILINE,
)


def _name_titlecase(s: str, preserve_acronyms: bool = False) -> str:
    """Convert an ALL-CAPS name/firm to readable title case.

    Entity suffixes (PLLC, P.C., USA, ...) keep their capitalization;
    small connecting words (and, of, the) are lowercased; everything
    else is title-cased. `preserve_acronyms` is accepted for call-site
    compatibility but no longer changes behavior.
    """
    if not s or not (s.isupper() or s == s.upper()):
        return s.strip() if s else s
    keep = {
        "LLP", "PLLC", "P.C.", "PC", "L.L.P.", "INC", "INC.", "LLC", "L.L.C.",
        "M.D.", "MD", "PHD", "ESQ", "II", "III", "IV", "JR", "SR",
        "USA", "U.S.A.", "P.A.", "PA", "CO.", "CORP",
    }
    small = {"and", "of", "the", "for", "or", "a", "an"}
    parts = []
    for p in s.split():
        bare = p.upper().strip(",.")
        if bare in keep:
            parts.append(p.upper())
        elif len(bare) == 1 and bare.isalpha():
            # A single letter is a middle initial (e.g. "A."), not a word.
            parts.append(p.upper())
        elif p.lower().strip(",.") in small:
            parts.append(p.lower())
        else:
            parts.append(p.title())
    return " ".join(parts).strip()


def _is_caps_line(line: str) -> bool:
    """True if a line is all-uppercase text (firm-name material).

    A firm name in a pleading signature block is often split across
    several consecutive ALL-CAPS lines (e.g. "BRAIN AND SPINE PERSONAL /
    INJURY LAWYERS OF SAN / ANTONIO, PLLC"). The boundary above it is a
    non-caps line such as "-and-".
    """
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


_FIRM_INDICATORS = (
    "LAW FIRM", "LAW OFFICE", "LAW OFFICES", "PLLC", "P.C.", "PC",
    "LLP", "L.L.P.", "LAWYERS", "ATTORNEYS", "ASSOCIATES", "& ",
)


def _firm_block_before(text: str, sig_pos: int) -> Optional[str]:
    """Return the firm name immediately preceding a signature at sig_pos.

    Walks upward from the signature collecting the run of consecutive
    ALL-CAPS lines, which is the typed firm name. The first non-caps
    line (a blank line or "-and-") ends the block.
    """
    before = text[:sig_pos].rstrip()
    lines = before.split("\n")
    block: list[str] = []
    for raw in reversed(lines):
        line = raw.strip()
        if not line:
            if block:
                break
            continue
        if _is_caps_line(line):
            block.append(line)
        else:
            break
    if not block:
        return None
    block.reverse()
    joined = " ".join(block).strip().rstrip(",").strip()
    upper = joined.upper()
    if not any(ind in upper for ind in _FIRM_INDICATORS):
        return None
    return _name_titlecase(joined, preserve_acronyms=True)


def extract_signing_attorney(text: str) -> dict:
    """Return the attorney who signed the pleading and their firm.

    The signing attorney is the one next to the /s/ block. Their firm is
    the firm name typed immediately ABOVE the /s/ -- NOT simply the first
    firm in the document. A NOD signed by co-counsel from two firms (here:
    Cukjati Law Firm and Brain & Spine) lists both firms; only the one
    directly above the signature belongs to the signer.
    """
    out: dict = {}

    typed_name = None
    sig_pos = None
    if m := _RE_SIGNING_PATTERN_1.search(text):
        typed_name = m.group(2).strip()
        sig_pos = m.start()
    elif m := _RE_SIGNING_PATTERN_2.search(text):
        typed_name = m.group(1).strip()
        sig_pos = m.start()

    if typed_name and typed_name.upper() not in {"STATE BAR NO", "ATTORNEY", "ATTORNEYS"}:
        out["custodial_name"] = _name_titlecase(typed_name)

    # Firm = the caps block immediately above the signature.
    if sig_pos is not None:
        firm = _firm_block_before(text, sig_pos)
        if firm:
            out["requesting_party"] = firm

    # Fallback: first firm line after "Respectfully submitted".
    if "requesting_party" not in out:
        rs_match = re.search(r"Respectfully\s+submitted,?", text, re.IGNORECASE)
        window = text[rs_match.end():rs_match.end() + 1500] if rs_match else text
        candidates = list(_FIRM_LINE_RE.finditer(window))
        if candidates:
            out["requesting_party"] = _name_titlecase(
                candidates[0].group(1).strip(), preserve_acronyms=True
            )

    return out


# --- All attorney appearances ----------------------------------------

_RE_BAR_ATTORNEY = re.compile(
    r"([A-Z][A-Za-z.'\-]+(?:[ \t]+[A-Z][A-Za-z.'\-]+){1,3})"
    r"(?:,[ \t]*Of[ \t]+Counsel)?[ \t]*\n[ \t]*"
    r"(?:State[ \t]+Bar|Texas[ \t]+State[ \t]+Bar)[ \t]+No\.?[ \t]*([0-9]+)",
    re.IGNORECASE,
)

_RE_ATTORNEY_OF_RECORD = re.compile(
    r"attorney\s+of\s+record,\s*"
    r"([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){1,3}),\s*"
    r"([A-Z][A-Z0-9,.&'\s]+?(?:P\.?C\.?|PLLC|L\.?L\.?P\.?))",
    re.IGNORECASE,
)


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _nearest_firm_above(text: str, pos: int) -> Optional[str]:
    """Find the firm name nearest above a character offset."""
    before = text[:pos]
    best = None
    for m in _FIRM_LINE_RE.finditer(before):
        best = m
    if best:
        return _name_titlecase(best.group(1).strip())
    # Caps-block fallback (multi-line firm names without a keyword on
    # every line).
    return _firm_block_before(text, pos)


def extract_appearances(text: str) -> list[dict]:
    """Extract every attorney appearance from a NOD pleading.

    Returns a list of {name, firm, bar_number, side}. Two sources are
    mined: the signature block (each attorney followed by "State Bar
    No.") and the "TO: ... attorney of record" line (opposing counsel).
    """
    appearances: list[dict] = []
    seen: set[str] = set()

    # Side of the signature block: "ATTORNEYS FOR PLAINTIFF/DEFENDANT".
    sig_side = "unknown"
    if re.search(r"ATTORNEYS?\s+FOR\s+PLAINTIFF", text, re.IGNORECASE):
        sig_side = "plaintiff"
    elif re.search(r"ATTORNEYS?\s+FOR\s+DEFENDANT", text, re.IGNORECASE):
        sig_side = "defendant"

    for m in _RE_BAR_ATTORNEY.finditer(text):
        name = _name_titlecase(_collapse_ws(m.group(1)))
        key = name.lower()
        if key in seen or len(name) < 4:
            continue
        seen.add(key)
        appearances.append({
            "name": name,
            "firm": _nearest_firm_above(text, m.start()),
            "bar_number": m.group(2).strip(),
            "side": sig_side,
        })

    # Opposing counsel from the "TO: ... attorney of record" line.
    if m := _RE_ATTORNEY_OF_RECORD.search(text):
        name = _name_titlecase(_collapse_ws(m.group(1)))
        key = name.lower()
        if key not in seen and len(name) >= 4:
            seen.add(key)
            to_side = "defendant"
            if re.search(r"TO:\s*Plaintiff", text, re.IGNORECASE):
                to_side = "plaintiff"
            appearances.append({
                "name": name,
                "firm": _name_titlecase(_collapse_ws(m.group(2))),
                "bar_number": None,
                "side": to_side,
            })

    # The signing attorney's firm is the caps block above the /s/ -- more
    # reliable than the nearest-firm-above scan, which can land on a
    # line-wrapped fragment. Patch it in.
    signing = extract_signing_attorney(text)
    signer_name = (signing.get("custodial_name") or "").lower()
    signer_firm = signing.get("requesting_party")
    if signer_firm:
        for appearance in appearances:
            if appearance["name"].lower() == signer_name:
                appearance["firm"] = signer_firm

    return appearances


def extract_all_firms(text: str) -> list[str]:
    """Every distinct law-firm name in the pleading.

    Derived from the structured appearances (each carries a firm) plus
    the signing attorney's firm -- more reliable than a loose line scan.
    """
    firms: list[str] = []
    seen: set[str] = set()

    def _add(firm: Optional[str]) -> None:
        if not firm or len(firm) <= 5:
            return
        key = firm.lower()
        if key not in seen:
            seen.add(key)
            firms.append(firm)

    for appearance in extract_appearances(text):
        _add(appearance.get("firm"))
    _add(extract_signing_attorney(text).get("requesting_party"))
    return firms


def parse(text: str) -> list[dict]:
    if not text:
        return []

    identity = extract_case_identity(text)
    caption = extract_caption(text)
    if caption:
        identity["caption_full"] = caption

    sections = find_notice_sections(text)
    if len(sections) <= 1:
        sections = [text]

    records: list[dict] = []
    for section in sections:
        record = dict(identity)
        section_deponents = extract_deponents(section)
        if section_deponents:
            record["witness_name"] = section_deponents[0]
        if d := extract_date(section):
            record["date_iso"] = d
        if t := extract_time(section):
            record["start_time"] = t
        if loc := extract_location(section):
            record["location_raw"] = loc
            record["location_type"] = "zoom" if is_zoom_location(loc) else "in_person"
        records.append(record)

    return records
