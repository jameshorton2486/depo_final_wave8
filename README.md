# DEPO-PRO

Local-first desktop workspace for producing certified legal depositions.
FastAPI backend, SQLite persistence (Layer 1 schema), static
HTML/Tailwind/JavaScript frontend, PyWebView desktop runtime.

## Status

| Layer            | State          | Notes                                                       |
| ---------------- | -------------- | ----------------------------------------------------------- |
| Desktop launcher | working        | PyWebView shell, FastAPI on background thread               |
| FastAPI backend  | working (thin) | `/api/health` only; no domain routers yet                   |
| SQLite (Layer 1) | working        | v1 schema applied on startup; `form_templates` seeded       |
| Frontend (UI)    | working (mock) | Six interactive stages, in-memory mock data, no persistence |
| Persistence API  | not started    | next milestone — see "Next up" below                        |
| NOD parser       | not started    | spec in `docs/nod_parser_spec.md`                           |
| Deepgram         | not started    | reserved package only                                       |
| AI cleanup       | not started    | reserved package only                                       |
| DOCX export      | not started    | current export is a text blob with `.docx` extension        |

The frontend currently runs entirely off the in-memory `state` object
in `frontend/assets/js/state.js`. Refresh wipes everything; this is by
design until the persistence API lands.

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

Optional frontend tooling for the maintenance scripts:

```powershell
npm install --save-dev prettier eslint
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

The backend serves the static frontend from `frontend/` and applies
the v1 SQLite schema to `data\sqlite\depo_pro.db` on startup.

## Project Layout

```text
depo_final/
├── backend/
│   ├── api/              # FastAPI routers (placeholder; nothing wired yet)
│   ├── database/         # initialize_database() entrypoint (delegates to db/)
│   ├── db/               # canonical schema + migrations + seeds
│   │   ├── schema_v1.sql
│   │   ├── migrations.py
│   │   └── seeds.py
│   ├── deepgram/         # reserved
│   ├── models/           # reserved
│   ├── preprocessing/    # reserved
│   ├── services/         # reserved
│   ├── transcript/       # reserved
│   ├── app.py            # FastAPI app + static mount
│   └── config.py         # Settings dataclass + env wiring
├── desktop/
│   └── launcher.py       # PyWebView runtime
├── frontend/             # static UI (Tailwind CDN, vanilla JS)
│   ├── index.html
│   ├── assets/{css,js}/
│   └── screens/          # stage_1_intake.html … stage_6_export.html
├── data/                 # runtime files (sqlite, cases, exports, audio, …)
├── docs/                 # ufm_schema_v1.md, nod_parser_spec.md, architecture.md
├── scripts/              # *.bat maintenance helpers (Windows)
├── tests/                # empty; tests live here once written
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
| `DEPOPRO_LAUNCHER_SMOKE_TEST`| unset       | `1` makes launcher exit before GUI   |
| `DEEPGRAM_API_KEY`           | unset       | Required once Deepgram lands         |

## Maintenance Scripts

```powershell
scripts\cleanup_python.bat       # black + ruff --fix
scripts\cleanup_frontend.bat     # prettier + eslint --fix
scripts\verify_project.bat       # smoke test: imports, DB, FastAPI, launcher
scripts\full_maintenance.bat     # all of the above
```

## Next Up (the work tracked elsewhere)

1. Persistence API: `POST/GET/PUT /api/cases`, swap the frontend
   `simulateSave()` toast for a real round-trip against the v1 schema.
2. NOD parser endpoint: `POST /api/nod/parse` per
   `docs/nod_parser_spec.md`. Start with the Type A (S.A. Legal
   Solutions) form layout.
3. Deepgram batch ingestion to replace the mock progress simulator on
   Stage 2.

See `docs/architecture.md` for the four-layer model and
`docs/ufm_schema_v1.md` for the canonical data contract.
