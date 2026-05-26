> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 2 — Step 1: Case persistence

## What this build adds

A round-trippable `cases` API. The Stage 1 intake form now saves to
SQLite and reloads on app restart. Concretely:

- `POST /api/cases` — create a new case row
- `GET /api/cases` — list cases, newest first
- `GET /api/cases/{case_id}` — read one
- `PUT /api/cases/{case_id}` — partial update
- `DELETE /api/cases/{case_id}` — remove

The cloud-save button in the header (previously a fake toast) now hits
the real backend. On every app launch the frontend asks the server for
the most recent case and re-populates Stage 1 from it.

## What persists vs. what does not

This first persistence pass covers only the **case-level** UFM fields,
because those are the ones with a settled table in `schema_v1.sql`.

**Survives a refresh:**

- Cause Number (`case_number_value`)
- Full Caption / Style (`caption_full`)
- Court / Judicial District (`judicial_district`)
- County of Venue (`county`)
- State (`state`)
- Jurisdiction type and case-number label (defaulted to `texas_state` /
  `cause_no` — explicit picker UI comes later)

**Does NOT survive a refresh yet** (will be added in the next
milestones, as the matching backend routers come online):

- Deponent / Witness Name → belongs in `sessions.witness_name`
- Deposition Date, Start Time, End Time → belong in
  `sessions.scheduled_at` / new column for end time
- Physical / Virtual Address → `sessions.location_address`
- CSR Name, License, Cert Expiration → `reporters`
- Firm Registration → `reporting_firms`
- Custodial Attorney / Requesting Party → `case_attorneys` /
  `attorneys`
- Signature, certification state → certification chain (Phase D)
- Transcript lines, exhibits, corrections, provenance log → Layer 2/3
  tables (Phase C)

If you save the form now and refresh, the five case-level fields will
come back and the rest will be blank. That's expected.

## Files touched

```
backend/
  api/
    __init__.py            UPDATED   (re-export cases module)
    cases.py               NEW       (router with CRUD endpoints)
  db/
    repository.py          NEW       (SQL access for cases)
  models/
    __init__.py            UPDATED   (re-export Pydantic models)
    cases.py               NEW       (CaseCreate, CaseUpdate, CaseRead, CaseList)
  app.py                   UPDATED   (include cases router)
  config.py                UPDATED   (unfrozen Settings for test override)
  requirements-dev.txt     NEW       (pytest + httpx)

frontend/
  assets/js/
    api.js                 NEW       (HTTP client; UI<->backend field translation)
    state.js               UPDATED   (added state.caseId)
    app.js                 UPDATED   (real save + startup hydration)
  index.html               UPDATED   (load api.js after state.js)

tests/
  __init__.py              NEW
  conftest.py              NEW       (isolated DB per test, FastAPI TestClient fixture)
  test_cases_api.py        NEW       (13 tests, all passing)

docs/
  wave2_step1_persistence.md   NEW   (this file)
  architecture.md              UPDATED (note new router)
```

## Verifying it works locally

After installing the dev dependencies once:

```powershell
pip install -r backend\requirements-dev.txt
```

You can run the test suite:

```powershell
python -m pytest tests\ -v
```

Expected: 13 passed.

Then run the app:

```powershell
python main.py
```

Click around the Stage 1 form, then click the small **cloud-save**
button at the top right (next to the case label). You should see a
toast like:

```
Case 2024-CI-28593 saved (id 1460cf97…).
```

Close the app. Reopen it. The Stage 1 form should re-populate the
cause number, caption, court, county, and state from the database.

If something goes wrong with the backend, the app falls back to a
warning toast (`Workspace initialized (offline mode — no server).`)
and continues to work as before with in-memory state only — saving
will simply fail with an error toast.

## Manual API checks (optional)

While the app is running you can poke the API from PowerShell or any
HTTP client:

```powershell
# List cases
curl http://127.0.0.1:8765/api/cases

# Read one (replace with a real case_id)
curl http://127.0.0.1:8765/api/cases/<case_id>

# Create one
curl -Method POST http://127.0.0.1:8765/api/cases `
     -ContentType "application/json" `
     -Body '{"case_number_value":"2024-CI-99999","caption_full":"TEST"}'
```

The OpenAPI docs are auto-generated at:

```
http://127.0.0.1:8765/docs
```

(Browse to that URL while the app is running.)

## Known limitations

- One case per app launch. The startup hydration loads the most
  recent case. There is no "switch case" or "new case" UI yet — that
  needs a case picker.
- No optimistic concurrency. Two writers updating the same case will
  last-write-win.
- Errors from the API are surfaced as toasts but don't gate the form.
  You can keep typing and re-save.

## Next milestones

In dependency order, these are the natural follow-ups:

1. **Sessions router.** Same pattern — `POST/GET/PUT /api/sessions`.
   Once it exists, the date/time/address/witness fields persist too.
2. **Reporters router.** Same again. Once it exists, CSR fields
   persist.
3. **Case picker UI.** A small dropdown in the top bar to switch
   between saved cases, plus a "New case" button. Becomes useful once
   you have more than one case in the database.
4. **NOD parser.** `POST /api/nod/parse` accepting a PDF, returning
   the parsed UFM as JSON. Spec is in `docs/nod_parser_spec.md`.
