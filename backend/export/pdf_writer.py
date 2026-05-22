"""PDF export writer — Wave 18.

Generates a REAL PDF from the canonical ExportDocument, using reportlab.
Monospaced, paginated, one PDF page per transcript page.

Wave 18 scope: a real, correct, paginated PDF. It does NOT yet draw the
UFM format box / marginal geometry -- that is Wave 19.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.transcript.export_render import ExportDocument

_FONT = "Courier"
_FONT_PT = 10
_LEFT_MARGIN = 72        # 1 inch
_TOP_MARGIN = 720        # start y (72pt from top of 792pt letter page)
_LINE_HEIGHT = 14


def write_pdf(doc: ExportDocument, path: str | Path) -> Path:
    """Write the export document as a real .pdf file. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    pdf = canvas.Canvas(str(path), pagesize=letter)

    def _draw_caption_page() -> None:
        y = _TOP_MARGIN
        pdf.setFont(f"{_FONT}-Bold", _FONT_PT + 1)
        for text in (
            doc.caption,
            f"CAUSE NO. {doc.cause_number}" if doc.cause_number else "",
            f"CERTIFIED DEPOSITION OF {doc.witness.upper()}"
            if doc.witness else "",
        ):
            if text:
                pdf.drawCentredString(letter[0] / 2, y, text)
                y -= _LINE_HEIGHT * 1.5

    if doc.caption or doc.cause_number or doc.witness:
        _draw_caption_page()
        pdf.showPage()

    for page in doc.pages:
        # Page number, top-right.
        pdf.setFont(_FONT, _FONT_PT)
        pdf.drawRightString(letter[0] - _LEFT_MARGIN, _TOP_MARGIN + 18,
                            f"Page {page.page_number}")
        y = _TOP_MARGIN
        for ln in page.lines:
            prefix = str(ln.line_number).rjust(2)
            pdf.setFont(_FONT, _FONT_PT)
            pdf.drawString(_LEFT_MARGIN, y, f"{prefix}  {ln.text}")
            y -= _LINE_HEIGHT
        pdf.showPage()

    pdf.save()
    return path
