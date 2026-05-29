"""Router for /api/corrections -- per-case regex correction rules (Wave 14).

Endpoints:
    GET    /api/corrections/cases/{case_id}/regex-rules   list rules
    PUT    /api/corrections/cases/{case_id}/regex-rules   replace rule set
    DELETE /api/corrections/cases/{case_id}/regex-rules   clear rules
    POST   /api/corrections/regex-preview                 dry-run a rule set
"""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from backend.corrections import correction_log_store
from backend.corrections.regex_rules import (
    RegexRule, apply_regex_rules, apply_regex_rules_to_text,
)
from backend.db import regex_rules_repo as rrepo
from backend.transcript import provenance as provenance_mod
from backend.transcript import repository as trepo
from backend.transcript import working_state as working_state_mod

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


class ApplyRulesRequest(BaseModel):
    rules: list[RegexRuleModel] = Field(default_factory=list)


@router.post("/jobs/{job_id}/apply-rules")
def apply_rules_now(job_id: str, payload: ApplyRulesRequest) -> dict:
    """Apply operator-supplied regex rules to the WORKING layer now.

    A manual find/replace surfaced by the Stage 3 "Apply Rule" control.
    Runs the rules through the deterministic regex module (Pipeline B's
    entry point) and persists the result via the single working-layer
    write authority -- RAW is never touched. Records a `regex_apply_manual`
    provenance event so the change is attributable and distinguishable
    from the engine's auto-run.
    """
    if trepo.get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript job {job_id} not found",
        )
    if not payload.rules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("No rules provided. To run a case's saved rules, use the "
                    "case regex-rules endpoint (future workstream)."),
        )
    for m in payload.rules:
        try:
            re.compile(m.find_pattern)
        except re.error as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid regex pattern {m.find_pattern!r}: {exc}",
            )

    utterances = working_state_mod.get_working_utterances(job_id)
    rules = [_to_rule(m, i) for i, m in enumerate(payload.rules)]
    new_utterances, subs = apply_regex_rules(utterances, rules)

    # Persist only utterances whose text actually changed -- a no-match
    # apply leaves the working layer untouched.
    orig = {u.get("utterance_id"): (u.get("text") or "") for u in utterances}
    overrides = [
        {"utterance_id": u.get("utterance_id"), "working_text": u.get("text") or ""}
        for u in new_utterances
        if u.get("utterance_id")
        and (u.get("text") or "") != orig.get(u.get("utterance_id"))
    ]
    if overrides:
        working_state_mod.persist_working_transcript(
            job_id, overrides, source="regex_apply_manual")

    # Correction-log sidecar: one entry per changed utterance (before -> after),
    # so the Stage 3 correction-log viewer shows manual regex edits alongside
    # the engine's auto-run.
    reason = "; ".join(f"{m.find_pattern} -> {m.replace_with}" for m in payload.rules)
    rule_id = rules[0].rule_id if rules else "regex"
    log_entries = [
        {"rule_id": rule_id, "before": orig.get(u.get("utterance_id"), ""),
         "after": u.get("text") or "", "reason": reason, "stage": "regex"}
        for u in new_utterances
        if u.get("utterance_id")
        and (u.get("text") or "") != orig.get(u.get("utterance_id"))
    ]
    correction_log_store.append_run(job_id, log_entries, source="manual_regex")

    substitutions = sum(getattr(s, "match_count", 0) for s in subs)
    event = provenance_mod.record_event(
        job_id,
        event_type="regex_apply_manual",
        title="Manual regex apply",
        detail=f"{len(rules)} rule(s), {substitutions} substitution(s).",
        source="workspace",
        metadata={
            "rules": [
                {"find_pattern": m.find_pattern, "replace_with": m.replace_with}
                for m in payload.rules
            ],
            "substitutions": substitutions,
            "utterances_changed": len(overrides),
        },
    )
    logger.info(
        f"Manual regex apply for {job_id}: {substitutions} substitution(s) "
        f"across {len(overrides)} utterance(s)."
    )
    return {
        "substitutions": substitutions,
        "rules_applied": len(rules),
        "provenance_event_id": event["event_id"],
    }
