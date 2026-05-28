"""Stage S render object model.

A single RenderLine dataclass with a line_type field -- deliberately
flat, not a subclass per line kind. Every RenderLine carries
source_utterance_ids pointing back to the RAW transcript so any
rendered line is traceable to its origin (reversibility is mandatory).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Render-state constants.
ON_RECORD = "ON_RECORD"
OFF_RECORD = "OFF_RECORD"

# Line types.
LINE_Q = "Q"                       # examination question
LINE_A = "A"                       # witness answer
LINE_COLLOQUY = "colloquy"         # named speaker, not Q/A
LINE_PARENTHETICAL = "parenthetical"
LINE_BY = "by_line"                # "BY MR. SMITH:" attribution line
LINE_EXAMINATION = "examination"   # "EXAMINATION" section header
LINE_FLAGGED = "flagged"           # unmapped cluster
LINE_BLANK = "blank"

# Tab levels (semantic -- the export layer resolves these to twips).
TAB_MARGIN = 0
TAB_QA_DESIGNATION = 1             # "Q." / "A." sit here
TAB_QA_TEXT = 2                    # Q/A spoken text begins here
TAB_COLLOQUY = 3                   # colloquy speaker label
TAB_PARENTHETICAL = 4              # procedural parentheticals


@dataclass
class RenderLine:
    """One structurally-rendered line of the WORKING transcript."""

    line_id: str
    line_type: str
    text: str = ""
    speaker_label: str = ""
    source_utterance_ids: list[str] = field(default_factory=list)
    tab_level: int = TAB_MARGIN
    procedural: bool = False        # True => generated procedural line
    render_state: str = ON_RECORD
    audit_note: str = ""

    def to_dict(self) -> dict:
        return {
            "line_id": self.line_id,
            "line_type": self.line_type,
            "text": self.text,
            "speaker_label": self.speaker_label,
            "source_utterance_ids": list(self.source_utterance_ids),
            "tab_level": self.tab_level,
            "procedural": self.procedural,
            "render_state": self.render_state,
            "audit_note": self.audit_note,
        }
