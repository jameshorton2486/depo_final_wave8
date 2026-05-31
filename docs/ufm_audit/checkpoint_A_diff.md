# checkpoint_A_diff.md — Phase A comparison (older reference vs live-tree audit)

> Purpose: reconcile the older snapshot-based `checkpoint_A.md` reference
> against the independent live-tree Phase A audit now saved at
> `docs/ufm_audit/checkpoint_A.md`.

---

## Agree

These findings were stable across both passes and can be treated as the Phase A
structural spine.

1. **Packaging remains the single assembly authority.**
   - Both passes found `backend/packaging/packager.py` as the authoritative
     assembly seam and the same `SECTION_ORDER`:
     `caption → appearances → chronological_index → witness_index → exhibit_index → BODY_MARKER → corrections_signature → certificate`.

2. **The packaging metadata bridge still runs through `_build_metadata_for_job(...)`.**
   - Both passes identified `backend/api/packaging.py` as the seam from stored
     case/session/reporter/deposition metadata into `assemble_package(...)`.

3. **Caption lineage is intact for the flat intake subset.**
   - Both passes traced `ufmCause`/`ufmStyle`/`ufmCounty`/`ufmWitness`/date/time
     into `cases` / `sessions`, then through packaging into the caption page.

4. **Exhibit index format is the simple `Description … Page` shape.**
   - Both passes found `backend/packaging/indices.py` and the exhibit-index page
     builder using description-to-page lineage rather than an OFFERED/ADMITTED
     scheme.

5. **The live certificate builder emits most of TRCP 203.2.**
   - Both passes agreed that `backend/packaging/admin_pages.py::build_certificate_page(...)`
     emits (a), (b), (d), (e), (f), and (g), plus the disinterest/package
     binding language.

6. **CNA and interpreter pages are absent from the live packager.**
   - Both passes found no CNA page builder and no interpreter certificate page
     builder in `backend/packaging/admin_pages.py`, and neither surface appears
     in `SECTION_ORDER`.

---

## Newly resolved in the live-tree audit

These were open or only inferred in the older reference and are now resolved by
direct reading of the live tree.

1. **`depo_meta` UI write-path is confirmed.**
   - Resolved surface:
     - `backend/api/depo_meta.py`
     - `backend/db/depo_meta_repo.py`
     - `frontend/assets/js/screens/stage_5.js`
   - Live-tree conclusion:
     - Stage 5 certificate fields are loaded and saved through the `depo_meta`
       API, so certificate fields like examination disposition, volume, charges,
       service date, and time-per-party do have a UI/API persistence path.
   - This converts the older `[VERIFY]` on “does a UI drive the depo_meta API?”
     into a confirmed yes.

2. **Duplicate-render question is resolved as layered rendering with one export-writing surface.**
   - Resolved surface:
     - `backend/api/transcripts.py`
     - `backend/transcript/export_render.py`
     - `backend/export/export_service.py`
     - `backend/export/{docx_writer,pdf_writer,rtf_writer,txt_writer}.py`
   - Live-tree conclusion:
     - `stage_s/renderer.py`, `transcript/render.py`, and
       `transcript/export_render.py` are layered render stages.
     - Final file output flows through `backend/export/export_service.py` and the
       export writers rather than through competing certified DOCX/PDF writers.

3. **Blueprint-doc reconciliation is now in scope and completed.**
   - Resolved surface:
     - `docs/DEPO-PRO_UFM_Data_Dictionary_v2.md`
     - `docs/DEPO-PRO_Field_Template_Matrix.md`
   - Live-tree conclusion:
     - The older reference could not reconcile against these docs because they
       were absent from the older snapshot.
     - The live run confirmed several doc-to-code drifts that now belong in the
       compliance and population matrices rather than being left implicit.

---

## Drift / confirmed remediation items

These are the live issues that should drive Phase C planning and later build
passes.

1. **`appearances → case_attorneys` is a confirmed lineage break.**
   - Surfaces:
     - parser emit: `backend/services/nod_parser/type_b_pleading.py`
     - parser bridge: `backend/services/nod_parser/orchestrator.py`
     - packaging read: `backend/api/packaging.py`
     - missing normalized write owner: `backend/services/intake_store.py` /
       `backend/db/repository.py`
   - Live-tree finding:
     - The parser emits structured appearances.
     - Packaging reads normalized `case_attorneys`.
     - No application write path was found persisting parsed appearances into
       `attorneys` / `case_attorneys`.
   - Impact:
     - breaks the normalized appearances page lineage
     - breaks the certificate counsel-of-record block unless intake fallback
       happens to fill it

2. **Geometry has a live tab-stop drift against the prompt/spec baseline.**
   - Surface:
     - `backend/geometry/profile.py`
   - Live-tree finding:
     - Text width is compliant at `6.5"`, but the profile exposes a five-tab
       system rather than only the three UFM-required 5th/10th/15th-space stops
       emphasized by the audit prompt.
   - Impact:
     - belongs in the compliance matrix as a geometry/spec reconciliation item,
       not as a silent “geometry closed” conclusion

3. **Certificate clause (c) remains the narrow explicit content gap.**
   - Surface:
     - `backend/packaging/admin_pages.py::build_certificate_page(...)`
   - Live-tree finding:
     - The builder is substantially complete, but no explicit “changes, if any,
       are attached” clause was found.
   - Impact:
     - this is a targeted certificate remediation row, not a wholesale
       certificate rewrite

4. **Blueprint docs overstate the current normalized persistence path.**
   - Surfaces:
     - `docs/DEPO-PRO_UFM_Data_Dictionary_v2.md`
     - `docs/DEPO-PRO_Field_Template_Matrix.md`
     - `backend/services/intake_store.py`
     - `backend/db/repository.py`
     - `backend/api/packaging.py`
   - Live-tree finding:
     - The docs assume richer structured persistence for parties, attorneys,
       appearances, and some admin-page inputs than the live intake write path
       actually stores.
   - Impact:
     - this drift must be logged in the gap analysis rather than silently
       resolved in favor of either the docs or the code

5. **CNA and interpreter pages remain true implementation gaps.**
   - Surface:
     - `backend/packaging/admin_pages.py`
     - `backend/packaging/packager.py`
   - Live-tree finding:
     - These are not just undocumented or hidden; they are absent from the live
       package builder.

---

## Still open / should not disappear

These were not fully resolved by the live-tree pass and should remain explicit
Phase B or later-audit items rather than silently vanishing.

1. **Chronological / witness index event reliability is still not fully proven.**
   - Surface:
     - transcript-stage event production feeding `backend/packaging/indices.py`
   - Status:
     - Both passes agree the indexes are transcript-state driven.
     - Neither pass fully proved that the underlying chronological/witness index
       events are always reliably produced across real cases.
   - Carry-forward:
     - keep open into Phase B sample-output validation.

2. **Corrections/signature page completeness remains only partially resolved.**
   - Surface:
     - `backend/packaging/admin_pages.py::build_corrections_signature_page(...)`
   - Status:
     - The live pass improved this from a generic `[VERIFY]` by identifying the
       page as minimal, but it still needs rendered-output validation against the
       expected `PAGE | LINE | CHANGE | REASON` style and any jurat expectations.
   - Carry-forward:
     - keep open into Phase B sample-output review.

3. **Placeholder-vs-populated certificate behavior remains a Phase B output question.**
   - Surfaces:
     - `backend/packaging/admin_pages.py`
     - live data in `deposition_metadata` and any future `case_attorneys` rows
   - Status:
     - The write path for `depo_meta` exists, but whether real jobs currently
       render populated vs placeholder certificate sections can only be answered
       by generating a live DOCX/PDF from `data/transcripts/`.

---

## Net conclusion

The live-tree audit did what the older reference could not:

- it **resolved** the `depo_meta` write-path question
- it **resolved** the duplicate-render question
- it **reconciled** against the live blueprint docs
- and it **upgraded** `appearances → case_attorneys` from a suspicion to a
  confirmed lineage break

The shared spine between the two checkpoints is real. The meaningful Phase A
differences are exactly where an independent live pass should have found them:
the blueprint-doc reconciliation, the UI/API path for certificate metadata, the
single export-writing surface, and the narrower live certificate gap.
