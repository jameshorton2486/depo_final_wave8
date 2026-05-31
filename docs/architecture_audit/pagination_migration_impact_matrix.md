# Pagination Migration Impact Matrix

Audit date: 2026-05-30  
Mode: read-only planning

## Phase 0 — Scope Confirmation

Reviewed:

- `docs/architecture_audit/pagination_authority_audit.md`
- `docs/architecture_audit/pagination_capability_matrix.md`
- `docs/architecture_audit/architecture_recommendation.md`

### Contradictions

No material contradictions found.

Those three documents are internally consistent on the key points:

- runtime authority today = `export_render` private pagination
- intended authority = `backend.pagination`
- `backend.pagination` is built, tested, and documented
- `export_render` duplicates pagination behavior
- recommendation = `OPTION B` (migrate runtime to `backend.pagination`)

## File Impact Matrix

| File | Current Role | Future Role | Risk | Change Type |
|---|---|---|---|---|
| `backend/transcript/export_render.py` | Active runtime pagination authority via `_paginate_formatted_stream(...)`; builds `PaginatedDocument` from preformatted stream | Adapter layer only; should stop owning pagination allocation | High | Replace duplicate pagination with adapter/bridge to `backend.pagination` |
| `backend/pagination/paginator.py` | Built/tested engine, bypassed by runtime | Primary pagination authority | Medium | Integration-facing interface additions or adapter support |
| `backend/pagination/flow_rules.py` | Policy module only effective when `paginate(...)` is used; currently bypassed | Live runtime flow policy authority | Medium | No likely logic change; becomes active by integration |
| `backend/pagination/model.py` | Shared page model already used by both paths | Shared canonical page model remains | Low | Likely unchanged |
| `backend/api/transcripts.py` | Builds export documents via `render_export_with_layout(...)`, then exports them | Must route export preview/export through canonical paginator-backed path | Medium | Rewire call path to new authority |
| `backend/api/packaging.py` | Builds package paginated input via `render_export_with_layout(...)` | Must route packaging through canonical paginator-backed path | Medium | Rewire call path to new authority |
| `backend/export/export_service.py` | Export orchestrator; applies geometry to supplied `PaginatedDocument` | Likely unchanged, continues to consume `PaginatedDocument` | Low | Confirm compatibility only |
| `backend/geometry/engine.py` | Consumes `PaginatedDocument` and applies physical geometry | Continues to consume `PaginatedDocument` from canonical paginator | Low | Likely unchanged |
| `backend/geometry/profile.py` | UFM geometry profile data | Unchanged | Low | None expected |
| `backend/packaging/packager.py` | Assembles package from `paginated_document` and metadata | Continues to consume `PaginatedDocument`, but now from canonical paginator | Low | Likely unchanged |
| `backend/packaging/indices.py` | Resolves page/line refs from `PaginatedDocument` | Continues unchanged if page/slot contracts remain stable | Medium | Validate output stability only |
| `tests/test_wave18_export.py` | Verifies export writers and export service | Must validate export behavior under canonical paginator | Medium | Update expectations/fixtures if page allocation changes |
| `tests/test_wave19_pagination_geometry.py` | Directly tests `backend.pagination` and geometry | Becomes closer to live runtime coverage | Low | Mostly unchanged; may gain authority assertions |
| `tests/test_wave20_packaging.py` | Tests packaging with `paginate(...)` in fixtures | Should align more closely with runtime packaging path | Medium | Possibly minor updates to match live call chain |

## Notes

- `backend/stage_s/renderer.py` is upstream and already active; it is not a primary pagination migration target.
- `backend/stage_s/formatting.py` is not part of the migration surface.
