# UFM Templates + Exhibits Screens — Design Questions & Scope Reconciliation

> **Status:** PRE-DESIGN. No mockups, wireframes, data models, or API specs
> produced yet — held pending the answers below, per the brief's "questions
> first, do not assume" instruction.
> **Builds on:** `docs/audits/UFM_CERT_AND_EXHIBIT_INDEX_AUDIT_2026-05-31.md`
> and `docs/ufm_audit/checkpoint_A.md`.
> **Ground truth:** Shaw 191216 (Texas/TRCP) and Filpi 190604 (federal/FRCP),
> Myler/Lexitas certified.

---

## Part A — Stage order (proposed, one open question)

| New # | Screen | Current file | Change |
|---|---|---|---|
| 1 | Intake | `stage_1_intake.html` | none |
| 2 | Transcripts | `stage_2_transcripts.html` (+ `stage_2b_speakers.html`) | none |
| 3 | Workspace | `stage_3_workspace.html` | none |
| 4 | UFM Templates *(or Package Builder — see Q1)* | — | **new** |
| 5 | Exhibits | `stage_4_insertions.html` | rename + renumber |
| 6 | Certify | `stage_5_certify.html` | renumber |
| 7 | Export | `stage_6_export.html` | renumber |

**A-Q1.** Does **Speakers (`stage_2b`)** remain a sub-stage of Transcripts, fold
into Transcripts, or become its own numbered stage? It is absent from the
requested order.

**Implementation note (not a question):** renumbering 4/5/6 → 5/6/7 and
inserting a new stage 4 touches frontend routing, `state.currentStage` checks
(e.g. `app.js` hardcodes `currentStage === 3` for Workspace persistence), and
every `stage_N` filename/handler. This is mechanical but wide; it is a build
item, not a design item, and is out of scope until screens are approved.

---

## Part B — Scope decisions required before design (the honest forks)

These are flagged because each contradicts either the 2026-05-31 audit or the
project's scope-discipline principle. Each needs an explicit yes/no.

**B-Q1. Screen 4 identity — Template manager vs. Package builder.**
The brief conflates two screens:
- *Package Builder:* assemble **this job's** package (component checklist,
  order preview, validation, jurisdiction). Per-job, no persistence beyond the
  job.
- *Template Manager:* view / edit / duplicate / create firm-specific / set
  default **reusable** layouts. A new persistent subsystem (storage, versioning,
  firm scoping) that does not exist today — only the `ADMIN_TEMPLATE_VERSIONS`
  seam exists.
Which is screen 4? Both? If both, the template manager is its own workstream and
should not gate the package builder.

**B-Q2. Offered / Admitted tracking on the Exhibits screen.**
Ground truth: neither Shaw nor Filpi prints offered/admitted on the exhibit
index. Options:
- (a) Drop offered/admitted entirely (matches the audit recommendation).
- (b) Track as **working-only metadata**, explicitly never rendered into the
  certified package.
- (c) Render it — only if you have a non-Myler reference that shows it; the
  current corpus does not.
Default recommendation: (a) or (b). Not (c) without an artifact.

**B-Q3. EXPAND-line pages.** CNA, interpreter certificate, rough-draft
disclaimer, and the full federal page set are all parked behind core-engine
maturity in checkpoint_A. Are any being pulled forward now, or does screen 4
simply *list* them as future/disabled options? (Listing them disabled is cheap;
building their builders is the EXPAND line.)

**B-Q4. Jurisdiction-aware certificate.** The audit established Texas = two-part
(Reporter's Certificate + Further Certification under Rule 203) and federal =
single inline form. If screen 4 surfaces jurisdiction selection, does that imply
committing to **Cert Option B** (the structural jurisdiction branch), or is the
selection cosmetic for now while the cert stays flat (Cert Option A)?

---

## Part C — Already settled by ground truth (do NOT re-ask)

These were pinned to real depos in the audit; treat as fixed inputs to design.

**C1. Exhibit index format.** Three columns — `NO.` (bare numeral) /
`DESCRIPTION` (full, multi-line, wrapped, includes Bates ranges) / `PAGE` (bare
number, leader-dotted, right-aligned). `EXHIBITS (cont.)` header on
continuation. No OFFERED/ADMITTED columns. Source field is `description`, not
just `exhibit_title`.

**C2. Certificate structure.** Texas two-part vs. federal single (see B-Q4).
The missing clause is (c) "changes attached"; wording lifted from Shaw's
Further-Certification page / Filpi's inline clause.

**C3. Signature/Changes page.** Header `CHANGES AND SIGNATURE`; `WITNESS / DATE`
line; `PAGE LINE CHANGE REASON` columns; ~23 ruled lines (live builder has 3);
witness affix-signature statement; **plus a full notary jurat** (STATE/COUNTY /
"Before me…" / NOTARY PUBLIC / COMMISSION EXPIRES) — absent from the live
builder.

**C4. Witness index.** Alphabetical by surname; one row per examination with
examination-type detail; transcript-state driven (already implemented).

---

## Part D — Genuinely open questions (no artifact yet — do not assume)

Grouped per the brief's categories; only unsettled items listed.

**Texas vs Federal.** Beyond the certificate (C2/B-Q4): do caption, appearances,
and signature pages differ by jurisdiction in your corpus, or only the
certificate? Which jurisdictions must v1 support — Texas + Federal only, or is
"Other" a real near-term target or just a placeholder?

**Administrative page ordering.** Live `SECTION_ORDER` is fixed
(caption → appearances → chronological → witness → exhibit → body →
corrections/signature → certificate). The brief proposes **drag-and-drop**
reordering. Is operator reordering actually permitted, or is order
UFM-mandated and the "preview" should be read-only? (Reorderable order conflicts
with a fixed compliant sequence.)

**Multi-volume.** No multi-volume artifact in the current corpus. What triggers
a volume split, how are volumes labeled, and do indexes/certificates repeat
per-volume or consolidate? Needs a reference example before design.

**Certificate of Non-Appearance.** When is a CNA issued, what fields, and does it
*replace* the transcript body and standard certificate or supplement them? Need a
CNA reference (NkemakonamCNA is in the corpus — is it a CNA example to mine?).

**Interpreter.** Need an interpreter-certificate reference. What fields
(interpreter name, language, oath), and where does it sit in `SECTION_ORDER`?

**Rough draft.** Disclaimer wording source? Does rough-draft mode suppress the
certificate and indexes entirely, or stamp every page? Need the rule.

**Firm-specific customization.** Tied to B-Q1. If templates are firm-scoped:
what is "firm" in the data model (there's `reporting_firm_offices`), who can edit
defaults, and how does a firm template interact with jurisdiction-mandated
structure (can a firm template override required pages, or only styling)?

**Exhibit anchoring UX.** "Jump to transcript location / owning render line" —
the data exists (`anchor_utterance_id` → render line). Confirm: is this
navigation only, or also a re-anchoring editor? Re-anchoring after snapshot lock
has integrity implications (state hash).

---

## Part E — Sequence proposed

1. You answer A-Q1 and B-Q1…Q4 (the forks).
2. Provide references for any EXPAND item being pulled forward (CNA, interpreter,
   multi-volume, rough draft).
3. Then design deliverables per screen (mockup, UX flow, wireframe, data model,
   API, validation rules, future enhancements) — scoped to confirmed items only.
