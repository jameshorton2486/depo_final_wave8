> DOCUMENT STATUS: CANONICAL ROOT AUTHORITY
> Scope: repository-wide governance, transcript-safety invariants, documentation hierarchy, and agent work rules.
> Read this first. If another active document conflicts with this one, this file wins unless it explicitly defers to a named canonical subsystem spec or active subsystem spec.

# CLAUDE.md — Agent Onboarding & Documentation Authority

> **Read this file first, before any other documentation in this repository.**
> It tells you what DEPO-PRO is, which documents are authoritative, which are
> historical, the invariants you must never violate, and how you are required
> to work. If any other document contradicts this file, this file wins —
> except where this file explicitly defers to a named subsystem spec.

---

## 1. What DEPO-PRO is

DEPO-PRO is a **local-first desktop application that produces certified legal
deposition transcripts**. Stack: FastAPI backend, SQLite persistence,
vanilla-JS + Tailwind frontend, PyWebView desktop shell. The workflow is six
stages: Intake -> Transcripts -> Speakers -> Workspace -> Insertions ->
Certify -> Export.

The product is **real, persisted, and operational** — not a mock, not
in-memory, not a prototype. Any document that describes it as static, mock, or
unwired is **historical and wrong**; see Section 4.

A deposition transcript is a **sworn, verbatim legal record**. The correctness
and integrity of testimony outrank every other consideration — performance,
elegance, cleanliness, and feature scope all come second.

---

## 2. Documentation authority — read in this order

Read top-down. Do not read historical docs by default; reach for them only
when explicitly investigating project history.

1. **`CLAUDE.md`** (this file) — authority hierarchy, invariants, work rules.
2. **`README.md`** — concise human overview and setup.
3. **`docs/wave_status_report.md`** — current wave-by-wave operational status.
4. **Current architecture & rules** (the named canonical docs in Section 3).
5. **Subsystem specs** — only when working on that subsystem.
6. **`docs/archive/`** — historical record. **Never treat as current.**

If you need the current state of the system, items 1-4 are the answer. Item 5
is consulted per-task. Item 6 is never consulted to learn "what is true now."

### 2A. Active document classes

DEPO-PRO uses six live documentation classes. Agents must not treat them as
interchangeable:

1. **Root governance authority** — repository-wide governance and current-state
   hierarchy enforcement.
2. **Canonical contract** — the primary current contract for one concern or
   subsystem.
3. **Active subsystem spec** — still-governing subsystem design/behavior docs
   that remain relevant to live code, but are narrower than root authority.
4. **Active reference** — setup guides, commands, and operational context that
   do not own architecture.
5. **Temporary operational document** — validation checklists, live logs, and
   stabilization instruments that help operations but must eventually expire,
   be superseded, or be archived.
6. **Superseded active document** — retained in active locations for provenance
   only; explicitly not safe as current truth.

Audits and validation logs are never architecture authority. They may report on
the system accurately or inaccurately, but they do not own it.

---

## 3. Canonical documents

These are the **only** documents that describe the current system. Each owns
exactly one concern. If you change behavior, update the matching canonical doc.

| Concern | Canonical document |
|---|---|
| Human overview & setup | `README.md` |
| Wave / feature status & current priorities | `docs/wave_status_report.md` |
| Data model | `docs/ufm_schema_v1.md` |
| System ownership map | `docs/SYSTEM_OWNERSHIP.md` |
| Transcript orchestration & layer lifecycle | `docs/TRANSCRIPT_ORCHESTRATION.md` |
| Export / certification pipeline ownership | `docs/EXPORT_AND_CERTIFICATION_PIPELINE.md` |
| Active document registry | `docs/ACTIVE_SPEC_REGISTRY.md` |
| Governance maintenance lifecycle | `docs/GOVERNANCE_MAINTENANCE_RULES.md` |
| Transcript safety invariants | `docs/architecture/transcript_engine/TRANSCRIPT_ENGINE_RULES.md` |
| Correction engine spec | `docs/architecture/transcript_engine/deterministic_correction_engine_spec.md` |
| Diff / diagnostics spec | `docs/architecture/transcript_engine/transcript_diff_harness_spec.md` |
| Open blockers & policy decisions | `docs/BLOCKERS.md` |

Volatile state — test counts, "operational" claims, and the current priority
order — lives in `docs/wave_status_report.md` and `docs/BLOCKERS.md` **only**.
Do not record test counts or a frozen priority list anywhere else (including in
this file): such lists go stale within days and become the next source of
drift. To learn the current test count, run the suite (see Section 8). To learn
current priorities, read `wave_status_report.md` and `BLOCKERS.md`.

### 3A. Active subsystem specs

The following are live subsystem specs that still govern code and must not be
treated as historical build records:

| Concern | Active subsystem spec |
|---|---|
| NOD parsing contract | `docs/nod_parser_spec.md` |
| Pagination / geometry behavior | `docs/wave19_ufm_layout.md` |
| Packaging / certification package behavior | `docs/wave20_packaging.md` |

These specs do not outrank the canonical root authorities above, but they do
govern their named subsystem unless superseded by a newer canonical subsystem
spec.

### 3B. Active references and temporary operational docs

These documents are useful, but they do not own architecture:

- `development_workflow.md` — runtime transcription trust modes.
- `docs/development_workflow.md` — developer setup and local maintenance.
- `docs/audits/MVP_WORKFLOW_VALIDATION_CHECKLIST.md` — manual validation checklist.
- `docs/audits/REAL_WORLD_VALIDATION_LOG.md` — active operational validation log.
- `docs/audits/STAGE3_WORKSPACE_STABILIZATION_AUDIT_2026-05-25.md` — historical-in-place audit that may no longer reflect current code; verify before use.

---

## 4. Documents you must NOT trust as current

The repository contains historical execution records — old audits, progress
logs, single-wave build plans, and one-off investigations. They are valuable
forensic history but **must not be read as the current architecture**. After
the documentation consolidation pass they live under `docs/archive/` and carry
a `HISTORICAL` or `SUPERSEDED` banner.

Known high-risk historical docs (do not act on these as current):

- `docs/architecture.md` — describes a pre-backend mock; **factually wrong**
  about the current system.
- `docs/backlog.md` — a Phase-A-era snapshot of an in-memory mock.
- `docs/AUDIT.md`, `docs/PROGRESS.md`, `docs/OVERNIGHT_BUILD.md` — old
  build/audit logs; claim subsystems are unwired that are in fact operational.
- `docs/roadmap_ufm_production.md` — claims later waves are not started.
- Any `docs/wave*.md` single-wave build document (other than
  `wave_status_report.md`) — a historical build record, not a live spec.

**Historical-document quarantine.** Documents under `docs/archive/` are for
forensic reference only. You MUST NOT:

- use an archived doc as implementation authority;
- restore a deprecated architecture or workflow from the archive;
- revive an abandoned subsystem because an old doc describes it;
- copy old workflow assumptions or status claims into current code or docs.

If any document — archived or not — tells you a subsystem is "mock", "not
started", "not wired", or "next pass", **verify against the code and
`wave_status_report.md` before acting.** The codebase has consistently moved
ahead of its documentation.

---

## 5. Core invariants — never violate

These are enforced in code and are not negotiable. A change that breaks one of
these is wrong even if tests pass.

- **Raw transcript immutability.** The raw Deepgram transcript is immutable
  once captured. It is hash-anchored and verified on load. Never write the raw
  layer after capture; never bypass `RawTranscriptImmutableError`.
- **Single-layer compliance.** Every change belongs to exactly one transcript
  layer — raw / working / corrected / certified. A change in one layer must
  never write into another.
- **Certified records are immutable.** A certified snapshot can never change.
  Re-certification creates a new lineage; rollback never alters a certified
  record.
- **Deterministic formatting only.** Pagination, geometry, tabs, spacing, and
  layout are deterministic and derive solely from the geometry authority
  (`backend/geometry/profile.py`). **AI must never make a formatting,
  pagination, or layout decision.**
- **Diagnostics are read-only.** The diff / diagnostics layer
  (`backend/diagnostics/`) never writes to the raw or working transcript.
- **Mutation detection gates certification.** Unexplained transcript drift
  blocks certification; a logged, attributable change does not.
- **No parallel authority systems.** When a concern already has a code
  authority or a canonical doc owner, extend it. Do not create a second
  transcript pipeline, pagination engine, certification path, working-text
  store, or governance doc that quietly competes with the first.

### 5A. Transcript semantic safety — verbatim-first

The transcript system is **verbatim-first**. A deposition records what a
witness actually said, including imperfect speech. Coding agents tend to
"clean up" text by default — here, that is data corruption of a legal record.

You MUST NEVER, anywhere in the pipeline:

- silently delete or drop words;
- summarize, paraphrase, or "tidy" testimony;
- remove filler words, false starts, or repetitions;
- normalize away hesitation or uncertainty language;
- rewrite or "improve" a witness's wording or meaning;
- infer or reassign speaker identity by heuristic guesswork.

Every transcript change must be **deterministic, attributable, diff-auditable,
reversible, and provenance-linked**. AI may *suggest* edits surfaced for human
review; AI may never *silently apply* a semantic rewrite. When in doubt,
preserve the original text exactly and surface the question.

---

## 6. Code authorities — single ownership

Each concern below has exactly one authoritative owner in the codebase. Use
these modules; do not build alternates beside them.

| Concern | Authoritative module |
|---|---|
| Geometry / pagination measurements | `backend/geometry/profile.py` |
| Pagination engine | `backend/pagination/` |
| Transcript diffing / diagnostics | `backend/diagnostics/` |
| Correction orchestration | `backend/corrections/pipeline.py` |
| Raw transcript integrity | `backend/transcript/integrity.py` |
| Transcript layers (raw / working) | `backend/transcript/` |
| Snapshots, state hashing, certification lineage | `backend/transcript_state/` |
| Package assembly, validation, certification | `backend/packaging/` |

### 6A. Architectural anti-patterns — forbidden

The repo is now large enough that careless work creates duplicate ownership.
Do **not** create:

- a parallel transcript pipeline or correction engine;
- a duplicate transcript-state or snapshot system;
- an alternate geometry authority or pagination engine;
- an alternate certification or export flow.

**Extend the existing authority module instead.** If an existing module seems
inadequate, that is a Stop-and-Ask (Section 8), not a license to build a
second one.

---

## 7. High-risk transcript mutation zones

These areas can silently corrupt testimony. Treat any change here as
high-risk: trace the full path first (Section 8), and validate with
transcript-diff and mutation-detection checks afterward.

- audio preprocessing and chunk stitching;
- utterance assembly and transcript reconstruction;
- speaker reconciliation and mapping;
- the regex / deterministic correction pipeline;
- application of accepted AI edits to the working layer;
- pagination rebuild and export rendering.

A change in any of these zones is not complete until transcript integrity,
mutation detection, and the relevant regression tests have been verified.

These zones also trigger stricter documentation discipline: if a doc touching
one of these areas is stale, ambiguous, or contradicted by code, do not use it
as implementation authority without first reconciling it against the current
canonical docs and the live modules.

---

## 8. How agents must work

### 8A. Mandatory audit-first execution policy

**Do not begin implementation immediately.** For any non-trivial change, first:

1. Trace the complete execution path end to end.
2. Identify ownership boundaries, the transcript layers affected, mutation
   risks, the existing orchestration, and any existing implementation or stale
   / duplicated logic.
3. Produce a brief written audit summary **before** writing code.

Do **not** assume the task brief is correct, the architecture description is
current, a subsystem is unwired, or a module is unused. Verify every such claim
against the current code, the tests, the canonical docs, and
`wave_status_report.md`. The brief is a starting point, not ground truth.

### 8B. Refactor restrictions

Large or broad refactors are **forbidden unless explicitly requested.** Without
explicit human approval, do not: perform sweeping "cleanup" refactors, rename
architecture layers, move subsystem ownership, rewrite working orchestration,
or collapse the layered transcript states. Reuse existing architecture wherever
possible.

### 8B.1 No-silent-refactor rule

Do not use documentation cleanup, status reconciliation, or “governance”
changes as cover for architecture reinterpretation. If a repair would require
changing what module owns a concern, what layer is authoritative, or what a
certification/export path means, stop and ask.

### 8C. Stop-and-Ask

Before a schema migration, a file deletion, the creation of a new subsystem, or
any ambiguous-scope decision — stop and ask the human. Do not guess.

Stop immediately and report if:

- canonical ownership is ambiguous;
- two active docs appear to govern the same live behavior differently;
- transcript-layer ownership is unclear;
- mutation authority or certification authority is unclear;
- pagination, geometry, or export authority is split across parallel systems;
- code contradicts a canonical invariant;
- a doc appears both historical and operationally current;
- a requested “fix” would require architecture reinterpretation rather than
  factual documentation repair.

### 8D. Testing

Run `python -m pytest tests -q`. The repo pins `--basetemp=.pytest_tmp` in
`pyproject.toml`, so the plain command works on all machines — do not pass
`--basetemp` manually. Run the suite before and after changes; never leave it
red. Every behavioral change ships with a test.

Any transcript-related change additionally requires validation of: transcript
integrity, deterministic correction ordering, mutation-detection behavior,
pagination stability, certification lineage, diff-audit correctness, and export
correctness.

### 8E. Scope discipline

Do only what the task asks. If the work starts to widen, stop and ask. Keep
this file current: if the authority hierarchy, a code authority, or a core
invariant changes, update `CLAUDE.md` in the same change.

---

## 9. First-action checklist for a new task

1. Read this file, `README.md`, and `docs/wave_status_report.md`.
2. Identify which canonical doc (Section 3) and which code authority
   (Section 6) own the area you are changing.
3. Run the audit-first pass (Section 8A): trace the path, verify the brief's
   claims against the code — do not trust historical docs (Section 4).
4. Confirm the test baseline before starting (`python -m pytest tests -q`).
5. Make the change, with tests; keep the suite green; validate transcript
   safety (Sections 5, 5A, 8D) if the change touches a mutation zone
   (Section 7).
6. Update the matching canonical doc; leave historical docs untouched.
