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

Wave 19A consolidation: the private `_wrap()` helper has been removed.
Word-wrapping is now handled exclusively by `_wrap_text` from the
canonical `backend.pagination.wrapping` module (one authority for
word-wrap). Page allocation uses the Pagination Engine's model types
(`Page`, `PageSlot`, `PhysicalLine`, `PaginatedDocument`) so the
geometry layer can consume the same PaginatedDocument produced here.

The pre-formatted stream entries (text already carries Q./A. prefix and
indentation spaces) are placed as PhysicalLines directly -- the wrapping
step from `wrap_render_line` is intentionally bypassed because the text
is already wrapped to fit within body_width by `_body_lines_for`.

Stages not yet built (Stage S structural, Stage X lexicon) slot in
before this module; when they exist the preview reflects them with no
change here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.pagination.model import (
    LINES_PER_PAGE,
    Page,
    PageSlot,
    PhysicalLine,
    PaginatedDocument,
)
from backend.pagination.wrapping import _wrap_text

# Texas deposition layout standard.
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


def _body_lines_for(working_line: dict, body_width: int) -> list[tuple[str, str]]:
    """Turn one WORKING line into (text, line_kind) physical-line tuples.

    Q/A lines get a "Q." / "A." prefix and a hanging indent on wrap.
    Colloquy gets an ALL-CAPS speaker label line, then the indented body.
    Flagged (unmapped) lines render with their raw label, kind 'flagged'.

    Word-wrapping uses `_wrap_text` from `pagination.wrapping` -- the
    single word-wrap authority for this codebase.
    """
    line_type = working_line.get("line_type", "colloquy")
    text = (working_line.get("text") or "").strip()
    label = (working_line.get("speaker_label") or "").strip()

    out: list[tuple[str, str]] = []

    if line_type in ("examination", "by_line"):
        # Structural opening-ritual headers emitted by stage_s (the
        # EXAMINATION header and the BY MR./MS. ___: attribution line).
        # Render the text as-is with the existing "examination" line kind:
        # no QA indent, no appended colon (a by_line already carries its
        # single colon). Reuses existing header geometry -- no new tabs.
        out.append((text, "examination"))
        return out

    if line_type in ("Q", "A"):
        prefix = "Q.  " if line_type == "Q" else "A.  "
        wrapped = _wrap_text(text, body_width - len(QA_INDENT) - len(prefix))
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
        for seg in _wrap_text(text, body_width - len(QA_INDENT)):
            out.append((f"{QA_INDENT}{seg}", "flagged"))
        return out

    # colloquy -- named speaker label then indented body
    if label:
        out.append((f"{label}:", "colloquy"))
    for seg in _wrap_text(text, body_width - len(QA_INDENT)):
        out.append((f"{QA_INDENT}{seg}", "continuation" if out else "colloquy"))
    return out


def _new_export_page(page_number: int) -> Page:
    """An empty Pagination Engine Page with LINES_PER_PAGE numbered slots."""
    return Page(
        page_number=page_number,
        page_id=f"page-{page_number:04d}",
        slots=[PageSlot(slot_number=n)
               for n in range(1, LINES_PER_PAGE + 1)],
    )


def _paginate_formatted_stream(
    stream: list[tuple[str, str]],
) -> PaginatedDocument:
    """Allocate a pre-formatted (text, kind) stream into a PaginatedDocument.

    Each stream entry becomes one PhysicalLine placed in a PageSlot.
    The text is already wrapped and carries embedded indentation, so
    `wrap_render_line` is intentionally NOT called here -- that step
    would strip leading whitespace from the pre-formatted lines.

    Returns a canonical PaginatedDocument (same type as paginate() in
    `backend.pagination.paginator`) so the Geometry Layer can consume it.
    """
    pages: list[Page] = []
    current = _new_export_page(1)
    pages.append(current)
    next_slot = 0

    for i, (text, kind) in enumerate(stream):
        if next_slot >= LINES_PER_PAGE:
            current = _new_export_page(len(pages) + 1)
            pages.append(current)
            next_slot = 0
        current.slots[next_slot].physical_line = PhysicalLine(
            text=text,
            tab_level=0,          # text carries its own indentation
            line_type=kind,
            source_render_line_id=f"export-{i}",
        )
        next_slot += 1

    return PaginatedDocument(pages=pages, continuations=[])


def _paginated_to_export_document(
    paginated: PaginatedDocument,
    *,
    caption: str,
    cause_number: str,
    witness: str,
    is_approximate: bool,
) -> ExportDocument:
    """Convert a PaginatedDocument to an ExportDocument."""
    pages: list[ExportPage] = []
    total_lines = 0
    for page in paginated.pages:
        export_page = ExportPage(page_number=page.page_number)
        for slot in page.slots:
            if not slot.is_empty:
                phys = slot.physical_line
                export_page.lines.append(ExportLine(
                    page=page.page_number,
                    line_number=slot.slot_number,
                    text=phys.text,
                    line_kind=phys.line_type,
                ))
                total_lines += 1
            else:
                export_page.lines.append(ExportLine(
                    page=page.page_number,
                    line_number=slot.slot_number,
                    text="",
                    line_kind="blank",
                ))
        pages.append(export_page)
    return ExportDocument(
        caption=caption,
        cause_number=cause_number,
        witness=witness,
        pages=pages,
        total_pages=len(pages),
        total_lines=total_lines,
        is_approximate=is_approximate,
    )


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
    doc, _ = render_export_with_layout(
        working_lines,
        caption=caption,
        cause_number=cause_number,
        witness=witness,
        proceedings_date=proceedings_date,
        examining_attorney_label=examining_attorney_label,
        body_width=body_width,
        is_approximate=is_approximate,
    )
    return doc


def render_export_with_layout(
    working_lines: list[dict],
    *,
    caption: str = "",
    cause_number: str = "",
    witness: str = "",
    proceedings_date: str = "",
    examining_attorney_label: str = "",
    body_width: int = 64,
    is_approximate: bool = False,
) -> tuple[ExportDocument, PaginatedDocument | None]:
    """Render the canonical paginated export document and return the
    intermediate PaginatedDocument for use by the Geometry Layer.

    Returns (ExportDocument, PaginatedDocument). When the input is empty
    the second element is None.
    """
    # --- assemble the logical line stream -----------------------------
    stream: list[tuple[str, str]] = []

    # Front matter (caption is page-1 header, handled at pagination time).
    if proceedings_date:
        stream.append((f"PROCEEDINGS, {proceedings_date.upper()}", "proceedings"))
        stream.append(("", "blank"))
    # The opening ritual (witness-sworn block, EXAMINATION header, BY-line)
    # is owned by backend/stage_s/ and arrives in `working_lines`; this
    # module no longer emits a parallel ritual here. The witness-sworn
    # line specifically is gated (detect/flag/attest) in stage_s and is
    # never auto-asserted from a witness name. The `witness` and
    # `examining_attorney_label` params are retained for document metadata
    # / caller compatibility but no longer drive front-matter content.

    # Body.
    for wl in working_lines:
        for (text, kind) in _body_lines_for(wl, body_width):
            stream.append((text, kind))
        stream.append(("", "blank"))   # blank line between utterances

    if not stream:
        return (ExportDocument(
            caption=caption,
            cause_number=cause_number,
            witness=witness,
            pages=[],
            total_pages=0,
            total_lines=0,
            is_approximate=is_approximate,
        ), None)

    # --- paginate using the Pagination Engine's model types -----------
    paginated = _paginate_formatted_stream(stream)

    # --- convert to ExportDocument ------------------------------------
    export_doc = _paginated_to_export_document(
        paginated,
        caption=caption,
        cause_number=cause_number,
        witness=witness,
        is_approximate=is_approximate,
    )

    return export_doc, paginated


def render_export_to_dict(working_lines: list[dict], **kwargs) -> dict:
    """Convenience: render and return a plain dict for a JSON API response."""
    return render_export_document(working_lines, **kwargs).to_dict()
