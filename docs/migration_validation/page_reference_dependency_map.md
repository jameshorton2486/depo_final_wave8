# Page Reference Dependency Map

## Current Dependency Chain

### Transcript Body Path

`Stage S RenderLine / working line`
-> `export_render` or `backend.pagination`
-> `PaginatedDocument.pages[*].slots[*].physical_line`
-> `source_render_line_id`
-> `build_page_reference_map()`
-> `IndexEntry(page, line)`
-> `IndexEntry.reference`
-> administrative index pages
-> certified package JSON

### Exhibit Path

`transcript_exhibits.anchor_utterance_id`
-> snapshot exhibit state
-> `anchor_utterance_id -> render_line_id` in `backend/api/packaging.py`
-> `ExhibitEvent.render_line_id`
-> `build_page_reference_map()`
-> `Exhibit.reference`
-> exhibit index page
-> package manifest / package JSON

## Consumer Map

| Source | Transform | Consumer |
| ---- | ---- | ---- |
| `PaginatedDocument` slot placement | `build_page_reference_map()` | all package indices |
| `source_render_line_id` first occurrence | `_resolve()` | `IndexEntry.page`, `IndexEntry.line` |
| `IndexEntry.page/line` | `IndexEntry.reference` property | admin-page text and package JSON |
| `ExhibitEvent.render_line_id` | `build_exhibit_index()` | `Exhibit.reference` and exhibit index |
| `ExportDocument.page_number/line_number` | direct writer emission | DOCX/PDF/RTF/TXT transcript output |

## Reference Sensitivity

### Highly Sensitive

- chronological index
- witness index
- exhibit index
- exhibit identity records inside package output

These are sensitive because they do not store a semantic anchor plus a separately recomputed visible ref. They store the resolved ref directly in the package/index layer.

### Moderately Sensitive

- export-visible page numbers
- export-visible line numbers

These are regenerated on export, so they do not break structurally. But they change the human-facing citation map.

### Low Sensitivity

- certificate page
- metadata validation

These do not directly consume page or line refs.

## Dependency Notes

### `backend/packaging/indices.py`

This is the single most important downstream dependency file.

It assumes:

- `source_render_line_id` is stable
- the **first** physical occurrence is the authoritative legal reference

If semantic pagination moves that first occurrence, all resolved references move.

### `backend/api/packaging.py`

This is the exhibit bridge.

It assumes:

- utterance anchor -> render line mapping is stable enough to feed index generation

If pagination authority changes after that bridge, the bridge itself still works, but every downstream page reference can drift.

### `backend/export/*_writer.py`

Writers do not own references.

They trust the page/line structure already computed in `ExportDocument`.

That means a cutover here is not a code break; it is a visible output drift.
