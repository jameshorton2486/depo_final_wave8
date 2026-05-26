-- schema_v11.sql
-- Stage 3 durable transcript provenance events.
--
-- Every working-layer mutation, snapshot restore, certification freeze,
-- and export lineage event can be recorded here without touching the
-- immutable raw transcript or overwriting prior audit history.

CREATE TABLE IF NOT EXISTS transcript_provenance_events (
    event_id             TEXT PRIMARY KEY,
    job_id               TEXT NOT NULL,
    event_type           TEXT NOT NULL,
    title                TEXT NOT NULL,
    detail               TEXT,
    actor_type           TEXT NOT NULL DEFAULT 'system', -- user | system | ai
    source               TEXT,                           -- workspace | snapshots | export | ai_review | packaging
    metadata_json        TEXT,
    related_snapshot_id  TEXT,
    related_suggestion_id TEXT,
    related_package_id   TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES transcript_jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcript_provenance_events_job
    ON transcript_provenance_events(job_id, created_at DESC);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (11, 'Durable transcript provenance events for Stage 3 auditability');
