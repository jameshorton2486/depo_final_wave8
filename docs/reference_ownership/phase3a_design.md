## Phase 3A Design

Phase 3A adds internal ownership metadata without changing pagination authority, snapshot format, exports, or visible citations.

Transcript ownership:
- `IndexEntry.owner_snapshot_id`
- `IndexEntry.owner_render_line_id`

Exhibit ownership:
- `Exhibit.owner_snapshot_id`
- `Exhibit.owner_anchor_utterance_id`

Implementation scope:
- `backend/packaging/model.py`
- `backend/packaging/indices.py`
- `backend/api/packaging.py`
- `backend/packaging/package_repo.py`

Design constraints:
- Keep `Page N, Line M` as the only visible citation format.
- Keep existing package assembly and export behavior unchanged.
- Preserve compatibility with previously stored package rows by defaulting missing ownership fields to `""` during reconstruction.
- Do not change pagination authority or reference resolution consumers in this phase.

Forward seam:
- Phase 4 can migrate reference consumers to the ownership fields.
- Phase 5 can change pagination authority later without changing exhibit anchor ownership.
