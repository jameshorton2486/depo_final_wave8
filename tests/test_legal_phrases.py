"""Wave 15a — Stage X (legal_phrases) tests.

Garbled-objection and legal-phrase resolution, role-scoped, exact-match.
"""
from __future__ import annotations

from backend.corrections import legal_phrases


class _Ctx:
    job_config: dict = {}


# --- LEX-01 garbled objections (attorney-role gated) -----------------

def test_garbled_objection_resolved_for_attorney():
    out, log = legal_phrases.apply(
        "Action calls for circulation", "u1", _Ctx(),
        role="defending_attorney")
    assert out == "Objection.  Calls for speculation."
    assert log and log[0].rule_id == "LEX-01"


def test_garbled_objection_not_resolved_for_witness():
    # Role gate: a witness saying the same words is NOT corrected.
    out, log = legal_phrases.apply(
        "Action calls for circulation", "u1", _Ctx(), role="witness")
    assert out == "Action calls for circulation"
    assert not log


def test_garbled_objection_vague_ambiguous():
    out, _ = legal_phrases.apply(
        "Confection, vegan, ambiguous", "u1", _Ctx(),
        role="examining_attorney")
    assert out == "Objection.  Vague and ambiguous."


def test_garbled_objection_nonresponsive():
    out, _ = legal_phrases.apply(
        "I'm an objective, now I'm responsive", "u1", _Ctx(),
        role="defending_attorney")
    assert out == "Objection.  Nonresponsive."


def test_objection_idempotent():
    once, _ = legal_phrases.apply(
        "Infection.", "u1", _Ctx(), role="defending_attorney")
    twice, log = legal_phrases.apply(once, "u1", _Ctx(),
                                     role="defending_attorney")
    assert once == twice == "Objection."
    assert not log    # second pass is a no-op


# --- LEX-02 legal phrases (role-gated per entry) --------------------

def test_texas_rules_phrase_any_role():
    out, _ = legal_phrases.apply(
        "under the tech rules of texas texas rules", "u1", _Ctx(),
        role="witness")
    assert "Texas Rules of Civil Procedure" in out


def test_penalty_of_perjury():
    out, _ = legal_phrases.apply(
        "under penalty of curtory", "u1", _Ctx(), role="witness")
    assert out == "under penalty of perjury"


def test_remote_swearing_reporter_only():
    # Gated to court_reporter.
    out_rep, _ = legal_phrases.apply(
        "remote storing", "u1", _Ctx(), role="court_reporter")
    assert out_rep == "remote swearing of the witness"
    out_wit, _ = legal_phrases.apply(
        "remote storing", "u1", _Ctx(), role="witness")
    assert out_wit == "remote storing"   # not gated for witness


def test_pass_the_witness_examiner_only():
    out, _ = legal_phrases.apply(
        "past witness", "u1", _Ctx(), role="examining_attorney")
    assert out == "Pass the witness."


def test_so_help_you_god_is_NOT_corrected_here():
    # Q3 confirmed: flagged, never deterministically corrected.
    out, log = legal_phrases.apply(
        "so help you guide", "u1", _Ctx(), role="court_reporter")
    assert out == "so help you guide"     # untouched
    assert not log


# --- LEX-03 subpoena duces tecum ------------------------------------

def test_subpoena_duces_tecum_variants():
    for variant in ["subpoena deuces tikum", "due to stecum",
                    "duces take them"]:
        out, _ = legal_phrases.apply(variant, "u1", _Ctx(), role="witness")
        assert out == "subpoena duces tecum"


# --- pipeline integration -------------------------------------------

def test_stage_x_runs_inside_pipeline():
    from backend.corrections.pipeline import run
    from backend.corrections.model import Utterance
    utts = [Utterance(
        utterance_id="u1", speaker_index=1, role="defending_attorney",
        text="Action calls for circulation", participant_name="Zahn")]
    result = run(utts, job_config={}, speaker_map_confirmed=True)
    assert "Objection.  Calls for speculation." in result.lines[0].text
    assert any(e.stage == "X" for e in result.log)


# --- regex pre-stage integration (Wave 15a) -------------------------

def test_regex_prestage_runs_inside_engine():
    from backend.corrections.pipeline import run
    from backend.corrections.model import Utterance
    utts = [Utterance(
        utterance_id="u1", speaker_index=1, role="witness",
        text="I saw trinaty there", participant_name="T")]
    cfg = {"regex_rules": [
        {"rule_id": "r1", "find_pattern": "trinaty",
         "replace_with": "Trinity", "rule_order": 0, "enabled": True},
    ]}
    result = run(utts, job_config=cfg, speaker_map_confirmed=True)
    assert "Trinity" in result.lines[0].text
    assert any(e.stage == "regex" for e in result.log)


def test_regex_prestage_absent_is_safe():
    from backend.corrections.pipeline import run
    from backend.corrections.model import Utterance
    utts = [Utterance(
        utterance_id="u1", speaker_index=1, role="witness",
        text="nothing to change", participant_name="T")]
    result = run(utts, job_config={}, speaker_map_confirmed=True)
    assert result.lines[0].text == "nothing to change"
