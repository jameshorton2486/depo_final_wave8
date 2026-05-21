"""Stage S — the deterministic structural rendering layer.

Consumes the immutable RAW transcript + confirmed speaker mapping and
produces a structurally compliant WORKING render: Q/A segmentation,
colloquy isolation, objection isolation, off-record suppression, and
procedural parentheticals.

Stage S never mutates RAW and never invents words. See
docs/wave13_stage_s_structural.md.
"""
from backend.stage_s.models import RenderLine
from backend.stage_s.renderer import render_stage_s

__all__ = ["RenderLine", "render_stage_s"]
