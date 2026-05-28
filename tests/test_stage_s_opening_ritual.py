"""Stage 3 opening-ritual + QA-01 trigger gate tests.

New tests for the opening-ritual build pass (EXAMINATION header, BY-line,
inline re-attribution). Kept in a dedicated file so the pass adds tests
without editing the existing stage_s renderer test suite.
"""
from __future__ import annotations

from backend.stage_s import models
from backend.stage_s.line_builder import examination_header_line
from backend.stage_s.renderer import render_stage_s


def _participants():
    return [
        {"participant_id": "p1", "role": "examining_attorney",
         "name": "Coleman", "honorific": "MR",
         "speaker_indices": "[1]", "sort_order": 0},
        {"participant_id": "p2", "role": "witness",
         "name": "David Shaw", "honorific": "MR",
         "speaker_indices": "[2]", "sort_order": 1},
        {"participant_id": "p3", "role": "defending_attorney",
         "name": "Norman", "honorific": "MS",
         "speaker_indices": "[5]", "sort_order": 2},
    ]


def _utt(uid, idx, spk, text):
    return {"utterance_id": uid, "utterance_index": idx,
            "speaker_index": spk, "speaker_label": f"Speaker {spk}",
            "text": text}


# --- Phase 1: LINE_EXAMINATION constant -----------------------------------

def test_line_examination_constant_exists():
    assert hasattr(models, "LINE_EXAMINATION")
    assert models.LINE_EXAMINATION == "examination"


# --- Phase 2: examination_header_line factory ------------------------------

def test_examination_header_line_shape():
    ln = examination_header_line("s-0001")
    assert ln.line_type == models.LINE_EXAMINATION
    assert ln.text == "EXAMINATION"
    assert ln.procedural is True
    assert ln.source_utterance_ids == []
    assert ln.line_id == "s-0001"


# --- Phase 3: opening ritual + trigger gate --------------------------------

def test_opening_ritual_precedes_first_question():
    utts = [_utt("u1", 0, 1, "Please state your full name.")]
    r = render_stage_s(utts, _participants())
    assert [ln.line_type for ln in r.lines] == ["examination", "by_line", "Q"]
    # EXAMINATION header first, then BY-line naming the examiner, then Q.
    assert r.lines[0].text == "EXAMINATION"
    assert r.lines[1].text == "BY MR. COLEMAN:"
    assert r.lines[2].line_type == "Q"
    assert r.lines[2].text == "Please state your full name."


def test_ritual_emitted_once_not_repeated():
    # Q, A, Q -- the ritual must fire only before the FIRST Q.
    utts = [
        _utt("u1", 0, 1, "State your name."),
        _utt("u2", 1, 2, "David Shaw."),
        _utt("u3", 2, 1, "Where do you live?"),
    ]
    r = render_stage_s(utts, _participants())
    types = [ln.line_type for ln in r.lines]
    assert types.count("examination") == 1
    assert types.count("by_line") == 1
    assert types == ["examination", "by_line", "Q", "A", "Q"]


def test_no_ritual_without_examining_attorney():
    # A transcript with no examining-attorney utterance never opens an
    # examination, so no ritual lines are emitted.
    utts = [_utt("u1", 0, 5, "We have a stipulation.")]
    r = render_stage_s(utts, _participants())
    assert all(ln.line_type != "examination" for ln in r.lines)
    assert all(ln.line_type != "by_line" for ln in r.lines)


def test_by_line_carries_examiner_label():
    utts = [_utt("u1", 0, 1, "State your name.")]
    r = render_stage_s(utts, _participants())
    by_lines = [ln for ln in r.lines if ln.line_type == "by_line"]
    assert len(by_lines) == 1
    assert by_lines[0].text == "BY MR. COLEMAN:"
