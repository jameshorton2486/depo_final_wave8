>  SUPERSEDED — FACTUALLY INACCURATE. This document describes an earlier,
> pre-backend state of DEPO-PRO and is WRONG about the current system. Do not
> use it for any decision. Current authority: CLAUDE.md at the repo root.

# AUDIT.md — Phase 0 Reality-State Classification

**Audited:** 2026-05-22  
**Test baseline:** 424 passed, 1 skipped (all green)

---

## Subsystem Classification

| # | Subsystem | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Transcript State Engine | **OPERATIONAL** | `backend/transcript_state/` complete; `api/snapshots.py` registered in `app.py:81`; 18 tests pass |
| 2 | Canonical Renderer Consolidation | **PARTIAL** | `_wrap()` in `export_render.py:100` is a duplicate of `_wrap_text()` in `pagination/wrapping.py:21`; inline paginator in `export_render.py:216-239` duplicates `paginate()` in `pagination/paginator.py:42`; Pagination Engine is NOT called by any production path |
| 3 | Filesystem-Native Export Engine | **OPERATIONAL** | All 4 writers (txt/rtf/pdf/docx) confirmed; single canonical renderer shared by export and preview; export endpoint registered in `api/transcripts.py` |
| 4 | Pagination Engine | **BUILT-NOT-WIRED** | `backend/pagination/` complete; 16 tests pass; but `paginate()` is called only from the test suite — never from export or preview paths |
| 5 | Geometry Layer | **PARTIAL** | `backend/geometry/profile.py` with `TEXAS_UFM` exists; `engine.py` is **missing**; DOCX/PDF writers use hardcoded constants, not the profile |
| 6 | Packaging Engine | **BUILT-NOT-WIRED** | 7 modules (~1300 lines) complete with models, packager, manifest, admin pages, indices, validation; **zero API endpoints**; not imported anywhere in the running app |

---

## Detail Notes

### 1. Transcript State Engine — OPERATIONAL (skip)
- `backend/transcript_state/model.py`, `snapshot_repo.py`, `snapshot_service.py`, `state_hash.py`
- `backend/api/snapshots.py` — registered in `app.py` line 81
- `tests/test_wave18_5_snapshots.py` — 18 tests pass

### 2 + 4. Canonical Renderer Consolidation + Pagination Engine — PARTIAL / BUILT-NOT-WIRED
- **Duplicate 1:** `_wrap()` in `export_render.py:100-117` vs `_wrap_text()` in `pagination/wrapping.py:21-42` — identical greedy word-wrap algorithm in two files.
- **Duplicate 2:** Inline 25-line paginator loop in `export_render.py:216-239` vs `paginate()` in `pagination/paginator.py:42-99`.
- `render_export_document()` never calls `paginate()`; it does all pagination internally.
- **Fix:** Remove `_wrap()` from export_render; import `_wrap_text` from pagination; replace inline loop with `paginate()` call; bridge via RenderLine conversion.

### 3. Export Engine — OPERATIONAL
- `backend/export/export_service.py` calls `render_export_document()` (single canonical renderer)
- `write_docx/pdf/rtf/txt` all confirmed — test files are produced
- Both export preview AND actual export call the same `render_export_document()` — no drift possible
- **Note:** docx_writer and pdf_writer use hardcoded constants; Wave 19 geometry is the correct fix (item 5).

### 5. Geometry Layer — PARTIAL
- `backend/geometry/profile.py` — `TEXAS_UFM` profile, all measurements present
- `backend/geometry/__init__.py` — imports profile only
- **Missing:** `backend/geometry/engine.py` — `apply_geometry(paginated, profile) → GeometryDocument`
- **Missing wiring:** DOCX/PDF writers use hardcoded font size (10pt vs 12pt in profile), margins, line spacing
- **Blocked measurement:** text area width conflict (8.5" - 1.25" left - 1.0" right = 6.25" actual vs 6.5" UFM minimum). Logged in BLOCKERS.md.

### 6. Packaging Engine — BUILT-NOT-WIRED
- 7 modules complete: `model.py`, `packager.py`, `manifest.py`, `admin_pages.py`, `indices.py`, `validation.py`, `__init__.py`
- `assemble_package()` and `certify_package()` work and are tested (35 tests pass)
- **Missing:** `backend/api/packaging.py` — no HTTP endpoints
- **Missing:** Registration in `app.py`
- **Missing:** Persistence layer — packages have no DB table

---

## Wiring Evidence Matrix

| Router Module | Registered in app.py | Evidence |
|---|---|---|
| `api/cases.py` | YES | app.py:73 |
| `api/sessions.py` | YES | app.py:74 |
| `api/reporters.py` | YES | app.py:75 |
| `api/nod.py` | YES | app.py:76 |
| `api/intake.py` | YES | app.py:77 |
| `api/transcripts.py` | YES | app.py:78 |
| `api/corrections.py` | YES | app.py:79 |
| `api/ai_review.py` | YES | app.py:80 |
| `api/snapshots.py` | YES | app.py:81 |
| `api/packaging.py` | **NO** | File does not exist |

---

## Work to be done (in order)

1. ~~Transcript State Engine~~ — SKIP (OPERATIONAL)
2. Canonical Renderer Consolidation — consolidate `_wrap()` and inline paginator into Pagination Engine
3. ~~Export Engine~~ — SKIP (OPERATIONAL after item 2)
4. Pagination Engine wiring — completed by item 2
5. Geometry Layer — create `engine.py`, wire into DOCX/PDF writers
6. Packaging Engine API — create `api/packaging.py`, add DB table, register in `app.py`
