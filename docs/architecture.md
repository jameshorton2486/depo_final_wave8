# DEPO-PRO Architecture

## Scope (current state)

DEPO-PRO is a local-first desktop application for producing certified
legal depositions. The current build consists of:

- A FastAPI backend (`backend/app.py`) exposing `/api/health` and
  serving the static frontend.
- A SQLite database initialized via `backend/db/migrations.py`
  (`schema_v1.sql`, Layer 1 tables) on application startup.
- A static HTML/Tailwind/JavaScript frontend in `frontend/` with six
  fully-rendered stage screens and an in-memory mock state.
- A PyWebView desktop runtime (`desktop/launcher.py`) that starts the
  backend on a thread and opens the local UI.

The backend currently exposes the health endpoint plus the
`/api/cases`, `/api/sessions`, and `/api/reporters` routers — see
`docs/wave2_step1_persistence.md` and
`docs/wave2_step2_full_stage1_persistence.md`. The entire Stage 1
intake form (Blocks 1–4) now round-trips to SQLite. Transcripts,
exhibits, and certification still live in the browser's in-memory
`state` object.

## Runtime Layout

- `backend/app.py` — FastAPI app, lifespan calls `initialize_database()`,
  mounts `frontend/` at `/`.
- `backend/database/init_db.py` — thin shim that delegates to
  `backend/db/migrations.apply()` and `backend/db/seeds.seed()`.
- `backend/db/` — canonical schema (v1), migrations runner, seed data.
- `backend/config.py` — `Settings` dataclass; reads `DEPOPRO_*` env vars.
- `frontend/` — static UI served as-is. `frontend/assets/js/router.js`
  fetches the per-stage HTML fragments under `frontend/screens/`.
- `desktop/launcher.py` — starts uvicorn on a background thread, waits
  for the socket, opens PyWebView.

## Data Model

Layer 1 (intake metadata) is captured in `backend/db/schema_v1.sql`
and matches `docs/ufm_schema_v1.md`:

- `cases`, `parties`, `attorneys`, `case_attorneys`
- `reporting_firms`, `reporting_firm_offices`, `reporters`
- `sessions`, `form_templates`
- `schema_version` (migration tracking)

UUID text primary keys, ISO-8601 timestamps in UTC, foreign keys
enforced (`PRAGMA foreign_keys = ON`). The seed pass installs two
form templates: `Generic Fallback v1` and `S.A. Legal Solutions v1`.

Layers 2–4 (transcript canonical form, review state, export
artifacts) are documented in `docs/ufm_schema_v1.md` but not yet
implemented in SQL.

## Frontend Foundation

- Top global header with brand, layer badges (RAW / WORKING /
  CERTIFIED), 6-stage progress nav, current-case label, save button.
- Six screens loaded into `#appRoot` by a tiny client-side router
  (`frontend/assets/js/router.js`).
- `state` (in `frontend/assets/js/state.js`) holds case info, file
  queue, transcript lines, exhibits, corrections memory, provenance
  log, and playback flags. Pure in-memory.
- Mock UFM intake parser, mock Deepgram progress simulator, mock
  certification chain. All work end-to-end inside the browser; none
  call the backend yet.

## Extension Path

In rough order of dependency:

1. ~~`backend/api/cases.py` — case-level intake.~~ **Done — Wave 2 Step 1.**
2. ~~`backend/api/sessions.py` — deponent, schedule, location, custodial attorney.~~ **Done — Wave 2 Step 2.**
3. ~~`backend/api/reporters.py` — CSR identity.~~ **Done — Wave 2 Step 2.**
4. `backend/api/nod.py` — NOD parser endpoint per
   `docs/nod_parser_spec.md`. Server-side PDF extraction.
5. `backend/api/attorneys.py` and `backend/api/reporting_firms.py` —
   replace the denormalized columns from Wave 2 Step 2 with proper
   models. Needed once the UI grows multi-counsel support.
6. `backend/services/` — domain logic shared by routers (template
   resolution, party normalization, etc.).
7. `backend/deepgram/` — batch and streaming transcription.
8. `backend/preprocessing/` — VAD, loudness normalization, format
   conversion before Deepgram.
9. `backend/transcript/` — Layer 2/3 canonical transcript handling
   (review flags, provenance, certification chain).
10. Real DOCX export via `python-docx` to replace the
    `Blob([...], { type: 'application/...' })` shortcut in
    `frontend/assets/js/screens/stage_6.js`.
