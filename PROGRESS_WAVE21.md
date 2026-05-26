# PROGRESS_WAVE21.md — Wave 21 Running Log

## 2026-05-25 — Phase 0 Completed

Baseline:
- full suite run before Wave 21 changes
- result: `495 passed, 1 skipped, 29 warnings`

Audit result:
- Subsystem 1 — Case-Binding Integrity: `PARTIAL`
- Subsystem 2 — Exhibit Persistence Subsystem: `OPERATIONAL`
- Subsystem 3 — Certificate Data-Capture Path: `PARTIAL`
- Subsystem 4 — Runtime Offline-Provider Mode: `PARTIAL`
- Subsystem 5 — Documentation Reconciliation: `PARTIAL`

Key findings:
- Stage 4 exhibits are already real, persisted, snapshot-bound, and packaging-integrated.
- The old Stage 2 empty-panel bug no longer reproduces because the UI now loads all jobs and new uploads require valid case/session binding.
- Legacy orphan jobs still lack a re-bind path or documented backfill helper.
- Stage 5 certificate data capture is already built, but the validator still does not require the newer statutory fields.
- Offline transcription exists only as an implicit fallback when `DEEPGRAM_API_KEY` is absent; there is no explicit runtime provider switch yet.
- `README.md` and `docs/wave_status_report.md` are materially stale.

Immediate next build targets:
1. Subsystem 1 — add honest legacy case-binding remediation
2. Subsystem 3 — align certification validation with captured statutory fields
3. Subsystem 4 — implement explicit runtime offline-provider mode with certification refusal
4. Subsystem 5 — reconcile status docs to the verified codebase

## 2026-05-25 — Subsystem 1 Completed

Status change:
- Subsystem 1 — Case-Binding Integrity: `OPERATIONAL`

Implemented:
- `PUT /api/transcripts/jobs/{job_id}` to bind a transcript job to a real case
- `case_bound` surfaced on transcript job payloads
- Stage 2 job panel grouping:
  - current case
  - unbound jobs
  - other cases
- Stage 2 `Bind to Current Case` action for unbound jobs
- one-time backfill helper:
  - `scripts/bind_transcript_job_to_case.py`
- provenance event:
  - `job_case_bound`

Verification:
- targeted Stage 2 transcript API suite: `22 passed`
- JS syntax check:
  - `frontend/assets/js/screens/stage_2.js`
  - `frontend/assets/js/api.js`
- full suite:
  - `498 passed, 1 skipped, 29 warnings`

Net effect:
- legacy unbound jobs are now visible instead of misleadingly empty
- a reporter can bind an existing job to the current case through the UI or API
- new uploads remain case/session-bound at ingest time

Next build targets:
1. Subsystem 3 — align certification validation with captured statutory fields
2. Subsystem 4 — implement explicit runtime offline-provider mode with certification refusal
3. Subsystem 5 — reconcile status docs to the verified codebase
