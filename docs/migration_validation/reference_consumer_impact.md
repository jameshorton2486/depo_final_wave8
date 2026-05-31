# Reference Consumer Impact Audit

## Scope

This audit answers the Phase 2B question:

> What systems consume page references, and what breaks if pagination authority changes?

It is based on direct code inspection of:

- [backend/packaging/indices.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/indices.py)
- [backend/packaging/packager.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/packager.py)
- [backend/packaging/admin_pages.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/admin_pages.py)
- [backend/packaging/model.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/model.py)
- [backend/packaging/validation.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/validation.py)
- [backend/api/packaging.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/api/packaging.py)
- [backend/api/exhibits.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/api/exhibits.py)
- [backend/transcript/repository.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/transcript/repository.py)
- [backend/export/export_service.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/export/export_service.py)
- writers under `backend/export/`

## Consumer Table

| Consumer | Uses Page Ref | Uses Line Ref | Uses Exhibit Ref | Cutover Risk |
| ---- | ---- | ---- | ---- | ---- |
| `backend/packaging/indices.py` chronological index | Yes | Yes | Indirectly | CRITICAL |
| `backend/packaging/indices.py` witness index | Yes | Yes | No | HIGH |
| `backend/packaging/indices.py` exhibit index | Yes | Yes | Yes | CRITICAL |
| `backend/packaging/admin_pages.py` index pages | Yes, rendered from index entries | Yes | Yes | HIGH |
| `backend/packaging/model.py` `IndexEntry.reference` | Yes | Yes | Indirectly | HIGH |
| `backend/packaging/model.py` `Exhibit.reference` | Yes | Yes | Yes | CRITICAL |
| `backend/packaging/packager.py` | Consumes generated indices | Consumes generated indices | Yes | HIGH |
| `backend/api/packaging.py` snapshot exhibit-event mapping | Indirectly | Indirectly | Yes | CRITICAL |
| `backend/packaging/validation.py` | No hard page dependency | No hard page dependency | No | LOW |
| Certificate page generation | No | No | No embedded page refs | NONE |
| Export writers (`docx/pdf/rtf/txt`) | Regenerate displayed page/line labels from `ExportDocument` | Yes | No | MEDIUM |
| `backend/api/exhibits.py` / `backend/transcript/repository.py` | Stores utterance anchors, not page refs | No | Anchor only | MEDIUM |

## Findings By Consumer Category

### 1. Indices

Primary dependency:

- `build_page_reference_map(paginated_document)` in [backend/packaging/indices.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/indices.py)

What it does:

- walks frozen `PaginatedDocument.pages[*].slots[*].physical_line`
- records the **first** `(page_number, slot_number)` for each `source_render_line_id`
- uses that map to resolve:
  - chronological index entries
  - witness index entries
  - exhibit index entries

Why cutover risk is high:

- Phase 2A already showed material drift in `(page, slot)` references
- index generation is not insulated from that drift
- witness and exhibit indices would silently change without any packaging code change

Most exposed functions:

- `build_page_reference_map()`
- `_resolve()`
- `build_chronological_index()`
- `build_witness_index()`
- `build_exhibit_index()`

### 2. Exhibit Anchors

Stored source of truth:

- `transcript_exhibits.anchor_utterance_id`
- created/updated through [backend/transcript/repository.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/transcript/repository.py)
- exposed through [backend/api/exhibits.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/api/exhibits.py)

Important distinction:

- exhibit storage does **not** persist page references
- it persists **utterance anchors**
- packaging later converts those anchors into `render_line_id`, then into page references

Packaging bridge:

- [backend/api/packaging.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/api/packaging.py)
  - `_build_paginated_and_index_inputs_from_snapshot_state()`
  - maps `anchor_utterance_id -> render_line_id`
  - creates `ExhibitEvent(render_line_id=...)`

Why cutover risk is critical:

- utterance anchors stay stable
- but page references derived from those anchors do not
- Phase 2A already showed exhibit-discussion line page-reference drift
- formal exhibit index citations would change immediately under authority cutover

### 3. Packaging

Packaging does not compute page refs itself; it **consumes** them.

Key callsite:

- [backend/packaging/packager.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/packager.py)
  - `generate_indices(index_inputs, paginated_document)`

What packaging assumes:

- `paginated_document` is already authoritative and frozen
- `indices` produced from it are legally referenceable
- `included_exhibits` in the manifest are stable exhibit identities

Where reference assumptions surface:

- index pages rendered through `admin_pages.build_*_index_page(...)`
- `TranscriptPackage.indices`
- `Exhibit.reference`

Why continuation ownership matters:

- `build_page_reference_map()` uses **first physical occurrence**
- if semantic pagination changes where a logical line first lands, packaging references drift
- packaging itself does not notice or compensate

### 4. Certification

Certificate page in [backend/packaging/admin_pages.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/admin_pages.py):

- does **not** embed transcript body page refs
- does **not** embed exhibit page refs
- does **not** embed continuation refs

What it does embed:

- package identity
- snapshot id
- state hash
- counsel-of-record and Stage 5 metadata

Result:

- certificate wording itself is not a reference consumer
- certification remains indirectly exposed only because it certifies a package whose indices may drift

### 5. Export

Export writers do not persist external page references. They simply emit the page and line numbering in the `ExportDocument` they are given.

Evidence:

- `backend/export/docx_writer.py`
- `backend/export/pdf_writer.py`
- `backend/export/rtf_writer.py`
- `backend/export/txt_writer.py`

They consume:

- `page.page_number`
- `line.line_number`

They do **not** resolve:

- `render_line_id`
- exhibit anchors
- packaging index refs

Risk classification:

- MEDIUM, not because they break internally
- but because a cutover changes the visible transcript page map and therefore any downstream human/legal citation based on exported files

## Final Recommendation

### 1. Which consumers break if pagination authority changes?

The consumers that break first are:

- packaging index generation
- exhibit index references
- any package artifact relying on `IndexEntry.reference`
- any exhibit identity record relying on `Exhibit.reference`

These are the true downstream reference consumers.

### 2. Which consumers must be migrated before cutover?

Must be migrated or explicitly revalidated before cutover:

- `backend/packaging/indices.py`
- `backend/api/packaging.py` exhibit-event bridge
- package/admin-page rendering of chronological, witness, and exhibit indices
- any tests asserting stable package page references

### 3. Which consumers require no changes?

Likely no logic changes required:

- certificate wording/generation
- metadata validation
- exhibit CRUD storage itself

But they still need regression validation because they sit inside packages whose references change.

### 4. What is the minimum safe cutover sequence?

1. Freeze and compare reference maps for the target jobs.
2. Migrate and validate `backend/packaging/indices.py` consumers first.
3. Revalidate exhibit anchor -> render line -> page reference resolution.
4. Reassemble packages and diff all three indices.
5. Only then evaluate export-visible page-map cutover.

Until that is done, pagination authority cutover remains unsafe.
