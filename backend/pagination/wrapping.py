"""Line wrapping — Wave 19A.

The first Page Composition stage: RenderLine -> WrappedLines ->
PhysicalLine. Greedy word wrap to the box content width. Never splits a
word; never drops a word -- deterministic for identical input.

Wrap width comes from the geometry profile (Wave 19B supplies the
authoritative number). The UFM text area allows 56-63 characters per
line; the default here is conservative and overridable.
"""
from __future__ import annotations

from backend.pagination.model import PhysicalLine
from backend.stage_s.models import RenderLine

# UFM: 56-63 characters per line. Conservative default; the geometry
# profile overrides this with the authoritative figure.
DEFAULT_WRAP_WIDTH = 58


def _wrap_text(text: str, width: int) -> list[str]:
    """Greedy word wrap. Never splits a word; never drops a word.

    A run that is itself longer than `width` is emitted on its own
    line rather than dropped or hard-split.
    """
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
    return lines or [""]


def wrap_render_line(
    line: RenderLine,
    width: int = DEFAULT_WRAP_WIDTH,
) -> list[PhysicalLine]:
    """Wrap one RenderLine into one or more PhysicalLines.

    The first physical line carries is_continuation=False; any wrap
    remainder carries is_continuation=True. Tab level and line type are
    preserved on every physical line so the Geometry Layer can position
    them (and apply hanging-indent rules).
    """
    chunks = _wrap_text(line.text, width)
    out: list[PhysicalLine] = []
    for idx, chunk in enumerate(chunks):
        out.append(PhysicalLine(
            text=chunk,
            tab_level=line.tab_level,
            line_type=line.line_type,
            source_render_line_id=line.line_id,
            is_continuation=(idx > 0),
            procedural=line.procedural,
        ))
    return out


def wrap_render_lines(
    lines: list[RenderLine],
    width: int = DEFAULT_WRAP_WIDTH,
) -> list[PhysicalLine]:
    """Wrap a list of RenderLines into a flat list of PhysicalLines."""
    out: list[PhysicalLine] = []
    for line in lines:
        out.extend(wrap_render_line(line, width))
    return out
