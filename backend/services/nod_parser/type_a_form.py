"""Type A: S.A. Legal Solutions firm scheduling form.

Two known variants:
  - Standard (Brain & Spine, Israel Garcia, Goldman): inline label-value pairs,
    'Ordering Attorney:' / 'Copy Attorney:' / 'Sch Start Time:' fields.
  - Video (Marynell Maloney): different layout with 'Firm / CSR:', 'Videographer:',
    'Need Audio?:', 'Would you like a copy of the video?' fields.

Both variants share the field SEMANTICS (deponent, date, ordering attorney, etc.)
but differ in label layout. We try multiple regex patterns per field and accept
whichever matches.

Returns a flat dict of extracted strings. Missing fields are simply absent.
"""
from __future__ import annotations

import re

TYPE_A_MARKERS = (
    "Court Reporting",
    "Ordering Attorney:",
    "Copy Attorney:",
    "Sch Start Time:",
)


def looks_like_type_a(text: str) -> bool:
    if not text:
        return False
    return sum(1 for m in TYPE_A_MARKERS if m in text) >= 2


def _looks_like_form_junk(s: str) -> bool:
    """Reject obviously bad case_style values from form layout failures."""
    if not s:
        return True
    upper = s.upper()
    # Phrases that indicate we captured form labels, not a real case caption
    junk_markers = ("FIRM /", "FIRM/", "FIRM:", "EMAIL:", "PHONE:", "ADDRESS:",
                    "PIP:", "PLLC, ET AL.", "PLLC, ET AL")
    if any(j in upper for j in junk_markers):
        # Allow if 'v.' or 'vs.' is present AND the junk is a small fraction
        if (" V." in upper or " VS." in upper) and len(s) > 30:
            return False
        return True
    # Must have at least a versus indicator to be a valid caption
    return not (" V." in upper or " VS." in upper or " V " in upper)


def _stitch_split_email(text: str) -> str:
    """Fix 'service@brainspine-law.co\\nm' style line-wrapped emails."""
    return re.sub(
        r"(@[a-z0-9.\-]+\.[a-z]{1,3})\n([a-z]{1,3})\b",
        lambda m: m.group(1) + m.group(2),
        text,
        flags=re.IGNORECASE,
    )


# --- Patterns ---------------------------------------------------------

# Inline patterns work on the standard variant.
_RE_DATE_INLINE = re.compile(r"Date:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})")
_RE_DEPONENT_INLINE = re.compile(r"Deponent:\s*([^\n]+?)(?:\s+Case/Style:|\n|$)")
_RE_CASE_STYLE_INLINE = re.compile(
    r"Case/Style:\s*((?:[^\n]+\n){1,4})",
    re.IGNORECASE,
)
_RE_CSR_INLINE = re.compile(r"CSR:\s*(Yes|No)", re.IGNORECASE)
_RE_LOCATION_INLINE = re.compile(r"Location:[ \t]+([^\n]+?)(?:\s+Date:|$)", re.MULTILINE)
_RE_SCH_START_INLINE = re.compile(
    r"Sch Start Time:\s*([0-9]{1,2}:[0-9]{2}\s*[AP]M)", re.IGNORECASE
)
_RE_ORDERING_ATTY_INLINE = re.compile(
    r"Ordering Attorney:\s*([^\n]+?)(?:\s+Firm:|\n|$)"
)
_RE_PHONE = re.compile(
    r"(?:Phone:\s*)?(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})"
)
_RE_EMAIL = re.compile(
    r"\b([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})\b", re.IGNORECASE
)
_RE_ORDERED_BY = re.compile(
    r"O[dr]+ered by:\s*([^\n]+?)\s*$", re.IGNORECASE | re.MULTILINE
)

# Standalone date pattern (for the video form where values appear after all labels).
_RE_STANDALONE_DATE = re.compile(r"^\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})\s*$", re.MULTILINE)
_RE_STANDALONE_TIME = re.compile(
    r"^\s*([0-9]{1,2}:[0-9]{2}\s*[AP]M)\s*$", re.MULTILINE | re.IGNORECASE
)


def _try_inline_then_standalone(text: str) -> dict:
    """For the video form variant, fields are: labels first, then values appear
    in document order. Extract by combining inline matches with standalone values."""
    out: dict = {}

    # Try inline patterns first
    if m := _RE_DATE_INLINE.search(text):
        out["form_date_raw"] = m.group(1).strip()
    if m := _RE_DEPONENT_INLINE.search(text):
        out["deponent"] = m.group(1).strip()
    if m := _RE_CASE_STYLE_INLINE.search(text):
        cs = m.group(1).strip()
        # Insert spaces before strip — preserve word boundaries before collapsing whitespace
        cs = re.sub(r"\s+", " ", cs)
        cs = re.sub(
            r"\s+(Yes|No|Y\s*/\s*N|Original|Standard|MPG1|MP4|Flash\s+Drive|"
            r"E-Trans|Hard\s+Copy|Rush\s+Due|Firm:|CSR:|Sch\s+Start|Start\s+Time|"
            r"End\s+Time|Email:|Phone:|Address:|Ordering|Copy\s+Attorney|Copy\?).*$",
            "",
            cs,
            flags=re.IGNORECASE,
        )
        # Strip city-state leaks from form layout (anywhere in the string, including end)
        cs = re.sub(
            r"\s+(?:San Antonio|Dallas|Houston|McAllen|Austin|Fort Worth)\s+TX(?:\s+\d{5})?",
            " ",
            cs,
        )
        # Re-introduce spaces where pdfplumber collapsed them due to column overlap:
        # 'andAllAmericanHeavyEquipmentLeasing' → 'and All American Heavy Equipment Leasing'
        # Insert space between lowercase→uppercase letter boundaries
        cs = re.sub(r"([a-z])([A-Z])", r"\1 \2", cs)
        cs = re.sub(r"\s+", " ", cs).strip().rstrip(",").strip()
        if cs and len(cs) > 5 and not _looks_like_form_junk(cs):
            out["case_style"] = cs
    if m := _RE_CSR_INLINE.search(text):
        out["csr_required"] = m.group(1).lower() == "yes"
    if m := _RE_LOCATION_INLINE.search(text):
        loc = m.group(1).strip()
        loc = re.sub(r"\s+Date:.*$", "", loc, flags=re.IGNORECASE).strip()
        if loc:
            out["location_raw"] = loc
    if m := _RE_SCH_START_INLINE.search(text):
        out["form_start_time"] = m.group(1).strip().upper()
    if m := _RE_ORDERING_ATTY_INLINE.search(text):
        out["ordering_attorney"] = m.group(1).strip()
    if m := _RE_ORDERED_BY.search(text):
        out["ordered_by"] = m.group(1).strip()

    # Fallback: standalone date / time (video form layout) — never use as location
    if "form_date_raw" not in out:
        if m := _RE_STANDALONE_DATE.search(text):
            out["form_date_raw"] = m.group(1).strip()
    if "form_start_time" not in out:
        if m := _RE_STANDALONE_TIME.search(text):
            out["form_start_time"] = m.group(1).strip().upper()

    return out


# Copy attorneys block: each occurrence delimits one opposing-counsel record.
_RE_COPY_BLOCK_START = re.compile(r"Copy Attorney:")


def _extract_copy_attorneys(text: str) -> list[dict]:
    """Walk through each 'Copy Attorney:' block and try to pull name/firm/email/phone.

    Best-effort: blocks are heterogeneous. Empty blocks (template only) are skipped.
    """
    parts = _RE_COPY_BLOCK_START.split(text)
    if len(parts) < 2:
        return []
    blocks = parts[1:]  # everything after the first split is a block
    results = []
    for block in blocks:
        block = _stitch_split_email(block)
        # Take the first ~600 chars of the block to avoid pulling fields from the next one
        block = block[:600]
        entry: dict = {}

        # Name: first non-empty line that isn't a label or 'Yes / No'
        for line in block.split("\n")[:8]:
            line = line.strip()
            if not line:
                continue
            if any(skip in line for skip in [
                "Firm:", "Address:", "Phone:", "Email:", "Format:", "Delivery:",
                "Yes / No", "Copy?", "Notes:", "Signature:", "Original", "Standard",
                "E-Trans", "Hard Copy", "Rush Due", "Y / N", "MP4", "MPG1", "Flash Drive",
            ]):
                continue
            # Strip trailing 'Copy?' label residue
            line = re.sub(r"\s*Copy\?\s*$", "", line)
            line = re.sub(r"\s+Yes / No\s*$", "", line)
            if line and re.search(r"[A-Za-z]", line):
                entry["name"] = line
                break

        # Firm: line right after the name, often before 'Original Standard'
        firm_match = re.search(
            r"(?:Yes\s*/\s*No|Copy\?)\s*([^\n]+?)(?:\s+Original\s+Standard|\n)",
            block,
        )
        if firm_match:
            firm = firm_match.group(1).strip()
            firm = re.sub(r"\s+Original\s+Standard.*$", "", firm)
            entry["firm"] = firm

        # Phone, email
        if m := _RE_PHONE.search(block):
            entry["phone"] = m.group(1)
        if m := _RE_EMAIL.search(block):
            entry["email"] = m.group(1)

        # Skip empty templates
        if entry.get("name") or entry.get("firm") or entry.get("email"):
            results.append(entry)

    return results


def _extract_ordering_firm(text: str) -> str | None:
    """The firm name appears on the line right after 'Ordering Attorney: NAME'."""
    m = re.search(
        r"Ordering Attorney:[^\n]*\n([^\n]+?)(?:\s+Original\s+Standard|\n|$)",
        text,
    )
    if not m:
        # Video form: 'Firm:' on its own line after Ordering Attorney
        m = re.search(
            r"Ordering Attorney:\s*([^\n]+)\n[^\n]*\nFirm:\s*([^\n]+)",
            text,
            re.IGNORECASE,
        )
        if m:
            return m.group(2).strip()
        return None
    firm = m.group(1).strip()
    firm = re.sub(r"\s+Original\s+Standard.*$", "", firm)
    return firm or None


def parse(text: str) -> dict:
    """Parse a Type A firm form. Returns a dict of whatever could be extracted."""
    if not text:
        return {}
    text = _stitch_split_email(text)

    out = _try_inline_then_standalone(text)

    if "ordering_attorney" in out and "ordering_firm" not in out:
        firm = _extract_ordering_firm(text)
        if firm:
            out["ordering_firm"] = firm

    # Phone & email — first occurrences usually belong to ordering attorney
    phones = _RE_PHONE.findall(text)
    emails = _RE_EMAIL.findall(text)
    if phones:
        out["ordering_phone"] = phones[0]
    if emails:
        out["ordering_email"] = emails[0]

    copy_attys = _extract_copy_attorneys(text)
    if copy_attys:
        out["copy_attorneys"] = copy_attys

    return out
