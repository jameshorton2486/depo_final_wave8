> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# PROGRESS_STAGE5.md — Stage 5 Certify Wiring

## Status: COMPLETE

All completion criteria from STAGE5_CERTIFY_WIRING.md are met.

---

## What is complete

### Phase 0 — Audit
- Baseline: 464 passed, 1 skipped.
- Full API contract documented in `AUDIT_STAGE5.md`.
- Call sequence confirmed from `test_packaging_certify_full_workflow`.

### Phase 1 — API client (`frontend/assets/js/api.js`)
Added four methods matching the existing style:
- `createSnapshot(jobId, category)` — `POST /api/snapshots/jobs/{job_id}`
- `lockSnapshot(snapshotId)` — `POST /api/snapshots/{snapshot_id}/lock`
- `assemblePackage(jobId, snapshotId, metadata)` — `POST /api/packages/jobs/{job_id}`
- `certifyPackage(packageId, metadata)` — `POST /api/packages/{package_id}/certify`

### Phase 2 — Wire signTranscript() (`frontend/assets/js/screens/stage_5.js`)
Rewrote `signTranscript()` to:
1. Validate preconditions (signature, 3 checkboxes, active jobId)
2. Disable the sign button (double-submit guard)
3. Call `_saveCertFields()` (existing)
4. Create and lock a CERTIFIED snapshot via the API
5. Assemble a DRAFT package from the locked snapshot
6. Certify the package

### Phase 3 — Honest result + failure handling
- **On success**: `certPostLock` is populated with real API response fields:
  `package_id`, `certified_at` (as locale timestamp), `manifest_hash` (truncated).
  The certified badge appears **only** on a real 200 CERTIFIED response.
- **On failure**: `#certErrorArea` (new element) becomes visible with the exact
  `detail` string from the 422/400 response. The screen stays in `certPreLock`
  state; the certified badge is never shown. The sign button is re-enabled.
- Provenance log records success and failure with real package data.

### Phase 4 — Contract test (`tests/test_stage5_certify_contract.py`)
Three tests covering the exact UI call sequence:
1. `test_certify_full_workflow_matches_ui_sequence` — positive path; asserts all
   response fields the UI reads (`certified`, `package_id`, `package_state`,
   `manifest_hash`, `certified_at`, `generation_report.certification_status`,
   `generation_report.validation_passed`).
2. `test_certify_empty_body_returns_422_with_detail` — empty transcript → 422 with
   a non-empty `detail` string mentioning "body".
3. `test_certify_already_certified_returns_400` — re-certifying a CERTIFIED package
   returns 400 (not 500), detail mentions "certified".

### Test results
- **467 passed, 1 skipped** (3 new contract tests added; no regressions).
- `node --check frontend/assets/js/api.js` — OK
- `node --check frontend/assets/js/screens/stage_5.js` — OK

---

## What is partial / blocked

None. All phases complete.

---

## Manual smoke-test checklist

There is no JS test runner in this repo. The following steps must be verified
manually after starting the server (`uvicorn backend.app:app --reload`):

**Happy path**
- [ ] Open Stage 5 (Certify) for a job that has utterances (real content).
- [ ] Fill in the Reporter's Certificate Fields (volume, disposition, etc.) and
      click elsewhere — confirm "Saved." appears briefly.
- [ ] Check all three acknowledgement checkboxes.
- [ ] Enter a signature in the signature field.
- [ ] Click "Lock & Sign Document Bundle".
  - Verify the button becomes disabled during the request.
  - Verify the screen transitions to `certPostLock` (green shield icon).
  - Verify **Package ID**, **Manifest Hash**, and **Timestamp** show real values
    from the API (not placeholder text or hardcoded values).
  - Verify the certified badge (`#badgeCertified`) appears in the sidebar.
  - Verify the "Continue to File Export Panel" button works.

**Failure path — empty body**
- [ ] Open Stage 5 for a job with NO utterances.
- [ ] Check all boxes, enter a signature, click "Lock & Sign Document Bundle".
  - Verify the screen stays in `certPreLock` (no certified badge).
  - Verify `#certErrorArea` becomes visible with a message mentioning "body".
  - Verify the sign button is re-enabled after the error.

**Failure path — missing metadata**
- [ ] Simulate a 422 by temporarily removing a required field from the DB for a
      real-content job, or by inspecting network traffic.
  - Verify the error area shows the full detail string from the API.
  - Verify no "Certified" badge appears.

**Re-certification guard**
- [ ] After successfully certifying, reload the page and attempt to certify again.
  - Verify a 400 error is surfaced in `#certErrorArea`.
