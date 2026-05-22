"""Wave 14 — backend regex correction pipeline tests."""
from __future__ import annotations

from backend.corrections.regex_rules import (
    RegexRule,
    apply_regex_rules,
    apply_regex_rules_to_text,
)


def _rule(rid, find, repl, order=0, enabled=True):
    return RegexRule(rule_id=rid, find_pattern=find, replace_with=repl,
                     rule_order=order, enabled=enabled)


# --- application -----------------------------------------------------

def test_single_rule_applies():
    r = apply_regex_rules_to_text(
        "the trinaty device", [_rule("r1", r"trinaty", "Trinity")])
    assert r.text == "the Trinity device"
    assert r.changed


def test_disabled_rule_skipped():
    r = apply_regex_rules_to_text(
        "the trinaty device",
        [_rule("r1", r"trinaty", "Trinity", enabled=False)])
    assert r.text == "the trinaty device"
    assert not r.changed


def test_rules_apply_in_order():
    # r1 turns 'a' -> 'b'; r2 turns 'b' -> 'c'. Order matters.
    rules = [
        _rule("r1", r"a", "b", order=0),
        _rule("r2", r"b", "c", order=1),
    ]
    r = apply_regex_rules_to_text("a", rules)
    assert r.text == "c"


def test_rule_order_is_respected_when_unsorted():
    # Provide rules out of order; engine must sort by rule_order.
    rules = [
        _rule("r2", r"b", "c", order=1),
        _rule("r1", r"a", "b", order=0),
    ]
    r = apply_regex_rules_to_text("a", rules)
    assert r.text == "c"


def test_malformed_regex_is_skipped_not_crashed():
    rules = [
        _rule("bad", r"([unclosed", "x"),
        _rule("good", r"hello", "world"),
    ]
    r = apply_regex_rules_to_text("hello there", rules)
    assert r.text == "world there"          # good rule still applied
    assert "bad" in r.skipped_rules         # bad rule logged + skipped


def test_match_count_recorded():
    r = apply_regex_rules_to_text(
        "na na na", [_rule("r1", r"na", "yo")])
    assert r.substitutions[0].match_count == 3


def test_empty_rule_set_is_safe():
    r = apply_regex_rules_to_text("unchanged", [])
    assert r.text == "unchanged"
    assert not r.changed


# --- across utterances ----------------------------------------------

def test_apply_across_utterances_does_not_mutate_input():
    utts = [{"utterance_id": "u1", "text": "trinaty one"},
            {"utterance_id": "u2", "text": "trinaty two"}]
    before = [u["text"] for u in utts]
    new_utts, subs = apply_regex_rules(
        utts, [_rule("r1", r"trinaty", "Trinity")])
    assert [u["text"] for u in utts] == before     # RAW untouched
    assert new_utts[0]["text"] == "Trinity one"
    assert new_utts[1]["text"] == "Trinity two"


def test_regex_is_deterministic():
    rules = [_rule("r1", r"\bx\b", "y")]
    a = apply_regex_rules_to_text("x and x", rules)
    b = apply_regex_rules_to_text("x and x", rules)
    assert a.text == b.text


# --- persistence (DB) -----------------------------------------------

def test_regex_rules_persist_per_case(client):
    case_id = "case-regex-test"
    # Save a rule set.
    res = client.put(
        f"/api/corrections/cases/{case_id}/regex-rules",
        json={"rules": [
            {"find_pattern": "trinaty", "replace_with": "Trinity"},
            {"find_pattern": "axon", "replace_with": "Axone"},
        ]},
    )
    assert res.status_code == 200
    # Read it back -- order preserved.
    got = client.get(f"/api/corrections/cases/{case_id}/regex-rules").json()
    assert len(got["rules"]) == 2
    assert got["rules"][0]["find_pattern"] == "trinaty"
    assert got["rules"][0]["rule_order"] == 0
    assert got["rules"][1]["rule_order"] == 1


def test_regex_rules_replace_is_clean(client):
    case_id = "case-regex-replace"
    client.put(f"/api/corrections/cases/{case_id}/regex-rules",
               json={"rules": [{"find_pattern": "a", "replace_with": "b"}]})
    # Replace with a different set.
    client.put(f"/api/corrections/cases/{case_id}/regex-rules",
               json={"rules": [{"find_pattern": "c", "replace_with": "d"}]})
    got = client.get(f"/api/corrections/cases/{case_id}/regex-rules").json()
    assert len(got["rules"]) == 1
    assert got["rules"][0]["find_pattern"] == "c"


def test_regex_preview_endpoint(client):
    res = client.post("/api/corrections/regex-preview", json={
        "sample_text": "the trinaty device",
        "rules": [{"find_pattern": "trinaty", "replace_with": "Trinity"}],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["after"] == "the Trinity device"
    assert body["changed"] is True
