"""Idempotent seed data for Depo-Pro.

Currently seeds:
- form_templates: 'Generic Fallback v1' and 'S.A. Legal Solutions v1'

Re-running seed() is safe - uses INSERT OR IGNORE on UNIQUE name.
"""
from __future__ import annotations

import json
import uuid

from loguru import logger

from backend.db.migrations import _connect

GENERIC_TEMPLATE_LAYOUT = {
    "type": "generic_fallback",
    "version": 1,
    "fields_expected": [
        "case_caption",
        "cause_number",
        "court",
        "deponent",
        "scheduled_date",
        "scheduled_time",
        "location",
        "ordering_attorney",
        "ordered_by",
    ],
    "parser_hints": {
        "section_order": "header_then_body",
    },
}

SA_LEGAL_TEMPLATE_LAYOUT = {
    "type": "sa_legal_solutions",
    "version": 1,
    "header_tokens": ["S.A. LEGAL SOLUTIONS", "Court Reporting"],
    "fields_expected": [
        "Location", "Date", "Deponent", "Case/Style", "CSR",
        "Sch Start Time", "Start Time", "End Time",
        "Appearance", "CNA", "Read & Sign", "Signature Waived", "Send To",
        "Video/Med/Tech", "Pages", "Exhibit Count", "BW", "Color",
        "Ordering Attorney", "Firm", "Format", "Delivery",
        "Address", "Phone", "Email", "Notes",
        "Copy Attorney",
        "Interpreter", "Conference Room", "Travel Miles", "Parking",
        "Special Instructions, If Any",
        "Ordered by",
    ],
    "parser_hints": {
        "is_tabular": True,
        "supports_multiple_copy_attorneys": True,
    },
}


def _new_id() -> str:
    return str(uuid.uuid4())


def seed() -> dict[str, dict[str, int]]:
    """Insert seed rows. Returns counts of new and existing rows by table."""
    conn = _connect()
    try:
        added = {"form_templates": 0}
        existing = {"form_templates": 0}

        generic_id = _new_id()
        cur = conn.execute(
            "INSERT OR IGNORE INTO form_templates "
            "(template_id, name, reporting_firm_id, layout_json, is_default) "
            "VALUES (?, ?, NULL, ?, 1)",
            (generic_id, "Generic Fallback v1", json.dumps(GENERIC_TEMPLATE_LAYOUT)),
        )
        if cur.rowcount > 0:
            added["form_templates"] += 1
        else:
            existing["form_templates"] += 1

        sa_id = _new_id()
        cur = conn.execute(
            "INSERT OR IGNORE INTO form_templates "
            "(template_id, name, reporting_firm_id, layout_json, is_default) "
            "VALUES (?, ?, NULL, ?, 0)",
            (sa_id, "S.A. Legal Solutions v1", json.dumps(SA_LEGAL_TEMPLATE_LAYOUT)),
        )
        if cur.rowcount > 0:
            added["form_templates"] += 1
        else:
            existing["form_templates"] += 1

        conn.commit()
        logger.info(f"Seeds applied - added: {added}, existing: {existing}")
        return {"added": added, "existing": existing}
    finally:
        conn.close()
