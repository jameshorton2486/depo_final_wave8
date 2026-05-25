# AUDIT_CERT.md — Certificate & Caption Fields Audit

## Baseline: 442 passed, 1 skipped

## All [BRACKETED] fields in `backend/packaging/admin_pages.py`

### Caption page (`build_caption_page`)

| metadata_key | Placeholder | Type | Entity | Storage status |
|---|---|---|---|---|
| `cause_number` | `[CAUSE NUMBER]` | str | Case | EXISTING — `cases.case_number_value` |
| `plaintiff_names` | `[PLAINTIFF NAME(S)]` | str | Case/Party | EXISTING — join `parties` WHERE role='plaintiff' |
| `defendant_names` | `[DEFENDANT NAME(S)]` | str | Case/Party | EXISTING — join `parties` WHERE role='defendant' |
| `county` | `[COUNTY]` | str | Case | EXISTING — `cases.county` |
| `judicial_district` | `[JUDICIAL DISTRICT]` | str | Case | EXISTING — `cases.judicial_district` |
| `witness_name` | `[WITNESS NAME]` | str | Session | EXISTING — `sessions.witness_name` |
| `proceedings_date` | `[DATE OF DEPOSITION]` | str | Session | EXISTING — derived from `sessions.scheduled_at` |
| `volume` | `1` (default) | str | Job | NEW — `deposition_metadata.volume` |
| `party_at_instance` | `[PARTY]` | str | Session | EXISTING — `sessions.requesting_party_name` |
| `start_time` | `[START TIME]` | str | Session | EXISTING — derived from `sessions.scheduled_at` |
| `end_time` | `[END TIME]` | str | Session | EXISTING — derived from `sessions.scheduled_end_at` |
| `deposition_method` | `[METHOD]` | str | Session | EXISTING — mapped from `sessions.location_type` |
| `reporter_name` | `[REPORTER NAME]` | str | Reporter | EXISTING — `reporters.full_name` |
| `proceedings_month` | `[MONTH]` | str | Session | EXISTING — derived from `sessions.scheduled_at` |
| `proceedings_day` | `[DAY]` | str | Session | EXISTING — derived from `sessions.scheduled_at` |
| `proceedings_year` | `[YEAR]` | str | Session | EXISTING — derived from `sessions.scheduled_at` |

Also auto-populated (used in validation, not directly bracketed):
- `caption` ← `cases.caption_full`
- `court` ← derived from `cases.judicial_district` + `cases.county` + `cases.state`

### Certificate page (`build_certificate_page`)

| metadata_key | Placeholder | Type | Entity | Storage status |
|---|---|---|---|---|
| `reporter_name` | `[REPORTER NAME]` | str | Reporter | EXISTING — `reporters.full_name` |
| `reporter_csr_number` | `[CSR NUMBER]` | str | Reporter | EXISTING — `reporters.csr_number` |
| `witness_name` | `[WITNESS NAME]` | str | Session | EXISTING — `sessions.witness_name` |
| `proceedings_date` | `[DATE]` | str | Session | EXISTING — derived from `sessions.scheduled_at` |
| `examination_disposition` | `[waived/retained]` | str | Job | NEW — `deposition_metadata.examination_disposition` |
| `custodial_attorney` | `[CUSTODIAL ATTORNEY]` | str | Session | EXISTING — `sessions.custodial_attorney_name` |
| `officer_charges_amount` | `[AMOUNT]` | str | Job | NEW — `deposition_metadata.officer_charges_amount` |
| `charges_party` | `[PARTY]` | str | Job | NEW — `deposition_metadata.charges_party` |
| `certificate_service_date` | `[DATE]` | str | Job | NEW — `deposition_metadata.certificate_service_date` |
| `certified_day` | `[DAY]` | str | Computed | AUTO — `datetime.now().day` (ordinal) |
| `certified_month` | `[MONTH]` | str | Computed | AUTO — `datetime.now().strftime('%B')` |
| `certified_year` | `[YEAR]` | str | Computed | AUTO — `datetime.now().year` |
| `reporter_csr_expiration` | `[##/##/####]` | str | Reporter | EXISTING — `reporters.csr_expiration` |
| `firm_registration_no` | `[####]` | str | Reporter | EXISTING — `reporters.firm_registration_number` |
| `firm_address` | `[FIRM ADDRESS]` | str | Firm office | EXISTING — `reporting_firm_offices.address_line` |
| `firm_city_state_zip` | `[CITY, STATE, ZIP]` | str | Firm office | EXISTING — `reporting_firm_offices.(city, state, zip)` |
| `time_per_party` (list) | `[TIME USED PER PARTY]` | list[{party,duration}] | Job | NEW — `deposition_metadata.time_per_party_json` |
| `counsel_of_record` (list) | `[COUNSEL OF RECORD]` | list[{name,role}] | Case | EXISTING — join `case_attorneys`, `attorneys`, `parties` |

### Appearances page (`build_appearances_page`)

| metadata_key | Entity | Storage status |
|---|---|---|
| `appearances` (list) | Case | EXISTING — join `case_attorneys`, `attorneys`, `parties` |
| `also_present` (list) | Job | NEW — `deposition_metadata.also_present_json` |

## New storage required: `deposition_metadata` table (schema_v9)

All job-specific certificate fields that have no existing home:

| Column | Type | Maps to metadata_key |
|---|---|---|
| `job_id` | TEXT PK | (FK to transcript_jobs) |
| `volume` | TEXT DEFAULT '1' | `volume` |
| `examination_disposition` | TEXT | `examination_disposition` |
| `officer_charges_amount` | TEXT | `officer_charges_amount` |
| `charges_party` | TEXT | `charges_party` |
| `certificate_service_date` | TEXT | `certificate_service_date` |
| `time_per_party_json` | TEXT (JSON) | `time_per_party` |
| `also_present_json` | TEXT (JSON) | `also_present` |

## Metadata auto-population path

At `assemble` and `certify` time, `_build_metadata_for_job(job_id, override)` in
`backend/api/packaging.py` pulls from:

1. `transcript_jobs` → get `session_id`, `case_id`
2. `cases` → `cause_number`, `caption`, `court`, `county`, `judicial_district`
3. `parties` → `plaintiff_names`, `defendant_names`
4. `case_attorneys` + `attorneys` + `parties` → `appearances`, `counsel_of_record`
5. `sessions` → `witness_name`, `party_at_instance`, `custodial_attorney`,
   `proceedings_date/month/day/year`, `start_time`, `end_time`, `deposition_method`
6. `reporters` → `reporter_name`, `reporter_csr_number`, `reporter_csr_expiration`,
   `firm_registration_no`
7. `reporting_firm_offices` → `firm_address`, `firm_city_state_zip`
8. `deposition_metadata` → `volume`, `examination_disposition`, `officer_charges_amount`,
   `charges_party`, `certificate_service_date`, `time_per_party`, `also_present`
9. Computed → `certified_day`, `certified_month`, `certified_year`
10. Caller `override` dict wins on any key conflict

## Data ownership decisions

- `examination_disposition` → job-level: determined at deposition close, reporter enters it
- `officer_charges_amount` / `charges_party` → job-level: reporter's fee, set after transcript
- `certificate_service_date` → job-level: date certificate copy was served on all parties
- `time_per_party` → job-level: each attorney's time usage, recorded by reporter
- `also_present` → job-level: non-attorney attendees, varies per deposition
- `volume` → job-level: volume number for this transcript file

## Phase completion tracking

- [x] Phase 0 — Audit
- [x] Phase 1 — Data model (schema_v9 + depo_meta_repo + tests)
- [x] Phase 2 — API (depo_meta router + tests)
- [x] Phase 3 — Wire into packaging + no-placeholder test
- [x] Phase 4 — UI form on Stage 5 Certify screen
