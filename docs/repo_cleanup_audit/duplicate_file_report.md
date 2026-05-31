# Duplicate File Report

Audit basis:

- exact duplicates by SHA-256
- basename collisions
- repository-wide reference scan to identify canonical versions

## Exact Duplicates

### Intentional placeholder files

Identical `.gitkeep` files are expected and not cleanup issues:

- `data/audio/.gitkeep`
- `data/cases/.gitkeep`
- `data/exports/.gitkeep`
- `data/sqlite/.gitkeep`
- `data/transcripts/.gitkeep`
- `docs/.gitkeep`
- `docs/audits/.gitkeep`
- `frontend/assets/css/.gitkeep`
- `frontend/assets/js/.gitkeep`
- `frontend/screens/.gitkeep`
- `tests/.gitkeep`

### Empty package markers

- `tests/__init__.py`
- `tests/corrections/__init__.py`

These are intentional package markers, not useful deletion targets by themselves.

## Basename Collisions (Not Automatically Duplicates)

### Canonical keep-both pairs

| Name | Paths | Why both exist |
|---|---|---|
| `development_workflow.md` | root + `docs/` | Explicitly separated in `CLAUDE.md`; runtime trust behavior vs local dev workflow |
| `tailwind.css` | `frontend/src/styles/tailwind.css` + `frontend/assets/css/tailwind.css` | Source file + compiled runtime artifact referenced by `package.json` and `frontend/index.html` |
| `requirements.txt` | root + `backend/requirements.txt` | Distinct dependency manifests |
| `README.md` | root + multiple docs subfolders | Folder-local readmes are expected |

### Review-manually pairs

| Name | Paths | Canonical view | Recommendation |
|---|---|---|---|
| `WAVE10_FOUNDATION_NOTES.md` | `backend/corrections/` and `docs/archive/completed_phases/` | Backend copy is still cited by active spec registry; archive copy is historical | KEEP both for now |
| `client.py` | `backend/ai_review/`, `backend/deepgram/` | Different subsystems | KEEP |
| `cases.py`, `reporters.py`, `sessions.py`, `transcripts.py` | `backend/api/` vs `backend/models/` | API layer vs model layer | KEEP |
| `repository.py` | `backend/db/` vs `backend/transcript/` | Different storage owners | KEEP |

### High-interest generated duplicates-by-pattern

These are repeated filenames across transcript fixture folders, but each belongs to a separate tracked transcript snapshot and is not a duplicate candidate:

- `asr_response.json`
- `raw.json`
- `working.json`

## Likely Canonical Versions

- Runtime CSS canonical source: `frontend/src/styles/tailwind.css`
- Runtime CSS canonical output: `frontend/assets/css/tailwind.css`
- Governance workflow canonical pair:
  - runtime trust modes: `development_workflow.md`
  - local dev maintenance: `docs/development_workflow.md`

## Duplicate Conclusions

- Exact duplicates are intentional placeholders/package markers.
- Basename collisions are mostly legitimate layer or archive separations.
- No duplicate set has enough proof to mark one side `SAFE_DELETE`.
