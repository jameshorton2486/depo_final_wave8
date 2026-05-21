-- Depo-Pro Layer 3+: Canonical Participant Identity
-- Schema version: v3
--
-- WHY THIS TABLE EXISTS
--   Deepgram diarization emits speaker indices (0, 1, 2, ...). Those are
--   ACOUSTIC CLUSTERS, not people. On real depositions one person is
--   routinely split across several indices (a witness on a failing mic
--   becomes Speaker 2 AND Speaker 3); two indices may also be the same
--   attorney. A certified transcript can never ride on raw indices.
--
--   transcript_participants is the canonical identity layer: each row is
--   ONE real person/role, and speaker_indices lists every raw diarization
--   index that collapses onto them. The reporter confirms this mapping in
--   the Speaker Mapping step; the app then renders Q/A and colloquy from
--   it deterministically -- no AI, no heuristic, in the certified path.
--
--   The raw transcript_speakers / transcript_utterances / transcript_words
--   rows are NEVER mutated by this layer. Participants sit on top of them.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS transcript_participants (
    participant_id   TEXT PRIMARY KEY,
    job_id           TEXT NOT NULL,
    name             TEXT,                       -- "Heath Thomas" (NULL until the reporter fills it)
    role             TEXT NOT NULL DEFAULT 'other'
                        CHECK (role IN (
                            'examining_attorney',
                            'witness',
                            'defending_attorney',
                            'co_counsel',
                            'court_reporter',
                            'videographer',
                            'interpreter',
                            'off_record',
                            'other'
                        )),
    speaker_indices  TEXT NOT NULL DEFAULT '[]', -- JSON array of raw diarization indices, e.g. "[2, 3]"
    is_prefill       INTEGER NOT NULL DEFAULT 0  -- 1 = deterministic first guess, not yet confirmed by the reporter
                        CHECK (is_prefill IN (0, 1)),
    sort_order       INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES transcript_jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcript_participants_job
    ON transcript_participants(job_id);

-- Schema version row (insert last).
INSERT OR IGNORE INTO schema_version (version, description)
VALUES (3, 'Layer 3+: transcript_participants (canonical speaker identity)');
