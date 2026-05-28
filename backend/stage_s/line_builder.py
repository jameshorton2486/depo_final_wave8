"""Stage S line builder.

Converts one mapped RAW block into one or more RenderLine objects,
given the current render state. The line builder does NOT decide
record transitions or objection ordering -- that orchestration lives
in renderer.py. It is the deterministic "block -> line(s)" primitive.
"""
from __future__ import annotations

from backend.stage_s.colloquy import colloquy_inline_text, colloquy_label
from backend.stage_s.models import (
    LINE_A,
    LINE_BY,
    LINE_COLLOQUY,
    LINE_EXAMINATION,
    LINE_FLAGGED,
    LINE_PARENTHETICAL,
    LINE_Q,
    ON_RECORD,
    RenderLine,
    TAB_COLLOQUY,
    TAB_PARENTHETICAL,
    TAB_QA_DESIGNATION,
    TAB_MARGIN,
)

# role -> Q/A mode
_QA_ROLE = {"examining_attorney": "Q", "witness": "A"}


def qa_line(
    line_id: str,
    mode: str,                 # "Q" or "A"
    text: str,
    utterance_ids: list[str],
    render_state: str = ON_RECORD,
    by_label: str = "",
) -> RenderLine:
    """Build a Type 1 Q/A line.

    When `by_label` is given the text is prefixed with the inline
    "(BY MR. SMITH)" reminder -- still a normal Q line, no new type.
    """
    body = (text or "").strip()
    if by_label:
        body = f"(BY {by_label.upper()})  {body}"
    return RenderLine(
        line_id=line_id,
        line_type=LINE_Q if mode == "Q" else LINE_A,
        text=body,
        speaker_label="",
        source_utterance_ids=list(utterance_ids),
        tab_level=TAB_QA_DESIGNATION,
        procedural=False,
        render_state=render_state,
    )


def colloquy_line(
    line_id: str,
    speaker_label: str,
    text: str,
    utterance_ids: list[str],
    render_state: str = ON_RECORD,
    audit_note: str = "",
) -> RenderLine:
    """Build a Type 3 colloquy line (named non-Q/A speaker)."""
    return RenderLine(
        line_id=line_id,
        line_type=LINE_COLLOQUY,
        text=colloquy_inline_text(speaker_label, text),
        speaker_label=colloquy_label(speaker_label),
        source_utterance_ids=list(utterance_ids),
        tab_level=TAB_COLLOQUY,
        procedural=False,
        render_state=render_state,
        audit_note=audit_note,
    )


def parenthetical_line(
    line_id: str,
    text: str,
    render_state: str = ON_RECORD,
    audit_note: str = "",
) -> RenderLine:
    """Build a Type 4 procedural parenthetical line."""
    return RenderLine(
        line_id=line_id,
        line_type=LINE_PARENTHETICAL,
        text=text,
        speaker_label="",
        source_utterance_ids=[],
        tab_level=TAB_PARENTHETICAL,
        procedural=True,
        render_state=render_state,
        audit_note=audit_note,
    )


def by_attribution_line(
    line_id: str,
    examiner_label: str,
    render_state: str = ON_RECORD,
) -> RenderLine:
    """Build a 'BY MR. SMITH:' examination attribution line."""
    label = (examiner_label or "").strip().upper().rstrip(":")
    return RenderLine(
        line_id=line_id,
        line_type=LINE_BY,
        text=f"BY {label}:",
        speaker_label=f"BY {label}:",
        source_utterance_ids=[],
        tab_level=TAB_MARGIN,
        procedural=True,
        render_state=render_state,
        audit_note="Examination attribution re-emitted after resumption.",
    )


def examination_header_line(
    line_id: str,
    render_state: str = ON_RECORD,
) -> RenderLine:
    """Build an 'EXAMINATION' section header line.

    A generated procedural line carrying the literal word EXAMINATION.
    Tab level matches by_attribution_line (TAB_MARGIN): there is no
    centered-header geometry primitive in this module, and inventing one
    is out of scope for this pass. The export/geometry layer owns final
    placement; this records the semantic line.
    """
    return RenderLine(
        line_id=line_id,
        line_type=LINE_EXAMINATION,
        text="EXAMINATION",
        speaker_label="",
        source_utterance_ids=[],
        tab_level=TAB_MARGIN,
        procedural=True,
        render_state=render_state,
        audit_note="Examination section header emitted at examination start.",
    )


def flagged_line(
    line_id: str,
    raw_label: str,
    text: str,
    utterance_ids: list[str],
    render_state: str = ON_RECORD,
) -> RenderLine:
    """Build a flagged line for an unmapped speaker cluster."""
    return RenderLine(
        line_id=line_id,
        line_type=LINE_FLAGGED,
        text=(text or "").strip(),
        speaker_label=raw_label or "UNIDENTIFIED SPEAKER",
        source_utterance_ids=list(utterance_ids),
        tab_level=TAB_COLLOQUY,
        procedural=False,
        render_state=render_state,
        audit_note="Unmapped speaker cluster -- flagged for review.",
    )


def qa_mode_for_role(role: str) -> str:
    """Return 'Q', 'A', or '' (colloquy) for a participant role."""
    return _QA_ROLE.get((role or "").strip(), "")
