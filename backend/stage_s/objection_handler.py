"""Stage S objection isolation.

An objection spoken by defending counsel often arrives diarized inside
the flow of an examination. Stage S isolates it into its own standalone
colloquy block and marks the interruption with spaced double-hyphens.

Dash policy (explicit signoff -- Wave 13):
    Punctuation is NOT governed by the verbatim mandate, which protects
    spoken *words*. UFM 2.9 and Morson's Rule 87 mandate dashes at an
    interruption. Stage S therefore emits the spaced "--" at the
    segmentation boundary when it is not already present. The RAW
    utterance record is never mutated -- the dash is added to the
    rendered line text only, and the insertion is audited.
"""
from __future__ import annotations

# Leading tokens that mark a spoken objection.
_OBJECTION_MARKERS = (
    "objection",
    "object to",
    "i object",
    "form, vague",
    "vague and ambiguous",
    "calls for speculation",
    "misstates",
    "asked and answered",
    "nonresponsive",
)

DASH = "--"


def looks_like_objection(text: str) -> bool:
    """Heuristic: does this block begin with an objection marker?"""
    low = (text or "").strip().lower()
    return any(low.startswith(m) for m in _OBJECTION_MARKERS)


def _ends_with_dash(text: str) -> bool:
    return (text or "").rstrip().endswith(DASH)


def _starts_with_dash(text: str) -> bool:
    return (text or "").lstrip().startswith(DASH)


def append_interruption_dash(text: str) -> tuple[str, bool]:
    """Append a spaced '--' to an interrupted line if not already there.

    Returns (new_text, inserted?). Morson's Rule 91: no comma/colon/
    semicolon immediately before the dash -- a trailing one is stripped.
    """
    body = (text or "").rstrip()
    if _ends_with_dash(body):
        return body, False
    # Strip a trailing comma/colon/semicolon before inserting the dash.
    while body and body[-1] in ",;:":
        body = body[:-1].rstrip()
    return f"{body} {DASH}", True


def prepend_resumption_dash(text: str) -> tuple[str, bool]:
    """Prepend a spaced '--' to a resuming line if not already there.

    Returns (new_text, inserted?). No comma/colon/semicolon immediately
    after the dash -- a leading one is stripped.
    """
    body = (text or "").lstrip()
    if _starts_with_dash(body):
        return body, False
    while body and body[0] in ",;:":
        body = body[1:].lstrip()
    return f"{DASH} {body}", True
