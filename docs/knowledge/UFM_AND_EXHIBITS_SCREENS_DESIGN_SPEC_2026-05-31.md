# Stage 4 (UFM Templates) + Stage 5 (Exhibits) — Design Spec

> Companion to `mockups/ufm_templates_and_exhibits_mockup.html`.
> Scope tags: **[GROUNDED]** maps to existing code/ground-truth · **[WORKING-ONLY]**
> tracked but never printed · **[DEFERRED]** EXPAND-line, scaffolded not built ·
> **[OPEN]** needs your decision.
> Ground truth: Shaw 191216 (TX), Filpi 190604 (Fed), Nkemakonam 200813 (CNA) — all Myler.

---

## Scope decisions encoded in this design

1. **Screen 4 = builder + template manager** (per your refined brief). The template
   manager is marked a **new subsystem** — it's the largest net-new commitment here.
2. **Offered/Admitted/Retention = [WORKING-ONLY].** The grid tracks them; the certified
   index preview prints `NO./DESCRIPTION/PAGE` only, matching both reference depos. Your
   current `stage_4_insertions.html` preview shows "Offered into Evidence" lines — that
   illustrative mock is *not* what Myler prints, and the new preview corrects it.
3. **Package order = locked, not free drag-and-drop.** UFM mandates the sequence; only
   optional rows (chronological/exhibit index) reorder. Free reordering would let an
   operator produce a non-compliant package, so the brief's "drag-and-drop" is rendered
   as a constrained preview with lock indicators.
4. **CNA / Interpreter / Rough Draft / Federal pages = [DEFERRED].** Listed and disabled,
   not built — consistent with checkpoint_A's EXPAND line.

---

## Stage 4 — UFM Templates

### UX workflow
Enter from Workspace → jurisdiction auto-set from intake (editable) → component
availability adjusts → operator confirms components → package structure renders in
mandated order → validation must be clean → Proceed to Exhibits.

### Data model
- **[GROUNDED]** Package assembly already exists (`SECTION_ORDER`, `assemble_package`).
  No new model needed for the *builder* itself — it's a UI over existing packaging.
- **[OPEN] Template subsystem (new):** proposed `package_templates` table —
  `template_id, name, jurisdiction (tx|fed|other), scope (system|firm), firm_id (→ reporting_firm_offices),
  is_default, component_flags (JSON), optional_order (JSON), template_version, created/updated_at`.
  Open questions: can a firm template toggle *optional* pages only (recommended) or also
  styling? Versioning model? These are real architecture decisions, not UI.

### Backend API
- **[GROUNDED]** `POST /api/packaging/jobs/{job_id}` already assembles from a locked snapshot.
- **New, builder:** `GET /api/packaging/jobs/{job_id}/plan` (preview structure + validation
  without assembling); `PATCH …/plan` (persist selected optional components/order for the job).
- **[OPEN] New, templates:** `GET/POST/PUT/DELETE /api/templates`, `POST …/{id}/set-default`,
  `POST …/{id}/duplicate`. Gated on the template-subsystem decision.

### Validation rules
- **[GROUNDED]** Missing cause number / witness name (already validated in `_build_metadata_for_job`).
- Jurisdiction conflicts: Rule 203 Further-Certification page selected on a Federal package → error;
  Texas package missing Further-Certification → error (ties to Cert Option B).
- Required page disabled → error. "Other" jurisdiction → warn (rules unconfirmed).

### Future enhancements
Multi-volume package planning; per-firm letterhead; template diff/preview; jurisdiction
rule packs as data.

---

## Stage 5 — Exhibits

### UX workflow
Grid of exhibits (working layer) → select row → detail panel edits metadata + anchoring →
jump-to-anchor opens Workspace at the owning render line → certified index preview shows
the printed result → validation gates certification.

### Data model
- **[GROUNDED]** `TranscriptExhibit` already has: `exhibit_number, exhibit_title,
  description, offering_attorney, anchor_utterance_id, anchor_note, sort_order`.
- **[WORKING-ONLY] additions:** `marked_by`, `offered_by`, `offered_ref`, `admitted (bool)`,
  `admitted_ref`, `retained_by (counsel|reporter|none)`, `bates_range`. Persisted, captured
  in the snapshot's working layer, **excluded from index generation**.
- **[GROUNDED, fix]** `ExhibitEvent` must carry `description` (today it carries only
  `exhibit_title`) so the index can print the real description — per the 2026-05-31 audit.

### Backend API
- **[GROUNDED]** Full CRUD exists: `/api/exhibits` (list/create/update/delete) + provenance.
  New working-only fields extend the existing create/update payloads.
- New: `GET /api/exhibits/{job}/index-preview` returning the rendered `NO./DESCRIPTION/PAGE`
  block from current anchors + frozen pagination (read-only).

### Validation rules [GROUNDED — maps to brief]
Duplicate exhibit number; missing description; missing/unresolved anchor; exhibit referenced
in body but not indexed ("discussed but not indexed"). All are computable from existing
exhibit + transcript state.

### Certified index format [GROUNDED — locked]
`EXHIBITS` / `NO. DESCRIPTION PAGE`; bare numeral; full wrapped `description`; leader dots;
bare right-aligned page; `EXHIBITS (cont.)` on continuation. **No offered/admitted columns.**

### Future enhancements
Exhibit document attachment/packaging (the `Exhibit.reference` seam already exists);
auto-suggest exhibit marks from "(Exhibit N marked)" parentheticals; cross-volume exhibit
continuity.

---

## CNA — real fields from Nkemakonam (answers the brief's CNA questions) [GROUNDED]

A CNA **replaces** the transcript body + standard certificate. Structure:
caption → title block ("CERTIFICATE OF NONAPPEARANCE FOR THE [VIDEOCONFERENCE]
DEPOSITION OF [WITNESS], [DATE], (Reported Remotely)") → reporter certify line → "I appeared
[remotely via Zoom / at location] on [date] to report … pursuant to Notice, scheduled for
[time]" → **present-attendees list** (attorneys + parties represented) → "by [time], [witness]
had not appeared; the following proceedings were had:" → short **proceedings record** (on-record
statements, attaching the Notice as Exhibit A, reserve-right-to-redepose) → "(End of proceedings
at [time])" → disinterest clause → **jurat** ("SUBSCRIBED AND SWORN TO …") → reporter signature block.

Design implication: CNA is a **package mode**, not just a page. When in scope it gates out
body/witness-index/standard-cert and substitutes this. Still **[DEFERRED]** until you pull it forward.

---

## Still [OPEN] — won't design on assumption
- **Multi-volume:** trigger, labeling, per-volume vs consolidated indexes/certs. No artifact.
- **Interpreter certificate:** need a reference for fields + placement.
- **Rough draft:** disclaimer wording + whether it suppresses cert/indexes. No artifact.
- **Template subsystem:** firm scope semantics, versioning, override boundaries.
- **"Other" jurisdiction:** real target or placeholder?
