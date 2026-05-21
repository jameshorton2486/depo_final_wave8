"""Stage S colloquy formatting.

Type 3 lines: a named speaker who is neither the examining attorney
(Q.) nor the witness (A.). Rendered with the speaker label at tab 3,
ALL CAPS, a colon, and exactly two spaces, with the spoken text inline
on the same line.

This module produces the *semantic* line. The two-space colon and tab
geometry are recorded as data; the export layer paints the pixels.
"""
from __future__ import annotations

# Exactly two spaces follow the colon (Morson's Rule 36 / UFM 2.11).
COLON_GAP = "  "


def colloquy_label(speaker_label: str) -> str:
    """Normalise a colloquy speaker label to ALL CAPS with trailing colon.

    "Mr. Vance" -> "MR. VANCE:"
    """
    base = (speaker_label or "").strip().upper().rstrip(":")
    return f"{base}:" if base else ":"


def colloquy_inline_text(speaker_label: str, text: str) -> str:
    """Build the inline colloquy line body: 'LABEL:  spoken text'.

    The label and text share one line; the two-space gap is mandated.
    """
    label = colloquy_label(speaker_label)
    body = (text or "").strip()
    return f"{label}{COLON_GAP}{body}" if body else label
