# checkpoint_A.md — Phase A (Topology · Data Lineage · NOD Parser)

> **How this was produced.** This Phase A was run against the current repo tree
> in `C:\Users\james\PycharmProjects\PythonProject\depo_final_wave8`, by
> reading the live code and the live DEPO-PRO blueprint docs. It is read-only:
> no code, template, test, or repo-data changes were made as part of the audit.
> Findings below are tagged **[CONFIRMED]** when directly established from the
> live code/docs and **[DRIFT]** when the live code diverges from
> `docs/DEPO-PRO_UFM_Data_Dictionary_v2.md` or
> `docs/DEPO-PRO_Field_Template_Matrix.md`.

---

## A1. Module topology (live tree)

**Packaging is the single assembly/index/certificate authority [CONFIRMED]**
- `backend/packaging/packager.py` is the authoritative assembly seam.
  `SECTION_ORDER` is:
  `caption → appearances → chronological_index → witness_index → exhibit_index → BODY_MARKER → corrections_signature → certificate`.
- `backend/packaging/admin_pages.py` builds the administrative pages listed in
  `SECTION_ORDER`.
- `backend/packaging/indices.py` generates the chronological, witness, and
  exhibit indexes from packaged/paginated transcript state.
- `backend/api/packaging.py` is the bridge from persisted case/session/reporter/
  deposition metadata into `assemble_package(...)`.

**Export / render surfaces are layered, not duplicate file writers [CONFIRMED]**
- `backend/stage_s/renderer.py` performs structural render.
- `backend/transcript/render.py` builds transcript-oriented line structures.
- `backend/transcript/export_render.py` converts transcript state plus layout
  into an `ExportDocument`.
- `backend/export/export_service.py` and
  `backend/export/{docx_writer,pdf_writer,rtf_writer,txt_writer}.py` write the
  final export artifacts.
- `backend/api/transcripts.py` export endpoints route the final output path
  through `render_export_with_layout(...)` and then `export_service.export_document(...)`.
- **Duplicate-engine determination:** the current tree shows layered render
  stages feeding a single export-writing surface, not parallel certified DOCX/PDF
  writers.

**Geometry / pagination [CONFIRMED]**
- `backend/geometry/profile.py` sets:
  - left margin = `1800` twips (`1.25"`)
  - right margin = `1080` twips (`0.75"`)
  - text area = exactly `6.5"`
  - `lines_per_page = 25`
  - `chars_per_line_min = 56`
  - `chars_per_line_max = 63`
  - `meets_text_area_minimum()` present
- `backend/geometry/engine.py` and `backend/pagination/` consume the profile in
  the render/export path.

**NOD parser [CONFIRMED]**
- `backend/services/nod_parser/orchestrator.py`
- `backend/services/nod_parser/type_a_form.py`
- `backend/services/nod_parser/type_b_pleading.py`
- `backend/services/nod_parser/intelligence.py`
- `backend/services/nod_parser/pdf_text.py`

**Persistence surfaces actually used by intake/packaging [CONFIRMED]**
- `backend/services/intake_store.py` persists Stage 1 intake state and builds the
  canonical workspace/session packets.
- `backend/db/repository.py` persists `cases`, `sessions`, and `reporters`.
- `backend/db/depo_meta_repo.py` persists `deposition_metadata`.
- `backend/api/depo_meta.py` exposes the deposition-metadata API used by the UI.

**Blueprint docs consumed in this live run [CONFIRMED]**
- `docs/DEPO-PRO_UFM_Data_Dictionary_v2.md`
- `docs/DEPO-PRO_Field_Template_Matrix.md`

---

## A2. Blueprint reconciliation (live docs vs live code)

**The v2 blueprint docs are authoritative inputs, but the live code does not yet
match them end to end [DRIFT]**

1. **Structured parties / attorneys / case-attorney relationships are defined in
   the blueprint and present in schema, but not wired in the live intake write
   path.**
   - The dictionary and matrix assume party/attorney/caption population beyond
     the flat intake subset.
   - The live intake path in `backend/services/intake_store.py` only builds
     `CaseIdentity`, `ReporterCredentials`, and `DepositionSession`.
   - No application write path was found for `parties`, `attorneys`, or
     `case_attorneys`.

2. **CNA and interpreter pages exist in the matrix as expected outputs, but no
   live builder exists.**
   - No `build_*` implementation for Certificate of Non-Appearance or an
     interpreter certificate was found in `backend/packaging/admin_pages.py`.
   - Neither surface appears in `SECTION_ORDER`.

3. **The dictionary’s field ownership split is richer than the current live
   packaging feed.**
   - The dictionary distinguishes NOD-owned scheduled/session identity fields
     from transcript-owned actual on-record facts.
   - The live packaging metadata bridge still pulls core timing/location data
     from `sessions.scheduled_at`, `sessions.scheduled_end_at`,
     `sessions.location_address`, and `sessions.location_type`.
   - That means the current administrative-page package is still driven largely
     by session scheduling fields rather than a transcript-owned actual-record
     lineage.

4. **Template Population Matrix must extend the existing matrix, not replace it
   [CONFIRMED].**
   - This checkpoint therefore logs drift rather than regenerating a competing
     matrix from scratch.

---

## A3. Data lineage per administrative page

### Caption page

**Caption lineage is substantially intact for the flat intake subset [CONFIRMED]**

`Source document → parser/intake → persistence → packaging metadata → builder → output`

- `cause_number`
  - source: NOD / intake
  - parser/intake: `ufmCause`
  - persistence: `cases.case_number_value`
  - packaging bridge: `_build_metadata_for_job(...)`
  - builder: `build_caption_page(...)`
- `caption`
  - source: NOD / intake
  - parser/intake: `ufmStyle`
  - persistence: `cases.caption_full`
  - builder: `build_caption_page(...)`
- `county`
  - source: NOD / intake
  - parser/intake: `ufmCounty`
  - persistence: `cases.county`
  - builder: `build_caption_page(...)`
- `judicial_district` / court text
  - source: NOD / intake
  - parser/intake: `ufmCourt`
  - persistence: `cases.judicial_district`
  - builder composes court text from stored fields
- `witness_name`
  - source: NOD / intake
  - parser/intake: `ufmWitness`
  - persistence: `sessions.witness_name`
  - builder: `build_caption_page(...)`
- `proceedings_date`, `start_time`, `end_time`
  - source: NOD / intake or operator session edits
  - persistence: `sessions.scheduled_at`, `sessions.scheduled_end_at`
  - builder: `build_caption_page(...)`
- `party_at_instance`
  - source: NOD / intake
  - persistence: `sessions.requesting_party_name`
  - builder: `build_caption_page(...)`
- `volume`
  - source: operator / depo-meta
  - persistence: `deposition_metadata.volume`
  - builder: `build_caption_page(...)`

**Drift / break notes**
- `plaintiff_names` / `defendant_names` are read from `parties` via
  `_populate_party_names(...)`, with caption parsing/intake fallback when absent.
- **[DRIFT]** The schema and builders anticipate normalized `parties`, but the
  live intake write path does not populate `parties`.

### Appearances page

**Appearances page has a confirmed relational-persistence break [CONFIRMED]**

- Builder path:
  - `backend/api/packaging.py::_populate_appearances(case_id)` reads
    `case_attorneys` joined to `attorneys` and `parties`.
  - fallback path:
    `_populate_appearances_from_intake(parser_meta)` reads
    `parser_metadata.appearances` from intake JSON.
- Parser path:
  - `backend/services/nod_parser/type_b_pleading.py::extract_appearances(...)`
    emits structured attorney appearance rows.
  - `backend/services/nod_parser/orchestrator.py` places them in
    `parsed.appearances`, `to_frontend_dict()`, and canonical participants.
- Persistence path:
  - **No application write path was found that persists parsed appearances into
    `attorneys` / `case_attorneys`.**
  - `backend/db/repository.py` writes `cases`, `sessions`, and `reporters`, but
    no create/update path for `attorneys` or `case_attorneys` was found.
- Output effect:
  - The page can render from the intake fallback, but the normalized relational
    path appears unwired.

**Phase A finding**
- `appearances → case_attorneys` is not merely unconfirmed; it is a live lineage
  break until a write path is added.

### Chronological / witness / exhibit indexes

**Indexes are transcript-state driven, not intake-metadata driven [CONFIRMED]**

- Builder path:
  - `backend/packaging/indices.py::generate_indices(...)`
  - `backend/packaging/admin_pages.py` renders the index pages from the
    generated index models.
- Input path:
  - paginated/rendered transcript document
  - exhibit events from snapshot state
- Output shape:
  - three indexes are built: chronological, witness, exhibit
  - exhibit index is a simple `description → page` lineage, not an
    offered/admitted scheme

**Drift note**
- This aligns with the older checkpoint’s exhibit-index observation and matches
  the current code: no separate OFFERED/ADMITTED columns were found in the live
  generator.

### Corrections / signature page

**Corrections/signature page exists but is minimal [CONFIRMED]**

- `backend/packaging/admin_pages.py::build_corrections_signature_page(...)`
  renders a short page keyed primarily by `witness_name`.
- The current builder does **not** show a full errata grid and does **not** emit
  a notary jurat in the live implementation.

**Phase A finding**
- This page is implemented, but it is materially thinner than the fuller
  signature/changes expectations implied by the blueprint/matrix.

### Certificate page

**Certificate is substantially more complete in live code than a template-only
reading would suggest [CONFIRMED]**

The live `build_certificate_page(...)` includes:
- (a) sworn / true record language
- (b) examination/signature disposition language
- (d) original delivered language
- (e) time used per party language
- (f) officer charges language
- counsel-of-record block
- (g) copy served on all parties language
- disinterest statement
- package identity / hash binding lines

**Data lineage for certificate inputs [CONFIRMED]**
- reporter identity / credentials
  - persistence: `reporters`
- reporting office / firm contact
  - persistence: `reporting_firm_offices`
- officer charges, charges party, service date, examination disposition,
  time-per-party, volume
  - persistence: `deposition_metadata`
  - API: `backend/api/depo_meta.py`
  - repo: `backend/db/depo_meta_repo.py`
  - UI write path: `frontend/assets/js/screens/stage_5.js`
- counsel of record
  - persistence expectation: `case_attorneys`
  - current fallback risk: placeholder if relational rows are absent

**Resolved Phase A questions**
- **`depo_meta` UI/API write path exists [CONFIRMED].**
  - Stage 5 certificate fields are loaded/saved through
    `/api/depo-meta/jobs/{jobId}` and persisted by `upsert_depo_meta(...)`.
- **Counsel block remains dependent on the missing `case_attorneys` write path
  [CONFIRMED lineage break].**

**Remaining certificate gap**
- **Clause (c) is still absent in explicit form [CONFIRMED].**
  - No clear “changes, if any, are attached” clause was found in the live
    `build_certificate_page(...)`.
  - This is a narrower and more accurate finding than the earlier template-level
    claim that multiple TRCP 203.2 clauses were missing.

### CNA and interpreter pages

**CNA and interpreter pages are unimplemented in the live package builder [CONFIRMED]**
- No CNA page builder found
- No interpreter certificate page builder found
- Neither page appears in `SECTION_ORDER`

---

## A4. NOD parser field mapping (live tree)

**Parser output surfaces [CONFIRMED]**
- `ParsedNOD.to_frontend_dict()` emits:
  - `fields`
  - `metadata` including `detected_types`, `jurisdiction_type`,
    `location_type`, `additional_sessions`, `field_sources`, `warnings`
  - `appearances`
  - `keyterms`
  - `speaker_hints`
  - `deepgram_config`
- `ParsedNOD.to_canonical()` emits:
  - `identity`
  - `session`
  - `reporter`
  - `participants`
  - `keyterms`

**Handler split [CONFIRMED]**
- `type_a_form.py` extracts worksheet-style/session cover data
- `type_b_pleading.py` extracts pleading/caption/cause/court/county data
- `orchestrator.py` merges them, with Type B taking precedence for canonical
  case fields and Type A filling gaps

**Field-by-field mapping**

| UFM / admin-page field | NOD source | Parser owner | Persistence destination | Packaging / output destination | Phase A status |
|---|---|---|---|---|---|
| cause number | pleading caption/body | `type_b_pleading` | `cases.case_number_value` | caption page | [CONFIRMED] |
| case style / caption | pleading caption, worksheet | `type_b_pleading` + Type A fallback | `cases.caption_full` | caption page | [CONFIRMED] |
| county | pleading caption/body | `type_b_pleading` | `cases.county` | caption page | [CONFIRMED] |
| judicial district / court | pleading caption/body | `type_b_pleading` | `cases.judicial_district` | caption page | [CONFIRMED] |
| witness / deponent | worksheet / notice body | Type A / Type B | `sessions.witness_name` | caption, corrections page | [CONFIRMED] |
| scheduled date / start time | worksheet / notice body | Type A / Type B | `sessions.scheduled_at` | caption page | [CONFIRMED] |
| scheduled end time | usually not in NOD | none / operator entry | `sessions.scheduled_end_at` | caption page | [CONFIRMED external source] |
| requesting party / custodial attorney | worksheet / notice body | parser | `sessions.requesting_party_name` and related flat fields | caption metadata only | [CONFIRMED flat-only] |
| appearances / attorneys | signature block / attorney lines | `type_b_pleading.extract_appearances()` | expected: `attorneys` / `case_attorneys` | appearances page, certificate counsel block | **[CONFIRMED BREAK]** no write path found |
| parties | caption parsing / canonical participants | parser canonical model | expected: `parties` | caption name population | **[DRIFT]** normalized persistence not wired |
| reporter credentials | not a NOD-owned field | reporter profile / manual | `reporters` | certificate | [CONFIRMED external source] |
| charges / service date / time used | not a NOD-owned field | depo-meta UI/API | `deposition_metadata` | certificate | [CONFIRMED external source] |

**Meaning of the live mapping**
- The parser itself emits richer structured data than the current relational
  persistence path stores.
- The flat 16-ish intake/session/case subset persists cleanly.
- Structured appearances / attorney relationships do not currently survive into
  the normalized packaging read path.

---

## A5. Geometry and UFM-specific compliance observations

1. **Text area minimum is satisfied [CONFIRMED].**
   - The live profile computes exactly `6.5"` text width.

2. **25 lines/page and 56–63 chars/line are declared in the live profile [CONFIRMED].**

3. **Tab-stop configuration diverges from the prompt’s three-tab UFM baseline [DRIFT].**
   - The live profile exposes five tab stops:
     `(360, 900, 1440, 2160, 2880)`.
   - The Phase A prompt baseline emphasizes the UFM-required 5th/10th/15th-space
     stops.
   - This is not an automatic failure, but it is a live geometry/spec divergence
     that must be reconciled in the compliance matrix rather than silently
     ignored.

4. **Phase A does not by itself prove the render path enforces every declared
   geometry property on final output.**
   - That remains a Phase B sample-output validation question.

---

## A6. Ranked Phase A findings

1. **S2 — Certificate clause gap is narrower than previously thought, but real.**
   - Live certificate builder is substantially TRCP 203.2-complete.
   - The remaining explicit clause gap is **(c) changes attached**.

2. **S2/S3 — `appearances → attorneys/case_attorneys` is a confirmed lineage break.**
   - Parser emits appearances.
   - Packaging reads `case_attorneys`.
   - No application persistence path currently bridges those two surfaces.

3. **S3 — CNA and interpreter administrative pages are not built.**
   - Expected by blueprint/matrix; absent from live packager.

4. **S3 — Corrections/signature page exists but is materially thinner than the
   blueprint/matrix expectation.**

5. **S1 — Geometry text width baseline is satisfied, but tab-stop reconciliation
   remains open.**

6. **S3/S5 — Blueprint docs overstate current normalized data lineage.**
   - The docs anticipate richer structured persistence than the live intake path
     actually writes.

---

## A7. Gate to Phase B

Phase B should proceed with these Phase A conclusions locked:

- Packaging is the single assembly authority.
- Export/render surfaces are layered, not duplicate file-writing engines.
- The certificate problem is **data lineage + one explicit clause gap**, not a
  wholesale certificate rewrite.
- The major structural lineage break is normalized appearance/attorney
  persistence.
- CNA and interpreter pages are genuinely unimplemented.
- The live run must carry these drift items into the compliance and population
  matrices rather than flattening them into template-only findings.

**Phase B preconditions**
- Generate outputs through the live export path only.
- Use the existing matrix/dictionary as reconciliation inputs, not as assumed
  truth.
- If certified Myler depos are available locally, use them for the level-3
  comparison; otherwise mark that comparison blocked and proceed with the rest of
  Phase B.
