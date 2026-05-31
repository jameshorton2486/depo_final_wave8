# Runtime / Python Dependency Map

Audit basis:

- static import graph from tracked Python files
- runtime roots: `main.py`, `desktop/launcher.py`, `backend/app.py`
- additional evidence: pytest imports, CLI usage, doc/spec references

Important caution: “not reachable from the app root” is **not** enough to mark a file unused. Test-only, CLI-only, and governance-only code stays out of `UNUSED`.

## Runtime Entry Points

- `main.py` imports `desktop.launcher`
- `desktop/launcher.py` imports `backend.app`
- `backend/app.py` includes all FastAPI routers and mounts frontend static files

App-wiring evidence:

- `backend/app.py:82-93` includes the API routers
- `backend/app.py:96-98` mounts the frontend static app
- `frontend/assets/js/router.js:7-13` maps stage numbers to `frontend/screens/stage_*.html`
- `frontend/index.html:158-164` loads all per-stage JS files
- `frontend/assets/js/app.js:386-476` performs the main save flow

## Classification Rules

- `ACTIVE_RUNTIME`: reachable from the runtime roots or used directly by mounted routes / export path
- `OPTIONAL_RUNTIME`: explicit CLI/test/support code, or code used by supported but not default runtime flows
- `UNKNOWN`: no app-root reachability and no hard execution proof, but enough references that deletion would be unsafe
- `UNUSED`: no import/use proof after repository-wide reference scan

## ACTIVE_RUNTIME

Covered by direct runtime reachability:

- `main.py`
- `desktop/launcher.py`
- `backend/app.py`

Active backend subsystems (all files in these paths are runtime-reachable from the app root):

- `backend/ai_review/*.py`
- `backend/api/*.py`
- `backend/config.py`
- `backend/corrections/*.py`
- `backend/database/init_db.py`
- `backend/db/*.py`
- `backend/deepgram/*.py`
- `backend/export/__init__.py`
- `backend/export/docx_writer.py`
- `backend/export/export_service.py`
- `backend/export/pdf_writer.py`
- `backend/export/rtf_writer.py`
- `backend/export/txt_writer.py`
- `backend/geometry/engine.py`
- `backend/geometry/profile.py`
- `backend/lexicon/merge.py`
- `backend/lexicon/model.py`
- `backend/lexicon/stage_x.py`
- `backend/models/canonical.py`
- `backend/models/cases.py`
- `backend/models/reporters.py`
- `backend/models/sessions.py`
- `backend/models/transcripts.py`
- `backend/packaging/*.py`
- `backend/preprocessing/__init__.py`
- `backend/preprocessing/presets.py`
- `backend/preprocessing/probe.py`
- `backend/services/*.py`
- `backend/services/nod_parser/*.py`
- `backend/stage_s/__init__.py`
- `backend/stage_s/audit.py`
- `backend/stage_s/colloquy.py`
- `backend/stage_s/line_builder.py`
- `backend/stage_s/models.py`
- `backend/stage_s/objection_handler.py`
- `backend/stage_s/off_record.py`
- `backend/stage_s/parentheticals.py`
- `backend/stage_s/render_state.py`
- `backend/stage_s/renderer.py`
- `backend/stage_s/transitions.py`
- `backend/transcript/*.py`
- `backend/transcript_state/*.py`

Why these are active:

- API routes are included in `backend/app.py`
- transcript export path calls `backend.export.export_service` from `backend/api/transcripts.py`
- packaging path calls `backend.packaging.assemble_package` from `backend/api/packaging.py`
- frontend save/intake flows hit the included API routes, which import these backends

## OPTIONAL_RUNTIME

These files are real, referenced, and executable, but not part of the default app-import spine:

### CLI / operator tools

- `scripts/bind_transcript_job_to_case.py`
  - Evidence: standalone argparse script; not imported by app root
- `tools/run_diff.py`
  - Evidence: CLI wrapper over `backend.diagnostics`

### Test/doc-supported backend helpers

- `backend/export/export_validation.py`
  - Evidence: referenced by `tests/test_export_validation.py`, `docs/EXPORT_AND_CERTIFICATION_PIPELINE.md`, `docs/SYSTEM_OWNERSHIP.md`
- `backend/pagination/flow_rules.py`
  - Evidence: imported by `backend/pagination/paginator.py`; referenced by tests and docs, but not reached from the app root path used today
- `backend/pagination/paginator.py`
  - Evidence: used by tests (`tests/test_wave19_pagination_geometry.py`, `tests/test_export_validation.py`, `tests/test_wave20_packaging.py`) and docs; not reached from the active app root graph
- `backend/diagnostics/ref_import.py`
  - Evidence: used by `tests/diagnostics/test_diagnostics_hardening.py`; referenced by `docs/architecture/transcript_engine/transcript_diff_harness_spec.md`

### Test-only Python

All tracked files under:

- `tests/**/*.py`

These are not runtime imports, but they are actively required by the test suite.

## UNKNOWN

These files are not reached from the app root and do not have strong execution evidence, but they still have enough repository references that deletion is unsafe:

- `backend/__init__.py`
- `backend/database/__init__.py`
- `backend/diagnostics/__init__.py`
- `backend/geometry/__init__.py`
- `backend/lexicon/__init__.py`
- `backend/models/__init__.py`
- `backend/pagination/__init__.py`
- `backend/stage_s/formatting.py`

Notes:

- Most `__init__.py` files are package markers / re-export points. Even when static reachability is weak, they are standard package infrastructure and not good deletion candidates.
- `backend/stage_s/formatting.py` had only documentary references in the repo-wide scan. That makes it a **review manually** file, not a safe delete.

## UNUSED

No tracked Python file met the bar for `UNUSED` with proof strong enough for deletion recommendation.

## Frontend Dependency Tree

### Active frontend files

- `frontend/index.html`
- `frontend/assets/js/api.js`
- `frontend/assets/js/app.js`
- `frontend/assets/js/provenance.js`
- `frontend/assets/js/router.js`
- `frontend/assets/js/screens/stage_1.js`
- `frontend/assets/js/screens/stage_2.js`
- `frontend/assets/js/screens/stage_2b.js`
- `frontend/assets/js/screens/stage_3.js`
- `frontend/assets/js/screens/stage_4.js`
- `frontend/assets/js/screens/stage_5.js`
- `frontend/assets/js/screens/stage_6.js`
- `frontend/assets/js/state.js`
- `frontend/assets/js/ui.js`
- `frontend/screens/stage_1_intake.html`
- `frontend/screens/stage_2_transcripts.html`
- `frontend/screens/stage_2b_speakers.html`
- `frontend/screens/stage_3_workspace.html`
- `frontend/screens/stage_4_insertions.html`
- `frontend/screens/stage_5_certify.html`
- `frontend/screens/stage_6_export.html`
- `frontend/assets/css/tailwind.css`
- `frontend/assets/css/app.css`
- `frontend/src/styles/tailwind.css`

Evidence:

- `frontend/index.html` script tags load the JS entrypoints
- `frontend/assets/js/router.js` fetches all six HTML stage screens
- `package.json` builds `frontend/src/styles/tailwind.css` into `frontend/assets/css/tailwind.css`
- `frontend/index.html` links to `frontend/assets/css/tailwind.css`

## Candidate Runtime Risks to Review Later

- `backend/pagination/paginator.py` and `backend/pagination/flow_rules.py` are important to tests/specs, but current runtime reachability is weaker than expected. That is a usage-shape finding, not a deletion signal.
- `backend/stage_s/formatting.py` is the clearest “review manually” Python file in the repo.
