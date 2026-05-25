# PROGRESS_CERT.md — Final Summary

## Status: COMPLETE

All placeholder fields are captured, persisted, wired into metadata, and the
end-to-end no-placeholder test passes. Test suite: **464 passed, 1 skipped**.

---

## What is complete

### Phase 0 — Audit
- Identified every `[BRACKETED]` field in `backend/packaging/admin_pages.py`
- Classified each field by entity (case / session / reporter / job / computed)
- Filed `AUDIT_CERT.md` with the complete decision record

### Phase 1 — Data model
- **`backend/db/schema_v9.sql`**: new `deposition_metadata` table (job-keyed)
  - Stores: `volume`, `examination_disposition`, `officer_charges_amount`,
    `charges_party`, `certificate_service_date`, `time_per_party_json`,
    `also_present_json`
- **`backend/db/depo_meta_repo.py`**: `get_depo_meta()` + `upsert_depo_meta()`
- **8 persistence tests** — all pass

### Phase 2 — API
- **`backend/api/depo_meta.py`**: `GET /api/depo-meta/jobs/{job_id}` and
  `PUT /api/depo-meta/jobs/{job_id}` — create/update certificate fields
- Registered in **`backend/app.py`**
- **9 API tests** — all pass

### Phase 3 — Wire into packaging
- **`_build_metadata_for_job(job_id, override)`** added to
  `backend/api/packaging.py`
  - Pulls from: `cases`, `sessions`, `reporters`, `reporting_firm_offices`,
    `parties`, `case_attorneys`, `attorneys`, `deposition_metadata`
  - Computes: `certified_day/month/year` from `datetime.now()`
  - Caller `override` wins on every key (explicit request body always takes priority)
- `assemble` and `certify` endpoints updated to call it
- **5 packaging integration tests** including:
  - `test_assembled_certificate_has_no_placeholders` — confirms zero `[` chars
    in the certificate page for a fully-populated job
  - `test_certify_succeeds_with_auto_populated_metadata` — full assemble →
    certify path with empty explicit metadata
  - `test_existing_packaging_tests_unaffected` — regression guard

### Phase 4 — UI
- **`frontend/screens/stage_5_certify.html`**: "Reporter's Certificate Fields"
  form panel added above the certification checklist, with inputs for:
  - Examination disposition (waived / retained select)
  - Volume number
  - Officer's charges amount + billed-to party
  - Certificate service date
  - Time used per party (multi-line text, "Party - H:MM" format)
- **`frontend/assets/js/screens/stage_5.js`**:
  - `_saveCertFields()` — POSTs form values to `/api/depo-meta/jobs/{jobId}`
    immediately before the sign action (async, non-blocking on error)
  - `loadCertFields()` — pre-fills the form from saved data on stage entry
  - Both functions exported to `window`

---

## What is partial

None. All fields have a defined storage location and reach `metadata`.

---

## What is blocked

None.

---

## Fields auto-populated from existing tables (no new storage needed)

| metadata_key | Source |
|---|---|
| `cause_number` | `cases.case_number_value` |
| `caption` | `cases.caption_full` |
| `court` | derived: `judicial_district + county + state` |
| `county` | `cases.county` |
| `judicial_district` | `cases.judicial_district` |
| `plaintiff_names` | `parties` WHERE role='plaintiff' |
| `defendant_names` | `parties` WHERE role='defendant' |
| `witness_name` | `sessions.witness_name` |
| `party_at_instance` | `sessions.requesting_party_name` |
| `custodial_attorney` | `sessions.custodial_attorney_name` |
| `proceedings_date/month/day/year` | derived from `sessions.scheduled_at` |
| `start_time` | derived from `sessions.scheduled_at` |
| `end_time` | derived from `sessions.scheduled_end_at` |
| `deposition_method` | mapped from `sessions.location_type` |
| `reporter_name` | `reporters.full_name` |
| `reporter_csr_number` | `reporters.csr_number` |
| `reporter_csr_expiration` | `reporters.csr_expiration` |
| `firm_registration_no` | `reporters.firm_registration_number` |
| `firm_address` | `reporting_firm_offices.address_line` (default office) |
| `firm_city_state_zip` | `reporting_firm_offices.(city, state, zip)` |
| `appearances` | joined: `case_attorneys` + `attorneys` + `parties` |
| `counsel_of_record` | same join |
| `certified_day/month/year` | `datetime.now()` at assembly time |

## New fields captured via `deposition_metadata` table

| metadata_key | Column |
|---|---|
| `volume` | `deposition_metadata.volume` |
| `examination_disposition` | `deposition_metadata.examination_disposition` |
| `officer_charges_amount` | `deposition_metadata.officer_charges_amount` |
| `charges_party` | `deposition_metadata.charges_party` |
| `certificate_service_date` | `deposition_metadata.certificate_service_date` |
| `time_per_party` | `deposition_metadata.time_per_party_json` (JSON) |
| `also_present` | `deposition_metadata.also_present_json` (JSON) |

---

## Commit trail

| Phase | Commit | Description |
|---|---|---|
| 0+1 | 7424f31 | Audit + schema_v9 + depo_meta_repo + 8 tests |
| 2 | 50b9f3c | /api/depo-meta GET+PUT + 9 tests |
| 3 | 497f127 | _build_metadata_for_job + 5 integration tests |
| 4 | 7ff093f | UI form on Stage 5 Certify screen |
