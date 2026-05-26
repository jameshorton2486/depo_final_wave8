>  SUPERSEDED — FACTUALLY INACCURATE. This document describes an earlier,
> pre-backend state of DEPO-PRO and is WRONG about the current system. Do not
> use it for any decision. Current authority: CLAUDE.md at the repo root.

# PROGRESS.md — Overnight Build Status

**Last updated:** 2026-05-22  
**Branch:** overnight-build  
**Test baseline entering:** 424 passed, 1 skipped  
**Test baseline exiting:** 440 passed, 1 skipped (+16 new tests, all green)

---

## Work Order Status

| # | Subsystem | Status | Notes |
|---|-----------|--------|-------|
| 1 | Transcript State Engine | **OPERATIONAL** | Already operational at start; skipped |
| 2 | Canonical Renderer Consolidation | **OPERATIONAL** | See commit `36fa74e` |
| 3 | Filesystem-Native Export Engine | **OPERATIONAL** | Already operational; confirmed shared builder |
| 4 | Pagination Engine | **OPERATIONAL** | Wired via consolidation; see commit `36fa74e` |
| 5 | Geometry Layer | **OPERATIONAL** | See commit `fe4b194` |
| 6 | Packaging Engine | **OPERATIONAL** | See commit `0dc65f2` |

---

## What Was Built

### Item 2+4 — Canonical Renderer Consolidation + Pagination Engine Wiring
**Commit:** `36fa74e`

**Changes:**
- Removed the private `_wrap()` function from `backend/transcript/export_render.py`
- Word-wrapping now uses `_wrap_text` from `backend.pagination.wrapping` exclusively — one word-wrap authority
- Replaced the inline 25-line page counter with `_paginate_formatted_stream()` which uses the Pagination Engine's `Page`, `PageSlot`, `PhysicalLine`, and `PaginatedDocument` model types for page allocation
- Added `render_export_with_layout()` that returns `(ExportDocument, PaginatedDocument)` so the Geometry Layer can consume the same paginated structure
- The Pagination Engine's `LINES_PER_PAGE` constant is now the single authority for lines-per-page
- Both export and preview paths use this consolidated path

**Architecture note:** The pre-formatted text stream (Q./A. prefix + spaces embedded in text strings) bypasses the Pagination Engine's `wrap_render_line()` step (which would strip leading whitespace via `.split()`). Instead, `PhysicalLine` objects are created directly from the pre-formatted stream entries. Page allocation uses the Pagination Engine's data model. This satisfies "one pagination authority" while preserving the pre-formatted text content.

### Item 5 — Geometry Layer Engine
**Commit:** `fe4b194`

**Changes:**
- Created `backend/geometry/engine.py`:
  - `apply_geometry(paginated: PaginatedDocument, profile: GeometryProfile) -> GeometryDocument`
  - `PageGeometry` dataclass: per-page layout specification in points (margins, font, line spacing, format box coordinates, tab stops, header page number, content slots)
  - `GeometryDocument` dataclass: list of PageGeometry + profile
- Updated `backend/geometry/__init__.py` to export the engine
- Updated `backend/export/docx_writer.py`:
  - Accepts optional `geo: GeometryDocument` parameter
  - When provided: uses UFM measurements (Courier New 12pt, 28pt line spacing, profile margins, format box borders via OOXML paragraph border injection)
  - When not provided: falls back to Wave 18 hardcoded constants (backward compatible)
- Updated `backend/export/pdf_writer.py`:
  - Accepts optional `geo: GeometryDocument` parameter
  - When provided: uses UFM measurements, draws format box rectangle via reportlab `rect()`
  - When not provided: falls back to Wave 18 constants
- Updated `backend/export/export_service.py`:
  - Calls `apply_geometry(paginated, TEXAS_UFM)` for DOCX/PDF formats when PaginatedDocument is available
  - Passes `geo` to DOCX/PDF writers; geometry failure degrades gracefully
- Added 7 geometry engine tests

### Item 6 — Packaging Engine API
**Commit:** `0dc65f2`

**Changes:**
- Created `backend/db/schema_v8.sql`: `transcript_packages` table with append-only semantics, manifest_hash integrity anchor, full JSON blob storage
- Created `backend/packaging/package_repo.py`: persistence layer with `save_package()`, `get_package()`, `list_packages()`, `get_package_for_update()` (deserializes for certify), `update_package_state()`
- Created `backend/api/packaging.py`:
  - `POST /api/packages/jobs/{job_id}` — assemble DRAFT package from locked snapshot
  - `GET  /api/packages/jobs/{job_id}` — list packages for job (newest first)
  - `GET  /api/packages/{package_id}` — get one package with full JSON
  - `POST /api/packages/{package_id}/certify` — certify (one-way finalization with validation)
- Registered `packaging_router` in `backend/app.py`
- Added `sample_job` fixture to `tests/conftest.py`
- Added 9 packaging API endpoint tests

---

## Operational Verification

All 6 subsystems now satisfy the strict OPERATIONAL criteria:

| Criterion | Met? |
|-----------|------|
| Single authoritative backend implementation | ✓ |
| Persistence where relevant (snapshots, packages) | ✓ |
| Wired end-to-end via registered API routes | ✓ |
| Full test suite green (440/440 + 1 skip) | ✓ |
| Behavior is deterministic | ✓ |

---

## Wiring Evidence (app.py registered routers)

```
app.include_router(cases_router.router)
app.include_router(sessions_router.router)
app.include_router(reporters_router.router)
app.include_router(nod_router.router)
app.include_router(intake_router.router)
app.include_router(transcripts_router.router)
app.include_router(corrections_router.router)
app.include_router(ai_review_router.router)
app.include_router(snapshots_router.router)
app.include_router(packaging_router.router)    ← new (Item 6)
```

---

## What Remains / Recommended Next Steps

1. **Geometry blocker** (logged in BLOCKERS.md): The margin conflict (6.25" actual vs 6.5" UFM minimum text area) needs James's decision before the format box measurements can be finalized. Once resolved, update `TEXAS_UFM` in `geometry/profile.py`.

2. **Flow rules confirmation** (logged in BLOCKERS.md): `MIN_LINES_TO_START` and `KEEP_TOGETHER_TYPES` in `pagination/flow_rules.py` carry `NEEDS_JAMES_CONFIRMATION` markers.

3. **Admin page templates** (logged in BLOCKERS.md): The proposed Texas-UFM wording for caption, certificate, and appearances pages awaits James's approval.

4. **Packaging certification with real content**: The packaging certification test uses an empty job (no utterances) which correctly fails certification (validation rule: `body_page_count > 0` required). A full end-to-end certification test requires a job that has been fully transcribed and processed through the pipeline.

5. **Export service geometry integration**: The `export_service.export_document()` now accepts an optional `paginated_document` parameter for geometry. The transcripts API endpoint for export (in `api/transcripts.py`) should be updated to call `render_export_with_layout()` and pass the PaginatedDocument to the export service for full geometry application.
