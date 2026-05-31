# Pagination Capability Matrix

| Capability | `export_render` | `backend.pagination` | Winner |
|---|---|---|---|
| Active runtime use | Yes | No | `export_render` |
| Stage S input handling | Consumes post-mapped working lines and builds pre-formatted stream | Consumes `RenderLine` objects directly | `backend.pagination` |
| Wrapping | No dedicated `wrap_render_line`; text arrives preformatted | Uses `wrap_render_line(...)` with wrap width | `backend.pagination` |
| 25-line pages | Yes | Yes | Tie |
| Page model compatibility | Yes (`PaginatedDocument`) | Yes (`PaginatedDocument`) | Tie |
| Continuation tracking | No (`continuations=[]`) | Yes (`ContinuationState`) | `backend.pagination` |
| Widow/orphan control | No evidence | `can_start_on_page(...)` | `backend.pagination` |
| Q/A tethering | No evidence | `requires_qa_tether(...)` | `backend.pagination` |
| Page identity / slot numbering | Yes | Yes | Tie |
| Packaging/index compatibility | Yes, because it returns shared pagination model | Yes | Tie |
| Geometry compatibility | Yes | Yes | Tie |
| Exhibit/page references | Usable through shared model | Usable through shared model + richer structure semantics | `backend.pagination` |
| UFM-oriented design intent | Partial | Strong | `backend.pagination` |
| Direct dedicated tests | Indirect export tests | Dedicated pagination tests | `backend.pagination` |
| Documentation alignment | Diverges from expected architecture | Matches expected architecture | `backend.pagination` |
| Runtime authority today | Yes | No | `export_render` |
| Recommended long-term authority | No | Yes | `backend.pagination` |

## Supporting Evidence

- `backend/transcript/export_render.py:180-211`
- `backend/transcript/export_render.py:351-352`
- `backend/pagination/paginator.py:45-117`
- `backend/pagination/flow_rules.py:53-70`
- `tests/test_wave19_pagination_geometry.py`
- `tests/test_wave20_packaging.py`
- `backend/api/transcripts.py:1112-1119`
- `backend/api/packaging.py:478`
