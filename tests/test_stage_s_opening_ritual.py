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


# --- Phase 4: inline re-attribution on resumption --------------------------

def test_reattribution_after_colloquy_interruption():
    # Q, then a defending-attorney colloquy (breaks attribution), then the
    # examiner resumes -> the resumed Q gets the inline (BY MR. COLEMAN).
    utts = [
        _utt("u1", 0, 1, "I don't remember that."),
        _utt("u2", 1, 5, "I think we met at your office."),
        _utt("u3", 2, 1, "Yes, that's mine."),
    ]
    r = render_stage_s(utts, _participants())
    q_lines = [ln for ln in r.lines if ln.line_type == "Q"]
    # First Q has no inline marker (it follows the opening BY-line).
    assert "(BY MR. COLEMAN)" not in q_lines[0].text
    # Resumed Q after the colloquy carries the inline re-attribution.
    assert q_lines[1].text.startswith("(BY MR. COLEMAN)")
    assert "Yes, that's mine." in q_lines[1].text


def test_no_reattribution_in_unbroken_exchange():
    # Q -> A -> Q with no interruption: the second Q gets no inline marker.
    utts = [
        _utt("u1", 0, 1, "State your name."),
        _utt("u2", 1, 2, "David Shaw."),
        _utt("u3", 2, 1, "Where do you live?"),
    ]
    r = render_stage_s(utts, _participants())
    q_lines = [ln for ln in r.lines if ln.line_type == "Q"]
    assert all("(BY MR." not in ln.text for ln in q_lines)
    assert q_lines[1].text == "Where do you live?"


def test_same_speaker_continuation_preserves_verbatim_dash():
    # GUARDRAIL: when the SAME examiner completes their own interrupted
    # sentence, the prior emitted line is their own Q (not a colloquy /
    # parenthetical), so attribution is NOT broken -> no inline marker is
    # added, and a verbatim leading dash in the text is preserved as-is.
    utts = [
        _utt("u1", 0, 1, "You can still answer --"),
        _utt("u2", 1, 1, "-- the question."),
    ]
    r = render_stage_s(utts, _participants())
    q_lines = [ln for ln in r.lines if ln.line_type == "Q"]
    assert q_lines[1].text == "-- the question."
    assert "(BY MR." not in q_lines[1].text
