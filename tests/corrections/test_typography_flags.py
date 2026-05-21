"""Stage T (typography) and Stage F (flags) tests."""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.corrections import typography
from backend.corrections.flags import FlagRegistry, detect


@dataclass
class _Ctx:
    job_config: dict = field(default_factory=dict)
    parity_mode: bool = False


# --------------------------------------------------------------------
# Stage T — typography
# --------------------------------------------------------------------


def test_post01_two_space_after_sentence():
    out, log = typography.apply("I do. Thank you.", "u1", _Ctx())
    assert "I do.  Thank you." in out
    assert any(e.rule_id == "POST-01" for e in log)


def test_post01_abbreviation_not_two_spaced():
    # "Mr. Smith" must NOT get two spaces after "Mr."
    out, _ = typography.apply("Mr. Smith arrived", "u1", _Ctx())
    assert "MR. Smith" in out  # honorific upcased, still ONE space


def test_post02_objection_two_space():
    out, log = typography.apply("Objection. Calls for speculation.", "u1", _Ctx())
    assert "Objection.  Calls" in out
    assert any(e.rule_id == "POST-02" for e in log)


def test_post03_honorific_one_space_caps():
    # Q2 decision: ALL-CAPS, ONE space after the period.
    out, log = typography.apply("I spoke with Mr. Nunez and Ms. Zahn.", "u1", _Ctx())
    assert "MR. Nunez" in out
    assert "MS. Zahn" in out
    assert "MR.  " not in out  # never two spaces after the honorific period
    assert any(e.rule_id == "POST-03" for e in log)


def test_post05_miss_normalized():
    out, log = typography.apply("Miss Garcia testified", "u1", _Ctx())
    assert "Ms. Garcia" in out
    assert any(e.rule_id == "POST-05" for e in log)


def test_post05_quoted_miss_preserved():
    out, _ = typography.apply('she won "Miss Congeniality" award', "u1", _Ctx())
    assert "Miss Congeniality" in out


def test_post06_em_dash_to_double_hyphen():
    out, log = typography.apply("I went\u2014then stopped", "u1", _Ctx())
    assert " -- " in out
    assert "\u2014" not in out
    assert any(e.rule_id == "POST-06" for e in log)


def test_post07_time_formatting():
    out, log = typography.apply("The time is 09:01 AM.", "u1", _Ctx())
    assert "9:01 a.m." in out
    assert any(e.rule_id == "POST-07" for e in log)


def test_post07_ampm_does_not_double_period():
    # "AM." at end of sentence must become "a.m.", never "a.m.."
    out, _ = typography.apply("The time is 09:01 AM.", "u1", _Ctx())
    assert "a.m.." not in out
    assert out.rstrip().endswith("a.m.")


def test_post08_money_and_percent():
    out, log = typography.apply("It cost $1,200.00 and 5% interest", "u1", _Ctx())
    assert "$1,200" in out and ".00" not in out
    assert "5 percent" in out
    assert any(e.rule_id == "POST-08" for e in log)


def test_stage_t_idempotent():
    once, _ = typography.apply("Mr. Smith said. Then 09:01 AM.", "u1", _Ctx())
    twice, log2 = typography.apply(once, "u1", _Ctx())
    assert once == twice
    assert log2 == []


# --------------------------------------------------------------------
# Stage F — flags
# --------------------------------------------------------------------


def test_flag06_garbled_oath_flagged_not_corrected():
    reg = FlagRegistry()
    out = detect("Do you so happy God affirm this", "u1", _Ctx(), reg)
    # The garbled phrase is left verbatim; a flag marker is inserted.
    assert "so happy God" in out
    assert "[SCOPIST: FLAG 1" in out
    assert reg.flags[0].category == "oath"


def test_flag02_list3_item_flagged_not_corrected():
    reg = FlagRegistry()
    out = detect("the criminal investigator arrived", "u1", _Ctx(), reg)
    assert "criminal investigator" in out  # left verbatim
    assert "[SCOPIST: FLAG 1" in out
    assert reg.flags[0].category == "entity"


def test_flag_numbering_sequential_across_utterances():
    reg = FlagRegistry()
    detect("so happy God", "u1", _Ctx(), reg)
    detect("the criminal investigator", "u2", _Ctx(), reg)
    assert [f.flag_number for f in reg.flags] == [1, 2]


def test_no_flags_on_clean_text():
    reg = FlagRegistry()
    out = detect("The witness answered the question.", "u1", _Ctx(), reg)
    assert out == "The witness answered the question."
    assert reg.flags == []
