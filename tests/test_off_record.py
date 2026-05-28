"""Wave 13 — off-record state machine tests.

Off-record text must be SUPPRESSED from the structured Q/A render but
still present in the data (tagged OFF_RECORD), never deleted.
"""
from __future__ import annotations

from backend.stage_s import off_record
from backend.stage_s.models import OFF_RECORD, ON_RECORD
from backend.stage_s.renderer import render_stage_s


def _parts():
    return [
        {"participant_id": "p1", "role": "examining_attorney",
         "name": "Nunez", "honorific": "MR",
         "speaker_indices": "[1]", "sort_order": 0},
        {"participant_id": "p4", "role": "videographer", "name": None,
         "honorific": None, "speaker_indices": "[9]", "sort_order": 1},
    ]


def _utt(uid, idx, spk, text):
    return {"utterance_id": uid, "utterance_index": idx,
            "speaker_index": spk, "speaker_label": f"Speaker {spk}",
            "text": text}


# --- trigger detection ----------------------------------------------

def test_off_trigger_detected_in_videographer_block():
    assert off_record.detect_transition(
        "videographer", "We are going off the record.") == "OFF"


def test_on_trigger_back_on_the_record():
    assert off_record.detect_transition(
        "videographer", "We are back on the record.") == "ON"


def test_on_trigger_we_are_back():
    assert off_record.detect_transition(
        "videographer", "We are back, the time is 9:20.") == "ON"


def test_plain_on_the_record_is_not_a_trigger():
    # "Are we on the record?" must NOT flip state.
    assert off_record.detect_transition(
        "videographer", "Are we on the record?") is None


def test_trigger_ignored_outside_videographer_role():
    # An attorney saying "off the record" is not a state transition.
    assert off_record.detect_transition(
        "examining_attorney", "Let's go off the record.") is None


def test_time_extraction():
    assert off_record.extract_time("off the record at 9:15 a.m.") == "9:15 a.m"
    assert off_record.extract_time("no time mentioned") == ""


# --- render behaviour -----------------------------------------------

def test_off_record_text_is_tagged_not_deleted():
    utts = [
        _utt("u1", 0, 9, "We are going off the record at 9:15 a.m."),
        _utt("u2", 1, 1, "This is said while off the record."),
        _utt("u3", 2, 9, "We are back on the record at 9:20 a.m."),
    ]
    r = render_stage_s(utts, _parts())
    # The off-record utterance still appears as a line...
    off_lines = [l for l in r.lines if l.render_state == OFF_RECORD
                 and not l.procedural]
    assert any("said while off the record" in l.text for l in off_lines)
    # ...and is tagged OFF_RECORD, not erased.
    assert all(l.render_state == OFF_RECORD for l in off_lines)


def test_off_record_emits_recess_parenthetical():
    utts = [_utt("u1", 0, 9, "Off the record at 9:15 a.m.")]
    r = render_stage_s(utts, _parts())
    assert any("recess was taken at 9:15 a.m" in l.text for l in r.lines)


def test_on_record_reemits_by_line():
    utts = [
        _utt("u1", 0, 1, "First question before recess."),
        _utt("u2", 1, 9, "Off the record at 9:15 a.m."),
        _utt("u3", 2, 9, "Back on the record at 9:20 a.m."),
    ]
    r = render_stage_s(utts, _parts())
    by_lines = [l for l in r.lines if l.line_type == "by_line"]
    # Two BY-lines now: the opening-ritual attribution emitted before the
    # first Q, and the resumption re-attribution after the recess.
    assert len(by_lines) == 2
    assert all("BY MR. NUNEZ:" in l.text for l in by_lines)


def test_state_returns_to_on_record_after_resumption():
    utts = [
        _utt("u1", 0, 9, "Off the record at 9:15 a.m."),
        _utt("u2", 1, 9, "Back on the record at 9:20 a.m."),
        _utt("u3", 2, 1, "Question after the break."),
    ]
    r = render_stage_s(utts, _parts())
    last = r.lines[-1]
    assert last.render_state == ON_RECORD
    assert last.line_type == "Q"
