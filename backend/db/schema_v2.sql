-- Depo-Pro Layer 2 + Layer 3: Transcript Metadata + Transcript Content
-- Schema version: v2
-- Reference: docs/ufm_schema_v1.md, Screen 2 (Transcripts Engine) build plan.
--
-- Design principle (non-negotiable, from the Screen 2 build plan):
--   The transcript is stored as CANONICAL WORD OBJECTS, never as a giant
--   mutable transcript string. The RAW layer is immutable; all edits live
--   in the WORKING layer (transcript_words.working_text).
--
-- All TEXT primary keys are UUIDv4 strings. Timestamps are ISO 8601 UTC.
-- Audio offsets (start_time / end_time) are floating-point SECONDS.

PRAGMA foreign_keys = ON;

-- ====================================================================
-- L2: transcript_jobs
-- One row == one uploaded media file run through the ingestion pipeline.
-- A "batch" of session media is simply several rows ordered by
-- sequence_index and sharing a case_id.
-- ====================================================================
CREATE TABLE IF NOT EXISTS transcript_jobs (
    job_id              TEXT PRIMARY KEY,
    case_id             TEXT,                       -- nullable: media can be transcribed before a case is saved
    session_id          TEXT,                       -- nullable: links to a Layer 1 session once known
    source_filename     TEXT NOT NULL,
    source_size_bytes   INTEGER NOT NULL DEFAULT 0,
    media_kind          TEXT NOT NULL DEFAULT 'prerecorded'
                            CHECK (media_kind IN ('prerecorded', 'live')),
    sequence_index      INTEGER NOT NULL DEFAULT 0, -- chronological order within a batch
    status              TEXT NOT NULL DEFAULT 'queued'
                            CHECK (status IN ('queued', 'preprocessing', 'transcribing',
                                              'assembling', 'completed', 'failed')),
    engine              TEXT NOT NULL DEFAULT 'deepgram-nova-3',
    transcription_source TEXT,                      -- 'deepgram' | 'offline-fallback'
    error_message       TEXT,
    duration_seconds    REAL,
    word_count          INTEGER NOT NULL DEFAULT 0,
    utterance_count     INTEGER NOT NULL DEFAULT 0,
    speaker_count       INTEGER NOT NULL DEFAULT 0,
    avg_confidence      REAL,
    audio_path          TEXT,                       -- data/audio/{job_id}__{filename}
    raw_packet_path     TEXT,                       -- data/transcripts/{job_id}/raw.json      (IMMUTABLE)
    working_packet_path TEXT,                       -- data/transcripts/{job_id}/working.json  (editable)
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at        TEXT,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_transcript_jobs_case ON transcript_jobs(case_id);
CREATE INDEX IF NOT EXISTS idx_transcript_jobs_status ON transcript_jobs(status);
CREATE INDEX IF NOT EXISTS idx_transcript_jobs_created ON transcript_jobs(created_at);

-- ====================================================================
-- L3: transcript_speakers
-- The speaker map for one job. assigned_name / speaker_role are filled
-- in later by the reporter in the Workspace stage.
-- ====================================================================
CREATE TABLE IF NOT EXISTS transcript_speakers (
    speaker_row_id  TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    speaker_index   INTEGER NOT NULL,               -- diarization index from the ASR engine (0, 1, 2, ...)
    speaker_label   TEXT NOT NULL,                  -- display label, e.g. "Speaker 0"
    assigned_name   TEXT,                           -- reporter-mapped attorney / witness name
    speaker_role    TEXT,                           -- "WITNESS", "EXAMINING_ATTORNEY", "REPORTER", ...
    word_count      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (job_id) REFERENCES transcript_jobs(job_id) ON DELETE CASCADE,
    UNIQUE (job_id, speaker_index)
);

CREATE INDEX IF NOT EXISTS idx_transcript_speakers_job ON transcript_speakers(job_id);

-- ====================================================================
-- L3: transcript_utterances
-- Speaker-turn blocks. One utterance == one continuous turn of speech.
-- ====================================================================
CREATE TABLE IF NOT EXISTS transcript_utterances (
    utterance_id     TEXT PRIMARY KEY,
    job_id           TEXT NOT NULL,
    utterance_index  INTEGER NOT NULL,              -- strict ordering within the job (0-based)
    speaker_index    INTEGER,
    speaker_label    TEXT NOT NULL,
    start_time       REAL NOT NULL,
    end_time         REAL NOT NULL,
    text             TEXT NOT NULL,                 -- concatenated verbatim text (raw layer)
    avg_confidence   REAL,
    FOREIGN KEY (job_id) REFERENCES transcript_jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcript_utterances_job ON transcript_utterances(job_id, utterance_index);

-- ====================================================================
-- L3: transcript_words  -- THE CANONICAL TRANSCRIPT LAYER
-- raw_text is IMMUTABLE: it is the verbatim ASR output and is never
-- modified after ingestion. working_text is the editable override used
-- by the Workspace stage; NULL means "unedited, use raw_text".
-- ====================================================================
CREATE TABLE IF NOT EXISTS transcript_words (
    word_id        TEXT PRIMARY KEY,
    job_id         TEXT NOT NULL,
    utterance_id   TEXT NOT NULL,
    word_index     INTEGER NOT NULL,                -- global strict ordering within the job (0-based)
    raw_text       TEXT NOT NULL,                   -- IMMUTABLE verbatim ASR token
    working_text   TEXT,                            -- editable override (NULL = unedited)
    speaker_index  INTEGER,
    start_time     REAL NOT NULL,
    end_time       REAL NOT NULL,
    confidence     REAL NOT NULL,                   -- model confidence [0.0, 1.0]
    is_filler      INTEGER NOT NULL DEFAULT 0 CHECK (is_filler IN (0, 1)),
    reviewed       INTEGER NOT NULL DEFAULT 0 CHECK (reviewed IN (0, 1)),
    FOREIGN KEY (job_id) REFERENCES transcript_jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY (utterance_id) REFERENCES transcript_utterances(utterance_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcript_words_job ON transcript_words(job_id, word_index);
CREATE INDEX IF NOT EXISTS idx_transcript_words_utterance ON transcript_words(utterance_id);
CREATE INDEX IF NOT EXISTS idx_transcript_words_confidence ON transcript_words(job_id, confidence);

-- Schema version row (insert last, after all v2 tables exist)
INSERT OR IGNORE INTO schema_version (version, description)
VALUES (2, 'Layer 2/3: transcript_jobs, transcript_speakers, transcript_utterances, transcript_words');
