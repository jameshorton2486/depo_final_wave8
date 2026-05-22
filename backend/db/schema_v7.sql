-- schema_v7.sql
-- Wave 18.5: the Transcript State Engine (Snapshot Layer).
--
-- A snapshot is an immutable capture of the COMPLETE transcript state
-- at a moment in time. History is append-only: snapshots are never
-- mutated or deleted; rollback creates a NEW snapshot.

CREATE TABLE IF NOT EXISTS transcript_snapshots (
    snapshot_id      TEXT PRIMARY KEY,
    job_id           TEXT NOT NULL,
    category         TEXT NOT NULL DEFAULT 'MANUAL',
                     -- AUTO_SAVE|MANUAL|PRE_AI|POST_AI|POST_REVIEW
                     --  |PRE_EXPORT|EXPORT|CERTIFIED
    state_hash       TEXT NOT NULL,        -- deterministic state hash
    state_json       TEXT NOT NULL,        -- full captured state (JSON)
    ai_trace_json    TEXT,                 -- AI review traceability
    export_refs_json TEXT,                 -- exports made from this state
    locked           INTEGER NOT NULL DEFAULT 0,   -- 1 = Certification Snapshot
    note             TEXT,
    created_by       TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transcript_snapshots_job
    ON transcript_snapshots (job_id, created_at);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (7, 'Layer 7: Wave 18.5 Transcript State Engine snapshot layer');
