# DEPO-PRO Runtime Wiring Audit

Audit date: 2026-05-30  
Mode: read-only  
Branch at audit: `main`

## Scope

Audited subsystems:

1. `backend/export/export_service.py`
2. `backend/packaging/*`
3. `backend/pagination/paginator.py`
4. `backend/pagination/flow_rules.py`
5. `backend/geometry/*`
6. `backend/stage_s/formatting.py`

Goal: determine whether the **active runtime architecture** matches the
documented target architecture.

## Expected Flow

Expected architecture from docs/spec framing:

`Transcript -> Stage S -> Pagination -> Geometry -> Packaging -> Export`

## Current Runtime Flow

There are actually **two active runtime flows**, not one:

### A. Transcript export flow (DOCX/PDF/RTF/TXT)

`Transcript working state`
-> `Stage S render`
-> `export_render.render_export_with_layout()`
-> **private export_render pagination**
-> `geometry.apply_geometry()` for DOCX/PDF only
-> `export_service.export_document()`
-> `*_writer.py`

Evidence:

- `backend/api/transcripts.py:1047-1049` calls `render_stage_s(...)`
- `backend/api/transcripts.py:1112-1119` calls `render_export_with_layout(...)`
- `backend/api/transcripts.py:1373-1380` calls `export_service.export_document(...)`
- `backend/export/export_service.py:123-135` applies geometry for DOCX/PDF when `paginated_document` is present

### B. Packaging / certification flow

`Transcript snapshot / working state`
-> `Stage S render`
-> `export_render.render_export_with_layout()`
-> **private export_render pagination**
-> `packaging.assemble_package(...)`
-> package JSON / certification validation

Evidence:

- `backend/api/packaging.py:450` calls `render_stage_s(...)`
- `backend/api/packaging.py:478` calls `render_export_with_layout(working)`
- `backend/api/packaging.py:557-564` calls `assemble_package(...)`

## Key Architectural Drift

The active runtime does **not** currently use `backend/pagination/paginator.py`
as the pagination authority.

Instead, `backend/transcript/export_render.py` performs its own inline
pagination through `_paginate_formatted_stream(...)`.

Evidence:

- `backend/transcript/export_render.py:180-211` defines `_paginate_formatted_stream(...)`
- `backend/transcript/export_render.py:351-352` uses `_paginate_formatted_stream(stream)`
- `backend/transcript/export_render.py:190-191` explicitly says it returns the same
  `PaginatedDocument` type as `backend.pagination.paginator`, implying type reuse,
  not engine reuse

So the runtime path is:

`Stage S -> export_render private pagination -> Geometry/Packaging/Export`

not:

`Stage S -> backend.pagination.paginator -> Geometry/Packaging/Export`

## Subsystem Review

| Subsystem | Expected Role | Actual Role | Runtime Status |
|---|---|---|---|
| `backend/export/export_service.py` | Orchestrate export after canonical render/layout | Active export orchestrator; chooses writer, resolves destination, applies geometry for DOCX/PDF | `ACTIVE` |
| `backend/packaging/*` | Assemble administrative pages, indexes, certification package | Active in package/certification path, but separate from transcript file export path | `ACTIVE` |
| `backend/pagination/paginator.py` | Canonical pagination engine between Stage S and Geometry/Export | Not used by active transcript export or package assembly runtime flow; used by tests and helper validation paths | `BYPASSED` |
| `backend/pagination/flow_rules.py` | Pagination flow policy feeding canonical paginator | Used by `paginator.py`, but because runtime bypasses `paginator.py`, these rules are effectively bypassed in live export/package paths | `BYPASSED` |
| `backend/geometry/*` | Apply UFM geometry to paginated transcript for physical export | Active for DOCX/PDF export via `apply_geometry(paginated_document, TEXAS_UFM)` | `ACTIVE` |
| `backend/stage_s/formatting.py` | Shared Stage S formatting helpers | Defines `normalize_ws()` and `is_blank()`, but no import/use evidence found in runtime/tests | `UNUSED` |

## Detailed Findings

### 1. `backend/export/export_service.py`

**Expected role:** final export orchestrator after canonical layout.

**Actual role:** matches expectation.

Evidence:

- `backend/export/export_service.py:22-25` imports all writer modules
- `backend/export/export_service.py:26-27` imports `apply_geometry` and `TEXAS_UFM`
- `backend/export/export_service.py:81-147` is the live export function used by `backend/api/transcripts.py`

Status: `ACTIVE`

### 2. `backend/packaging/*`

**Expected role:** package assembly, admin pages, indexes, certification validation.

**Actual role:** active and real, but it is **not** the same thing as the
export writer path. Packaging produces package/certification artifacts, while
transcript export writes DOCX/PDF/RTF/TXT from the export flow.

Evidence:

- `backend/api/packaging.py:557-564` calls `assemble_package(...)`
- `backend/packaging/packager.py:62` defines `assemble_package(...)`
- `backend/packaging/packager.py:102` calls `generate_indices(...)`
- `backend/packaging/packager.py:175-191` performs certification validation and raises on blocking errors

Status: `ACTIVE`

Important nuance:

- Packaging is active, but it is not wired into the current transcript file-export path that writes DOCX/PDF.
- That is why earlier UFM audit work found that package-layer admin pages do not automatically appear in the live transcript export files.

### 3. `backend/pagination/paginator.py`

**Expected role:** canonical pagination engine between Stage S and downstream geometry/export.

**Actual role:** present, tested, and documented, but not used by the active
runtime export/package flow.

Evidence:

- `backend/pagination/paginator.py:45` defines `paginate(...)`
- `backend/pagination/paginator.py:120` defines `paginated_to_render_check(...)`
- `backend/transcript/export_render.py:351-352` does **not** call `paginate(...)`; it calls its own `_paginate_formatted_stream(...)`
- repo-wide runtime callsite scan found tests and validation references, but not an active export/package runtime callsite

Status: `BYPASSED`

### 4. `backend/pagination/flow_rules.py`

**Expected role:** implement pagination flow policy for page starts and Q/A tethering.

**Actual role:** feeds the dedicated paginator, but since runtime bypasses that
paginator, the flow rules are bypassed too in live export/package paths.

Evidence:

- `backend/pagination/paginator.py:19-22` imports `can_start_on_page` and `requires_qa_tether`
- `backend/pagination/paginator.py:78-95` applies those rules
- no active export/package runtime callsite reaches `paginate(...)`

Status: `BYPASSED`

### 5. `backend/geometry/*`

**Expected role:** apply UFM physical layout after pagination.

**Actual role:** active for DOCX/PDF export, but it consumes the
`PaginatedDocument` produced by `export_render`’s private pagination, not by
the dedicated `backend.pagination.paginator`.

Evidence:

- `backend/export/export_service.py:123-135` conditionally applies geometry
- `backend/transcript/export_render.py:190-191` returns the same paginated type the geometry layer consumes

Status: `ACTIVE`

### 6. `backend/stage_s/formatting.py`

**Expected role:** shared semantic formatting helpers for Stage S.

**Actual role:** tiny helper module containing:

- `normalize_ws(text: str) -> str`
- `is_blank(text: str) -> bool`

Evidence:

- `backend/stage_s/formatting.py:1-20`
- repository-wide reference scan found documentary references but no import/use callsites in runtime or tests

Interpretation:

- This looks like orphaned helper code or an unfinished extraction
- It is not participating in the active runtime architecture

Status: `UNUSED`

## Current Path vs Expected Path

### Current Path

`Transcript`
-> `Stage S`
-> `export_render.render_export_with_layout`
-> `export_render._paginate_formatted_stream` (private)
-> `Geometry`
-> `Export`

And separately:

`Transcript/Snapshot`
-> `Stage S`
-> `export_render.render_export_with_layout`
-> `export_render._paginate_formatted_stream`
-> `Packaging`
-> package/certification JSON

### Expected Path

`Transcript`
-> `Stage S`
-> `Pagination`
-> `Geometry`
-> `Packaging`
-> `Export`

## Identified Gaps

1. **Dedicated paginator is bypassed in runtime**
   - `backend/pagination/paginator.py` exists, is tested, and is documented
   - live runtime export/package flows do not call it

2. **Flow rules are therefore bypassed too**
   - Q/A tethering and start-of-page rules in `flow_rules.py` do not govern the active runtime path

3. **Packaging is not the terminal stage of the transcript export flow**
   - packaging is active, but it is a parallel certification/package path
   - transcript export files are produced by `export_service.py` from `ExportDocument`, not from `assemble_package(...)`

4. **Stage S formatting helper module is not wired**
   - `backend/stage_s/formatting.py` is present but unused

## Final Status Snapshot

| Subsystem | Runtime Status |
|---|---|
| Export service | `ACTIVE` |
| Packaging | `ACTIVE` |
| Pagination engine | `BYPASSED` |
| Pagination flow rules | `BYPASSED` |
| Geometry | `ACTIVE` |
| `stage_s/formatting.py` | `UNUSED` |

## Bottom Line

The documented architecture and the active runtime architecture are **not the same**.

What is active:

- Stage S
- private pagination inside `export_render`
- geometry for DOCX/PDF
- packaging for package/certification generation
- export service for transcript file writing

What is not active in the live runtime path:

- the dedicated `backend.pagination.paginator`
- its `flow_rules`
- `backend/stage_s/formatting.py`

This is architectural drift, not merely file clutter. No code changes were made in this audit.
