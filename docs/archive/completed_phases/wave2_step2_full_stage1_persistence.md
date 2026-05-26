> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 2 — Step 2: Full Stage 1 persistence + case picker

## What this build adds

Two things:

1. **The entire Stage 1 form now persists.** Blocks 2, 3, and 4 (witness
   logistics, court reporter credentials, custodial attorney) round-trip
   to SQLite alongside the Block 1 fields that already worked.
2. **A case picker dropdown** in the top header. Click the case label
   (next to the cloud-save icon) to see all saved cases, switch between
   them, or start a new one.

## New API endpoints

- `GET    /api/sessions?case_id=...`
- `POST   /api/sessions`
- `GET    /api/sessions/{session_id}`
- `PUT    /api/sessions/{session_id}`
- `DELETE /api/sessions/{session_id}`
- `GET    /api/reporters`
- `POST   /api/reporters`
- `GET    /api/reporters/{reporter_id}`
- `PUT    /api/reporters/{reporter_id}`
- `DELETE /api/reporters/{reporter_id}`

OpenAPI docs (browsable) at `http://127.0.0.1:8765/docs` while the app
is running.

## Schema changes

Additive only — all applied idempotently via the existing
`_ensure_column()` helper in `backend/db/migrations.py`. The
non-trivial ones are documented here for context:

| Table     | New column                 | Type | Why                                                                                            |
| --------- | -------------------------- | ---- | ---------------------------------------------------------------------------------------------- |
| sessions  | `scheduled_end_at`         | TEXT | Stage 1 has start AND end times; schema v1 only had `scheduled_at`                             |
| sessions  | `custodial_attorney_name`  | TEXT | Block 4 field. Properly belongs in `case_attorneys` once that router exists; denormalized v1   |
| sessions  | `requesting_party_name`    | TEXT | Block 4 field. Same denormalization caveat                                                     |
| reporters | `firm_registration_number` | TEXT | Block 3 field. Properly belongs in `reporting_firms` once that router exists; denormalized v1  |

If you ever delete `data\sqlite\depo_pro.db`, all schema changes are
re-applied on next startup — no manual migration step.

## Save flow (what happens when you click the cloud icon)

1. `POST` (or `PUT`) `/api/cases` with the Block 1 fields. Required:
   cause number. The case is the parent of everything else.
2. If Block 3 has at least a CSR name, `POST` (or `PUT`)
   `/api/reporters`.
3. If Block 2 has at least a date AND a deponent, `POST` (or `PUT`)
   `/api/sessions`, linking the case and (if it exists) the reporter
   via `reporter_id`.

A single toast summarizes what was saved (e.g., "Saved: case updated,
session updated, reporter updated."). Errors on any individual save
turn the toast amber and are logged to the console — earlier saves
still succeed.

## Hydration flow (what happens on app startup or "load case")

1. `GET /api/cases` — used to populate the picker dropdown.
2. The most recent case (`listing.cases[0]`) is loaded via
   `GET /api/cases/{id}`.
3. `GET /api/sessions?case_id={id}` — if any sessions exist, the most
   recent is merged into the form.
4. If that session has a `reporter_id`, `GET /api/reporters/{id}`
   merges Block 3 too.
5. The Stage 1 form is re-rendered from `state.caseInfo`.

## Case picker UI

The dropdown lives in the top header where the static
`Jenkins_v_Nexus.mp3` label used to be. It shows:

- Each saved case as a row (cause number + caption preview).
- The currently-loaded case highlighted in indigo.
- A `+ New case` button in the top-right of the dropdown that clears
  state and lets you start over.

Clicking a case loads it (case + session + reporter) and closes the
dropdown.

## What still does NOT persist

The full transcript editor (Stage 3), exhibits (Stage 4),
certification (Stage 5), and any of the Deepgram / streaming /
provenance state. Those belong to the transcript Layer 2/3/4 routers
that come later (after the NOD parser, ideally — see
`docs/architecture.md` for the dependency order).

Also still denormalized rather than fully modeled: the custodial
attorney and requesting party (live as plain text columns on
`sessions`), and the reporter's firm (lives as plain text on
`reporters`). Both have a path to proper modeling once the
`attorneys` and `reporting_firms` routers exist.

## Files touched

```
backend/
  api/
    __init__.py            UPDATED   re-export sessions, reporters
    sessions.py            NEW       router
    reporters.py           NEW       router
  db/
    migrations.py          UPDATED   _ensure_column() helper + 4 new columns
    repository.py          UPDATED   sessions_*() and reporters_*() functions
  models/
    __init__.py            UPDATED   re-export new models
    sessions.py            NEW       Pydantic models
    reporters.py           NEW       Pydantic models
  app.py                   UPDATED   include sessions + reporters routers

frontend/
  index.html               UPDATED   case picker UI replaces static case label
  assets/js/
    api.js                 UPDATED   sessions + reporters HTTP methods + translators
    state.js               UPDATED   added state.sessionId, state.reporterId
    app.js                 UPDATED   multi-resource save, multi-resource hydrate,
                                     loadCaseById, newCase, refreshCasePicker,
                                     toggleCasePicker
    screens/stage_1.js     UPDATED   stale topCaseLabel reference fixed

tests/
  conftest.py              UPDATED   added sample_session_payload,
                                     sample_reporter_payload, created_case fixtures
  test_sessions_api.py     NEW       12 tests
  test_reporters_api.py    NEW       8 tests

docs/
  wave2_step2_full_stage1_persistence.md   NEW   (this file)
  architecture.md                          UPDATED
```

## Verification on your machine

```powershell
pip install -r backend\requirements-dev.txt
python -m pytest tests\
```

Expected: **33 passed** (13 case + 12 session + 8 reporter).

Then:

```powershell
python main.py
```

Click the **Run AI Notes Parser** button on Stage 1 to populate the
whole form (or fill it in manually). Click the cloud-save icon. The
toast should say something like:

```
Saved: case created, session created, reporter created.
```

Close the app entirely. Run `python main.py` again. The form should
re-populate **including** witness name, dates, address, CSR name, CSR
license, firm registration, expiration, custodial attorney, and
requesting party — i.e., everything you saved.

Then click the case label at the top right — the dropdown should show
your saved case. Click `+ New case` to start a fresh form. Save that.
Click the dropdown again — both cases should be listed, with the
current one highlighted in indigo.

## Next milestones

Per `docs/architecture.md`:

1. **NOD parser** — `POST /api/nod/parse` accepting a PDF, returning
   parsed UFM JSON. Spec is in `docs/nod_parser_spec.md`. Needs a real
   sample NOD to validate against.
2. **Deepgram batch ingestion** — first real backend work past the
   Stage 1 form.
3. **Transcript Layer 2/3 tables** — needed before transcript edits
   can persist.
