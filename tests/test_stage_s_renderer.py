"""Wave 13 — Stage S renderer tests: render consistency, segmentation."""
from __future__ import annotations

from backend.stage_s.renderer import render_stage_s


def _participants():
    return [
        {"participant_id": "p1", "role": "examining_attorney",
         "name": "Steven Nunez", "honorific": "MR",
         "speaker_indices": "[1]", "sort_order": 0},
        {"participant_id": "p2", "role": "witness",
         "name": "Heath Thomas", "honorific": "MR",
         "speaker_indices": "[2]", "sort_order": 1},
        {"participant_id": "p3", "role": "defending_attorney",
         "name": "Lucia Zahn", "honorific": "MS",
         "speaker_indices": "[5]", "sort_order": 2},
        {"participant_id": "p4", "role": "videographer", "name": None,
         "honorific": None, "speaker_indices": "[9]", "sort_order": 3},
    ]


def _utt(uid, idx, spk, text):
    return {"utterance_id": uid, "utterance_index": idx,
            "speaker_index": spk, "speaker_label": f"Speaker {spk}",
            "text": text}


def test_examining_attorney_renders_as_q():
    utts = [_utt("u1", 0, 1, "State your name.")]
    r = render_stage_s(utts, _participants())
    # The QA-01 opening ritual (EXAMINATION header + BY-line) now precedes
    # the first question. The examining attorney's utterance is still
    # typed Q -- it is now the last of the three opening lines.
    assert [ln.line_type for ln in r.lines] == ["examination", "by_line", "Q"]
    assert r.lines[-1].line_type == "Q"
    assert r.lines[-1].text == "State your name."


def test_witness_renders_as_a():
    utts = [_utt("u1", 0, 2, "Heath Thomas.")]
    r = render_stage_s(utts, _participants())
    assert r.lines[0].line_type == "A"


def test_other_role_renders_as_colloquy():
    utts = [_utt("u1", 0, 5, "We have a stipulation.")]
    r = render_stage_s(utts, _participants())
    assert r.lines[0].line_type == "colloquy"
    assert r.lines[0].text.startswith("MS. ZAHN:")


def test_colloquy_has_two_space_gap():
    utts = [_utt("u1", 0, 5, "We have a stipulation.")]
    r = render_stage_s(utts, _participants())
    assert "MS. ZAHN:  We have" in r.lines[0].text


def test_unmapped_cluster_is_flagged():
    utts = [_utt("u1", 0, 88, "Who is speaking here.")]
    r = render_stage_s(utts, _participants())
    assert r.lines[0].line_type == "flagged"
    assert r.lines[0].text == "Who is speaking here."


def test_every_line_traces_to_source():
    utts = [_utt("u1", 0, 1, "State your name."),
            _utt("u2", 1, 2, "Heath Thomas.")]
    r = render_stage_s(utts, _participants())
    # Non-procedural lines must carry a source utterance id.
    for ln in r.lines:
        if not ln.procedural and ln.line_type != "blank":
            assert ln.source_utterance_ids


def test_render_does_not_mutate_input():
    utts = [_utt("u1", 0, 1, "State your name.")]
    before = utts[0]["text"]
    render_stage_s(utts, _participants())
    assert utts[0]["text"] == before  # RAW untouched


def test_empty_transcript_is_safe():
    r = render_stage_s([], _participants())
    assert r.lines == []
