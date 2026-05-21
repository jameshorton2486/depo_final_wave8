"""Full-pipeline tests: end-to-end, idempotency, verbatim preservation,
no-sentinel residue, parity mode, the speaker-map gate.

Spec section 19 (Test Plan).
"""
from __future__ import annotations

import pytest

from backend.corrections import run
from backend.corrections.model import SpeakerMapUnverifiedError, Utterance
from backend.corrections.guards import has_sentinels


def _utt(uid, text, role="witness", idx=1):
    return Utterance(utterance_id=uid, speaker_index=idx, role=role, text=text)


def _transcript():
    return [
        _utt("u1", "THE COURT REPORTER: We are on the record.", "court_reporter", 0),
        _utt("u2", "Doctor. Smith, state your name. Thank you.", "examining_attorney", 1),
        _utt("u3", "Well, um, I worked worked there for 5% of my career.", "witness", 2),
        _utt("u4", "Objection. Calls for speculation.", "defending_attorney", 4),
        _utt("u5", "I spoke with Mr. Nunez at 09:01 AM.", "witness", 2),
    ]


def test_pipeline_runs_end_to_end():
    result = run(_transcript(), {})
    assert len(result.lines) == 5
    assert all(ln.line_type == "utterance" for ln in result.lines)
    # Corrections fired and were logged.
    assert len(result.log) > 0
    rules = {e.rule_id for e in result.log}
    assert "PRE-02" in rules   # label standardisation
    assert "PRE-04" in rules   # "the the" collapsed
    assert "PRE-06" in rules   # Doctor. -> Dr.
    assert "POST-02" in rules  # objection spacing
    assert "POST-03" in rules  # honorific


def test_verbatim_preservation():
    # Fillers, stutters, false starts, ellipsis must survive untouched.
    t = [_utt("u1", "Well, uh, I -- I went . . . to the b-bank, you know.")]
    result = run(t, {})
    out = result.lines[0].text
    assert "Well" in out and "uh" in out
    assert "I -- I" in out
    assert ". . ." in out
    assert "b-bank" in out


def test_no_sentinel_residue():
    result = run(_transcript(), {})
    for ln in result.lines:
        assert not has_sentinels(ln.text)


def test_pipeline_idempotent():
    first = run(_transcript(), {})
    # Feed the corrected lines back through as utterances.
    second_input = [
        Utterance(
            utterance_id=ln.utterance_ids[0],
            speaker_index=ln.speaker_index,
            role=ln.role or "other",
            text=ln.text,
        )
        for ln in first.lines
    ]
    second = run(second_input, {})
    assert [ln.text for ln in first.lines] == [ln.text for ln in second.lines]


def test_speaker_map_gate_blocks_unconfirmed():
    with pytest.raises(SpeakerMapUnverifiedError):
        run(_transcript(), {}, speaker_map_confirmed=False)


def test_parity_mode_flag_is_honored():
    result = run(_transcript(), {"deterministic_parity_mode": True})
    assert result.parity_mode is True
    # Foundation: G/A/M/T/F/U only, so parity and full are identical —
    # both still correct mechanical artifacts.
    full = run(_transcript(), {"deterministic_parity_mode": False})
    assert [ln.text for ln in result.lines] == [ln.text for ln in full.lines]


def test_confirmed_spellings_flow_through_pipeline():
    t = [_utt("u1", "I worked at home depot usa for years.")]
    result = run(t, {"confirmed_spellings": {"home depot usa": "Home Depot U.S.A., Inc."}})
    assert "Home Depot U.S.A., Inc." in result.lines[0].text


def test_correction_log_is_complete_and_auditable():
    result = run(_transcript(), {})
    # Every log entry has the fields the reporter needs to audit it.
    for e in result.log:
        assert e.rule_id and e.stage and e.utterance_id
        assert e.before != e.after


def test_oath_garble_is_flagged_not_corrected():
    t = [_utt("u1", "Do you so happy God swear it.", "court_reporter", 0)]
    result = run(t, {})
    assert "so happy God" in result.lines[0].text  # verbatim
    assert len(result.flags) == 1
    assert result.flags[0].category == "oath"
