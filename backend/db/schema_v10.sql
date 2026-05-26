-- schema_v10.sql
-- Stage 3 authoritative working transcript layer.
--
-- RAW transcript rows remain immutable. Reporter-reviewed transcript
-- text is stored as utterance-level overrides here, keyed back to the
-- canonical RAW utterances. Only utterances whose working text differs
-- from RAW need a row; the absence of a row means "use RAW as-is".

CREATE TABLE IF NOT EXISTS transcript_working_utterances (
    working_row_id    TEXT PRIMARY KEY,
    job_id            TEXT NOT NULL,
    utterance_id      TEXT NOT NULL,
    working_text      TEXT NOT NULL,
    source            TEXT,                           -- stage3_workspace | snapshot_rollback | api | etc.
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES transcript_jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY (utterance_id) REFERENCES transcript_utterances(utterance_id) ON DELETE CASCADE,
    UNIQUE (utterance_id)
);

CREATE INDEX IF NOT EXISTS idx_transcript_working_utterances_job
    ON transcript_working_utterances(job_id, updated_at);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (10, 'Layer 3 working transcript overrides for Stage 3 authority');
