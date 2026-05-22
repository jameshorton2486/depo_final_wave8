-- schema_v9.sql
-- Wave 21: Deposition metadata capture for certificate fields.
--
-- Stores job-specific fields that the Reporter's Certificate requires
-- but that have no home in any existing table: examination disposition,
-- officer charges, time used per party, and similar reporter-recorded
-- facts captured after the deposition closes.
--
-- All JSON columns store UTF-8 JSON arrays.

CREATE TABLE IF NOT EXISTS deposition_metadata (
    job_id                   TEXT PRIMARY KEY,
    volume                   TEXT NOT NULL DEFAULT '1',
    examination_disposition  TEXT,   -- 'waived' or 'retained'
    officer_charges_amount   TEXT,   -- e.g. "450.00"
    charges_party            TEXT,   -- which party owes the charges
    certificate_service_date TEXT,   -- ISO date or formatted date
    time_per_party_json      TEXT,   -- JSON: [{party, duration}, ...]
    also_present_json        TEXT,   -- JSON: [{name, role}, ...]
    created_at               TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at               TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (9, 'Layer 9: deposition_metadata capture table for certificate fields');
