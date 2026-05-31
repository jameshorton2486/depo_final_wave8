# Reference Ownership Audit

## Question

How should DEPO-PRO own transcript references?

Current behavior makes visible legal citations:

- `Page N`
- `Page N, Line M`

look like the owned reference.

This audit reviews whether ownership should instead derive from:

- `RenderLine` identity
- anchored transcript identity
- snapshot-bound canonical transcript identity
- or a hybrid model

## Current Source of Truth

### 1. Page references

Current source of truth for page references is:

- the frozen `PaginatedDocument`
- specifically the **first physical occurrence** of each `source_render_line_id`

Evidence:

- [backend/packaging/indices.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/indices.py)
  - `build_page_reference_map()`
  - uses `phys.source_render_line_id`
  - stores first `(page_number, slot_number)`

So the current model is:

`page allocation -> first physical occurrence -> legal reference`

Not:

`semantic identity -> stable reference -> rendered citation`

### 2. Exhibit references

Current source of truth for exhibit references is a two-step chain:

1. exhibit storage owns `anchor_utterance_id`
2. packaging resolves that anchor to `render_line_id`
3. pagination resolves that `render_line_id` to `(page, line)`

Evidence:

- [backend/transcript/repository.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/transcript/repository.py)
  - `transcript_exhibits.anchor_utterance_id`
- [backend/api/packaging.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/api/packaging.py)
  - `_build_paginated_and_index_inputs_from_snapshot_state()`
  - `anchor_utterance_id -> render_line_id`
- [backend/packaging/indices.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/indices.py)
  - `render_line_id -> page,line`

So exhibit references are **already internally anchor-owned**, but the
package output still treats the final page citation as if it were the
reference itself.

## Are references generated from page allocation?

Yes.

Visible package references are generated from page allocation.

Evidence:

- `IndexEntry.reference` is derived from `page` and `line`
- `Exhibit.reference` is stored as resolved `"Page N, Line M"`
- those values originate from `build_page_reference_map(paginated_document)`

This means visible citations are downstream of pagination authority, not
independent from it.

## Can current references survive pagination changes?

No, not as currently modeled.

They can survive only if:

- the page map stays the same, or
- all downstream consumers are willing to accept new page refs

Phase 2A already established that page maps drift materially under the
semantic paginator.

Therefore the current visible-reference model is **not stable across
pagination authority changes**.

## Stable identities already present in the code

The system already carries more stable identities than it exposes:

### Transcript body

- `RenderLine.line_id`
- `PhysicalLine.source_render_line_id`
- snapshot binding via `transcript_snapshot_id` + `state_hash`

### Exhibit layer

- `anchor_utterance_id`
- resolved `render_line_id`

### Package layer

- `TranscriptPackage.identity.transcript_snapshot_id`
- `PackageManifest.identity`

The missing piece is not identity generation. The missing piece is
**ownership policy**: which identity is authoritative, and which
citations are merely rendered views of it.

## Recommendation Options

### Option A — Maintain page-number ownership

Meaning:

- visible `Page N, Line M` remains the owned reference
- pagination output remains the primary source of truth

Strengths:

- matches current behavior
- smallest conceptual change

Weaknesses:

- makes pagination authority changes inherently dangerous
- provides no stable internal identity across page-map changes
- keeps package references tightly coupled to one pagination engine

Assessment:

- viable only if runtime page map is preserved indefinitely
- poor fit for planned authority migration

### Option B — Introduce stable reference ownership

Meaning:

- visible page refs stop being the owned identity
- ownership moves to stable transcript identity only

Candidates:

- `RenderLine.line_id`
- `anchor_utterance_id`
- snapshot-bound canonical transcript identity

Strengths:

- robust against pagination changes
- clean ownership model

Weaknesses:

- page/line citations are still the human/legal surface
- pure stable-id ownership alone is insufficient for current transcript products
- would require broader product and packaging redesign

Assessment:

- architecturally clean
- too abrupt for this codebase as a first migration move

### Option C — Hybrid model

Meaning:

- stable semantic identity is the owned internal reference
- visible `Page N, Line M` remains a derived, rendered citation
- package outputs carry both when needed

Concrete form:

- transcript-line ownership:
  - `transcript_snapshot_id` + `render_line_id`
- exhibit ownership:
  - `transcript_snapshot_id` + `anchor_utterance_id`
  - optionally resolved `reference_render_line_id`
- visible reference:
  - computed from current authoritative pagination

Strengths:

- fits the existing code seams
- preserves legal page citations
- decouples ownership from one page map
- gives cutover work a stable internal anchor

Weaknesses:

- adds dual-reference concepts to package/index models
- requires deliberate migration work before cutover

Assessment:

- best match for the current architecture and future migration needs

## Recommendation

Recommend: **Option C — Hybrid model**

Reason:

DEPO-PRO already has stable semantic identifiers in the transcript and
exhibit layers, and it still must emit visible page/line citations for
legal output. A hybrid model uses both correctly:

- stable identity owns the reference internally
- page/line remains the rendered legal citation

That is the only option that both:

1. respects current legal output requirements
2. makes pagination authority migration tractable
