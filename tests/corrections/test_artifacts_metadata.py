"""Stage A (artifacts) and Stage M (metadata) tests."""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.corrections import artifacts, metadata


@dataclass
class _Ctx:
    job_config: dict = field(default_factory=dict)
    parity_mode: bool = False


# --------------------------------------------------------------------
# Stage A — Deepgram artifact removal
# --------------------------------------------------------------------


def test_pre04_duplicate_collapsed():
    out, log = artifacts.apply("and then the witness witness said", "u1", _Ctx())
    assert out == "and then the witness said"
    assert any(e.rule_id == "PRE-04" for e in log)


def test_pre04_affirmation_not_collapsed():
    # "correct correct" is an intentional verbatim affirmation.
    out, log = artifacts.apply("That is correct correct.", "u1", _Ctx())
    assert out == "That is correct correct."
    assert log == []


def test_pre04_short_duplicate_left_intact():
    # 1-3 char duplicates are stutter evidence — left alone.
    out, _ = artifacts.apply("I I went there", "u1", _Ctx())
    assert out == "I I went there"


def test_pre05_standalone_artifact_normalized():
    out, log = artifacts.apply("K. Go ahead. Mhmm.", "u1", _Ctx())
    assert "Okay." in out and "Mm-hmm" in out
    assert any(e.rule_id == "PRE-05" for e in log)


def test_pre06_doctor_period_removed():
    out, log = artifacts.apply("Doctor. Smith testified", "u1", _Ctx())
    assert out == "Dr. Smith testified"
    assert any(e.rule_id == "PRE-06" for e in log)


def test_pre06_standalone_doctor_left_alone():
    out, log = artifacts.apply("yes doctor.", "u1", _Ctx())
    assert out == "yes doctor."
    assert log == []


def test_pre10_orphaned_dash_removed():
    out, log = artifacts.apply("the word -- -- next", "u1", _Ctx())
    assert "-- --" not in out
    assert any(e.rule_id == "PRE-10" for e in log)


def test_stage_a_idempotent():
    once, _ = artifacts.apply("the witness witness said K.", "u1", _Ctx())
    twice, log2 = artifacts.apply(once, "u1", _Ctx())
    assert once == twice
    assert log2 == []


# --------------------------------------------------------------------
# Stage M — metadata substitution
# --------------------------------------------------------------------


def test_pre01_reporter_name_corrected():
    ctx = _Ctx(job_config={"reporter_name": "Miah Bardot"})
    out, log = metadata.apply("Reported by Mia Bardo, CSR.", "u1", ctx)
    assert "Miah Bardot" in out
    assert any(e.rule_id == "PRE-01" for e in log)


def test_pre01_noop_without_reporter_name():
    out, log = metadata.apply("Reported by Mia Bardo.", "u1", _Ctx())
    assert out == "Reported by Mia Bardo."
    assert log == []


def test_pre02_court_reporter_label_corrected():
    out, log = metadata.apply("THE COURT REPORTER: Please continue.", "u1", _Ctx())
    assert out.startswith("THE REPORTER:")
    assert any(e.rule_id == "PRE-02" for e in log)


def test_pre07_confirmed_spellings_applied_longest_first():
    ctx = _Ctx(job_config={"confirmed_spellings": {
        "Home Depot": "Home Depot U.S.A., Inc.",
        "Depot": "DEPOT-WRONG",
    }})
    out, log = metadata.apply("worked at Home Depot for years", "u1", ctx)
    # Longest key wins — "Home Depot" replaced as a unit, not "Depot".
    assert "Home Depot U.S.A., Inc." in out
    assert "DEPOT-WRONG" not in out
    assert any(e.rule_id == "PRE-07" for e in log)


def test_pre08_keyterm_casing_corrected():
    ctx = _Ctx(job_config={"deepgram_keyterms": ["Ballymore"]})
    out, log = metadata.apply("the ballymore lift broke", "u1", ctx)
    assert "Ballymore" in out
    assert any(e.rule_id == "PRE-08" for e in log)


def test_pre09_cause_number_formatted():
    out, log = metadata.apply("Cause No. 25CV00598OLG is styled", "u1", _Ctx())
    assert "25-CV-00598-OLG" in out
    assert any(e.rule_id == "PRE-09" for e in log)


def test_stage_m_idempotent():
    ctx = _Ctx(job_config={"reporter_name": "Miah Bardot",
                           "confirmed_spellings": {"Home Depot": "Home Depot U.S.A., Inc."}})
    once, _ = metadata.apply("Mia Bardo at Home Depot, 25CV00598OLG.", "u1", ctx)
    twice, log2 = metadata.apply(once, "u1", ctx)
    assert once == twice
    assert log2 == []
