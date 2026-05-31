# UFM Certificate + Exhibit Index — Read-Only Audit (2026-05-31)

> **Status:** AUDIT ONLY. No code, tests, templates, or data changed.
> **Method:** Live code read in `depo_final_wave8-main` + ground-truth comparison
> against two Myler/Lexitas certified reference depositions (Shaw 191216 — Texas
> state/TRCP; Filpi 190604 — federal/FRCP). Findings tagged **[CONFIRMED]** when
> established directly from live code, **[GROUND-TRUTH]** when established from a
> real reference deposition, and **[DECISION]** where scope needs your sign-off.
> Builds on `docs/ufm_audit/checkpoint_A.md`.

---

## 0. Summary for sign-off

Both tasks are **finishing passes on subsystems that already exist end-to-end**,
not greenfield builds. Neither is blocked. The real work is small and
well-contained — but each has **one scope fork** that ground truth forces into
the open, and I want your call before any code is written.

| Task | Pipeline state | Real gap | Scope fork |
|---|---|---|---|
| UFM certificate | Fully wired; substantially TRCP-complete | Missing the "changes attached" clause (c) | Minimal one-clause insert **vs.** jurisdiction-aware two-part certificate |
| Exhibit index | Fully wired Stage 4 → snapshot → packaging → page | Index drops `description`, mis-formats columns/page-ref | Cosmetic format fix **vs.** also surfacing the captured `description` field |

---

## 1. UFM Certificate completion

### 1.1 What is already built [CONFIRMED]
`backend/packaging/admin_pages.py::build_certificate_page(...)` is one flat page
and already emits: sworn/true-record; examination-signature disposition;
original-delivered; time-used-per-party (data-driven, with placeholder
fallback); officer charges; counsel-of-record block (data-driven); copy-served;
disinterest statement; and the package/hash binding block. Metadata is loaded
and saved through `/api/depo-meta/jobs/{jobId}` (`backend/api/depo_meta.py`,
`backend/db/depo_meta_repo.py`, Stage 5 UI). This matches checkpoint_A.

### 1.2 The confirmed gap [CONFIRMED]
There is **no "changes/corrections by the witness, if any, are attached"
clause** in `build_certificate_page`. The page jumps from the
examination-signature clause directly to "original delivered." This is the only
explicit clause gap in the live builder.

### 1.3 Ground truth — and the complication [GROUND-TRUTH]
The reference depos show the clause exists, but **its placement depends on
jurisdiction**, which the live single-page builder does not model:

- **Shaw (Texas / TRCP 203)** uses a **two-part** certificate. The
  *Reporter's Certificate* page carries sworn/true-record, examination-signature
  submission, time-per-party, counsel, and disinterest — then states that
  further Rule 203 requirements *"will be certified to after they have
  occurred."* A **separate "FURTHER CERTIFICATION UNDER TRCP RULE 203" page**
  then carries: original returned/not-returned; **the changes-attached clause**
  ("If returned, the attached Changes and Signature page(s) contain any changes
  and the reasons therefor"); delivery to custodial attorney; officer charges;
  and copy-served/filed.
- **Filpi (federal / FRCP 30(f))** uses a **single** certificate that folds the
  changes-attached clause inline, tied to the FRCP signature-request mechanics.

The live builder is a hybrid: it claims TRCP 203.3 lineage but flattens
everything onto one page (charges + delivered + served sit *with* the
sworn/time/counsel block, which the real Texas form defers to the separate
Further Certification page). So clause (c) is missing from a structure that
itself diverges from the Texas reference.

### 1.4 [DECISION] Scope fork for the certificate
- **Option A — Minimal (low risk, ~1 commit).** Insert clause (c) into the
  existing flat page near the examination-signature clause, using the
  ground-truth wording. Closes the literal checkpoint_A finding. Does **not**
  resolve the flat-vs-two-part divergence.
- **Option B — Structural (correct, larger).** Add a jurisdiction-aware path:
  Texas → Reporter's Certificate + a new `further_certification` page
  (new `SECTION_ORDER` entry + builder); federal → single inline form. This is
  the same federal/state branch checkpoint_A parked in the EXPAND line, so it
  carries that whole item.

My read: **A is the honest "finish what exists" pass; B is product expansion.**
Recommend A now, log B explicitly as deferred — unless you want the Texas form
actually correct before any cert ships.

### 1.5 Adjacent (out of scope, flagging only)
The Changes/Signature page (`build_corrections_signature_page`) has 3 blank
correction lines and **no notary jurat**; Shaw's real page has ~23 lines plus a
full jurat (STATE/COUNTY/"Before me…"/NOTARY block). Not part of either task —
listed so it isn't mistaken for cert scope.

---

## 2. Exhibit index completion

### 2.1 What is already built [CONFIRMED]
The exhibit index is wired end-to-end:
- **Stage 4 capture:** `/api/exhibits` (`backend/api/exhibits.py`) — full
  list/create/update/delete with provenance events; `transcript_exhibits` table;
  repo methods in `backend/transcript/repository.py`; frontend UI in
  `stage_4_insertions.html` / `stage_4.js`.
- **Model** (`TranscriptExhibit`): `exhibit_number`, `exhibit_title`,
  `offering_attorney`, `description`, `anchor_utterance_id`, `anchor_note`,
  `sort_order`.
- **Snapshot capture:** `snapshot_service.py` freezes exhibits into snapshot
  state and is part of the state hash.
- **Producer:** `api/packaging.py` resolves each exhibit's
  `anchor_utterance_id` → render line → `ExhibitEvent`.
- **Generator/renderer:** `indices.py::build_exhibit_index(...)` →
  `admin_pages.py::build_exhibit_index_page(...)`, in `SECTION_ORDER`.

So the index is **not empty-by-design** — if an operator marks exhibits, they
flow to the page.

### 2.2 The real gaps [CONFIRMED]
1. **`description` is dropped.** `build_exhibit_index` reads only
   `exhibit_number` and `exhibit_title`. The captured `description` (and
   `offering_attorney`) never reach the page.
2. **Wrong column shape.** `_format_index` renders
   `"Exhibit {N} - {title} .......... {ref}"` with no `NO. / DESCRIPTION / PAGE`
   header and no description wrapping.
3. **Wrong page reference.** It emits the full `"Page X, Line Y"` reference; the
   real index shows a bare page number.
4. **"Exhibit" prefix in the number column** instead of a bare numeral.

### 2.3 Ground truth [GROUND-TRUTH]
Both Shaw and Filpi use an identical three-column form:

```
EXHIBITS
NO.  DESCRIPTION                                      PAGE
1    Plaintiff City of Jefferson, Texas' .............10
     Notice of Oral Deposition of ACT Pipe &
     Supply
2    ACT Pipe & Supply Trade References, Bates .......15
     No. COJ 0037
```

- Bare number in `NO.`; full **description** (multi-line, wrapped, includes Bates
  ranges) in `DESCRIPTION`; **leader dots** to a right-aligned bare **page
  number**; `EXHIBITS (cont.)` header on continuation pages.
- **No OFFERED / ADMITTED columns** in either reference.

### 2.4 [DECISION] Scope fork for the exhibit index
- **Option A — Format-only (low risk).** Reshape `build_exhibit_index` /
  `_format_index` to the `NO./DESCRIPTION/PAGE` form, bare number, bare page,
  leader dots, `(cont.)` header. Keep using `exhibit_title`.
- **Option B — Format + description (matches ground truth).** Same, but carry
  `description` through `ExhibitEvent` → index so the page shows the real
  multi-line descriptions operators already capture. This is what the reference
  depos actually print; `exhibit_title` alone produces a thinner index than
  Myler's.

My read: **B is the one that matches ground truth** and uses data already
captured — modest extra work (add a field to `ExhibitEvent`, thread it through
`build_exhibit_index`, wrap in `_format_index`). Recommend B.

### 2.5 Explicitly NOT a gap [GROUND-TRUTH]
The absence of OFFERED/ADMITTED tracking is **not** a defect — neither reference
deposition has those columns. Do not build offered/admitted status for this task.
(Parallels the QA-03 caution: don't build a feature ground truth doesn't show.)

---

## 3. Tests in the blast radius
`test_cert_fields_p1/p2/p3.py`, `test_stage5_certify_contract.py`,
`test_exhibits_api.py`, `test_wave20_packaging.py`, `test_export_validation.py`.
Any builder change should run with the Windows basetemp workaround
(`--basetemp="$env:TEMP\depo_pytest"`). Baseline to protect: 601 passed / 1 skipped.

---

## 4. Recommended build order (pending your decisions)
1. Confirm scope forks: **Cert = A or B**, **Exhibit index = A or B**.
2. Exhibit index pass (lower risk, self-contained: `indices.py` +
   `admin_pages._format_index`, plus `ExhibitEvent` if B).
3. Certificate clause pass (A = single-clause insert; B = jurisdiction branch +
   new further-certification page/section).
4. Four-commit separation per workstream (backend / frontend / tests / docs),
   working tree left uncommitted for your review.

**Stop-and-Ask gates:** (a) before adding any `SECTION_ORDER` page; (b) before
introducing a jurisdiction branch; (c) before editing the state-hash input set.
