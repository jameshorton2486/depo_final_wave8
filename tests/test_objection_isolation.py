"""Wave 13 — objection isolation tests.

Embedded objections must be pulled out into standalone colloquy blocks,
and the interruption marked with spaced double-hyphens. RAW is never
mutated -- dashes are added to the rendered line text only.
"""
from __future__ import annotations

from backend.stage_s import objection_handler as OH
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
    ]


def _utt(uid, idx, spk, text):
    return {"utterance_id": uid, "utterance_index": idx,
            "speaker_index": spk, "speaker_label": f"Speaker {spk}",
            "text": text}


# --- handler primitives ---------------------------------------------

def test_recognizes_objection():
    assert OH.looks_like_objection("Objection, form.")
    assert OH.looks_like_objection("Object to the form.")
    assert not OH.looks_like_objection("Yes, that is correct.")


def test_append_interruption_dash():
    out, inserted = OH.append_interruption_dash("were you there in 2019")
    assert inserted
    assert out.endswith("--")


def test_append_dash_strips_trailing_comma():
    # Morson Rule 91: no comma immediately before the dash.
    out, _ = OH.append_interruption_dash("were you there in 2019,")
    assert out.endswith("2019 --")
    assert ", --" not in out


def test_append_dash_idempotent():
    once, _ = OH.append_interruption_dash("text")
    twice, inserted = OH.append_interruption_dash(once)
    assert not inserted
    assert once == twice


def test_prepend_resumption_dash():
    out, inserted = OH.prepend_resumption_dash("were you there in 2019?")
    assert inserted
    assert out.startswith("--")


# --- render behaviour -----------------------------------------------

def test_objection_isolated_to_standalone_colloquy():
    utts = [
        _utt("u1", 0, 1, "And were you employed there in 2019,"),
        _utt("u2", 1, 5, "Objection, form."),
        _utt("u3", 2, 1, "were you employed there in 2019?"),
    ]
    r = render_stage_s(utts, _parts())
    obj = [l for l in r.lines if l.line_type == "colloquy"]
    assert len(obj) == 1
    assert obj[0].text.startswith("MS. ZAHN:")
    assert "Objection" in obj[0].text


def test_interrupted_question_gets_trailing_dash():
    utts = [
        _utt("u1", 0, 1, "And were you employed there in 2019,"),
        _utt("u2", 1, 5, "Objection, form."),
        _utt("u3", 2, 1, "were you employed there in 2019?"),
    ]
    r = render_stage_s(utts, _parts())
    q_lines = [l for l in r.lines if l.line_type == "Q"]
    assert q_lines[0].text.endswith("--")


def test_resumed_question_after_objection_gets_inline_reattribution():
    # A fresh question resuming after an objection interjection carries the
    # inline "(BY MR. NUNEZ)" re-attribution and NO leading dash -- matching
    # the source depositions (e.g. Shaw: 'Q.  (BY MR. COLEMAN)  ...' after
    # 'Objection.  Form.'). The auto resumption dash is suppressed here; the
    # marker carries the re-attribution.
    utts = [
        _utt("u1", 0, 1, "And were you employed there in 2019,"),
        _utt("u2", 1, 5, "Objection, form."),
        _utt("u3", 2, 1, "were you employed there in 2019?"),
    ]
    r = render_stage_s(utts, _parts())
    q_lines = [l for l in r.lines if l.line_type == "Q"]
    assert q_lines[1].text.startswith("(BY MR. NUNEZ)")
    assert not q_lines[1].text.startswith("--")
    assert "were you employed there in 2019?" in q_lines[1].text


def test_objection_does_not_repeat_question_text():
    utts = [
        _utt("u1", 0, 1, "And were you employed there in 2019,"),
        _utt("u2", 1, 5, "Objection, form."),
        _utt("u3", 2, 1, "were you employed there in 2019?"),
    ]
    r = render_stage_s(utts, _parts())
    # No invented "(Continuing)" text anywhere.
    assert all("Continuing" not in l.text for l in r.lines)


def test_raw_utterance_not_mutated_by_dash_insertion():
    utts = [
        _utt("u1", 0, 1, "And were you employed there in 2019,"),
        _utt("u2", 1, 5, "Objection, form."),
        _utt("u3", 2, 1, "were you employed there in 2019?"),
    ]
    raw_before = [u["text"] for u in utts]
    render_stage_s(utts, _parts())
    assert [u["text"] for u in utts] == raw_before


def test_dash_insertion_is_audited():
    utts = [
        _utt("u1", 0, 1, "And were you employed there in 2019,"),
        _utt("u2", 1, 5, "Objection, form."),
        _utt("u3", 2, 1, "were you employed there in 2019?"),
    ]
    r = render_stage_s(utts, _parts())
    kinds = [a["kind"] for a in r.audit]
    assert "dash_inserted" in kinds
    assert "objection_isolated" in kinds
