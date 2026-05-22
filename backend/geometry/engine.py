"""Geometry Layer Engine — Wave 19B.

Takes a PaginatedDocument + GeometryProfile and produces a
GeometryDocument: the per-page layout specification that DOCX and PDF
writers need to draw format boxes, place line numbers, apply headers
and footers, and use UFM-compliant typography.

All output measurements are in points (1 pt = 1/72 inch), since both
python-docx and reportlab work in points.

Pipeline position:
    PaginatedDocument (Wave 19A)
      + GeometryProfile (Wave 19B)
      -> apply_geometry()
      -> GeometryDocument
      -> DOCX/PDF writers (format box, line numbers, headers, footers)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.geometry.profile import GeometryProfile, TEXAS_UFM
from backend.pagination.model import PaginatedDocument, PageSlot

# Unit conversion: 1 twip = 1/20 point (20 twips per point).
_TWIPS_TO_PT: float = 1.0 / 20.0


def _pt(twips: int) -> float:
    return twips * _TWIPS_TO_PT


@dataclass(frozen=True)
class PageGeometry:
    """Layout specification for one transcript page.

    Carries the complete set of measurements and page-furniture data
    that a DOCX or PDF writer needs to render one page correctly:
    margins, font, line spacing, format-box coordinates, line-number
    column width, tab stops, header text, and the raw slot data from
    the PaginatedDocument.
    """

    page_number: int

    # --- page size (points) ---
    page_width_pt: float
    page_height_pt: float

    # --- margins (points) ---
    margin_left_pt: float
    margin_right_pt: float
    margin_top_pt: float
    margin_bottom_pt: float

    # --- text area (points) ---
    text_area_width_pt: float
    text_area_height_pt: float

    # --- typography ---
    font_name: str
    font_size_pt: float
    line_spacing_pt: float
    lines_per_page: int

    # --- format box (solid border enclosing the text area) ---
    format_box_left_pt: float    # = margin_left_pt
    format_box_right_pt: float   # = page_width_pt - margin_right_pt
    format_box_top_pt: float     # = margin_top_pt
    format_box_bottom_pt: float  # = page_height_pt - margin_bottom_pt
    format_box_line_pt: float    # border line width

    # --- line-number column ---
    # Width of the column to the left of the main text where 1..25
    # line numbers are printed in the margin.
    line_num_column_pt: float

    # --- tab stops (points from left text margin) ---
    tab_stops_pt: tuple

    # --- page header ---
    header_page_num: int         # page number shown in the header

    # --- content slots from the PaginatedDocument ---
    slots: tuple                 # tuple[PageSlot, ...]


@dataclass
class GeometryDocument:
    """A PaginatedDocument with geometry applied — ready for the writers.

    The writers (DOCX/PDF) consume this instead of the raw PaginatedDocument:
    every measurement is already in points, the format box is defined,
    and header/footer data is pre-computed per page.
    """

    profile: GeometryProfile
    pages: list[PageGeometry] = field(default_factory=list)

    @property
    def total_pages(self) -> int:
        return len(self.pages)


def apply_geometry(
    paginated: PaginatedDocument,
    profile: GeometryProfile = TEXAS_UFM,
) -> GeometryDocument:
    """Apply a geometry profile to a PaginatedDocument.

    Takes the paginated transcript body and the authoritative layout
    measurements, and produces a GeometryDocument containing per-page
    layout specifications.

    Parameters
    ----------
    paginated
        The PaginatedDocument from the Pagination Engine (Wave 19A) or
        from `render_export_with_layout()`.
    profile
        The GeometryProfile to apply. Defaults to TEXAS_UFM.

    Returns
    -------
    GeometryDocument with per-page PageGeometry specs.
    """
    margin_left_pt = _pt(profile.margin_left_twips)
    margin_right_pt = _pt(profile.margin_right_twips)
    margin_top_pt = _pt(profile.margin_top_twips)
    margin_bottom_pt = _pt(profile.margin_bottom_twips)
    page_width_pt = _pt(profile.page_width_twips)
    page_height_pt = _pt(profile.page_height_twips)
    text_area_width_pt = _pt(profile.text_area_width_twips)
    text_area_height_pt = _pt(profile.text_area_height_twips)
    tab_stops_pt = tuple(_pt(t) for t in profile.tab_stops_twips)

    # Line-number column: the first tab stop is the Q./A. designation
    # column; line numbers sit in the margin to the left of it.
    line_num_column_pt = tab_stops_pt[0]

    # Format box: a solid rectangle drawn at the exact text-area edges.
    fmt_left = margin_left_pt
    fmt_right = page_width_pt - margin_right_pt
    fmt_top = margin_top_pt
    fmt_bottom = page_height_pt - margin_bottom_pt

    pages = [
        PageGeometry(
            page_number=p.page_number,
            page_width_pt=page_width_pt,
            page_height_pt=page_height_pt,
            margin_left_pt=margin_left_pt,
            margin_right_pt=margin_right_pt,
            margin_top_pt=margin_top_pt,
            margin_bottom_pt=margin_bottom_pt,
            text_area_width_pt=text_area_width_pt,
            text_area_height_pt=text_area_height_pt,
            font_name=profile.body_font,
            font_size_pt=float(profile.body_font_pt),
            line_spacing_pt=float(profile.line_spacing_pt),
            lines_per_page=profile.lines_per_page,
            format_box_left_pt=fmt_left,
            format_box_right_pt=fmt_right,
            format_box_top_pt=fmt_top,
            format_box_bottom_pt=fmt_bottom,
            format_box_line_pt=float(profile.format_box_line_pt),
            line_num_column_pt=line_num_column_pt,
            tab_stops_pt=tab_stops_pt,
            header_page_num=p.page_number,
            slots=tuple(p.slots),
        )
        for p in paginated.pages
    ]

    return GeometryDocument(profile=profile, pages=pages)
