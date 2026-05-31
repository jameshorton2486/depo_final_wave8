# Pagination Adapter Requirements

Audit date: 2026-05-30  
Mode: read-only planning

## Question Set

### Are `RenderLine`s already available?

Yes.

Evidence:

- `backend/stage_s/renderer.py:62-65` returns `StageSResult` with `lines: list[RenderLine]`
- `backend/api/transcripts.py:1049` gets `stage_s = render_stage_s(...)`
- `backend/api/packaging.py:450` gets `stage_s = render_stage_s(...)`

So the canonical paginator’s input type already exists in the live path **before** runtime switches to the private export paginator.

### Does Stage S already generate them?

Yes.

Evidence:

- `backend/stage_s/renderer.py` is the live producer of `RenderLine`s

### Is wrapping duplicated?

Yes.

Current private path:

- `export_render` preformats and wraps body text internally
- imports `_wrap_text` from `backend.pagination.wrapping`
- then bypasses `wrap_render_line(...)`

Evidence:

- `backend/transcript/export_render.py:29-38`
- `backend/transcript/export_render.py:55`

Canonical path:

- `backend.pagination.paginator` uses `wrap_render_line(...)`

Evidence:

- `backend/pagination/paginator.py:31`
- `backend/pagination/paginator.py:70`

### Is line allocation duplicated?

Yes.

Private path:

- `_paginate_formatted_stream(...)`

Evidence:

- `backend/transcript/export_render.py:180-211`

Canonical path:

- `paginate(...)`

Evidence:

- `backend/pagination/paginator.py:45-117`

### Is continuation handling lost?

Yes, in the live runtime path.

Evidence:

- `backend/transcript/export_render.py:211` returns `PaginatedDocument(..., continuations=[])`
- `backend/pagination.paginator` records `ContinuationState` when structures cross pages
  - `backend/pagination/paginator.py:97-117`

### Is page identity preserved?

Mostly yes at the model level.

Evidence:

- both paths use the same `Page`, `PageSlot`, and `PaginatedDocument` types
- page ids are created in both paths as `page-{page_number:04d}`

But the page **allocation semantics** are not preserved, because the private path lacks the canonical flow rules and continuation model.

## Adapter Requirements Matrix

| Requirement | Why |
|---|---|
| Preserve the downstream `PaginatedDocument` contract | Geometry and packaging already consume that type |
| Bridge from live `RenderLine` output instead of from private preformatted stream | Stage S already produces canonical semantic lines |
| Decide who owns wrapping | Current runtime has split ownership between `_body_lines_for/_wrap_text` and `wrap_render_line(...)` |
| Preserve Q/A prefixes and indentation semantics | Export output currently depends on preformatted textual shapes |
| Preserve page/line reference stability or account for drift in tests | Packaging indices use `(page, slot)` refs from the paginated document |
| Expose continuation behavior explicitly in runtime | Canonical paginator supports it; private runtime path drops it |
| Ensure export preview and real export share the same authority | Current governance requires preview/export consistency |
| Ensure packaging consumes the same paginated authority as export | Avoid split page-reference behavior between package and transcript export |

## Likely Adapter Shape

The migration likely needs one of these strategies:

1. **Convert Stage S `RenderLine`s into the exact canonical `backend.pagination` path**, then convert the resulting `PaginatedDocument` into `ExportDocument`
2. **Teach `backend.pagination` how to preserve the preformatted export-specific indentation semantics**

The first strategy is cleaner architecturally, but both are implementation questions for the later build pass.

## Bottom Line

The hard part of the migration is not “where do pages come from?”  
It is:

- who owns wrapping,
- who owns indentation/prefix formatting,
- and how to preserve export output shape while switching pagination authority.
