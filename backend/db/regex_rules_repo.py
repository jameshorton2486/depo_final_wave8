"""Persistence for per-case regex correction rules — Wave 14.

CRUD over the case_regex_rules table (schema_v5). Rules are returned
in rule_order so the correction pipeline replays them deterministically.
"""
from __future__ import annotations

import uuid

from backend.corrections.regex_rules import RegexRule
from backend.db.repository import get_connection

_COLUMNS = (
    "rule_id", "case_id", "find_pattern", "replace_with",
    "rule_order", "enabled", "description", "created_at", "updated_at",
)


def _row_to_rule(row) -> RegexRule:
    return RegexRule(
        rule_id=row["rule_id"],
        find_pattern=row["find_pattern"],
        replace_with=row["replace_with"] or "",
        rule_order=row["rule_order"],
        enabled=bool(row["enabled"]),
        description=row["description"] or "",
    )


def list_rules(case_id: str) -> list[RegexRule]:
    """Return a case's regex rules, ordered by rule_order."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM case_regex_rules WHERE case_id = ? "
            "ORDER BY rule_order ASC, created_at ASC",
            (case_id,),
        ).fetchall()
    return [_row_to_rule(r) for r in rows]


def replace_rules(case_id: str, rules: list[dict]) -> list[RegexRule]:
    """Replace a case's entire rule set in one transaction.

    rule_order is assigned from list position so ordering is explicit
    and stable. Idempotent: re-saving overwrites cleanly.
    """
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM case_regex_rules WHERE case_id = ?", (case_id,))
        for order, r in enumerate(rules or []):
            find = (r.get("find_pattern") or "").strip()
            if not find:
                continue                      # skip empty patterns
            conn.execute(
                "INSERT INTO case_regex_rules "
                "(rule_id, case_id, find_pattern, replace_with, "
                " rule_order, enabled, description) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    r.get("rule_id") or str(uuid.uuid4()),
                    case_id,
                    find,
                    r.get("replace_with") or "",
                    order,
                    1 if r.get("enabled", True) else 0,
                    (r.get("description") or "").strip() or None,
                ),
            )
    return list_rules(case_id)


def delete_rules(case_id: str) -> int:
    """Delete all regex rules for a case. Returns the count removed."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM case_regex_rules WHERE case_id = ?", (case_id,))
        return cur.rowcount
