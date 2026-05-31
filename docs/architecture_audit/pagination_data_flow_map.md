# Pagination Data Flow Map

Audit date: 2026-05-30  
Mode: read-only planning

## Current Runtime

### Export path

`Transcript`
-> `Stage S`
-> `export_render` private pagination
-> `Geometry`
-> `Export`

Concrete path:

1. `backend/api/transcripts.py:1047-1049`
   - `render_stage_s(utterances, participants)`
2. `backend/api/transcripts.py:1112-1119`
   - `render_export_with_layout(working, ...)`
3. `backend/transcript/export_render.py:351-352`
   - `_paginate_formatted_stream(stream)`
4. `backend/api/transcripts.py:1373-1379`
   - `export_service.export_document(..., paginated_document=paginated)`
5. `backend/export/export_service.py:125-127`
   - `apply_geometry(paginated_document, TEXAS_UFM)`

### Packaging path

`Transcript`
-> `Stage S`
-> `export_render` private pagination
-> `Packaging`

Concrete path:

1. `backend/api/packaging.py:450`
   - `render_stage_s(utterances, participants)`
2. `backend/api/packaging.py:478`
   - `render_export_with_layout(working)`
3. `backend/transcript/export_render.py:351-352`
   - `_paginate_formatted_stream(stream)`
4. `backend/api/packaging.py:557-562`
   - `assemble_package(..., paginated_document=paginated, ...)`

## Proposed Runtime

### Export path

`Transcript`
-> `Stage S`
-> `backend.pagination`
-> `Geometry`
-> `Export`

### Packaging path

`Transcript`
-> `Stage S`
-> `backend.pagination`
-> `Packaging`

## Interface Mismatches

### 1. Input shape mismatch

`export_render` currently paginates:

- a preformatted `stream: list[tuple[str, str]]`

Evidence:

- `backend/transcript/export_render.py:180-183`

`backend.pagination` expects:

- `render_lines: list[RenderLine]`

Evidence:

- `backend/pagination/paginator.py:45-48`

This is the primary adapter boundary.

### 2. Wrapping ownership mismatch

`export_render` path:

- pre-wraps body lines via `_body_lines_for(...)`
- explicitly bypasses `wrap_render_line(...)`

Evidence:

- `backend/transcript/export_render.py:35-38`
- `backend/transcript/export_render.py:187-188`

`backend.pagination` path:

- wraps each `RenderLine` using `wrap_render_line(...)`

Evidence:

- `backend/pagination/paginator.py:31`
- `backend/pagination/paginator.py:70`

So runtime migration needs one authority for wrapping as well as pagination.

### 3. Continuation semantics mismatch

`export_render` always returns:

- `continuations=[]`

Evidence:

- `backend/transcript/export_render.py:211`

`backend.pagination` explicitly records:

- `ContinuationState`

Evidence:

- `backend/pagination/paginator.py:52-54`
- `backend/pagination/paginator.py:109-117`

### 4. Flow-policy mismatch

`backend.pagination` uses:

- `can_start_on_page(...)`
- `requires_qa_tether(...)`

Evidence:

- `backend/pagination/paginator.py:78`
- `backend/pagination/paginator.py:90`

Current runtime export/package path never reaches those rules.

### 5. Compatibility point that helps migration

Both paths already converge on the same model types:

- `Page`
- `PageSlot`
- `PhysicalLine`
- `PaginatedDocument`

Evidence:

- `backend/transcript/export_render.py:31-33`
- `backend/pagination/model.py`

This means geometry and packaging consumers do not need a new page model.

## Summary

The migration is not “replace one page model with another.”  
It is:

- replace a **private preformatted-stream paginator**
- with a **RenderLine-driven canonical paginator**
- while preserving the downstream `PaginatedDocument` contract

That is why this is an adapter problem, not a feature problem.
