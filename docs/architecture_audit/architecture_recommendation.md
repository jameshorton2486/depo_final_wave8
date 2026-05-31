# Architecture Recommendation

## Recommendation: OPTION B

**Migrate runtime to `backend.pagination` as the single pagination authority.**

## Why

The audit showed:

- `export_render` private pagination is the **actual** runtime authority today
- `backend.pagination` is the **richer and better-aligned** implementation
- `backend.pagination` is built, tested, and documented
- `export_render` duplicates core pagination behavior
- runtime currently bypasses:
  - continuation handling
  - page-start flow policy
  - Q/A tether rules

This means the current runtime architecture is a drifted shortcut, not the best supported authority.

## Evidence

- Runtime export/package paths call `render_export_with_layout(...)`, not `paginate(...)`
  - `backend/api/transcripts.py:1112-1119`
  - `backend/api/packaging.py:478`
- `render_export_with_layout(...)` uses `_paginate_formatted_stream(...)`
  - `backend/transcript/export_render.py:351-352`
- `_paginate_formatted_stream(...)` duplicates pagination allocation using the shared page model
  - `backend/transcript/export_render.py:180-211`
- `backend.pagination.paginator` contains the richer canonical engine
  - `backend/pagination/paginator.py:45-117`
- `backend.pagination.flow_rules` contains live-looking policy that runtime currently bypasses
  - `backend/pagination/flow_rules.py:53-70`
- dedicated tests exist for `backend.pagination`
  - `tests/test_wave19_pagination_geometry.py`

## Exact Files That Must Change in a Future Implementation Pass

At minimum:

- `backend/transcript/export_render.py`
  - remove/replace `_paginate_formatted_stream(...)`
  - adapt the current pre-formatted stream into `RenderLine` / wrapped-line input the canonical paginator can accept
- `backend/api/transcripts.py`
  - ensure export preview / export build path uses the canonical pagination route
- `backend/api/packaging.py`
  - ensure package assembly uses the same canonical pagination route

Likely supporting touch points:

- `backend/pagination/paginator.py`
  - possibly only interface adaptation, not core feature work
- `backend/pagination/wrapping.py`
  - if current export pre-formatting assumptions need bridging
- `backend/export/export_service.py`
  - probably unchanged except for consuming the same paginated model more consistently
- tests:
  - `tests/test_wave18_export.py`
  - `tests/test_wave19_pagination_geometry.py`
  - `tests/test_wave20_packaging.py`
  - any export preview/certification path tests affected by pagination behavior

## Risk Assessment

### Benefits

- eliminates duplicate pagination logic
- makes runtime match documented architecture
- turns flow rules into real runtime behavior
- makes continuation tracking real
- simplifies future UFM reasoning because one engine owns pagination

### Risks

- `export_render` currently paginates a **pre-formatted stream**, not raw `RenderLine`s
- bridging that gap may expose assumptions in export line formatting
- packaging/index/page-reference behavior depends on today’s exact `PaginatedDocument` shape and line allocation
- export preview and file export must remain identical during the migration

### Overall Risk

**Medium-high**, but justified.

This is not a cleanup task; it is an architecture correction task.

## What This Recommendation Does NOT Mean

- no implementation should happen in this audit pass
- no UFM behavior changes should be made here
- no packaging feature work should be bundled into the pagination authority pass

The next step, if accepted, should be a separate governed build prompt focused only on making `backend.pagination` the runtime authority.
