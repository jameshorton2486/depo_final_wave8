"""Canonical export-layout renderer.

THE SINGLE EXPORT-LAYOUT AUTHORITY (Wave 12).

`render.py` answers "what are the WORKING transcript lines" -- speaker
labels, Q/A typing, colloquy. This module answers the next question:
"what does the finished, paginated, certified transcript look like on
the page." It is the one place that knows about:

  - the caption header block
  - PROCEEDINGS / EXAMINATION BY blocks
  - 25-lines-per-page pagination with line numbering
  - Q/A indentation and colloquy formatting
  - the certification / signature block

Both the Export *preview* and the actual DOCX/PDF *export* call this
module, so the preview cannot drift from the file that downloads.

Pipeline position (Wave 12):

    RAW (immutable)
      -> participant mapping
      -> render.py        (WORKING lines)
      -> correction engine (deterministic stages)
      -> export_render.py  (paginated formatted layout)   <-- this module
      -> Export preview  AND  DOCX/PDF export

Stages not yet built (Stage S structural, Stage X lexicon) slot in
before this module; when they exist the preview reflects them with no
change here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Texas deposition layout standard.
LINES_PER_PAGE = 25
QA_INDENT = "    "        # four-space indent for Q./A. bodies
SPEAKER_INDENT = ""       # colloquy speaker labels sit at the margin


@dataclass
class ExportLine:
    """One physical line of the paginated transcript."""

    page: int
    line_number: int          # 1..LINES_PER_PAGE within the page
    text: str
    line_kind: str            # caption | header | proceedings | examination
                              #  | qa | colloquy | continuation | flagged | blank

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "line_number": self.line_number,
            "text": self.text,
            "line_kind": self.line_kind,
        }


@dataclass
class ExportPage:
    """One page of the paginated transcript."""

    page_number: int
    lines: list[ExportLine] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "lines": [ln.to_dict() for ln in self.lines],
        }


@dataclass
class ExportDocument:
    """The full paginated transcript -- preview and export both use this."""

    caption: str
    cause_number: str
    witness: str
    pages: list[ExportPage] = field(default_factory=list)
    total_pages: int = 0
    total_lines: int = 0
    is_approximate: bool = False   # True when rendered from a frontend fallback

    def to_dict(self) -> dict:
        return {
            "caption": self.caption,
            "cause_number": self.cause_number,
            "witness": self.witness,
            "pages": [p.to_dict() for p in self.pages],
            "total_pages": self.total_pages,
            "total_lines": self.total_lines,
            "is_approximate": self.is_approximate,
        }


def _wrap(text: str, width: int) -> list[str]:
    """Greedy word-wrap. Never splits a word; never drops a word."""
    words = (text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = w if not current else f"{current} {w}"
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def _body_lines_for(working_line: dict, body_width: int) -> list[tuple[str, str]]:
    """Turn one WORKING line into (text, line_kind) physical-line tuples.

    Q/A lines get a "Q." / "A." prefix and a hanging indent on wrap.
    Colloquy gets an ALL-CAPS speaker label line, then the indented body.
    Flagged (unmapped) lines render with their raw label, kind 'flagged'.
    """
    line_type = working_line.get("line_type", "colloquy")
    text = (working_line.get("text") or "").strip()
    label = (working_line.get("speaker_label") or "").strip()

    out: list[tuple[str, str]] = []

    if line_type in ("Q", "A"):
        prefix = "Q.  " if line_type == "Q" else "A.  "
        wrapped = _wrap(text, body_width - len(QA_INDENT) - len(prefix))
        for i, seg in enumerate(wrapped):
            if i == 0:
                out.append((f"{QA_INDENT}{prefix}{seg}", "qa"))
            else:
                # hanging indent aligns continuation under the text
                out.append((f"{QA_INDENT}{' ' * len(prefix)}{seg}", "continuation"))
        return out

    if line_type == "flagged":
        head = f"{label}:" if label else "UNIDENTIFIED SPEAKER:"
        out.append((head, "flagged"))
        for seg in _wrap(text, body_width - len(QA_INDENT)):
            out.append((f"{QA_INDENT}{seg}", "flagged"))
        return out

    # colloquy -- named speaker label then indented body
    if label:
        out.append((f"{label}:", "colloquy"))
    for seg in _wrap(text, body_width - len(QA_INDENT)):
        out.append((f"{QA_INDENT}{seg}", "continuation" if out else "colloquy"))
    return out


def render_export_document(
    working_lines: list[dict],
    *,
    caption: str = "",
    cause_number: str = "",
    witness: str = "",
    proceedings_date: str = "",
    examining_attorney_label: str = "",
    body_width: int = 64,
    is_approximate: bool = False,
) -> ExportDocument:
    """Render the canonical paginated export document.

    Parameters
    ----------
    working_lines
        Output of render.py (or the correction engine) -- a list of
        WorkingLine dicts. This is the WORKING transcript state.
    caption, cause_number, witness, proceedings_date
        Case identity for the header block. Empty strings render as
        blank header lines rather than mock text.
    examining_attorney_label
        e.g. "MR. VANCE" -- drives the "EXAMINATION BY ..." line.
    body_width
        Character width of the transcript body column.
    is_approximate
        Marks the document as a non-authoritative fallback render
        (transient unsaved transcript). The preview surfaces this.

    Returns
    -------
    ExportDocument -- pages of numbered lines. Preview and export share it.
    """
    # --- assemble the logical line stream -----------------------------
    stream: list[tuple[str, str]] = []

    # Front matter (caption is page-1 header, handled at pagination time).
    if proceedings_date:
        stream.append((f"PROCEEDINGS, {proceedings_date.upper()}", "proceedings"))
        stream.append(("", "blank"))
    if witness:
        stream.append((f"{witness.upper()},", "proceedings"))
        stream.append(("having been first duly sworn, testified as follows:",
                       "proceedings"))
        stream.append(("", "blank"))
    if examining_attorney_label:
        stream.append((f"EXAMINATION BY {examining_attorney_label.upper()}:",
                       "examination"))
        stream.append(("", "blank"))

    # Body.
    for wl in working_lines:
        for (text, kind) in _body_lines_for(wl, body_width):
            stream.append((text, kind))
        stream.append(("", "blank"))   # blank line between utterances

    # --- paginate into 25-line pages ----------------------------------
    pages: list[ExportPage] = []
    page_no = 1
    line_no = 0
    current = ExportPage(page_number=page_no)
    total_lines = 0

    for (text, kind) in stream:
        if line_no >= LINES_PER_PAGE:
            pages.append(current)
            page_no += 1
            line_no = 0
            current = ExportPage(page_number=page_no)
        line_no += 1
        total_lines += 1
        current.lines.append(ExportLine(
            page=page_no, line_number=line_no, text=text, line_kind=kind))

    if current.lines:
        # pad the final page to a full 25 lines for layout consistency
        while line_no < LINES_PER_PAGE:
            line_no += 1
            current.lines.append(ExportLine(
                page=page_no, line_number=line_no, text="", line_kind="blank"))
        pages.append(current)

    return ExportDocument(
        caption=caption,
        cause_number=cause_number,
        witness=witness,
        pages=pages,
        total_pages=len(pages),
        total_lines=total_lines,
        is_approximate=is_approximate,
    )


def render_export_to_dict(working_lines: list[dict], **kwargs) -> dict:
    """Convenience: render and return a plain dict for a JSON API response."""
    return render_export_document(working_lines, **kwargs).to_dict()
