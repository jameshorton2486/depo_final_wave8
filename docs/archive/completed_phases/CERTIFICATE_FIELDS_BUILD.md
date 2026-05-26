> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# CERTIFICATE_FIELDS_BUILD.md — Autonomous Build Plan

## Mission

Build ONE feature: a data-capture path for the certificate/caption
fields that currently render as `[BRACKETED]` placeholders in
`backend/packaging/admin_pages.py`, so a Certified Transcript Package
can be fully populated instead of held at DRAFT for missing data.

You are a disciplined senior engineer. Work sequentially and
autonomously. Continue to the next phase automatically. Stop only when
the mission is complete or genuinely blocked.

## Scope — strict

IN scope: capturing, persisting, and surfacing the missing
deposition-metadata fields, and feeding them into the packaging
engine's `metadata` dict.

OUT of scope — DO NOT TOUCH: pagination, geometry, the correction
engine, Stage S, AI review, the transcript body, or any wave's
existing behavior. If a change seems to require touching those, stop
and log it in `BLOCKERS.md` instead.

## Phase 0 — Audit first

1. Run `python -m pytest tests/ -q`; record the baseline (expect
   442 passed, 1 skipped).
2. Read `backend/packaging/admin_pages.py` and list EVERY field that
   resolves to a `[BRACKETED]` placeholder — the caption fields and
   the certificate fields (time used per party, officer's charges,
   custodial attorney, SBOT numbers, CSR expiration, firm
   registration, examination waived/retained, and any others).
3. Trace how `metadata` reaches the packaging engine: the
   `AssembleRequest` / `CertifyRequest` models in
   `backend/api/packaging.py`, and how `assemble` / `certify` pass
   `metadata` through. Determine where captured data must be stored
   and how it must be shaped to land in that `metadata` dict.
4. Write findings to `AUDIT_CERT.md`: the complete field list, each
   field's type, and whether it belongs to the case, the reporter,
   the session, or the deposition event.
5. Do NOT write feature code until the audit is complete.

## Completion criteria — strict

This feature is COMPLETE only when ALL hold:
- Every placeholder field has a defined storage location (a DB column
  or table) and a real persistence path.
- The fields are reachable end-to-end: a backend API accepts them,
  persists them, and they flow into the packaging `metadata` dict.
- A package assembled for a job with these fields filled produces a
  certificate with NO `[BRACKETED]` placeholders.
- The full test suite is green.
- The behavior is deterministic.

A UI form alone, or fields that exist but never reach `metadata`, does
NOT count as complete.

## Phase 1 — Data model

- Decide the storage: extend an existing table (case / reporter /
  session) or add a new `deposition_metadata` table keyed by job or
  case. Prefer extending existing tables where a field clearly belongs
  to that entity (e.g. CSR expiration belongs to the reporter).
- Add a new schema file `backend/db/schema_vN.sql` (next number in
  sequence) — never edit an existing schema file.
- Update the repository layer with save/get functions for the new
  fields.
- Add tests for the persistence layer.

## Phase 2 — API

- Add an endpoint (or extend an existing one) to accept and persist
  the deposition-metadata fields. Mirror the style of
  `backend/api/packaging.py` and `snapshots.py`.
- Register any new router in `backend/app.py`.
- Add API tests.

## Phase 3 — Wire into packaging

- Update `backend/api/packaging.py` so the `assemble` / `certify`
  endpoints gather the persisted fields and merge them into the
  `metadata` dict passed to the packaging engine. Captured data should
  populate automatically; an explicit request body may still override.
- Add a test that assembles + certifies a job whose fields are filled
  and asserts the resulting certificate contains NO `[` placeholder
  character in its lines.

## Phase 4 — UI (Certify screen)

- Add a simple, clean form to the Stage 5 Certify screen
  (`frontend/screens/stage_5_certify.html`,
  `frontend/assets/js/screens/stage_5.js`) to enter these fields
  before certification. Match the existing visual style — no new
  frameworks, no cosmetic redesign of the screen.
- The form posts to the Phase 2 API.

## Rules

- One authority per concern. Do not duplicate existing systems.
- Run the FULL test suite after every phase. Never proceed on red.
- `git add -A && git commit` after every phase with a clear message.
- If a real blocker appears (a field whose correct source is genuinely
  ambiguous, a legal question, a schema decision you cannot make
  safely), do NOT stop the whole run: log it in `BLOCKERS.md`, use the
  most reasonable default, mark that field PARTIAL, and continue.
- Maintain `AUDIT_CERT.md` and `PROGRESS_CERT.md` throughout.
- Do not invent statutory wording — the wording in `admin_pages.py` is
  already correct and final. This task only feeds it DATA.

## Stop conditions

Stop when every placeholder field is captured, persisted, wired into
`metadata`, and a filled job certifies with no placeholders — or when
all remaining fields are blocked. Write a final summary to
`PROGRESS_CERT.md`: what is complete, what is partial, what is blocked.

Begin with Phase 0 now.
