-- schema_v4.sql
-- Wave 11: Workspace Speaker Panel
--
-- Adds two columns to transcript_participants (introduced Wave 9):
--   name_source -- provenance of the participant's name/label, so the UI
--                  can show what is a deterministic guess vs. user-confirmed.
--   honorific   -- MR | MS | MRS | DR | NULL, for attorney/witness rows.
--                  The speaker label is rebuilt as "{HONORIFIC}. {SURNAME}"
--                  whenever this or the name changes. NULL for court officers.
--
-- SQLite cannot ADD COLUMN conditionally inside a plain script, so the
-- actual idempotent column adds are done by _ensure_column() in
-- migrations.py. This file only records the schema intent and bumps the
-- schema_version row.

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (4, 'Layer 4: Wave 11 participant name_source + honorific');
