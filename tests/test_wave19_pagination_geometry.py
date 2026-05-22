"""Wave 19 — Pagination Engine + Geometry Layer tests."""
from __future__ import annotations

from backend.geometry.engine import apply_geometry, GeometryDocument
from backend.geometry.profile import TEXAS_UFM, TWIPS_PER_INCH
from backend.pagination.flow_rules import can_start_on_page
from backend.pagination.model import LINES_PER_PAGE, PhysicalLine
from backend.pagination.paginator import paginate, paginated_to_render_check
from backend.pagination.wrapping import wrap_render_line
from backend.stage_s.models import RenderLine


def _rline(i: int, text: str, tab: int = 2, ltype: str = "qa") -> RenderLine:
    return RenderLine(line_id=f"L{i}", line_type=ltype, text=text,
                      tab_level=tab)


# --- wrapping (RenderLine -> PhysicalLine) --------------------------

def test_short_line_wraps_to_one_physical_line():
    phys = wrap_render_line(_rline(1, "Short line."), width=58)
    assert len(phys) == 1
    assert phys[0].is_continuation is False


def test_long_line_wraps_to_multiple_physical_lines():
    long_text = " ".join(["word"] * 60)
    phys = wrap_render_line(_rline(1, long_text), width=58)
    assert len(phys) > 1
    # first line is not a continuation; the rest are
    assert phys[0].is_continuation is False
    assert all(p.is_continuation for p in phys[1:])


def test_wrap_never_drops_a_word():
    text = " ".join(f"w{i}" for i in range(40))
    phys = wrap_render_line(_rline(1, text), width=20)
    rejoined = " ".join(p.text for p in phys)
    assert rejoined.split() == text.split()


def test_wrap_preserves_tab_level():
    phys = wrap_render_line(_rline(1, "x " * 50, tab=4), width=20)
    assert all(p.tab_level == 4 for p in phys)


# --- pagination ------------------------------------------------------

def test_pages_have_exactly_25_slots():
    lines = [_rline(i, f"Line {i}.") for i in range(70)]
    doc = paginate(lines)
    assert all(len(p.slots) == LINES_PER_PAGE for p in doc.pages)


def test_no_render_line_is_lost():
    lines = [_rline(i, f"Render line {i} has a few words.")
             for i in range(50)]
    doc = paginate(lines)
    chk = paginated_to_render_check(doc)
    # 50 short lines -> 50 physical lines placed.
    assert chk["placed_lines"] == 50


def test_pagination_is_deterministic():
    lines = [_rline(i, f"Deterministic line {i}.") for i in range(80)]
    a = paginate(lines)
    b = paginate(lines)
    assert a.to_dict() == b.to_dict()


def test_continuation_recorded_when_structure_spans_pages():
    # A single very long render line that must cross a page boundary.
    long_text = " ".join(["word"] * 800)
    doc = paginate([_rline(1, long_text, tab=2)])
    assert doc.total_pages >= 2
    assert len(doc.continuations) >= 1
    assert doc.continuations[0].render_line_id == "L1"


def test_slot_numbers_are_1_to_25():
    doc = paginate([_rline(i, f"Line {i}.") for i in range(30)])
    for page in doc.pages:
        assert [s.slot_number for s in page.slots] == list(range(1, 26))


def test_empty_input_is_safe():
    doc = paginate([])
    assert doc.total_pages == 1
    assert all(s.is_empty for s in doc.pages[0].slots)


# --- flow rules ------------------------------------------------------

def test_structure_does_not_start_with_too_few_slots():
    # 1 slot left, a 3-line structure that is not keep-together:
    # needs MIN_LINES_TO_START (2) -> cannot start.
    phys = [PhysicalLine(text="x", tab_level=2, line_type="qa",
                         source_render_line_id="L1") for _ in range(3)]
    assert can_start_on_page(1, phys) is False
    assert can_start_on_page(2, phys) is True


def test_structure_can_start_with_enough_slots():
    phys = [PhysicalLine(text="x", tab_level=2, line_type="qa",
                         source_render_line_id="L1")]
    assert can_start_on_page(5, phys) is True


# --- geometry profile ------------------------------------------------

def test_texas_ufm_margins():
    g = TEXAS_UFM
    assert g.margin_top_twips == 1440       # 1.0"
    assert g.margin_left_twips == 1800      # 1.25"
    assert g.page_width_twips == 12240      # 8.5"


def test_texas_ufm_tab_system():
    g = TEXAS_UFM
    # The 5-tab system, in twips.
    assert g.tab_twips(1) == 360            # Q./A. designations
    assert g.tab_twips(2) == 900            # Q/A text
    assert g.tab_twips(3) == 1440           # speaker labels
    assert g.tab_twips(4) == 2160           # parentheticals
    assert g.tab_twips(5) == 2880           # deep indent
    assert g.tab_twips(0) == 0              # left margin


def test_texas_ufm_typography():
    g = TEXAS_UFM
    assert g.body_font == "Courier New"
    assert g.body_font_pt == 12
    assert g.lines_per_page == 25
    assert g.line_spacing_pt == 28          # James's locked decision


def test_text_area_height_is_9_inches():
    # 11" - 1" top - 1" bottom = 9"
    assert TEXAS_UFM.text_area_height_twips == 9 * TWIPS_PER_INCH


# --- geometry engine (apply_geometry) -----------------------------------

def test_apply_geometry_returns_geometry_document():
    doc = paginate([_rline(i, f"Line {i}.") for i in range(30)])
    geo = apply_geometry(doc, TEXAS_UFM)
    assert isinstance(geo, GeometryDocument)
    assert geo.total_pages == doc.total_pages


def test_geometry_document_page_count_matches():
    lines = [_rline(i, f"Line {i}.") for i in range(60)]
    doc = paginate(lines)
    geo = apply_geometry(doc)
    assert geo.total_pages == doc.total_pages


def test_geometry_measurements_match_texas_ufm():
    doc = paginate([_rline(0, "Test line.")])
    geo = apply_geometry(doc, TEXAS_UFM)
    pg = geo.pages[0]
    # 1.25" left margin = 1800 twips = 90pt
    assert abs(pg.margin_left_pt - 90.0) < 0.01
    # 1.0" top margin = 1440 twips = 72pt
    assert abs(pg.margin_top_pt - 72.0) < 0.01
    # 8.5" page width = 12240 twips = 612pt
    assert abs(pg.page_width_pt - 612.0) < 0.01
    # 11" page height = 15840 twips = 792pt
    assert abs(pg.page_height_pt - 792.0) < 0.01


def test_geometry_font_from_profile():
    doc = paginate([_rline(0, "Test.")])
    geo = apply_geometry(doc, TEXAS_UFM)
    assert geo.pages[0].font_name == "Courier New"
    assert geo.pages[0].font_size_pt == 12.0
    assert geo.pages[0].line_spacing_pt == 28.0


def test_geometry_format_box_coords():
    doc = paginate([_rline(0, "Test.")])
    geo = apply_geometry(doc, TEXAS_UFM)
    pg = geo.pages[0]
    # Format box left = left margin, right = page_width - right_margin
    assert abs(pg.format_box_left_pt - pg.margin_left_pt) < 0.01
    assert abs(pg.format_box_right_pt - (pg.page_width_pt - pg.margin_right_pt)) < 0.01
    assert abs(pg.format_box_top_pt - pg.margin_top_pt) < 0.01
    assert abs(pg.format_box_bottom_pt - (pg.page_height_pt - pg.margin_bottom_pt)) < 0.01


def test_geometry_slots_match_paginated_document():
    lines = [_rline(i, f"Line {i}.") for i in range(30)]
    doc = paginate(lines)
    geo = apply_geometry(doc, TEXAS_UFM)
    for p_idx, page in enumerate(doc.pages):
        assert len(geo.pages[p_idx].slots) == LINES_PER_PAGE


def test_geometry_empty_paginated_document():
    doc = paginate([])
    geo = apply_geometry(doc, TEXAS_UFM)
    assert geo.total_pages == 1
    assert len(geo.pages[0].slots) == LINES_PER_PAGE
