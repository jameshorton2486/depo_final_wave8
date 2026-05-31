# Intake Drift Bug Note — 2026-05-30

## Summary

Two contaminated test cases exposed a real intake-layer drift bug:

- `6253b304-c5aa-4603-8934-7e44e009456f`
- `2066c0f3-f3b7-4275-8c63-6f3ce4655adc`

The issue is **not** a wrong join key. Packaging and export read the expected
keys:

- `case_id -> cases`
- `session_id -> sessions`
- `case_id -> data/cases/{case_id}/stage1_intake.json`

The confirmed defect is that Stage 1 JSON artifacts and relational `cases` /
`sessions` rows can drift apart under the same `case_id`.

## Confirmed Findings

### 1. The two stores diverged under the same `case_id`

For both contaminated cases, `stage1_intake.json` had a newer `updated_at`
timestamp than the corresponding `cases` / `sessions` rows. That shows later
Stage 1 artifact rewrites without a matching relational rewrite.

Observed pattern:

- SQL rows created first
- Stage 1 JSON updated later
- SQL rows remained unchanged

### 2. This can happen in normal UI flow

`frontend/assets/js/app.js::simulateSave()` performs separate writes:

1. create/update `cases` / `sessions`
2. `syncStage1Artifacts(state, 'operator')`

But Stage 1 also has sync-only paths in
`frontend/assets/js/screens/stage_1.js`:

- `persistStage1ArtifactsIfBound('nod-parser')`
- `persistStage1ArtifactsIfBound('text-parser')`
- `persistStage1ArtifactsIfBound('field-confirmed')`
- `persistStage1ArtifactsIfBound('confirm-all')`

Those paths require an already-bound `state.caseId` / `state.sessionId`, but do
**not** also rewrite `cases` / `sessions`.

That makes this a real normal-operator drift path, not only a test harness
artifact.

### 3. The cause-number duplication was cross-store, not duplicate SQL rows

Cause number `2025CI11923` appeared:

- in the `cases` row for `6253...`
- in `stage1_intake.json` for `2066...`

Only one SQL `cases` row actually held that cause number. The apparent
duplication was caused by cross-store drift.

### 4. Foreign keys are not enforcing integrity

`PRAGMA foreign_keys = 0` in the local SQLite database. The database therefore
does not prevent application-layer drift between related rows.

This is not the root cause, but it raises the value of an application-layer
guard.

## Cleanup Performed

The two contaminated test cases were removed after a timestamped SQLite backup:

- database backup created under `data/sqlite/`
- scoped delete executed in a single transaction
- only these two `case_id`s and their dependent `job_id`s were removed
- `data/cases/{case_id}` folders removed for both cases

## Severity

High enough to warrant a guarded remediation pass because it can silently render
crossed records, but contained to the intake layer. It does **not** indicate a
broken packaging join architecture.

## Recommended Remediation Order

1. Add a hard-fail mismatch guard before render/package work proceeds.
2. Audit and tighten the sync-only Stage 1 callsites.
3. Decide whether to make the writes atomic or to reconcile relational rows on
   sync-trigger paths.

## Explicit Non-Finding

This bug does **not** invalidate the appearances persistence fix committed in
`516203f`. That fix writes normalized relational data and remains safe.
