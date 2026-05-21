"""Stage G / Stage U — verbatim guard and unguard tests."""
from __future__ import annotations

from backend.corrections import guards
from backend.corrections.guards import has_sentinels


def _roundtrip(text: str) -> str:
    guarded, vault = guards.guard(text)
    return guards.unguard(guarded, vault)


def test_guard01_filler_words_preserved():
    text = "Well, um, I think so, okay."
    guarded, vault = guards.guard(text)
    assert len(vault) > 0
    assert _roundtrip(text) == text


def test_guard02_stutter_protected_not_compound():
    # Stutter is guarded; "cross-examination" is NOT (more than one char
    # before the hyphen).
    guarded, vault = guards.guard("the b-bank during cross-examination")
    assert "b-bank" not in guarded  # stutter was wrapped
    assert "cross-examination" in guarded  # compound left alone
    assert _roundtrip("the b-bank during cross-examination") == (
        "the b-bank during cross-examination"
    )


def test_guard03_false_start_preserved():
    text = "I went to the -- the store."
    assert _roundtrip(text) == text


def test_guard04_ellipsis_not_removed():
    for text in ("I was . . . unsure", "And then . . . .", "Wait... what"):
        assert _roundtrip(text) == text


def test_guard05_lc_marker_survives_all_passes():
    text = "The witness \u2039LC:see page 12\u203a confirmed it."
    guarded, vault = guards.guard(text)
    assert "\u2039LC:see page 12\u203a" not in guarded  # wrapped
    assert _roundtrip(text) == text


def test_unguard_no_sentinels_remain():
    text = "Um, well, the b-bank -- the bank . . . closed."
    guarded, vault = guards.guard(text)
    restored = guards.unguard(guarded, vault)
    assert not has_sentinels(restored)
    assert restored == text


def test_guard_is_idempotent_via_roundtrip():
    text = "So, uh, I -- I think . . . maybe."
    once = _roundtrip(text)
    twice = _roundtrip(once)
    assert once == twice == text
