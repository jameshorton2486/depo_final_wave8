# DEPO-PRO — UFM Data Dictionary (v2)

**Status: AUTHORITATIVE** for Texas civil freelance deposition intake.
Reconciled against the **Texas Uniform Format Manual for Texas Reporters'
Records (07/01/2010 edition)** and the five civil-freelance templates in
`DepoPro_UFM_Transcript_Templates.docx`. Field requirements cite the governing
UFM section. Benitez (freelance deposition) is the worked example. Source of
truth for: schema updates, the NOD parser, the transcript parser, intake
redesign, the Word template engine, and the UFM packaging engine.

## Two extraction sources (ownership principle)

Every field is filled by exactly one of two parsers, by what the document can
physically know:

- **NOD / Order parser** (pre-proceeding paper) owns: Case, Parties, Attorneys,
  Law Firms, Court info, scheduled Session, Witness identity, Interpreter-required,
  Subpoena/requested documents. It is written *before* anyone speaks.
- **Transcript parser** (the record) owns: actual Appearances, actual start/end
  times, situs, speaker mapping, exhibits *marked*, certified questions,
  read-and-sign status, interpreter oath, videographer, time-on-record.

A NOD cannot supply on-record facts (examining attorney, actual times, who
appeared) — those come from the transcript or operator entry. This split is why
the keyterm cast was wrong: the NOD parser was asked for people only the record
knows.

## Deferred architecture decisions (tracked, NOT built this pass)

- **`deposition_orders` table + court-order parser** — real need (orders override
  NODs), but no order document exists in the test corpus. ORDER seam is reserved
  in the Source legend. Build when order documents are in hand.
- **Provenance write-guard** — a writer (NOD parser / transcript parser / AI) may
  only touch fields it owns; profile, certificate, and billing data are never
  parser-writable. Implement as a **write-boundary guard keyed on the Source
  column**, not as separate physical tables.
- **`ufm_validation` gating layer** — packaging-time (Wave 20) gate that blocks
  "Generate Transcript Package" on missing required fields. `missing_required_fields`
  already enumerates; formalize the gate at packaging, not intake.
- **Explicit attorney roles** — store `noticing` / `custodial` / `examining` /
  `defending` on `case_attorneys` rather than inferring. Folds into Phase 2.

**Official vs. Freelance:** Benitez is a **Freelance Reporter's Record**. Per
UFM §3.1, several title-page fields are **Official-record-only** (judge name,
attorney State Bar number, attorney phone). For freelance, the manual requires
only attorney *name, address, and party represented*. Where a template captures
more than the freelance minimum, it is marked **[above manual floor]** — a valid
firm choice, not a manual requirement.

**UFM section authority (key sections):**
§2.18–2.19 page headings · §3.1 title pages (field list) · §3.4 freelance
certificate · §3.5 certified questions · §3.10 witness/exam setup ·
§3.11–3.12 interpreter · §3.24 freelance index · §5 exhibits · §6.3 volumes.

**Scope of these five templates:** Texas civil freelance deposition —
Caption, Appearances, Master Index, Exhibit Index, Reporter's Certificate.
They do **not** cover: CNA / certificate of non-appearance, federal caption
layout, 30(b)(6) corporate-rep specifics, or multi-volume sets. Those may add
fields the manual specifies.

---

## How to read this

**Source** = where the value comes from. Reliability descends in this order
(an explicit document always beats an on-record statement, which always beats
inference):

| Source code | Meaning |
|---|---|
| `ORDER` | Court order compelling/scheduling the deposition (highest) |
| `NOD` | Notice of Deposition |
| `JOB` | Reporting-firm job sheet / scheduling worksheet |
| `RECORD` | Stated on the record (appearances, swearing, times) |
| `PROFILE` | Saved reporter/firm profile (not parsed — looked up) |
| `COMPUTED` | Derived downstream (pagination, indices) — not parsed |
| `POST` | Captured after the proceeding (errata, billing, execution) |

**Schema** = coverage in `ufm_schema_v1.md`:
✓ present · ◐ partial / derivable · ✗ missing · ⚡ computed (not a parse target)

**Intake-16** = whether the *current live 16-field intake* exposes it: yes / no.

---

## A. Case & Court  *(from NOD / Court Order)*

| Field | Benitez example | Source | Schema | Intake-16 |
|---|---|---|---|---|
| cause_number | `2025CI11923` | NOD | ✓ | yes |
| case_number_label | `CAUSE NO.` | NOD | ✓ | ◐ |
| jurisdiction_type | `texas_state` | NOD | ✓ | no |
| court_name | `District Court` | NOD | ◐ | ◐ |
| judicial_district | `408th` | NOD | ✓ | yes |
| county | `Bexar` | NOD | ✓ | yes |
| state | `Texas` | NOD | ✓ | yes |

## B. Parties & Caption  *(from NOD / Court Order)*

| Field | Benitez example | Source | Schema | Intake-16 |
|---|---|---|---|---|
| plaintiff_full_name | `LOLA PAVAN, INDIVIDUALLY AND AS NEXT FRIEND OF A.S., A MINOR` | NOD | ✓ | ◐ (flat caption) |
| defendant_full_name | `FRANK ECHEVARRIA BENITEZ D/B/A FEB TRANSPORT AND JUNIOR BENITEZ` | NOD/RECORD | ✓ | ◐ |
| party.role | `plaintiff` / `defendant` | NOD | ✓ | no |
| party.role_modifier | `as next friend of` | NOD | ✓ | no |
| party.entity_type | `individual` / `llc` | NOD | ✓ | no |
| party.fka_or_dba | `D/B/A FEB Transport` | NOD | ✓ | no |
| case_style_display | derived caption string | COMPUTED from parties[] | ◐ | yes |

> **Caption caveat:** NOD spells the co-defendant **"Yunior"**; the certified
> transcript caption and the witness say **"Junior."** Parser must flag, not
> silently pick. The on-record caption governs the printed transcript.

## C. Counsel / Appearances  *(NOD for parties-on-paper; RECORD for who appeared — these can differ)*

Repeated per attorney. **Both sides.** This is the block the current parser gets
most wrong — it harvests NOD signatories instead of on-record appearances.

| Field | Benitez example (examining) | Source | Schema | Intake-16 |
|---|---|---|---|---|
| atty.honorific | `Mr.` | RECORD | ✗ | no |
| atty.full_name | `Gabriel Narvaez` | RECORD | ✓ | no |
| atty.last_name | `Narvaez` | COMPUTED from full_name | ◐ | no |
| atty.bar_number (SBOT) | (Narvaez's not on record; Hill = `24057902`) | NOD | ✗ (bug: used in test, absent from table) | no |
| | *§3.1j: Official-record-only — [above manual floor] for freelance* | | | |
| atty.firm_name | `Hill Law Firm` | NOD/RECORD | ✓ | no |
| atty.street_address | `445 Recoleta Rd.` | NOD | ✓ | no |
| atty.city / state / zip | `San Antonio, TX 78216` | NOD | ✓ | no |
| atty.phone | `(210) 960-3939` | NOD | ◐ (on firm and atty) | no |
| atty.email | `justin@jahlawfirm.com` | NOD | ◐ | no |
| atty.party_represented | `PLAINTIFF` | NOD/RECORD | ✓ | no |
| atty.appearance_type | `Examining Counsel` | RECORD | ✗ | no |
| atty.is_lead | `true` | NOD | ✓ | no |

**Defense example (Benitez):** `Mr.` / `Chris Madrid` / `Goldman & Peterson, PLLC`
/ `10100 Reunion Place, Suite 800` / `San Antonio, TX 78216` / `(210) 340-9800`
/ `Mail@LJGLaw.com` / represents `DEFENDANTS` / SBOT `24096375`.

> **Noticing ≠ examining:** NOD names **Justin Hill** as signing/noticing
> attorney; **Gabriel Narvaez** (same firm) actually appeared and examined.
> Both are real and both are needed — Hill for the noticing/custodial role,
> Narvaez for appearances and the examination index.

## D. Session / Proceeding  *(JOB sheet for scheduled; RECORD for actual)*

| Field | Benitez example | Source | Schema | Intake-16 |
|---|---|---|---|---|
| type_of_proceedings (§3.1f, REQ) | `Oral and Videotaped Deposition` | NOD/RECORD | ◐ | no |
| deposition_date (§3.1g, REQ) | `April 16, 2026` | NOD/JOB | ✓ | yes |
| day_number / month / year | `16th` / `April` / `2026` | COMPUTED from date | ◐ | ◐ |
| scheduled_start | `10:00 a.m.` | JOB | ✓ | yes (but mislabeled as actual) |
| actual_start_time (§3.1g, REQ) | `10:03 a.m.` | RECORD | ✓ | no |
| end_time (§3.1g, REQ) | `11:49 a.m.` | RECORD | ✓ | no |
| location_address (situs, §3.1g, REQ) | `2900 Blue Wing Road, San Antonio, Texas` | RECORD | ✓ | ◐ (only "via Zoom") |
| location_type | `zoom` | NOD/JOB | ✓ | ◐ |
| method_of_recording (§3.1i, REQ) | `oral stenography` | RECORD | ✗ | no |
| volume_number (§3.1h, REQ) | `Volume 1 of 1` (no Roman numerals) | COMPUTED | ◐ | no |
| noticing_party | `Plaintiff` | NOD | ◐ | yes (was null) |
| service_type | `CR_plus_Zoom` (CR+Video+Zoom) | JOB | ✓ | no |
| read_and_sign (waived/retained) | `retained` (changes & signature page present) | NOD/JOB/RECORD | ✗ | no |
| witness_name (§3.10, REQ) | `Frank Echevarria Benitez` | NOD/RECORD | ✓ | yes |
| witness_type | `individual` | NOD | ✓ | no |
| witness_sworn (§3.10/§3.11, REQ) | `yes` (sworn through interpreter) | RECORD | ◐ | no |
| interpreter_required (§3.11, REQ if used) | `yes` | NOD/RECORD | ✓ | no |

## E. Reporter & Reporting Firm  *(JOB / PROFILE / RECORD / Certificate)*

| Field | Benitez example | Source | Schema | Intake-16 |
|---|---|---|---|---|
| reporter_full_name | `Miah Bardot` | RECORD/PROFILE | ✓ | yes |
| reporter_csr_number | `12129` | RECORD/PROFILE | ✓ | no (was null) |
| csr_expiration_date | `6-30-2026` | PROFILE/Cert | ✓ | no (was null) |
| reporter_credentials | `CSR` | PROFILE | ✓ | no |
| reporter_phone / email | `469 740-9603` / — | PROFILE | ✗ | no |
| reporting_firm_name | `SA Legal Solutions` | NOD/JOB | ✓ | no |
| firm_registration_no | (not in any supplied doc) | PROFILE | ✓ | no (was null) |
| firm_address/city/state/zip/phone | `3201 Cherry Ridge B 208-3, San Antonio, TX 78230, (210) 591-1791` | NOD/PROFILE | ✓ | no |

> Reporter's own address on the cert (`7234 Hovingham, San Antonio 78257`)
> differs from the firm address — reporter is likely an independent contractor
> for SA Legal Solutions. Firm-reg and firm address should come from a saved
> **firm profile**, not from the NOD or the cert page.

## F. Other Attendees  *(RECORD only — never on the NOD)*

| Field | Benitez example | Source | Schema | Intake-16 |
|---|---|---|---|---|
| videographer_name | `Mario Leal` | RECORD | ✗ (no table) | no |
| videographer_company / phone / email | — | RECORD/JOB | ✗ | no |
| interpreter_name | `Mauricio Dominguez` | RECORD | ◐ (table exists) | no |
| interpreter_language_pair | `Spanish ⇄ English` | RECORD | ◐ | no |
| interpreter_sworn | `yes` | RECORD | ◐ | no |
| interpreter_cert_number | — | RECORD | ✗ | no |
| other_attendee_name / role | (n/a) | RECORD | ✗ | no |

## G. Exhibits, Requested Docs, Certified Questions  *(RECORD / during proceeding)*

| Field | Benitez example | Source | Schema | Intake-16 |
|---|---|---|---|---|
| exhibit_number | `(None offered)` | RECORD | ✓ | no |
| exhibit_description | — | RECORD | ✓ | no |
| exhibit_page_reference | — | COMPUTED | ✓ | no |
| exhibit_bates_stamp (range) | e.g. `BATES_0001–0012` | RECORD/exhibit doc | ✗ | no |
| exhibit_offered_by / admitted | — | RECORD | ◐ | no |
| requested_doc_no / description / page (duces tecum) | (none) | NOD/RECORD | ✗ | no |
| certified_question_no / description / page | (none) | RECORD | ✗ | no |

## H. Index Page References  *(COMPUTED — pagination/Index Engine, NOT parsed)*

`appearances_page`, `stipulations_page`, `examination_page_1..4`,
`signature_page`, `certificate_page`, `exhibit_page_n`. These come from Wave 19/20
pagination, not from any input document. Listed here so they aren't mistaken for
parse targets.

## I. Certificate / Execution / Billing  *(POST / JOB / Certificate)*

| Field | Benitez example | Source | Schema | Intake-16 |
|---|---|---|---|---|
| custodial_attorney | `Justin Hill / Hill Law Firm` | NOD/JOB | ◐ | no (was null) |
| time_on_record (per atty) | `Narvaez 01:35` · `Madrid 00:00` | RECORD/Cert | ✓ | no |
| def_hours_or_reserved | `00:00` | RECORD | ◐ | no |
| charges_amount | (blank on cert) | JOB/POST | ✗ | no |
| cost_party | `Plaintiffs` | NOD/JOB | ✗ | no |
| cert_execution_day/month/year | (blank — filled at cert) | POST | ◐ | no |
| county_of_execution / state_of_execution | (blank) | POST | ✗ | no |
| transcript_page_count / volume_count | `48` / `1` | COMPUTED | ◐ | no |
| reporter_signature_file | — | PROFILE | ✗ | no |

## J. Errata / Changes & Signature  *(POST — from witness)*

| Field | Example | Source | Schema | Intake-16 |
|---|---|---|---|---|
| errata.page / line | `12 / 5` | POST | ✗ (no table) | no |
| errata.original_text / corrected_text | `yes` → `no` | POST | ✗ | no |
| errata.reason | `transcription error` | POST | ✗ | no |
| errata.witness_signed / signature_date | `yes` / `2026-05-15` | POST | ✗ | no |

---

## Record-type scope boundary

The dictionary above targets **Texas civil freelance depositions** — the entire
current test corpus (Benitez, Shaw, Filpi, Embry, Yean). Two record-type
variations are **in scope** because they are freelance-deposition outcomes:

- **Certificate of Non-Appearance** — witness fails to appear; fields:
  scheduled-for datetime, attorneys present, statement time, location,
  reserved-right-to-redepose. Modeled as `non_appearance_events`.
- **Interpreted / signature-waived certificate** — interpreter source-language
  + `read_and_sign = waived`.

The following are **deferred profiles — do NOT build into the first parser
pass** (consistent with roadmap Q-PROFILE "Texas-UFM-only for now"):

- **Federal** caption + FRCP 30(f)(1) certificate (different jurisdiction).
- **Texas criminal** co-caption, multi-cause, "THE STATE OF TEXAS" as plaintiff.
- **Official trial reporter's record** (`REPORTER'S RECORD / VOLUME X OF Y`)
  — distinct from the freelance `DEPOSITION OF [WITNESS]` title style (§3.1).

Keep the export-profile seam clean so these can be added later as named
profiles, the same way the Geometry Layer defers California/arbitration.

---



Marked **[UFM-REQ]** where the manual makes the field *mandatory* (not optional):

1. `method_of_recording` — machine/manual shorthand or oral stenography **[UFM-REQ §3.1i]**
2. `type_of_proceedings` **[UFM-REQ §3.1f]** and `volume_number` "X of Y" **[UFM-REQ §3.1h]**
3. `cost_party` (party responsible for costs) **[UFM-REQ §3.4]**
4. `time_on_record` per party **[UFM-REQ §3.4 / TRCP 203.2(e)]** *(table exists in schema ✓)*
5. `firm_registration_no` **[UFM-REQ §3.4 if freelance firm]** *(field exists ✓ — just unpopulated)*
6. Attorney `honorific` and `appearance_type` (examining / defending / of counsel)
7. Attorney `bar_number` — used in canonical test but absent from table *(Official-only per §3.1j)*
8. **Videographer** — no table at all
9. Interpreter `cert_number` *(table exists but thin; interpreter handling is §3.11–3.12)*
10. Subpoena **duces tecum / requested information** **[UFM-REQ in index §3.24a-8 if applicable]**
11. **Certified questions** **[UFM-REQ in index §3.24a-7 if applicable]** — Benitez has live candidates
12. `read_and_sign` waived/retained status
13. **Certificate execution metadata** — execution date/county/state, signature file
14. **Errata / changes-and-signature** line items (no table) **[index §3.24a-5]**

> **Manual scope confirmation:** The 07/01/2010 UFM adds **no field categories
> beyond what these five templates already imply.** It does, however, define a
> separate **Certificate of Non-Appearance** path (referenced via TRCP 203) and
> distinct rules for **non-stenographic** records (§3.7) and **rough drafts**
> (§4). Benitez needs none of those, but your template set already includes a CNA
> template — that page type has its own field subset (scheduled-for datetime,
> attorneys present, statement time, reserved-right-to-redepose), already modeled
> in `ufm_schema_v1` as `non_appearance_events`.

## The decision this forces

The current intake captures **16 fields**. These templates need roughly **50**
parsed fields (plus computed page references and post-proceeding data). Going
from 16 → ~50 is a real expansion, not a tweak. The good news: `ufm_schema_v1`
already models ~75–80% of it — the work is mostly (a) exposing that richness in
intake and (b) closing the 11 gaps above. That is a conscious scope decision to
make before any parser is built.
