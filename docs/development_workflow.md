> DOCUMENT STATUS: ACTIVE REFERENCE
> Scope: developer setup, local maintenance, DB rebuild workflow, and daily commands.
> This file is for local development workflow. It does not own runtime transcript trust behavior; that lives in the root `development_workflow.md`.

# Development Workflow

## Setup

1. Create and activate a Python 3.13 virtual environment.
2. `pip install -r backend\requirements.txt`
3. Optional: `npm install --save-dev prettier eslint` for the frontend
   maintenance scripts.
4. Optional: `cp .env.example .env` and edit. All variables have
   working defaults; only edit if you need to.

## Daily Commands

Backend dev server (auto-reload on file change):

```powershell
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8765
```

Desktop launcher (PyWebView):

```powershell
python desktop\launcher.py
```

## Maintenance

```powershell
scripts\cleanup_python.bat       :: black + ruff --fix
scripts\cleanup_frontend.bat     :: prettier + eslint --fix on frontend/
scripts\verify_project.bat       :: import + DB + FastAPI + launcher smoke test
scripts\full_maintenance.bat     :: runs all three in order
```

## Database

The SQLite DB lives at `data\sqlite\depo_pro.db` and is created on
first run by the FastAPI lifespan via
`backend.db.migrations.apply()`. To rebuild it from scratch, stop
the server and delete the file — it will be regenerated on next
startup.

Migrations are hand-rolled SQL files in `backend/db/schema_vN.sql`.
The migrations runner is idempotent; running `migrations.apply()`
against an up-to-date DB is a no-op.

Seeds (`backend/db/seeds.py`) use `INSERT OR IGNORE` on unique
columns; re-running is safe.
