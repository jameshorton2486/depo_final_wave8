# Reference Ownership Impact Matrix

## Scope

This is the Phase 3A pre-implementation blueprint for the accepted
**Option C — Hybrid Model**.

Accepted model:

- internal ownership
  - transcript references: `snapshot_id + render_line_id`
  - exhibit references: `snapshot_id + anchor_utterance_id`
- visible legal citation
  - derived `Page N`
  - derived `Page N, Line M`

This document identifies **what must change** to implement that model.

No implementation is performed here.

## High-Level Answer

The hybrid model can be implemented **without changing visible transcript
output** if Phase 3A limits itself to:

- internal/package model enrichment
- package JSON / API enrichment
- reference-generation logic changes

It does **not** require:

- SQLite table schema changes
- snapshot storage format changes
- DOCX/PDF/RTF/TXT export format changes

It **does** require:

- package/index model changes
- package persistence reconstruction changes
- packaging API/package JSON changes

## Object Impact Matrix

| Object | Current Fields | Future Fields | Migration Required | Data Conversion Required | Risk |
| ---- | ---- | ---- | ---- | ---- | ---- |
| `IndexEntry` | `label`, `page`, `line`, `detail`, derived `reference` | add stable owner such as `reference_snapshot_id`, `reference_render_line_id`; keep `page`, `line`, `reference` as derived citation | YES | Existing stored package JSON entries need backward-compatible reconstruction | HIGH |
| `Exhibit` | `exhibit_number`, `exhibit_title`, `reference_render_line_id`, `reference`, `exhibit_files` | add stable exhibit owner such as `reference_snapshot_id`, `reference_anchor_utterance_id`; retain `reference_render_line_id`; keep `reference` as derived citation | YES | Existing stored package JSON entries need backward-compatible reconstruction | HIGH |
| Packaging models | package/index dataclasses carry visible refs only | package/index dataclasses carry stable owner + visible citation | YES | Package JSON backward compatibility required | HIGH |
| Snapshot models | already carry `snapshot_id`, `state_hash`, full `state` | likely no new required fields; existing `snapshot_id` is enough for ownership | NO required structural change | No | LOW |
| Transcript models | `TranscriptExhibit` carries `anchor_utterance_id`; transcript lines already have `utterance_id`; Stage S has `RenderLine.line_id` | likely no required API model change for transcript CRUD; optional future exposure only | NO required structural change | No | LOW |
| Export models | `ExportDocument`, `ExportPage`, `ExportLine` carry visible page/line output only | no required change if visible output stays the same | NO | No | LOW |
| API responses | package JSON currently exposes visible refs only | package JSON likely needs new stable-owner fields; transcript/exhibit CRUD APIs can stay unchanged in first pass | YES for packaging responses | Backward-compatible package JSON handling required | MEDIUM |

## Exact File List

### Files that must change

These are the minimum files that must change to implement the hybrid model.

1. [backend/packaging/model.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/model.py)
   - `IndexEntry`
   - `Exhibit`
   - package JSON shape via `to_dict()`

2. [backend/packaging/indices.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/indices.py)
   - populate stable owner fields while still deriving visible `page,line`
   - preserve current visible `reference`

3. [backend/api/packaging.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/api/packaging.py)
   - exhibit bridge must pass the correct stable ownership inputs
   - likely add snapshot-bound owner data into generated package objects

4. [backend/packaging/package_repo.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/package_repo.py)
   - reconstruct new fields from stored package JSON
   - maintain backward compatibility for older packages lacking them

5. [backend/packaging/__init__.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/__init__.py)
   - only if new fields / exports are surfaced through public packaging API

### Files likely to change

These depend on the exact implementation shape, but are likely participants.

6. [backend/packaging/admin_pages.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/admin_pages.py)
   - only if admin-page text generation starts reading new reference structures
   - not required if it continues to consume visible `reference`

7. [backend/packaging/validation.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/validation.py)
   - only if certification/package validation begins checking stable-owner presence
   - not required for a first internal-only pass

8. package-related tests
   - especially:
     - [tests/test_wave20_packaging.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/tests/test_wave20_packaging.py)
     - any tests reconstructing package JSON or asserting index/exhibit dict shape

### Files that do not need to change for Phase 3A implementation

1. [backend/pagination/model.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/pagination/model.py)
   - already carries `source_render_line_id`

2. [backend/transcript/export_render.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/transcript/export_render.py)
   - no required visible-output change for hybrid ownership

3. [backend/transcript_state/model.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/transcript_state/model.py)
4. [backend/transcript_state/snapshot_repo.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/transcript_state/snapshot_repo.py)
   - current snapshot identity is already sufficient

5. [backend/models/transcripts.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/models/transcripts.py)
   - transcript/exhibit CRUD models already expose anchor identity

6. export writers / export service
   - [backend/export/export_service.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/export/export_service.py)
   - [backend/export/docx_writer.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/export/docx_writer.py)
   - [backend/export/pdf_writer.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/export/pdf_writer.py)
   - [backend/export/rtf_writer.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/export/rtf_writer.py)
   - [backend/export/txt_writer.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/export/txt_writer.py)

## Model-Level Changes

### `IndexEntry`

Current:

- `label`
- `page`
- `line`
- `detail`
- derived `reference`

Future minimum:

- `reference_snapshot_id: str = ""`
- `reference_render_line_id: str = ""`
- keep `page`, `line`, `reference`

Reason:

- page/line becomes derived citation
- stable identity becomes owned internal reference

### `Exhibit`

Current:

- `exhibit_number`
- `exhibit_title`
- `reference_render_line_id`
- `reference`

Future minimum:

- `reference_snapshot_id: str = ""`
- `reference_anchor_utterance_id: str = ""`
- keep `reference_render_line_id`
- keep `reference`

Reason:

- exhibit identity is truly anchored by utterance identity, not page location

## Direct Answers

### 1. Which files must change?

Required:

- `backend/packaging/model.py`
- `backend/packaging/indices.py`
- `backend/api/packaging.py`
- `backend/packaging/package_repo.py`

Likely:

- `backend/packaging/__init__.py`
- package/index-related tests

### 2. Which models must change?

Required:

- `IndexEntry`
- `Exhibit`

Likely no required change:

- `PackageIdentity`
- `PackageManifest`
- transcript CRUD models
- snapshot models
- export models

### 3. Does SQLite schema change?

**No table schema change is required.**

Reason:

- package JSON already stores flexible serialized payloads
- snapshot tables already store `snapshot_id` and full state
- transcript exhibit storage already carries `anchor_utterance_id`

What does change:

- JSON content stored in `transcript_packages.package_json`
- reconstruction logic in `package_repo.py`

### 4. Does snapshot format change?

**No required snapshot format change.**

Reason:

- `snapshot_id` already exists
- `snapshot.state` already contains transcript/exhibit state
- the hybrid model can bind to existing snapshot identity

Optional future enhancement:

- snapshot state could carry precomputed semantic reference metadata, but that is not required for Phase 3A implementation

### 5. Does export format change?

**No.**

Reason:

- DOCX/PDF/RTF/TXT exports emit visible page and line numbering
- hybrid ownership changes internal reference ownership, not visible transcript rendering

### 6. Does packaging output change?

**Yes, package JSON output changes.**

Reason:

- package/index/exhibit objects would gain stable-owner fields
- visible `reference` string can remain unchanged

Important distinction:

- human-facing admin-page text does not need to change
- serialized package/API payload shape likely does

### 7. Can Phase 3A be implemented without changing visible output?

**Yes.**

If implementation is scoped correctly:

- visible transcript export output: unchanged
- visible admin-page index lines: unchanged
- visible certificate output: unchanged

Only internal/package JSON ownership fields change.

## Risk Notes

### Highest risk

- `backend/packaging/package_repo.py`
  - backward compatibility for previously stored packages

- `backend/packaging/model.py`
  - new fields must not break current JSON consumers

### Medium risk

- `backend/api/packaging.py`
  - must populate stable fields consistently from snapshot state

### Low risk

- export path
- snapshot persistence
- transcript CRUD APIs

## Implementation Shape Recommended for Phase 3A

Implement Phase 3A as an **internal ownership enrichment pass**:

1. add stable owner fields to packaging models
2. populate them during index/exhibit generation
3. preserve visible `reference` output exactly as-is
4. keep SQLite schema unchanged
5. keep snapshot format unchanged
6. add backward-compatible package reconstruction

That is the smallest path that realizes Option C without visible-output churn.
