"""Wave 13 — parenthetical registry tests: canonical wording."""
from __future__ import annotations

from backend.stage_s import parentheticals as P


def test_recess_with_time():
    assert P.recess("9:15 a.m") == "(Whereupon, a recess was taken at 9:15 a.m.)"


def test_recess_without_time_drops_at_clause():
    assert P.recess("") == "(Whereupon, a recess was taken.)"


def test_resumed_with_time():
    assert P.resumed("9:20 a.m") == \
        "(Whereupon, the proceedings resumed at 9:20 a.m.)"


def test_commenced_and_concluded():
    assert P.commenced("9:00 a.m") == \
        "(Whereupon, the deposition commenced at 9:00 a.m.)"
    assert P.concluded("5:00 p.m") == \
        "(Whereupon, the deposition concluded at 5:00 p.m.)"


def test_exhibit_marked_injects_number():
    assert P.exhibit_marked(7) == \
        "(Exhibit No. 7 was marked for identification.)"


def test_fixed_phrases_present():
    assert P.WITNESS_SWORN == "(The witness was sworn.)"
    assert P.DISCUSSION_OFF_RECORD == "(Discussion off the record)"
    assert P.NO_VERBAL_RESPONSE == "(No verbal response)"
    assert P.INTERPRETER_SWORN == "(Interpreter sworn)"


def test_is_canonical_recognizes_registry_phrases():
    assert P.is_canonical(P.WITNESS_SWORN)
    assert P.is_canonical(P.WITNESS_COMPLIED)
    assert not P.is_canonical("(Some invented parenthetical.)")


def test_no_time_proceedings_phrase():
    assert P.on_record_proceedings("") == \
        "(The following proceedings were had on the record.)"
    assert "10:00 a.m" in P.on_record_proceedings("10:00 a.m")
