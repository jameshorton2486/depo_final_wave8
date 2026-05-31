# Repository Topology Report

Audit basis: tracked files only (`git ls-files`), read-only inspection on 2026-05-30.

## Top-Level Folders

| Path | Tracked files | Notes |
|---|---:|---|
| `backend/` | 147 | FastAPI app, persistence, transcript pipeline, packaging/export, NOD parser |
| `data/` | 47 | Tracked fixture-like transcript JSON and `.gitkeep` anchors |
| `desktop/` | 1 | Desktop launcher wrapper |
| `docs/` | 82 | Governance, specs, archive, audits, UFM audit artifacts |
| `frontend/` | 27 | Static HTML/CSS/JS app, routed stage screens |
| `scripts/` | 5 | Operator/maintenance scripts |
| `tests/` | 71 | Pytest suite plus frontend contract tests |
| `tools/` | 1 | CLI diagnostic helper |

Top-level tracked files outside folders:

- `.env.example`
- `.eslintrc.json`
- `.gitignore`
- `.prettierrc`
- `CLAUDE.md`
- `README.md`
- `collect_intake_audit_bundle.ps1`
- `depo_pack_frontend.ps1`
- `development_workflow.md`
- `main.py`
- `package-lock.json`
- `package.json`
- `postcss.config.js`
- `pyproject.toml`
- `requirements.txt`
- `tailwind.config.js`

## Major Subsystems

### Backend

- `backend/app.py`: FastAPI app root; includes all API routers and mounts the frontend static app.
- `backend/api/`: HTTP surface for cases, sessions, reporters, intake, NOD, transcripts, packaging, depo meta, corrections, AI review, snapshots.
- `backend/db/`: SQLite repository and migrations.
- `backend/models/`: Pydantic request/response and canonical models.
- `backend/services/`: intake artifact store, intake text parser, NOD parser, workspace helpers, keyterms, speaker mapping.
- `backend/transcript/`: transcript job, storage, render, ingest, provenance, export-prep.
- `backend/transcript_state/`: snapshots and state hashes.
- `backend/packaging/`: administrative pages, indexes, package assembly, certification validation.
- `backend/export/`: DOCX/PDF/RTF/TXT writers and export service.
- `backend/geometry/` + `backend/pagination/`: layout rules, wrapping, pagination.
- `backend/stage_s/` + `backend/lexicon/` + `backend/corrections/` + `backend/ai_review/`: transcript cleanup/structure pipeline.

### Frontend

- `frontend/index.html`: static shell.
- `frontend/assets/js/router.js`: screen router; fetches `frontend/screens/stage_*.html`.
- `frontend/assets/js/app.js`: global state + save flow.
- `frontend/assets/js/screens/stage_*.js`: per-screen logic.
- `frontend/assets/css/tailwind.css`: built runtime CSS.
- `frontend/src/styles/tailwind.css`: Tailwind source file compiled by `package.json` scripts.

### Documentation / Governance

- `CLAUDE.md`: repo governance and ownership rules.
- `docs/ACTIVE_SPEC_REGISTRY.md`, `docs/SYSTEM_OWNERSHIP.md`, `docs/BLOCKERS.md`: active control docs.
- `docs/DEPO-PRO_UFM_Data_Dictionary_v2.md`, `docs/DEPO-PRO_Field_Template_Matrix.md`: active blueprint docs.
- `docs/archive/`: historical but intentionally retained phase records.
- `docs/ufm_audit/`: current UFM / cert-pipeline audit outputs.

## File Counts by Type

Tracked-file counts:

| Type | Count |
|---|---:|
| Python (`.py`) | 203 |
| Markdown (`.md`) | 79 |
| JSON (`.json`) | 45 |
| DOCX (`.docx`) | 4 |
| PDF (`.pdf`) | 1 |
| SQL (`.sql`) | 12 |
| HTML (`.html`) | 8 |
| JavaScript (`.js`) | 18 |
| CSS (`.css`) | 3 |
| PowerShell (`.ps1`) | 2 |
| TXT (`.txt`) | 3 |
| TOML (`.toml`) | 1 |
| No extension | 13 |

Tracked ZIP files: **0**

## Repository Size

- Total tracked files: **397**
- Approximate tracked size: **287,051,231 bytes** (~273.8 MiB)

## Notes for Cleanup Scope

- Raw environment folders (`.venv/`, `node_modules/`, caches) were excluded from audit classification.
- `data/` is part of the tracked project surface here; it is not disposable by default because runtime, tests, and audit work all rely on pieces of it.
