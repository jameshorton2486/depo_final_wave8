# Pagination Migration Risk Matrix

Audit date: 2026-05-30  
Mode: read-only planning

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| Page numbering drift | High | Medium | dual-run old/new pagination and compare page counts + first/last line anchors before cutover |
| Line numbering drift | High | Medium | compare `(page, slot)` refs on known stable fixtures and packaging index outputs |
| Continuation drift | Medium | High | explicitly snapshot new `ContinuationState` behavior and update expectations deliberately |
| Certificate page references | High | Medium | validate packaging/certification outputs against the same `PaginatedDocument` source before switch |
| Exhibit page references | High | Medium | compare `generate_indices(...)` outputs before/after on the same transcript snapshot |
| Preview/export mismatch | High | Medium | migrate preview and export builder together; do not switch one without the other |
| Packaging regression | High | Medium | keep packaging on the same paginated authority as export; regression-test `tests/test_wave20_packaging.py` |
| Wrapping drift | High | High | settle a single wrapping authority before switching page allocation |
| Q/A tether behavior changes visible output | Medium | High | baseline current outputs, then treat new tethering as intentional behavioral change requiring explicit acceptance |
| Geometry consuming unexpected page shapes | Medium | Low | preserve `PaginatedDocument` model contract; validate DOCX/PDF page/slot geometry after switch |
| Adapter complexity between `RenderLine` and preformatted stream | High | High | build adapter first, validate with dual-run mode before authority switch |
| Hidden runtime dependence on export_render pagination quirks | Medium | Medium | instrument export preview, export write, and packaging assembly during migration pass |

## Highest-Risk Areas

1. Wrapping authority mismatch
2. Page/line reference drift
3. Preview/export/packaging consistency during cutover

## Lowest-Risk Areas

1. Geometry model compatibility
2. `export_service.py` orchestration itself
3. `backend/pagination/model.py` staying stable
