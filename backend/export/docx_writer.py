"""DOCX export writer — Wave 18.

Generates a REAL Word document from the canonical ExportDocument, using
python-docx. This is a clean, paginated transcript: caption block, the
testimony in a monospaced font, line numbers, and a page break between
each transcript page.

Wave 18 scope: a real, correct, paginated .docx. It does NOT yet draw
the UFM format box / marginal line geometry -- that is Wave 19. The
page-per-page structure here is what Wave 19 will add geometry to.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from backend.transcript.export_render import ExportDocument

_MONO = "Courier New"
_FONT_PT = 10


def _mono_paragraph(doc_obj, text: str, *, bold: bool = False,
                    align=WD_ALIGN_PARAGRAPH.LEFT):
    """Add a monospaced paragraph with tight spacing."""
    p = doc_obj.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    run = p.add_run(text or "")
    run.font.name = _MONO
    run.font.size = Pt(_FONT_PT)
    run.bold = bold
    return p


def build_docx(doc: ExportDocument) -> Document:
    """Build a python-docx Document from the canonical ExportDocument."""
    word = Document()

    # --- caption block ---
    if doc.caption:
        _mono_paragraph(word, doc.caption, bold=True,
                        align=WD_ALIGN_PARAGRAPH.CENTER)
    if doc.cause_number:
        _mono_paragraph(word, f"CAUSE NO. {doc.cause_number}", bold=True,
                        align=WD_ALIGN_PARAGRAPH.CENTER)
    if doc.witness:
        _mono_paragraph(word, f"CERTIFIED DEPOSITION OF "
                        f"{doc.witness.upper()}", bold=True,
                        align=WD_ALIGN_PARAGRAPH.CENTER)

    # --- pages ---
    for p_index, page in enumerate(doc.pages):
        if p_index > 0 or doc.caption:
            word.add_page_break()
        # Page number, top-right (Wave 19 will refine geometry).
        _mono_paragraph(word, f"Page {page.page_number}",
                        align=WD_ALIGN_PARAGRAPH.RIGHT)
        for ln in page.lines:
            # Line-number prefix; Wave 19 moves this into a margin box.
            prefix = str(ln.line_number).rjust(2)
            _mono_paragraph(word, f"{prefix}  {ln.text}")

    return word


def write_docx(doc: ExportDocument, path: str | Path) -> Path:
    """Write the export document as a real .docx file. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    word = build_docx(doc)
    word.save(str(path))
    return path
