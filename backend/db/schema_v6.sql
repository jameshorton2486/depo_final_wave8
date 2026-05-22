-- schema_v6.sql
-- Wave 15b: the AI review queue.
--
-- Every AI-proposed change is persisted here as a pending suggestion.
-- Approval is the only path from a suggestion to the transcript; the
-- AI layer never writes the WORKING transcript directly.

CREATE TABLE IF NOT EXISTS ai_suggestions (
    suggestion_id        TEXT PRIMARY KEY,
    job_id               TEXT NOT NULL,
    kind                 TEXT NOT NULL,        -- speaker_map|boundary|garble|flag
    reason               TEXT NOT NULL DEFAULT '',
    target_utterance_id  TEXT,
    before_text          TEXT,
    after_text           TEXT,
    four_part_pass       INTEGER NOT NULL DEFAULT 0,
    status               TEXT NOT NULL DEFAULT 'pending',
    payload_json         TEXT,                 -- JSON, e.g. speaker-map
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at          TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_suggestions_job
    ON ai_suggestions (job_id, status);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (6, 'Layer 6: Wave 15b AI review queue');
