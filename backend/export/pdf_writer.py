"""PDF export writer — Wave 18 / Wave 19B.

Generates a real PDF from the canonical ExportDocument via reportlab.
When a GeometryDocument is provided (Wave 19B), the writer uses
UFM-compliant measurements: Courier New 12pt, 28pt line spacing, 1.25"
left margin, and draws the format box (solid marginal border).

Wave 18 fallback: if no GeometryDocument is provided, uses the original
hardcoded constants so existing tests continue to pass.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.transcript.export_render import ExportDocument

if TYPE_CHECKING:
    from backend.geometry.engine import GeometryDocument

# Wave 18 fallback constants.
_FALLBACK_FONT = "Courier"
_FALLBACK_FONT_PT = 10
_FALLBACK_LEFT_MARGIN = 72        # 1 inch in points
_FALLBACK_TOP_MARGIN = 720        # start y
_FALLBACK_LINE_HEIGHT = 14

# reportlab uses "Courier" not "Courier New" as the font name.
_REPORTLAB_MONO = "Courier"


def write_pdf(doc: ExportDocument, path: str | Path,
              geo: "GeometryDocument | None" = None) -> Path:
    """Write the export document as a real .pdf file. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Determine layout measurements.
    if geo and geo.pages:
        first = geo.pages[0]
        page_w = first.page_width_pt
        page_h = first.page_height_pt
        left = first.margin_left_pt
        right_margin = first.margin_right_pt
        top = first.margin_top_pt
        font_pt = first.font_size_pt
        line_h = first.line_spacing_pt
        fmt_left = first.format_box_left_pt
        fmt_right = first.format_box_right_pt
        fmt_top = first.format_box_top_pt
        fmt_bottom = first.format_box_bottom_pt
        fmt_lw = first.format_box_line_pt
        use_geometry = True
    else:
        page_w, page_h = letter
        left = _FALLBACK_LEFT_MARGIN
        right_margin = _FALLBACK_LEFT_MARGIN
        top = _FALLBACK_TOP_MARGIN
        font_pt = _FALLBACK_FONT_PT
        line_h = _FALLBACK_LINE_HEIGHT
        fmt_left = fmt_right = fmt_top = fmt_bottom = fmt_lw = 0.0
        use_geometry = False

    pdf = canvas.Canvas(str(path), pagesize=(page_w, page_h))

    def _draw_format_box() -> None:
        """Draw the solid marginal-line border (UFM format box)."""
        if not use_geometry:
            return
        pdf.setStrokeColorRGB(0, 0, 0)
        pdf.setLineWidth(fmt_lw)
        pdf.rect(
            fmt_left,
            fmt_bottom,
            fmt_right - fmt_left,
            fmt_top - fmt_bottom,
            stroke=1, fill=0,
        )

    def _draw_caption_page() -> None:
        y = page_h - top - font_pt
        pdf.setFont(f"{_REPORTLAB_MONO}-Bold", font_pt + 1)
        for text in (
            doc.caption,
            f"CAUSE NO. {doc.cause_number}" if doc.cause_number else "",
            f"CERTIFIED DEPOSITION OF {doc.witness.upper()}"
            if doc.witness else "",
        ):
            if text:
                pdf.drawCentredString(page_w / 2, y, text)
                y -= line_h * 1.5

    if doc.caption or doc.cause_number or doc.witness:
        _draw_caption_page()
        pdf.showPage()

    for page in doc.pages:
        _draw_format_box()

        # Page number, top-right (inside the format box).
        pdf.setFont(_REPORTLAB_MONO, font_pt)
        pdf.drawRightString(
            page_w - right_margin,
            page_h - top + (line_h * 0.5),
            f"Page {page.page_number}",
        )

        y = page_h - top
        for ln in page.lines:
            prefix = str(ln.line_number).rjust(2)
            pdf.setFont(_REPORTLAB_MONO, font_pt)
            pdf.drawString(left, y, f"{prefix}  {ln.text}")
            y -= line_h

        pdf.showPage()

    pdf.save()
    return path
