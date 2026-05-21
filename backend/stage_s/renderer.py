"""Stage S master renderer.

The primary orchestrator. Consumes the RAW transcript blocks + the
confirmed Wave 9/11 speaker mapping and produces the Stage S structural
render: an ordered list of RenderLine objects plus an audit log.

Deterministic and idempotent: the same inputs always yield byte-equal
output, and the renderer never mutates its inputs.

Pipeline position:
    RAW -> mapping -> correction engine -> render_stage_s() -> export
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.stage_s import off_record, transitions
from backend.stage_s.audit import AuditLog
from backend.stage_s.line_builder import (
    by_attribution_line,
    colloquy_line,
    flagged_line,
    parenthetical_line,
    qa_line,
    qa_mode_for_role,
)
from backend.stage_s.models import OFF_RECORD, ON_RECORD, RenderLine
from backend.stage_s.objection_handler import (
    append_interruption_dash,
    looks_like_objection,
    prepend_resumption_dash,
)
from backend.stage_s.render_state import RenderState
from backend.transcript.render import build_index_map


@dataclass
class StageSResult:
    """What render_stage_s returns."""

    lines: list[RenderLine] = field(default_factory=list)
    audit: list[dict] = field(default_factory=list)
    off_record_span_count: int = 0
    objection_count: int = 0

    def to_dict(self) -> dict:
        return {
            "lines": [ln.to_dict() for ln in self.lines],
            "audit": self.audit,
            "off_record_span_count": self.off_record_span_count,
            "objection_count": self.objection_count,
        }


def render_stage_s(
    utterances: list[dict],
    participants: list[dict],
) -> StageSResult:
    """Render the RAW transcript into Stage S structural lines.

    Parameters
    ----------
    utterances
        RAW transcript utterance dicts (immutable -- never written).
    participants
        Confirmed Wave 9/11 participant mapping.

    Returns
    -------
    StageSResult -- ordered RenderLine list + audit log.
    """
    audit = AuditLog()
    state = RenderState()
    index_map = build_index_map(participants)

    # Stable ordering by utterance index.
    ordered = sorted(
        utterances,
        key=lambda u: (u.get("utterance_index")
                       if u.get("utterance_index") is not None else 0),
    )

    lines: list[RenderLine] = []
    seq = 0

    def _next_id() -> str:
        nonlocal seq
        seq += 1
        return f"s-{seq:04d}"

    # Track the last non-procedural line so an objection can retro-mark
    # the interruption dash on the line it interrupted.
    last_content_idx: int | None = None
    pending_resumption_dash = False  # next Q/A line gets a leading "--"

    for utt in ordered:
        text = (utt.get("text") or "").strip()
        idx = utt.get("speaker_index")
        utt_id = utt.get("utterance_id") or ""
        info = index_map.get(idx) if idx is not None else None
        role = info["role"] if info else None
        label = info["label"] if info else ""

        # --- record-state transition (videographer blocks only) ------
        transition = off_record.detect_transition(role, text)
        if transition:
            time = off_record.extract_time(text)
            new_state = off_record.apply_transition(state.record_state, transition)
            state.record_state = new_state
            paren = transitions.transition_parenthetical(transition, time)
            if paren:
                lines.append(parenthetical_line(
                    _next_id(), paren, render_state=new_state,
                    audit_note=f"{transition} transition parenthetical."))
                audit.record("parenthetical_emitted",
                             f"{transition} -> {paren}", [utt_id])
            if transition == "OFF":
                audit.record("off_record_span", "Off-record span begins.",
                             [utt_id])
            if transitions.needs_by_line_after(transition) and state.current_examiner_label:
                lines.append(by_attribution_line(
                    _next_id(), state.current_examiner_label,
                    render_state=new_state))
                audit.record("by_line_emitted",
                             f"Re-emitted BY {state.current_examiner_label}:",
                             [utt_id])
            last_content_idx = None
            continue

        # --- off-record content: tagged, kept, not Q/A-structured ----
        if state.record_state == OFF_RECORD:
            ln = colloquy_line(_next_id(), label or "OFF THE RECORD",
                               text, [utt_id], render_state=OFF_RECORD,
                               audit_note="Spoken during off-record span.")
            lines.append(ln)
            continue

        # --- unmapped cluster ----------------------------------------
        if info is None:
            raw_label = (utt.get("speaker_label") or "").strip() \
                or (f"Speaker {idx}" if idx is not None else "Speaker ?")
            lines.append(flagged_line(_next_id(), raw_label, text, [utt_id]))
            last_content_idx = len(lines) - 1
            continue

        mode = qa_mode_for_role(role)

        # --- objection isolation -------------------------------------
        # A non-examining, non-witness speaker whose text reads as an
        # objection interrupts the Q/A flow: isolate it, and dash-mark
        # the interrupted line + the next resuming line.
        if mode == "" and looks_like_objection(text):
            if last_content_idx is not None:
                prev = lines[last_content_idx]
                new_text, inserted = append_interruption_dash(prev.text)
                if inserted:
                    prev.text = new_text
                    prev.audit_note = (prev.audit_note + " "
                                       "Interruption dash appended.").strip()
                    audit.record("dash_inserted",
                                 "Appended interruption dash to "
                                 f"line {prev.line_id}.",
                                 prev.source_utterance_ids)
            obj_line = colloquy_line(
                _next_id(), label, text, [utt_id],
                audit_note="Objection isolated to standalone colloquy.")
            lines.append(obj_line)
            audit.record("objection_isolated",
                         f"Objection by {label} isolated.", [utt_id])
            pending_resumption_dash = True
            last_content_idx = None
            continue

        # --- normal Q / A / colloquy ---------------------------------
        if mode in ("Q", "A"):
            if mode == "Q":
                state.set_examiner(label)
            body = text
            note = ""
            if pending_resumption_dash:
                body, inserted = prepend_resumption_dash(body)
                if inserted:
                    note = "Resumption dash prepended after objection."
                    audit.record("dash_inserted",
                                 "Prepended resumption dash.", [utt_id])
                pending_resumption_dash = False
            ln = qa_line(_next_id(), mode, body, [utt_id],
                         render_state=ON_RECORD)
            if note:
                ln.audit_note = note
            lines.append(ln)
            last_content_idx = len(lines) - 1
        else:
            ln = colloquy_line(_next_id(), label, text, [utt_id])
            lines.append(ln)
            last_content_idx = len(lines) - 1
            pending_resumption_dash = False

    return StageSResult(
        lines=lines,
        audit=audit.to_list(),
        off_record_span_count=audit.count("off_record_span"),
        objection_count=audit.count("objection_isolated"),
    )
