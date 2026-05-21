"""Wave 13 — render idempotency & immutability tests.

Running the Stage S renderer multiple times must produce byte-identical
structural output and must never corrupt or mutate its inputs.
"""
from __future__ import annotations

import copy

from backend.stage_s.renderer import render_stage_s


def _parts():
    return [
        {"participant_id": "p1", "role": "examining_attorney",
         "name": "Nunez", "honorific": "MR",
         "speaker_indices": "[1]", "sort_order": 0},
        {"participant_id": "p2", "role": "witness", "name": "Thomas",
         "honorific": "MR", "speaker_indices": "[2]", "sort_order": 1},
        {"participant_id": "p3", "role": "defending_attorney",
         "name": "Zahn", "honorific": "MS",
         "speaker_indices": "[5]", "sort_order": 2},
        {"participant_id": "p4", "role": "videographer", "name": None,
         "honorific": None, "speaker_indices": "[9]", "sort_order": 3},
    ]


def _utts():
    return [
        {"utterance_id": "u1", "utterance_index": 0, "speaker_index": 9,
         "speaker_label": "Speaker 9", "text": "On the record at 9:00 a.m."},
        {"utterance_id": "u2", "utterance_index": 1, "speaker_index": 1,
         "speaker_label": "Speaker 1", "text": "State your name,"},
        {"utterance_id": "u3", "utterance_index": 2, "speaker_index": 5,
         "speaker_label": "Speaker 5", "text": "Objection, form."},
        {"utterance_id": "u4", "utterance_index": 3, "speaker_index": 1,
         "speaker_label": "Speaker 1", "text": "please state your name."},
        {"utterance_id": "u5", "utterance_index": 4, "speaker_index": 2,
         "speaker_label": "Speaker 2", "text": "Heath Thomas."},
        {"utterance_id": "u6", "utterance_index": 5, "speaker_index": 9,
         "speaker_label": "Speaker 9", "text": "Off the record at 9:30 a.m."},
        {"utterance_id": "u7", "utterance_index": 6, "speaker_index": 1,
         "speaker_label": "Speaker 1", "text": "Side discussion here."},
        {"utterance_id": "u8", "utterance_index": 7, "speaker_index": 9,
         "speaker_label": "Speaker 9", "text": "Back on the record at 9:35 a.m."},
        {"utterance_id": "u9", "utterance_index": 8, "speaker_index": 1,
         "speaker_label": "Speaker 1", "text": "Were you employed there?"},
    ]


def test_render_is_idempotent():
    a = render_stage_s(_utts(), _parts()).to_dict()
    b = render_stage_s(_utts(), _parts()).to_dict()
    assert a == b


def test_double_render_same_object_inputs():
    utts, parts = _utts(), _parts()
    a = render_stage_s(utts, parts).to_dict()
    b = render_stage_s(utts, parts).to_dict()
    assert a == b


def test_render_does_not_mutate_utterances():
    utts = _utts()
    snapshot = copy.deepcopy(utts)
    render_stage_s(utts, _parts())
    assert utts == snapshot


def test_render_does_not_mutate_participants():
    parts = _parts()
    snapshot = copy.deepcopy(parts)
    render_stage_s(_utts(), parts)
    assert parts == snapshot


def test_line_ids_are_stable_across_runs():
    a = render_stage_s(_utts(), _parts())
    b = render_stage_s(_utts(), _parts())
    assert [l.line_id for l in a.lines] == [l.line_id for l in b.lines]


def test_audit_is_stable_across_runs():
    a = render_stage_s(_utts(), _parts())
    b = render_stage_s(_utts(), _parts())
    assert a.audit == b.audit
