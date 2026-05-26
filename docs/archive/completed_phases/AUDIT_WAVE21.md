> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# AUDIT_WAVE21.md — Wave 21 Reality Audit

Date: 2026-05-25
Branch: `mvp-e2e-validation`

## Phase 0 Baseline

Full suite run before any Wave 21 changes:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q --basetemp=.codex_tmp/pytest-wave21-baseline
```

Result:
- `495 passed`
- `1 skipped`
- `29 warnings`

This is the authoritative Wave 21 baseline.

## Premise Check

The Wave 21 plan included three explicit premises plus a doc-reconciliation premise.
They do not all match the current repo state.

### Premise A — "no exhibit table exists"

Status: `FALSE`

Evidence:
- `backend/db/schema_v12.sql` defines `transcript_exhibits`
- `backend/api/exhibits.py` exists
- `backend/api/__init__.py` exports the exhibits router
- `backend/app.py` includes the exhibits router
- `backend/transcript/repository.py` contains exhibit CRUD
- `backend/transcript_state/snapshot_service.py` captures/restores exhibits
- `backend/transcript_state/state_hash.py` includes exhibits in the snapshot hash
- `backend/api/packaging.py` converts snapshot exhibit rows into `ExhibitEvent`s
- tests already cover the path:
  - `tests/test_exhibits_api.py`
  - `tests/test_transcripts_api.py`
  - `tests/test_wave18_5_snapshots.py`
  - `tests/test_wave20_packaging.py`

Verdict: the Stage 4 persistence/certification chain is already built, wired, and tested.

### Premise B — "Stage 2 case filter still hides all jobs"

Status: `STALE / PARTIALLY FALSE`

Evidence:
- Historical report still exists at `docs/JOB_LOADING_REPORT.md`
- `backend/transcript/repository.py:list_jobs()` still supports a strict `WHERE case_id = ?`
- but `frontend/assets/js/screens/stage_2.js:refreshServerTranscriptJobs()` now calls:
  - `window.api.listTranscriptJobs(null)`
- so the Stage 2 persisted job panel now loads all jobs instead of forcing case scope
- new uploads in `backend/api/transcripts.py:upload_transcript()` now require:
  - valid `case_id`
  - valid `session_id`
  - matching case/session ownership

Remaining issue:
- legacy orphan jobs can still exist with `case_id IS NULL`
- there is no re-bind endpoint yet
- those legacy jobs do not inherit trustworthy Stage 1 metadata until manually recreated or otherwise backfilled

Verdict: the original false-empty Stage 2 panel reproduction no longer reproduces, but legacy orphan-job lineage is not fully remediated.

### Premise C — "certificate statutory fields are not captured"

Status: `PARTIALLY FALSE`

Evidence:
- `backend/db/schema_v9.sql` already extends `deposition_metadata`
- `backend/db/depo_meta_repo.py` exists
- `backend/api/depo_meta.py` exists and is wired
- `frontend/assets/js/screens/stage_5.js` already loads/saves:
  - `examination_disposition`
  - `officer_charges_amount`
  - `charges_party`
  - `certificate_service_date`
  - `time_per_party`
  - `also_present`
- `backend/api/packaging.py:_build_metadata_for_job()` hydrates those fields into package metadata
- `tests/test_cert_fields_p1.py`, `tests/test_cert_fields_p2.py`, and `tests/test_cert_fields_p3.py` verify storage and rendering
- `tests/test_cert_fields_p3.py` verifies a populated certificate has no `[BRACKETED]` placeholders

Remaining issue:
- `backend/packaging/validation.py:REQUIRED_METADATA_FIELDS` still only enforces the older core field set:
  - `cause_number`
  - `caption`
  - `court`
  - `witness_name`
  - `reporter_name`
  - `reporter_csr_number`
  - `proceedings_date`
- the newer statutory fields are rendered when present, but not yet required by the validator

Verdict: certificate data-capture is built and wired, but Wave 21 still needs certification-rule hardening if those fields must block certification.

### Premise D — "runtime offline provider mode exists for real-world validation"

Status: `FALSE`

Evidence:
- `backend/deepgram/client.py` has a deterministic offline fallback when `DEEPGRAM_API_KEY` is absent
- tests force the fallback by deleting the env var in `tests/conftest.py`
- but `backend/config.py` has no explicit runtime provider switch such as `DEPOPRO_TRANSCRIPTION_PROVIDER`
- earlier real-world validation confirmed fake media is rejected when a live key is present

Remaining issue:
- there is no explicit runtime offline mode for manual validation
- there is no hard certification refusal tied specifically to an offline-produced job beyond the existing source markers

Verdict: offline behavior exists as an implicit fallback, not as an explicit operational mode.

## Subsystem Classification

Statuses use only the allowed labels:
- `MISSING`
- `SPEC-ONLY`
- `PARTIAL`
- `BUILT-NOT-WIRED`
- `OPERATIONAL`

### Subsystem 1 — Case-Binding Integrity

Status: `PARTIAL`

Why:
- New ingestion is case/session bound at upload time.
- Stage 2 no longer hides all jobs behind a case-only filter.
- Legacy orphan jobs are still possible and there is no re-bind API or one-time backfill helper in `scripts/`.

Evidence:
- `backend/api/transcripts.py`
- `backend/transcript/repository.py`
- `frontend/assets/js/screens/stage_2.js`
- `docs/JOB_LOADING_REPORT.md`

### Subsystem 2 — Exhibit Persistence Subsystem

Status: `OPERATIONAL`

Why:
- Single authoritative backend exhibit store exists.
- Persisted via append-only migration `schema_v12.sql`.
- Wired through API, frontend, snapshot, hash, and packaging.
- Covered by tests.

Evidence:
- `backend/db/schema_v12.sql`
- `backend/api/exhibits.py`
- `backend/app.py`
- `backend/transcript/repository.py`
- `backend/transcript_state/snapshot_service.py`
- `backend/transcript_state/state_hash.py`
- `backend/api/packaging.py`
- `frontend/assets/js/screens/stage_4.js`
- `tests/test_exhibits_api.py`
- `tests/test_wave18_5_snapshots.py`
- `tests/test_wave20_packaging.py`

### Subsystem 3 — Certificate Data-Capture Path

Status: `PARTIAL`

Why:
- The capture path exists end-to-end through `deposition_metadata`, `depo-meta`, Stage 5 UI, and package rendering.
- The validator still does not require the newer statutory fields, so certification blocking is not fully aligned with the Stage 5 form.

Evidence:
- `backend/db/schema_v9.sql`
- `backend/api/depo_meta.py`
- `backend/api/packaging.py`
- `backend/packaging/validation.py`
- `frontend/assets/js/screens/stage_5.js`
- `tests/test_cert_fields_p1.py`
- `tests/test_cert_fields_p2.py`
- `tests/test_cert_fields_p3.py`

### Subsystem 4 — Runtime Offline-Provider Mode

Status: `PARTIAL`

Why:
- Deterministic offline fallback exists.
- It is not exposed as an explicit runtime provider mode.
- Manual validation with a real environment still hits live Deepgram when a key is present.

Evidence:
- `backend/deepgram/client.py`
- `backend/config.py`
- `tests/conftest.py`
- `docs/audits/REAL_WORLD_VALIDATION_LOG.md`

### Subsystem 5 — Documentation Reconciliation

Status: `PARTIAL`

Why:
- Docs exist, but major status lines are stale.
- `README.md` still describes the app as mostly mock / not started.
- `docs/wave_status_report.md` still says Waves 19 and 20 are built-not-wired, which is no longer true.
- `docs/BLOCKERS.md` says all five blockers are resolved, but the required-field-set follow-on remains open.

Evidence:
- `README.md`
- `docs/wave_status_report.md`
- `docs/BLOCKERS.md`

## What Wave 21 Actually Needs

Based on current code, Wave 21 should not rebuild Stage 4 from scratch.

The remaining real work is:
1. Finish legacy case-binding remediation honestly:
   - re-bind path and/or documented backfill helper
2. Harden certification validation for the Stage 5 statutory fields
3. Add an explicit runtime offline-provider switch with trust-safe certification refusal
4. Reconcile the docs to the verified repo state

## Skip List From This Audit

These subsystems should be skipped unless new evidence disproves the audit:
- Stage 4 exhibit persistence rebuild
- Stage 4 snapshot exhibit capture rebuild
- Stage 4 packaging ExhibitEvent integration rebuild
- Stage 5 basic cert-field capture UI build

They already exist.
