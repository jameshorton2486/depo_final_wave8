"""Wave 11 tests — label builder, candidate names, the canonical WORKING
renderer, and the speaker-mapping apply endpoint."""
from __future__ import annotations

from backend.services.speaker_mapping import (
    build_candidate_names,
    participant_label,
    prefill_name_from_appearance,
)
from backend.transcript.render import (
    build_index_map,
    render_working_transcript,
)


# --- label builder (spec wave11 section 6.1) -------------------------

def test_label_attorney_one_space_honorific():
    assert participant_label("examining_attorney", "Steven A. Nunez", "MR") == "MR. NUNEZ"


def test_label_witness():
    assert participant_label("witness", "Heath Thomas", "MR") == "MR. THOMAS"


def test_label_honorific_normalized_from_lowercase_with_period():
    assert participant_label("defending_attorney", "Lucia Zahn", "ms.") == "MS. ZAHN"


def test_label_court_reporter_is_the_reporter_not_the_court_reporter():
    assert participant_label("court_reporter", "anything") == "THE REPORTER"


def test_label_videographer_and_interpreter():
    assert participant_label("videographer", None) == "THE VIDEOGRAPHER"
    assert participant_label("interpreter", None) == "THE INTERPRETER"


def test_label_empty_when_named_role_missing_honorific():
    # Not finalised until the honorific is set.
    assert participant_label("witness", "Heath Thomas", None) == ""


def test_label_empty_when_named_role_missing_name():
    assert participant_label("examining_attorney", None, "MR") == ""


def test_label_invalid_honorific_rejected():
    assert participant_label("witness", "Heath Thomas", "SIR") == ""


# --- candidate names (spec wave11 section 4.3) -----------------------

def test_candidate_names_includes_attorneys_and_witness():
    meta = {
        "attorneys": [
            {"name": "Steven A. Nunez", "honorific": "MR", "role": "examining_attorney"},
            {"name": "Lucia Zahn", "honorific": "MS", "role": "defending_attorney"},
        ],
        "witness": {"name": "Heath Thomas", "honorific": "MR"},
    }
    names = build_candidate_names(meta, reporter_name="Richard Vance")
    assert "MR. NUNEZ" in names
    assert "MS. ZAHN" in names
    assert "MR. THOMAS" in names


def test_candidate_names_always_includes_court_officers():
    names = build_candidate_names({}, reporter_name=None)
    assert "THE REPORTER" in names
    assert "THE VIDEOGRAPHER" in names
    assert "THE INTERPRETER" in names


def test_candidate_names_deduplicates():
    names = build_candidate_names({}, reporter_name=None)
    assert len(names) == len(set(names))


# --- deterministic appearance-statement prefill ----------------------

def test_prefill_name_from_appearance_matches_pattern():
    txt = "Lucia Zahn for the defendant Home Depot USA Inc"
    assert prefill_name_from_appearance(txt) == "Lucia Zahn"


def test_prefill_name_from_appearance_rejects_non_pattern():
    assert prefill_name_from_appearance("Good afternoon, mister Nunez.") is None


def test_prefill_name_from_appearance_none_on_empty():
    assert prefill_name_from_appearance("") is None
    assert prefill_name_from_appearance(None) is None


# --- canonical renderer ----------------------------------------------

def _sample_utterances():
    return [
        {"utterance_id": "u1", "utterance_index": 0, "speaker_index": 1,
         "speaker_label": "Speaker 1", "text": "Please state your name.", "start_time": 1.0},
        {"utterance_id": "u2", "utterance_index": 1, "speaker_index": 2,
         "speaker_label": "Speaker 2", "text": "Heath Thomas.", "start_time": 3.0},
        {"utterance_id": "u3", "utterance_index": 2, "speaker_index": 5,
         "speaker_label": "Speaker 5", "text": "Objection, form.", "start_time": 5.0},
        {"utterance_id": "u4", "utterance_index": 3, "speaker_index": 9,
         "speaker_label": "Speaker 9", "text": "Unmapped words here.", "start_time": 7.0},
    ]


def _sample_participants():
    return [
        {"participant_id": "p1", "role": "examining_attorney", "name": "Steven Nunez",
         "honorific": "MR", "speaker_indices": "[1]", "sort_order": 0},
        {"participant_id": "p2", "role": "witness", "name": "Heath Thomas",
         "honorific": "MR", "speaker_indices": "[2, 3]", "sort_order": 1},
        {"participant_id": "p3", "role": "defending_attorney", "name": "Lucia Zahn",
         "honorific": "MS", "speaker_indices": "[5]", "sort_order": 2},
    ]


def test_render_assigns_q_to_examining_attorney():
    lines = render_working_transcript(_sample_utterances(), _sample_participants())
    assert lines[0].line_type == "Q"
    assert lines[0].speaker_label == "MR. NUNEZ"


def test_render_assigns_a_to_witness():
    lines = render_working_transcript(_sample_utterances(), _sample_participants())
    assert lines[1].line_type == "A"
    assert lines[1].speaker_label == "MR. THOMAS"


def test_render_other_role_is_named_colloquy():
    lines = render_working_transcript(_sample_utterances(), _sample_participants())
    assert lines[2].line_type == "colloquy"
    assert lines[2].speaker_label == "MS. ZAHN"


def test_render_unmapped_cluster_is_flagged_and_keeps_text():
    lines = render_working_transcript(_sample_utterances(), _sample_participants())
    unmapped = lines[3]
    assert unmapped.flagged is True
    assert unmapped.line_type == "flagged"
    # Testimony is never lost — the text survives even when unmapped.
    assert unmapped.text == "Unmapped words here."
    assert unmapped.speaker_label == "Speaker 9"


def test_render_loses_no_utterances():
    utts = _sample_utterances()
    lines = render_working_transcript(utts, _sample_participants())
    assert len(lines) == len(utts)


def test_merge_via_shared_participant():
    # speaker_indices [2, 3] under one participant IS the merge mechanism.
    idx_map = build_index_map(_sample_participants())
    assert idx_map[2]["participant_id"] == idx_map[3]["participant_id"] == "p2"


def test_render_is_deterministic():
    a = render_working_transcript(_sample_utterances(), _sample_participants())
    b = render_working_transcript(_sample_utterances(), _sample_participants())
    assert [l.to_dict() for l in a] == [l.to_dict() for l in b]


def test_delete_participant_unmaps_its_clusters():
    # Removing the witness participant => its clusters render flagged,
    # no text lost.
    parts = [p for p in _sample_participants() if p["role"] != "witness"]
    lines = render_working_transcript(_sample_utterances(), parts)
    witness_line = next(l for l in lines if l.text == "Heath Thomas.")
    assert witness_line.flagged is True
    assert witness_line.text == "Heath Thomas."


# --- apply endpoint --------------------------------------------------

def test_apply_endpoint_exists_and_rejects_unknown_job(client):
    res = client.post(
        "/api/transcripts/jobs/does-not-exist/speaker-mapping/apply",
        json={"participants": []},
    )
    assert res.status_code == 404


# --- correction-engine trigger (spec wave11 section 7.1) -------------

def test_correction_trigger_no_mapping_returns_none(client):
    # No confirmed participants for this job => engine is not run.
    from backend.services.correction_trigger import run_correction_engine_for_job
    assert run_correction_engine_for_job("no-such-job") is None


def test_correction_trigger_is_defensive_on_bad_job(client):
    # A defective job id must never raise — speaker mapping must not
    # break because the correction engine had a problem.
    from backend.services.correction_trigger import run_correction_engine_for_job
    result = run_correction_engine_for_job("")
    assert result is None
