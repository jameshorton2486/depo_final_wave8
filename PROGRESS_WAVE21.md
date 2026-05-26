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

## 2026-05-25 — Subsystem 3 Completed

Status change:
- Subsystem 3 — Certificate Data-Capture Path: `OPERATIONAL`

Implemented:
- certification validation now blocks when the existing Stage 5 statutory fields are missing:
  - `examination_disposition`
  - `custodial_attorney`
  - `officer_charges_amount`
  - `charges_party`
  - `certificate_service_date`
  - `reporter_csr_expiration`
  - `firm_registration_no`
  - `time_per_party`
  - `counsel_of_record`
  - `appearances`
- SBOT numbers are enforced through:
  - `appearances[n].sbot_no`
- Stage 5 now visibly marks the certificate fields as certification-gating
- added negative-path certification coverage for missing statutory fields

Verification:
- focused packaging/certification suites: `60 passed`
- full suite:
  - `501 passed, 1 skipped, 32 warnings`

Open decision carried forward:
- `Q20-6` remains open in `docs/BLOCKERS.md`
- the code now enforces the enumerated BLOCKER-3 follow-on fields without claiming that the broader final legal metadata set is settled forever

Next build targets:
1. Subsystem 4 — implement explicit runtime offline-provider mode with certification refusal
2. Subsystem 5 — reconcile status docs to the verified codebase

## 2026-05-25 — Subsystem 4 Completed

Status change:
- Subsystem 4 — Runtime Offline-Provider Mode: `OPERATIONAL`

Implemented:
- explicit runtime provider switch:
  - `DEPOPRO_TRANSCRIPTION_PROVIDER=deepgram`
  - `DEPOPRO_TRANSCRIPTION_PROVIDER=offline`
- deterministic offline mode now works even when a real `DEEPGRAM_API_KEY` is present
- offline-produced jobs are durably marked through their stored `transcription_source`
- transcript job payloads now surface:
  - `authoritative_transcript`
- Stage 2 visibly labels offline validation transcripts as non-certifiable
- Stage 5 lineage/status UI now warns when the active transcript is offline/non-authoritative
- packaging assembly hard-refuses offline validation transcripts from entering the certification chain
- operator docs added:
  - `.env.example`
  - `development_workflow.md`

Verification:
- focused offline/provider/certification suites: `34 passed`
- full suite:
  - `504 passed, 1 skipped, 33 warnings`

Trust outcome:
- manual MVP validation can now run end-to-end without a live provider key
- offline transcripts remain usable for workflow validation
- offline transcripts cannot be certified by accident

Next build target:
1. Subsystem 5 — reconcile status docs to the verified codebase
