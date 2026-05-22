"""Router for /api/corrections -- per-case regex correction rules (Wave 14).

Endpoints:
    GET    /api/corrections/cases/{case_id}/regex-rules   list rules
    PUT    /api/corrections/cases/{case_id}/regex-rules   replace rule set
    DELETE /api/corrections/cases/{case_id}/regex-rules   clear rules
    POST   /api/corrections/regex-preview                 dry-run a rule set
"""
from __future__ import annotations

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from backend.corrections.regex_rules import RegexRule, apply_regex_rules_to_text
from backend.db import regex_rules_repo as rrepo

router = APIRouter(prefix="/api/corrections", tags=["corrections"])


class RegexRuleModel(BaseModel):
    rule_id: str | None = None
    find_pattern: str
    replace_with: str = ""
    enabled: bool = True
    description: str = ""


class RegexRuleSet(BaseModel):
    rules: list[RegexRuleModel] = Field(default_factory=list)


class RegexPreviewRequest(BaseModel):
    sample_text: str
    rules: list[RegexRuleModel] = Field(default_factory=list)


def _to_rule(m: RegexRuleModel, order: int) -> RegexRule:
    return RegexRule(
        rule_id=m.rule_id or f"preview-{order}",
        find_pattern=m.find_pattern,
        replace_with=m.replace_with,
        rule_order=order,
        enabled=m.enabled,
        description=m.description,
    )


@router.get("/cases/{case_id}/regex-rules")
def get_regex_rules(case_id: str) -> dict:
    """List a case's persisted regex correction rules, in order."""
    rules = rrepo.list_rules(case_id)
    return {
        "case_id": case_id,
        "rules": [
            {
                "rule_id": r.rule_id,
                "find_pattern": r.find_pattern,
                "replace_with": r.replace_with,
                "rule_order": r.rule_order,
                "enabled": r.enabled,
                "description": r.description,
            }
            for r in rules
        ],
    }


@router.put("/cases/{case_id}/regex-rules")
def put_regex_rules(case_id: str, payload: RegexRuleSet) -> dict:
    """Replace a case's entire regex rule set (ordered by list position)."""
    saved = rrepo.replace_rules(
        case_id, [r.model_dump() for r in payload.rules])
    logger.info(f"Saved {len(saved)} regex rule(s) for case {case_id}")
    return {
        "case_id": case_id,
        "rules": [
            {
                "rule_id": r.rule_id, "find_pattern": r.find_pattern,
                "replace_with": r.replace_with, "rule_order": r.rule_order,
                "enabled": r.enabled, "description": r.description,
            }
            for r in saved
        ],
    }


@router.delete("/cases/{case_id}/regex-rules")
def delete_regex_rules(case_id: str) -> dict:
    """Clear all regex rules for a case."""
    removed = rrepo.delete_rules(case_id)
    return {"case_id": case_id, "removed": removed}


@router.post("/regex-preview")
def regex_preview(payload: RegexPreviewRequest) -> dict:
    """Dry-run a rule set against sample text without persisting anything."""
    rules = [_to_rule(m, i) for i, m in enumerate(payload.rules)]
    result = apply_regex_rules_to_text(payload.sample_text, rules)
    return {
        "before": payload.sample_text,
        "after": result.text,
        "changed": result.changed,
        "substitution_count": len(result.substitutions),
        "skipped_rules": result.skipped_rules,
    }
