> DOCUMENT STATUS: CANONICAL CURRENT-STATE GOVERNANCE
> Scope: export ownership, packaging ownership, snapshot authority, validation gates, and certification lineage.
> This document describes the current live export and certification pipeline.

# EXPORT_AND_CERTIFICATION_PIPELINE.md

## Ownership

| Concern | Owner |
|---|---|
| Working export render path | `backend/api/transcripts.py`, `backend/transcript/export_render.py`, `backend/export/export_service.py` |
| Pagination authority | `backend/pagination/` |
| Geometry authority | `backend/geometry/profile.py`, `backend/geometry/engine.py` |
| Export validation orchestrator | `backend/export/export_validation.py` |
| Package assembly / validation | `backend/packaging/`, `backend/api/packaging.py` |
| Snapshot lock / lineage | `backend/transcript_state/` |
| Mutation-detection certification gate | `backend/transcript/mutation_detection.py`, invoked by `backend/api/packaging.py` |

## Working Export

- Source of truth: current authoritative working transcript state.
- Entry point: `POST /api/transcripts/jobs/{job_id}/export` without a snapshot id.
- Preview path: `GET /api/transcripts/jobs/{job_id}/export-preview`.
- Authority note: working export is editable-state output, not certified-state
  output.

## Certified Export

- Source of truth: locked certification snapshot state.
- Entry point: `POST /api/transcripts/jobs/{job_id}/export` with `snapshot_id`.
- Only locked certification snapshots may drive certified export.
- Later working edits must not change prior certified export output.

## Package Assembly

- Entry point: `POST /api/packages/jobs/{job_id}`.
- Requires a locked snapshot.
- Rebuilds pagination and exhibit index inputs from the snapshot state.
- Persists package summaries and full package JSON through the package repo.

## Certification

- Entry point: `POST /api/packages/{package_id}/certify`.
- Requires:
  - raw integrity pass;
  - valid metadata;
  - valid indices;
  - non-empty body pages;
  - mutation-detection pass;
  - authoritative transcript source (offline-fallback transcripts are refused).

Certified packages are immutable. Recertification creates a new lineage entry.

## Validation Gates

### Export validation

`backend/export/export_validation.py` centralizes:

- pagination integrity;
- index resolution;
- certification-readiness validation;
- preview/export consistency.

### Packaging validation

`backend/packaging/validation.py` enforces:

- required metadata fields;
- required certificate fields;
- index reference validity;
- transcript body presence.

### Mutation detection

`backend/transcript/mutation_detection.py` compares raw vs frozen working
snapshot state using the diagnostics layer and blocks certification on
unexplained drift.

## Determinism Rules

- Pagination and geometry are backend-only deterministic authorities.
- Export writers do not decide layout independently.
- Package indices resolve against frozen pagination.
- Locked snapshot state is the only certification/package truth source.
