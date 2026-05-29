# DEPO-PRO — Field → Template Matrix (v1)

Companion to `DEPO-PRO_UFM_Data_Dictionary_v2.md`. Maps each in-scope field to
its **source parser**, whether the **UFM requires** it, and which **templates
consume** it. Scope: Texas civil freelance deposition. No federal.

**Template legend:** CAP = Title/Caption · APP = Appearances · IDX = Master Index
· EXI = Exhibit Index · CERT = Reporter's Certificate · SIG = Changes & Signature
· CNA = Certificate of Non-Appearance

**Source:** NOD · ORDER · JOB (job sheet) · RECORD (transcript parser) · PROFILE
· COMPUTED · POST

**Required:** Yes = UFM-mandatory (§ cited) · Cond = if applicable · Firm = above
manual floor (firm choice, optional per UFM)

| Field | Source | Required | Templates |
|---|---|---|---|
| cause_number | NOD | Yes §3.1d | CAP, CNA, CERT |
| case_number_label (CAUSE NO.) | NOD | Yes §3.1d | CAP, CNA |
| court_name + judicial_district | NOD | Yes §3.1a | CAP, CNA |
| county | NOD | Yes §3.1b | CAP, CNA, CERT |
| state | NOD | Yes §3.1b | CAP, CERT |
| plaintiff_full_name | NOD | Yes §3.1c | CAP, CNA |
| defendant_full_name | NOD/RECORD | Yes §3.1c | CAP, CNA |
| party.role / role_modifier / entity_type / fka_dba | NOD | Yes §3.1c | CAP |
| type_of_proceedings | NOD/RECORD | Yes §3.1f | CAP |
| deposition_date (day/month/year) | NOD/JOB | Yes §3.1g | CAP, CNA, CERT |
| actual_start_time | RECORD | Yes §3.1g | CAP |
| end_time | RECORD | Yes §3.1g | CAP |
| location_address (situs) | RECORD | Yes §3.1g | CAP, CNA |
| location_type | NOD/JOB | Cond | CAP |
| method_of_recording | RECORD | Yes §3.1i | CAP |
| volume_number (X of Y) | COMPUTED | Yes §3.1h | CAP |
| noticing_party | NOD | Yes | CAP, CNA |
| witness_name (deponent) | NOD/RECORD | Yes §3.10 | CAP, IDX, CERT, CNA |
| witness_type / title / employer / specialty | NOD/RECORD | Cond | CAP, IDX |
| witness_sworn / sworn_by | RECORD | Yes §3.10–3.11 | CERT |
| — Counsel (per attorney, both sides) — | | | |
| atty.full_name | NOD/RECORD | Yes §3.1j | APP, IDX, CERT |
| atty.last_name | COMPUTED | Yes | IDX, CERT |
| atty.honorific | RECORD | Cond | APP, IDX |
| atty.firm_name | NOD/RECORD | Yes §3.1j | APP |
| atty.street_address / city / state / zip | NOD | Yes §3.1j | APP |
| atty.phone | NOD | Firm (Official-only §3.1j) | APP |
| atty.email | NOD | Firm | APP |
| atty.bar_number (SBOT) | NOD | Firm (Official-only §3.1j) | APP |
| atty.party_represented | NOD/RECORD | Yes §3.1j | APP, IDX |
| atty.role (noticing/custodial/examining/defending) | NOD + RECORD | Yes | IDX, CERT |
| atty.appearance_type | RECORD | Cond | APP |
| — Reporter & firm — | | | |
| reporter_full_name | RECORD/PROFILE | Yes | CAP, CERT |
| reporter_csr_number | PROFILE | Yes | CERT |
| csr_expiration_date | PROFILE | Yes | CERT |
| reporter_credentials (CSR/RPR/CRR) | PROFILE | Cond | CERT |
| reporting_firm_name | NOD/PROFILE | Cond | CERT |
| firm_registration_no | PROFILE | Yes §3.4 (if firm) | CERT |
| firm_address/city/state/zip/phone | PROFILE | Cond | CERT |
| — Other attendees — | | | |
| videographer_name (+company/contact) | RECORD | Cond | APP |
| interpreter_name | RECORD | Cond §3.11 | APP, CERT(interp) |
| interpreter_language_pair | RECORD | Cond §3.12 | CERT(interp) |
| interpreter_sworn / cert_number | RECORD | Cond | CERT(interp) |
| — Exhibits / requests / certified Qs — | | | |
| exhibit_number / description / page | RECORD/COMPUTED | Cond | EXI, IDX |
| exhibit_bates_stamp | RECORD | Cond | EXI |
| requested_doc no/description/page | NOD/RECORD | Cond §3.24a-8 | EXI |
| certified_question no/description/page | RECORD | Cond §3.24a-7 | EXI |
| — Index page refs — | | | |
| app_page / stip_page / exam_page_1..4 / sig_page / cert_page | COMPUTED | Yes §3.24 | IDX |
| — Certificate / execution / billing — | | | |
| read_and_sign (waived/retained) | RECORD | Yes | SIG, CERT |
| custodial_attorney | NOD/JOB | Yes §3.4 | CERT |
| time_on_record (per attorney) | RECORD | Yes §3.4 / TRCP 203.2(e) | CERT |
| charges_amount | JOB/POST | Yes §3.4 | CERT |
| cost_party | NOD/JOB | Yes §3.4 | CERT |
| cert_execution date/county/state | POST | Yes | CERT |
| reporter_signature_file | PROFILE | Cond | CERT |
| transcript_page_count / volume_count | COMPUTED | Yes | CERT, CAP |
| — Errata (signature page) — | | | |
| errata page/line/original/corrected/reason/signed/date | POST | Cond §3.24a-5 | SIG |
| — CNA-specific — | | | |
| cna scheduled_for / statement_time | NOD/RECORD | Cond | CNA |
| cna attorneys_present | RECORD | Cond | CNA |
| cna reserved_right_to_redepose | RECORD | Cond | CNA |

## How to use this

1. **Parser contract:** every NOD-source row is a NOD-parser extraction target;
   every RECORD-source row is a transcript-parser target; PROFILE/COMPUTED/POST
   rows are never parsed. Build each parser to exactly its rows — nothing more.
2. **Template contract:** when building a template's population code, pull its
   column — every field marked with that template must have a resolved value or
   an explicit "missing required" before packaging.
3. **Validation seed:** the `Required = Yes` rows are the future `ufm_validation`
   ERROR set; `Cond` rows are WARNING-if-context-present.
