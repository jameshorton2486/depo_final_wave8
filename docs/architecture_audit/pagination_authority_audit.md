# Pagination Authority Audit

Audit date: 2026-05-30  
Mode: read-only

## Scope

Compared:

- `backend/transcript/export_render.py`
- `backend/pagination/paginator.py`
- `backend/pagination/flow_rules.py`
- geometry integration
- packaging integration
- export integration

## Current Runtime Reality

### Active export path

`Transcript -> Stage S -> export_render private pagination -> Geometry -> Export`

Evidence:

- `backend/api/transcripts.py:1047-1049` -> `render_stage_s(...)`
- `backend/api/transcripts.py:1112-1119` -> `render_export_with_layout(...)`
- `backend/transcript/export_render.py:351-352` -> `_paginate_formatted_stream(stream)`
- `backend/api/transcripts.py:1373-1379` -> `export_service.export_document(..., paginated_document=paginated)`
- `backend/export/export_service.py:125-127` -> `apply_geometry(paginated_document, TEXAS_UFM)`

### Active packaging path

`Transcript/Snapshot -> Stage S -> export_render private pagination -> Packaging`

Evidence:

- `backend/api/packaging.py:450` -> `render_stage_s(...)`
- `backend/api/packaging.py:478` -> `render_export_with_layout(working)`
- `backend/api/packaging.py:557-562` -> `assemble_package(..., paginated_document=paginated, ...)`

## Compared Implementations

### 1. `export_render` private pagination

Implementation:

- `backend/transcript/export_render.py:180-211`
- `_paginate_formatted_stream(stream) -> PaginatedDocument`

Characteristics:

- consumes a pre-formatted `(text, kind)` stream
- each stream entry becomes exactly one `PhysicalLine`
- allocates into `PageSlot`s using `LINES_PER_PAGE`
- produces a `PaginatedDocument`
- always returns `continuations=[]`
- intentionally bypasses `wrap_render_line`
- intentionally bypasses `backend.pagination.paginator.paginate()`

### 2. `backend.pagination`

Implementation:

- `backend/pagination/paginator.py:45-117`
- `backend/pagination/flow_rules.py`
- `backend/pagination/model.py`

Characteristics:

- consumes Stage S `RenderLine`s
- wraps each line via `wrap_render_line(...)`
- applies `can_start_on_page(...)`
- applies `requires_qa_tether(...)`
- records explicit `ContinuationState`
- returns diagnostic check helper `paginated_to_render_check(...)`

## Capability Findings

### Page breaking

- `export_render`: simple 25-line slot allocation only
- `backend.pagination`: true structure-aware pagination with wrapping and page-break decisions

Winner: `backend.pagination`

### Line numbering

- Both produce `PageSlot`-based line numbering using the shared pagination model

Winner: tie

### Continuation handling

- `export_render`: none; always `continuations=[]`
- `backend.pagination`: explicit `ContinuationState` objects when structures cross pages

Winner: `backend.pagination`

### Widow/orphan / flow control

- `export_render`: none visible in the private paginator
- `backend.pagination`: `can_start_on_page` and `requires_qa_tether`

Winner: `backend.pagination`

### Transcript flow rules

- `export_render`: bypasses `flow_rules.py`
- `backend.pagination`: embeds flow rules directly

Winner: `backend.pagination`

### Page identity

- Both use `Page`, `PageSlot`, and `PaginatedDocument` types from `backend.pagination.model`
- `export_render` reuses the model but not the engine

Winner: tie on model, `backend.pagination` on ownership coherence

### Page references / exhibit references

- Packaging/index generation needs stable `(page, line)` references from the frozen `PaginatedDocument`
- `backend/packaging/indices.py:56-73` builds those refs from the paginated document it is given
- Both can technically feed `indices.py` because both yield the same model type

Winner: tie on compatibility, `backend.pagination` on explicit continuation/reference semantics

### UFM support

- `export_render`: 25-line physical page shape, but lacks the richer rule layer
- `backend.pagination`: built specifically around documented Wave 19 / UFM page rules

Winner: `backend.pagination`

### Test coverage

- `export_render`: covered indirectly by export tests and transcript API/export paths
  - see `tests/test_wave18_export.py`
- `backend.pagination`: directly covered by dedicated pagination tests
  - see `tests/test_wave19_pagination_geometry.py`
- packaging also consumes `paginate(...)` in tests
  - see `tests/test_wave20_packaging.py`

Winner: `backend.pagination` for direct dedicated coverage

## Ownership Questions

### A. Is `backend.pagination` unfinished?

Evidence says **no**.

Why:

- It has a full model layer (`backend/pagination/model.py`)
- It has a real engine (`backend/pagination/paginator.py`)
- It has explicit flow-policy helpers (`backend/pagination/flow_rules.py`)
- It has dedicated tests (`tests/test_wave19_pagination_geometry.py`)
- Packaging tests also use it (`tests/test_wave20_packaging.py`)

Conclusion: built, tested, but not wired into active runtime

### B. Is `backend.pagination` superseded?

Evidence says **no**.

Why:

- Runtime bypasses it, but no code comments or docs indicate formal retirement
- Multiple docs still describe it as the intended architecture
- `export_render` explicitly says it returns the same `PaginatedDocument` type as `paginate()`, which reads as compatibility, not replacement

Conclusion: bypassed, not superseded

### C. Is `export_render` duplicated functionality?

Evidence says **yes**.

Why:

- It implements its own `_paginate_formatted_stream(...)`
- It creates `Page`, `PageSlot`, `PaginatedDocument` directly
- Historical docs already noted the duplication:
  - `docs/archive/completed_phases/AUDIT.md:33-36`

Conclusion: live duplicate pagination path

### D. Which implementation is the actual authority today?

**Actual runtime authority today:** `export_render` private pagination

Reason:

- It is the path both transcript export and packaging call in production

### E. Which implementation should become the authority?

**Should become authority:** `backend.pagination`

Reason:

- richer capabilities
- explicit flow rules
- continuation support
- direct tests
- closer match to the documented architecture

## UFM Impact Analysis

### If `backend.pagination` became authoritative

Improvements:

- flow rules (`requires_qa_tether`, `can_start_on_page`) become live
- continuation tracking becomes real
- runtime would match documented architecture
- one pagination engine instead of two

Likely files touched in a future implementation pass:

- `backend/transcript/export_render.py`
- `backend/api/transcripts.py`
- `backend/api/packaging.py`
- possibly `backend/export/export_service.py` only if interfaces change
- tests around export + packaging + pagination

Risk:

- medium/high because export and packaging currently depend on the private path’s assumptions about preformatted lines

### If `export_render` remains authoritative

Then documentation/specs are wrong or misleading in at least these areas:

- expected runtime architecture documents
- Wave 19 pagination expectations
- tests/docs that imply `backend.pagination` is the live path

Files/docs requiring update in that case:

- `docs/runtime_wiring_audit.md`
- Wave 19 / packaging architecture docs
- tests that present `backend.pagination` as the canonical runtime engine rather than a library/test path

Risk:

- lower short-term implementation risk
- higher long-term architectural drift and duplicated-logic risk
