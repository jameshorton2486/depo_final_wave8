# DEPO-PRO

Local-first desktop workspace for producing certified legal depositions.
FastAPI backend, SQLite persistence (Layer 1 schema), static
HTML/Tailwind/JavaScript frontend, PyWebView desktop runtime.

## Status

| Layer | State | Notes |
| --- | --- | --- |
| Desktop launcher | working | PyWebView shell over the same FastAPI backend |
| FastAPI backend | operational | 12 registered domain routers plus `/api/health` |
| SQLite persistence | operational | append-only schema migrations through `schema_v12.sql` |
| Frontend workflow | operational | Stage 1–6 UI is wired to the real backend |
| Persistence API | operational | cases, sessions, reporters, transcripts, snapshots, exhibits, packaging |
| NOD parser | operational | real parser + intelligence path, backend wired |
| Deepgram ingestion | operational | live Deepgram plus explicit offline validation mode |
| AI review | operational | advisory-only review with explicit apply flow |
| Export engine | operational | working export + certified snapshot export |
| Certification chain | operational | snapshot lock -> package assemble -> certify |

This is no longer a mock frontend. Stage 1 intake, Stage 2 transcript
ingestion, Stage 3 working transcript persistence, Stage 4 exhibits,
Stage 5 certification lineage, and Stage 6 export all persist through
the FastAPI + SQLite backend.

## Environment Setup

Targets:

- Windows 11
- Python 3.13
- PyCharm or another local Python IDE

Create and activate a virtual environment:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r backend\requirements.txt
```

Optional frontend tooling for the maintenance scripts and local Tailwind build:

```powershell
npm install
```

Copy `.env.example` to `.env` and adjust if needed. All variables are
optional; defaults match the README commands.

## Launching the Application

Backend only (browser-friendly dev loop):

```powershell
uvicorn backend.app:app --host 127.0.0.1 --port 8765 --reload
```

Then visit `http://127.0.0.1:8765/`.

Desktop shell (PyWebView wrapping the same backend):

```powershell
python desktop\launcher.py
```

The backend serves the static frontend from `frontend/` and applies the
full append-only SQLite migration chain to `data\sqlite\depo_pro.db` on
startup.

## Project Layout

```text
depo_final_wave8/
├── backend/
│   ├── api/              # FastAPI routers (cases, sessions, intake, transcripts, packaging, ...)
│   ├── database/         # initialize_database() entrypoint (delegates to db/)
│   ├── db/               # canonical schema + migrations + seeds
│   │   ├── schema_v1.sql
│   │   ├── ...
│   │   ├── schema_v12.sql
│   │   ├── migrations.py
│   │   └── seeds.py
│   ├── deepgram/         # live + offline transcription provider paths
│   ├── export/           # DOCX / PDF / TXT / RTF export writers
│   ├── packaging/        # certified package assembly + validation
│   ├── pagination/       # pagination + page geometry pipeline
│   ├── services/         # intake, keyterms, NOD parsing, workspace helpers
│   ├── transcript/       # ingest, repository, render, working state, provenance
│   ├── transcript_state/ # snapshots, rollback, state hashing
│   ├── app.py            # FastAPI app + static mount
│   └── config.py         # Settings dataclass + env wiring
├── desktop/
│   └── launcher.py       # PyWebView runtime
├── frontend/             # static UI (local Tailwind build, vanilla JS)
│   ├── index.html
│   ├── assets/{css,js}/
│   └── screens/          # stage_1_intake.html … stage_6_export.html
├── data/                 # runtime files (sqlite, cases, exports, audio, …)
├── docs/                 # ufm_schema_v1.md, nod_parser_spec.md, archive/completed_phases/architecture.md (historical — superseded; see CLAUDE.md)
├── scripts/              # *.bat maintenance helpers (Windows)
├── tests/                # backend + workflow integration tests
├── main.py               # python main.py == python desktop/launcher.py
├── pyproject.toml
└── requirements.txt
```

## Environment Variables

All optional. Read from `.env` (gitignored) or the process environment.

| Variable                     | Default     | Purpose                              |
| ---------------------------- | ----------- | ------------------------------------ |
| `DEPOPRO_HOST`               | `127.0.0.1` | Backend bind host                    |
| `DEPOPRO_PORT`               | `8765`      | Backend bind port                    |
| `DEPOPRO_DEBUG`              | `0`         | `1` enables DevTools + access logs   |
| `DEPOPRO_TRANSCRIPTION_PROVIDER` | `deepgram` | `deepgram` or `offline` runtime transcription mode |
| `DEPOPRO_LAUNCHER_SMOKE_TEST`| unset       | `1` makes launcher exit before GUI   |
| `DEEPGRAM_API_KEY`           | unset       | live Deepgram key for authoritative transcription |

## Maintenance Scripts

```powershell
scripts\cleanup_python.bat       # black + ruff --fix
scripts\cleanup_frontend.bat     # prettier + eslint --fix
scripts\verify_project.bat       # smoke test: imports, DB, FastAPI, launcher
scripts\full_maintenance.bat     # all of the above
```

## Current Focus

1. Real-world MVP validation using `docs/audits/REAL_WORLD_VALIDATION_LOG.md`.
2. Workflow trust verification across Stage 1–6 with real data.
3. Narrow stabilization fixes discovered during validation, not broad architecture rewrites.

See `CLAUDE.md` for current documentation authority and
`docs/ufm_schema_v1.md` for the canonical data contract.
