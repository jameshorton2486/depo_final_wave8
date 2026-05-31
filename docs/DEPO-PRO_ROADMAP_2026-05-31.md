# DEPO-PRO Roadmap — Post-Audit Stabilization & UI

**Date:** 2026-05-31 · **Status:** Architecture audits substantially complete · **Horizon:** next few weeks
**Governing rule:** Protect the stabilized architecture. UI *consumes* the architecture; it never redefines it.

---

## The one principle that governs everything

The biggest risk now is **not** technical — it's undoing stabilized architecture by changing things in the
wrong order or mixing concerns in a single pass. Work proceeds in three tracks that are **not mixed**:

- **Track A — Transcript Engine Architecture** (protect-first; finish pagination authority)
- **Track B — Package Builder & UFM Workflow** (rules-driven assembly, backend)
- **Track C — UI / UX** (the screens, which consume A and B)

Do **not**, while building UI: redesign pagination, packaging, ownership, references, or exports.

Every track item follows the established discipline: **read-only audit phase → written report → scope
agreed → code**, with Stop-and-Ask gates and four-commit separation (backend / frontend / tests / docs).

---

## TRACK A — Transcript Engine Architecture (protect-first)

Stable today: ownership foundation · consumer migration · packaging · references.

**A1 — Certified pagination ground-truth validation.**
Compare `export_render` vs `backend.pagination` vs the **real certified transcripts** (Shaw, Filpi — whose
page references we already have as text). Answer: which page map matches certified output; are
continuations, page references, and exhibit references legally correct.
→ Deliverable: `pagination_ground_truth_validation.md`.
**⛔ STOP gate: do not cut over pagination authority until this report exists.**

**A2 — Pagination authority decision (evidence-driven).**
Option A keep `export_render` · Option B cut over to `backend.pagination`. Decide only from A1's evidence.

---

## TRACK B — Package Builder & UFM Workflow (backend rules engine)

**B0 — Exhibit ownership + record-type exhibit-index fork** *(lowest-risk, fully grounded — best entry point)*.
Add the owner-pair fields to `TranscriptExhibit` (`owner_snapshot_id`, `owner_anchor_utterance_id`) — these
are **not yet in the codebase**; populate at anchor time, derive citations from them. Fork the exhibit index
by record type: Official prints offered + received (3.23(c)); Freelance prints description + page marked only
(3.24(a)(6)). Self-contained; no pagination-authority dependency.

**B1 — Package rules engine.**
Inputs Record Type × Jurisdiction × Case Type → derived architecture. Supports: Freelance deposition,
Official record, Certificate of Non-Appearance, Federal deposition, Capital murder, Multi-volume. The
engine generates mandatory packages; the reporter reviews and overrides with the basis shown.

**B2 — Administrative-page rules (logic forks).**
Texas / Federal / CNA / Official / Freelance forks. Mandatory pages locked; optional pages configurable.
Key forks (all verified against the 2010 UFM):
- Index: Official = three indexes (3.23); Freelance = consolidated, no required format (3.24(b), Fig 11).
- Certificate: Texas = Reporter's Cert + Further Certification (3.4); Federal = FRCP 30(f)(1) single form.
- Signature: Required → Changes/Signature page before cert; Waived → omit + signature-waived cert variant
  (3.4 → Figs 7–9; "9/9A" label ⚠VERIFY); Pending → advisory warning.
- CNA: body suppressed, appearances inline, own proceedings + jurat.

**B3 — Master index (multi-volume).**
**Gate to Official records.** When an Official record > 1 volume: Master Index in its own "Volume 1," VOL.
column on every entry, volume-summary listings rejected (3.23(d), Figs 24/26). 300-page volumes (6.3),
Arabic numerals (6.1). *Not* auto-triggered for multi-volume Freelance depositions (3.24(b) = no required format).

---

## TRACK C — UI / UX (consumes Tracks A and B)

**Approved workflow (8 stages):**
1 Intake · 2 Transcripts · 3 Workspace *(incl. Speaker Mapping)* · 4 Transcript Package Builder ·
5 Exhibits · 6 Transcript Preview · 7 Certify · 8 Export.

> **Stage-order note (your call, honored):** you've consistently placed **Builder (4) before Exhibits (5)**.
> That works as long as the Builder at Stage 4 sets *rules + structure* (which need no exhibits), while
> exhibit-anchor and index validation **finalize after Stage 5 and after pagination**. So the readiness score
> is *provisional* at Stage 4 and *final* before Certify. (The alternative — Exhibits before Builder — would
> let the Builder validate against real anchors immediately; either is fine, this is the data-flow to respect.)

- **C1 Package Builder** — tabs: Package Rules · Administrative Pages · Indices · Certificates · Template
  Selection · Validation · Package Preview. Includes: validation panel (conditional checks; blocking errors vs
  advisory warnings), readiness score, multi-volume controls, signature-status controls, Federal/Texas forks,
  visual package cards + per-component preview, template inheritance (firm → reporter, "inherited from / detach").
- **C2 Exhibits** — list · anchoring · timeline · index preview · validation · attachments · starting exhibit
  number · ownership-backed references. Working grid tracks offered/admitted; printed deposition index does not.
- **C3 Transcript Preview** — clean Word-style editor over the **same working transcript** (single source of
  truth — no parallel copy). Caption, appearances, indexes, body, certificates assembled, **no UFM geometry /
  no page numbers / no certification formatting**. Downloads: DOCX, PDF, ASCII, TXT (a clean export *profile*
  over existing writers, not new writers). Pre-certification, labeled non-certified.
- **C4 Certify** — validation + certification only, **no editing**. Checklist: transcript / exhibits / package /
  speaker mapping / ownership metadata / validation all complete.
- **C5 Export** — Certified PDF · Certified DOCX · Package ZIP · Agency Copy · Rough Draft · Archive Copy.

---

## Verified facts to build against (locked)

- Record Type is the **primary** gate; Jurisdiction and Case Type are secondary.
- UFM citations confirmed against the official 2010 manual: 3.1, 3.23, 3.24(b), 3.4, 3.3(a), 3.23(d)+Figs 24/26,
  6.3 (300 pp), 6.1 (Arabic), 2.5/2.13 (geometry), 2.10–2.11 (3 tabs), Preface (discipline).
- Geometry: 6.5" / 56–63 chars, 25 double-spaced lines, **3 tabs** at 5th/10th/15th (live profile exposes 5 — reconcile).
- Mandatory pages hard-locked; firm templates restyle + toggle optional pages only (Preface liability).

## Open / ⚠VERIFY (do not assert until resolved)

- Owner-pair exhibit fields not yet in this codebase (B0 closes this).
- Figure plates unverified from manual body: CNA (Fig 29?), signature-waived cert (Fig 9/9A?), master index,
  interpreter. Fetch the UFM figures section to lock layouts.
- Interpreter *certificate* page: manual has setup/oaths only — confirm a distinct cert page exists before building.
- "Other" jurisdiction: real target or placeholder?

## Guardrails

- **Mockups are not app code.** The `.html` prototypes live in `docs/design/mockups/` for reference. **Never**
  copy them into `frontend/` — they use a Tailwind CDN, fake data, and demo JS, and will not slot into the
  compiled-Tailwind app.
- Audit-first, always. Stop-and-Ask before any `SECTION_ORDER` change, jurisdiction branch, or state-hash edit.
- Pytest on Windows: `--basetemp="$env:TEMP\depo_pytest"`. Baseline to protect: 601 passed / 1 skipped.

---

## Reference artifacts (current vs superseded)

**Current (use these):**
- `docs/ufm_audit/UFM_RULES_REFERENCE_2026-05-31.md`
- `docs/ufm_audit/UFM_CITATION_VERIFICATION_2026-05-31.md`
- `docs/audits/UFM_CERT_AND_EXHIBIT_INDEX_AUDIT_2026-05-31.md`
- `docs/design/UFM_AND_EXHIBITS_SCREENS_DESIGN_SPEC_2026-05-31.md`
- `docs/design/LEGAL_TRANSCRIPT_PACKAGE_ORCHESTRATOR_v2.md`
- `docs/design/mockups/transcript_package_builder_v3.html` *(active Stage-4 reference)*
- `docs/design/mockups/transcript_preview_v1.html` *(active Stage-6 reference)*

**Superseded (history only — do not build from):**
- `docs/design/mockups/ufm_templates_and_exhibits_mockup.html`
- `docs/design/mockups/transcript_package_builder_and_exhibits_v2.html`
- `docs/design/UFM_AND_EXHIBITS_SCREENS_DESIGN_QUESTIONS_2026-05-31.md` *(mostly answered)*

---

## Recommended first move

Start **B0** (exhibit owner-pair fields + record-type exhibit-index fork) as the first audit-first build pass:
fully grounded, self-contained, no pagination dependency. Run **A1** in parallel as a read-only investigation
(it changes nothing). Hold all of Track C until A2 is decided.
