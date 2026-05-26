> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 19B Integrity Plan

Date: 2026-05-25

## Baseline

- Command:
  - `.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=.pytest_tmp`
- Result:
  - `504 passed, 1 skipped`

## Scope Confirmation

This pass is intentionally limited to:

1. Wave 19B transcript integrity subsystem
2. Thin Wave 20B export-validation orchestrator
3. Pytest environment stabilization so plain `pytest tests` works

No scope expansion is planned. In particular:

- no transcript-generation behavior changes
- no renderer / paginator / export-writer rewrite
- no Wave 19A / 19C / 20A / 20C changes unless a minimal integration hook is strictly required
- no unrelated refactors

## Planned Files To Touch

### Phase 0 — Pytest stabilization

- `pyproject.toml`
- `.gitignore`

### Phase 1 — Raw transcript integrity locking

- `backend/transcript/packet.py`
- `backend/transcript/ingest.py`
- `backend/transcript/repository.py`
- `backend/api/transcripts.py`
- `backend/api/packaging.py`
- `backend/models/transcripts.py`
- `tests/test_transcripts_api.py`

Potential new files:

- `backend/transcript/integrity.py`
- `tests/test_transcript_integrity.py`

### Phase 2 — Diff / diagnostics subsystem

New modules:

- `backend/diagnostics/__init__.py`
- `backend/diagnostics/diff_harness.py`
- `backend/diagnostics/metrics.py`
- `backend/diagnostics/align.py`
- `backend/diagnostics/report.py`
- `backend/diagnostics/ref_import.py`
- `tools/run_diff.py`
- `tests/diagnostics/test_metrics.py`
- `tests/diagnostics/test_align.py`
- `tests/diagnostics/test_diff_harness.py`

### Phase 3 — Mutation detection enforcement

- `backend/api/packaging.py`
- `backend/packaging/packager.py`
- `backend/transcript/provenance.py`
- `tests/test_wave20_packaging.py`

Potential new files:

- `backend/transcript/mutation_detection.py`
- `tests/test_mutation_detection.py`

### Phase 4 — Thin 20B orchestrator

- `backend/export/export_validation.py`
- `backend/api/transcripts.py`
- `backend/api/packaging.py`
- `tests/test_wave18_export.py`
- `tests/test_wave20_packaging.py`

## Schema / Stop-And-Ask Assessment

Current assessment: a schema migration is **not required** for this pass.

Plan:
- persist raw integrity metadata as a durable sidecar file adjacent to `raw.json`
- keep the diff harness read-only
- keep mutation enforcement separate from diagnostics

If a durable DB-backed raw-integrity record becomes necessary after implementation starts, work will stop for approval before any migration is added.
