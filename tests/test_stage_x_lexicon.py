"""Wave 14 — Stage X lexicon engine tests."""
from __future__ import annotations

from backend.lexicon.merge import merge_lexicon
from backend.lexicon.stage_x import apply_stage_x, apply_stage_x_to_text


# --- merge priority --------------------------------------------------

def test_confirmed_spellings_outrank_keyterms():
    lex = merge_lexicon(
        confirmed_spellings={"trinaty": "Trinity"},
        intake_keyterms=["trinaty"],   # lower priority, same key
    )
    entry = lex.get("trinaty")
    assert entry.replacement == "Trinity"
    assert entry.source == "confirmed_spellings"


def test_reporter_case_outranks_deepgram():
    lex = merge_lexicon(
        reporter_case_corrections={"axon": "Axone"},
        deepgram_keyterms=["Axon"],
    )
    assert lex.get("axon").source == "reporter_case"


def test_merge_combines_distinct_keys():
    lex = merge_lexicon(
        confirmed_spellings={"trinaty": "Trinity"},
        deepgram_keyterms=["Deepgram"],
    )
    assert len(lex) == 2


# --- whole-word substitution ----------------------------------------

def test_whole_word_substitution():
    lex = merge_lexicon(confirmed_spellings={"trinaty": "Trinity"})
    r = apply_stage_x_to_text("I saw trinaty there", lex)
    assert r.text == "I saw Trinity there"


def test_possessive_preserved():
    lex = merge_lexicon(confirmed_spellings={"trinaty": "Trinity"})
    r = apply_stage_x_to_text("that is trinaty's car", lex)
    assert r.text == "that is Trinity's car"


def test_no_substring_mutation():
    # "ultrinaty" must NOT become "ultraTrinity".
    lex = merge_lexicon(confirmed_spellings={"trinaty": "Trinity"})
    r = apply_stage_x_to_text("the ultrinaty device", lex)
    assert r.text == "the ultrinaty device"
    assert not r.changed


def test_multiword_entry():
    lex = merge_lexicon(
        confirmed_spellings={"acoustic neuroma": "Acoustic Neuroma"})
    r = apply_stage_x_to_text("the acoustic neuroma scan", lex)
    assert r.text == "the Acoustic Neuroma scan"


def test_multiword_long_phrase():
    lex = merge_lexicon(confirmed_spellings={
        "texas rules of civil procedure": "Texas Rules of Civil Procedure"})
    r = apply_stage_x_to_text("under texas rules of civil procedure today", lex)
    assert "Texas Rules of Civil Procedure" in r.text


def test_casing_correction_for_confirmed_entry():
    lex = merge_lexicon(confirmed_spellings={"miah bardot": "Miah Bardot"})
    r = apply_stage_x_to_text("miah bardot testified", lex)
    assert r.text == "Miah Bardot testified"


def test_no_op_when_already_correct():
    lex = merge_lexicon(confirmed_spellings={"trinaty": "Trinity"})
    r = apply_stage_x_to_text("Trinity is correct", lex)
    assert not r.changed


def test_substitution_is_audited():
    lex = merge_lexicon(confirmed_spellings={"trinaty": "Trinity"})
    r = apply_stage_x_to_text("trinaty here", lex)
    assert len(r.substitutions) == 1
    assert r.substitutions[0].before == "trinaty"
    assert r.substitutions[0].after == "Trinity"
    assert r.substitutions[0].source == "confirmed_spellings"


# --- immutability & determinism -------------------------------------

def test_apply_stage_x_does_not_mutate_input():
    lex = merge_lexicon(confirmed_spellings={"trinaty": "Trinity"})
    utts = [{"utterance_id": "u1", "text": "trinaty was here"}]
    before = utts[0]["text"]
    new_utts, subs = apply_stage_x(utts, lex)
    assert utts[0]["text"] == before          # RAW untouched
    assert new_utts[0]["text"] == "Trinity was here"


def test_stage_x_is_deterministic():
    lex = merge_lexicon(confirmed_spellings={"trinaty": "Trinity"})
    a = apply_stage_x_to_text("trinaty trinaty trinaty", lex)
    b = apply_stage_x_to_text("trinaty trinaty trinaty", lex)
    assert a.text == b.text


def test_empty_lexicon_is_safe():
    lex = merge_lexicon()
    r = apply_stage_x_to_text("nothing changes here", lex)
    assert r.text == "nothing changes here"
    assert not r.changed
