-- schema_v12.sql
-- Stage 4 authoritative exhibit anchors for transcript jobs.
--
-- Exhibits are persisted as transcript-bound records anchored to a
-- stable utterance_id. Pagination is derived later from the frozen
-- snapshot/export pipeline; page/line numbers are never stored here as
-- authority.

CREATE TABLE IF NOT EXISTS transcript_exhibits (
    exhibit_id         TEXT PRIMARY KEY,
    job_id             TEXT NOT NULL,
    case_id            TEXT,
    session_id         TEXT,
    exhibit_number     TEXT NOT NULL,
    exhibit_title      TEXT NOT NULL DEFAULT '',
    offering_attorney  TEXT NOT NULL DEFAULT '',
    description        TEXT NOT NULL DEFAULT '',
    anchor_utterance_id TEXT NOT NULL,
    anchor_note        TEXT NOT NULL DEFAULT '',
    sort_order         INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES transcript_jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY (anchor_utterance_id) REFERENCES transcript_utterances(utterance_id) ON DELETE CASCADE,
    UNIQUE (job_id, exhibit_number)
);

CREATE INDEX IF NOT EXISTS idx_transcript_exhibits_job
    ON transcript_exhibits(job_id, sort_order, created_at);

CREATE INDEX IF NOT EXISTS idx_transcript_exhibits_anchor
    ON transcript_exhibits(job_id, anchor_utterance_id);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (12, 'Stage 4 authoritative transcript exhibits anchored to utterances');
