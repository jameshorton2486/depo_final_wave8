"""Backend regex correction pipeline — Wave 14.

Applies a case's persisted, ordered regex correction rules to
transcript text. Deterministic, audited, replayable. A malformed
pattern is skipped with a logged warning -- it never crashes a render.

RAW is never mutated: callers apply this to a working copy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from loguru import logger


@dataclass
class RegexRule:
    """One persisted regex correction rule."""

    rule_id: str
    find_pattern: str
    replace_with: str = ""
    rule_order: int = 0
    enabled: bool = True
    description: str = ""


@dataclass
class RegexSubstitution:
    """One applied regex substitution, for the audit log."""

    rule_id: str
    before: str
    after: str
    match_count: int

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "before": self.before,
            "after": self.after,
            "match_count": self.match_count,
        }


@dataclass
class RegexResult:
    """Result of applying a rule set to a body of text."""

    text: str
    substitutions: list[RegexSubstitution] = field(default_factory=list)
    skipped_rules: list[str] = field(default_factory=list)  # malformed

    @property
    def changed(self) -> bool:
        return len(self.substitutions) > 0


def _compile(pattern: str) -> "re.Pattern | None":
    """Compile a rule pattern; return None (logged) if malformed."""
    try:
        return re.compile(pattern)
    except re.error as exc:
        logger.warning(f"Skipping malformed regex rule /{pattern}/: {exc}")
        return None


def apply_regex_rules_to_text(text: str, rules: list[RegexRule]) -> RegexResult:
    """Apply enabled rules, in rule_order, to one body of text."""
    if not text or not rules:
        return RegexResult(text=text or "")

    subs: list[RegexSubstitution] = []
    skipped: list[str] = []
    out = text

    for rule in sorted(rules, key=lambda r: r.rule_order):
        if not rule.enabled:
            continue
        compiled = _compile(rule.find_pattern)
        if compiled is None:
            skipped.append(rule.rule_id)
            continue
        new_out, n = compiled.subn(rule.replace_with, out)
        if n > 0 and new_out != out:
            subs.append(RegexSubstitution(
                rule_id=rule.rule_id, before=out, after=new_out,
                match_count=n))
            out = new_out

    return RegexResult(text=out, substitutions=subs, skipped_rules=skipped)


def apply_regex_rules(
    utterances: list[dict],
    rules: list[RegexRule],
) -> tuple[list[dict], list[RegexSubstitution]]:
    """Apply the rule set across utterance dicts.

    Returns (new_utterances, all_substitutions). Inputs are not mutated.
    """
    out: list[dict] = []
    all_subs: list[RegexSubstitution] = []
    for utt in utterances:
        result = apply_regex_rules_to_text(utt.get("text") or "", rules)
        new_utt = dict(utt)
        new_utt["text"] = result.text
        out.append(new_utt)
        for s in result.substitutions:
            # Tag the substitution with the utterance for the audit log.
            all_subs.append(RegexSubstitution(
                rule_id=s.rule_id,
                before=utt.get("utterance_id") or "",
                after=s.after, match_count=s.match_count))
    return out, all_subs
