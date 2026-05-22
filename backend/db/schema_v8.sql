-- schema_v8.sql
-- Wave 20: the Transcript Packaging Engine persistence layer.
--
-- A transcript_package row is the persisted form of a TranscriptPackage
-- produced by the Wave 20 packager. Packages are append-only and
-- immutable once certified: a row is never deleted or overwritten.
-- Certification produces a new row if the package is amended/superseded.
--
-- The manifest_json column stores the full PackageManifest (including
-- the manifest_hash integrity anchor). The package_json column stores
-- the complete TranscriptPackage as a JSON snapshot so any state can be
-- retrieved without re-running the packager.

CREATE TABLE IF NOT EXISTS transcript_packages (
    package_id       TEXT PRIMARY KEY,
    job_id           TEXT NOT NULL,
    snapshot_id      TEXT NOT NULL,
    state_hash       TEXT NOT NULL,
    package_state    TEXT NOT NULL DEFAULT 'DRAFT',
                     -- DRAFT|REVIEW|CERTIFIED|EXPORTED|SEALED|AMENDED|SUPERSEDED
    manifest_hash    TEXT,                -- SHA-256 of manifest (integrity anchor)
    manifest_json    TEXT NOT NULL,       -- full PackageManifest JSON
    package_json     TEXT NOT NULL,       -- full TranscriptPackage JSON snapshot
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    certified_at     TEXT                 -- set when package_state = CERTIFIED
);

CREATE INDEX IF NOT EXISTS idx_transcript_packages_job
    ON transcript_packages (job_id, created_at);

CREATE INDEX IF NOT EXISTS idx_transcript_packages_snapshot
    ON transcript_packages (snapshot_id);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (8, 'Layer 8: Wave 20 Transcript Packaging Engine persistence layer');
