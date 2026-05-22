-- schema_v5.sql
-- Wave 14: per-case regex correction rules.
--
-- Moves the regex find/replace correction out of the frontend-only
-- sandbox into a persisted, ordered, replayable backend pipeline.
-- Rules belong to a case, are individually enable/disable-able, and
-- apply in rule_order during every render.

CREATE TABLE IF NOT EXISTS case_regex_rules (
    rule_id        TEXT PRIMARY KEY,
    case_id        TEXT NOT NULL,
    find_pattern   TEXT NOT NULL,
    replace_with   TEXT NOT NULL DEFAULT '',
    rule_order     INTEGER NOT NULL DEFAULT 0,
    enabled        INTEGER NOT NULL DEFAULT 1,
    description    TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_case_regex_rules_case
    ON case_regex_rules (case_id, rule_order);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (5, 'Layer 5: Wave 14 per-case regex correction rules');
