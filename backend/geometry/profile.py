"""Geometry profiles — Wave 19B.

A GeometryProfile holds the exact physical measurements for one
jurisdiction's transcript format. TEXAS_UFM is the only profile built;
the abstraction exists so California / arbitration profiles can be
added later without reworking the Geometry Layer.

All values are James's authoritative UFM measurements. Twips are the
Word unit: 1 inch = 1440 twips, 1 point = 20 twips.
"""
from __future__ import annotations

from dataclasses import dataclass, field

TWIPS_PER_INCH = 1440
TWIPS_PER_POINT = 20


@dataclass(frozen=True)
class GeometryProfile:
    """Exact physical geometry for one transcript format."""

    name: str

    # --- page size (8.5 x 11 US Letter) ---
    page_width_twips: int = 12240
    page_height_twips: int = 15840

    # --- margins ---
    margin_top_twips: int = 1440        # 1.0"
    margin_bottom_twips: int = 1440     # 1.0"
    margin_left_twips: int = 1800       # 1.25"
    margin_right_twips: int = 1440      # 1.0"

    # --- format box ---
    # Solid black marginal lines enclosing the text.
    format_box_line_pt: float = 0.75
    # NOTE — measurement conflict flagged for James: the UFM spec
    # requires a text area >= 6.5" AND a 1.25" left + 1.0" right margin.
    # On an 8.5" page those cannot both hold (8.5 - 1.25 - 1.0 = 6.25").
    # text_area_width_twips below resolves to 9000 (6.25"). If the 6.5"
    # minimum is firm, the left margin must drop to 1.0". Awaiting
    # James's call; the margins as given are used until then.
    text_area_min_width_inches: float = 6.5

    # --- typography ---
    body_font: str = "Courier New"
    body_font_pt: int = 12
    lines_per_page: int = 25
    # UFM line spacing. James's locked decision: EXACTLY at 28pt.
    # This single constant is the one value to adjust if printed
    # output ever drifts off exactly 25 lines per page.
    line_spacing_pt: int = 28
    space_before_pt: int = 0
    space_after_pt: int = 0

    # --- the 5-tab system (twips from the left text margin) ---
    # Tab 1: Q./A. designations.  Tab 2: Q/A text start.
    # Tab 3: speaker labels.  Tab 4: procedural parentheticals.
    # Tab 5: deep indentation.
    tab_stops_twips: tuple = (360, 900, 1440, 2160, 2880)

    # --- character-per-line range (UFM: 56-63) ---
    chars_per_line_min: int = 56
    chars_per_line_max: int = 63

    @property
    def text_area_width_twips(self) -> int:
        return (self.page_width_twips
                - self.margin_left_twips - self.margin_right_twips)

    @property
    def text_area_height_twips(self) -> int:
        return (self.page_height_twips
                - self.margin_top_twips - self.margin_bottom_twips)

    def tab_twips(self, tab_number: int) -> int:
        """Twips for tab 1..5. Tab 0 is the left margin (0 twips)."""
        if tab_number <= 0:
            return 0
        idx = min(tab_number, len(self.tab_stops_twips)) - 1
        return self.tab_stops_twips[idx]


# The authoritative Texas UFM profile (James's measurements).
TEXAS_UFM = GeometryProfile(name="texas_ufm")
