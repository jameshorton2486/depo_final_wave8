# Pagination Migration Plan

Audit date: 2026-05-30  
Mode: read-only planning

This is a proposed implementation sequence only. No changes are made in this audit.

## Step 1 — Build the adapter layer

Goal:

- bridge the active Stage S / export path to `backend.pagination` without changing downstream geometry/export/package contracts yet

Why first:

- the core mismatch is input shape (`RenderLine` vs preformatted stream) and wrapping ownership

Primary files:

- `backend/transcript/export_render.py`
- `backend/pagination/paginator.py`
- possibly `backend/pagination/wrapping.py`

## Step 2 — Add dual-run validation mode

Goal:

- run current private pagination and canonical `backend.pagination` side by side on the same inputs

Compare:

- page counts
- line counts
- `(page, line)` references
- continuation states
- resulting `ExportDocument` shape

Why:

- catches page/line drift before authority switches

## Step 3 — Validate export preview and file export

Goal:

- ensure preview and real export still match after the canonical paginator path is introduced

Primary files:

- `backend/api/transcripts.py`
- export-related tests

## Step 4 — Switch packaging to the same authority

Goal:

- packaging uses the same canonical paginator-backed `PaginatedDocument` as export

Primary files:

- `backend/api/packaging.py`
- packaging tests

Why after export:

- export path is the more user-visible and easier validation surface; packaging depends on stable page/line refs from the same paginated object

## Step 5 — Cut over runtime authority

Goal:

- make `backend.pagination` the only live page-allocation authority

Meaning:

- active preview/export/package paths no longer rely on `_paginate_formatted_stream(...)`

## Step 6 — Remove duplicate path

Goal:

- retire private pagination logic in `export_render`

Constraint:

- only after Step 5 is stable and tests/validation all pass

## Recommended Validation Order During the Later Build Pass

1. canonical paginator direct tests
2. export preview
3. DOCX/PDF export
4. packaging/index refs
5. certification/package validation

## Implementation Boundaries

This migration pass should stay scoped to:

- pagination authority
- adapter/wrapping alignment
- runtime callsite rewiring
- tests required to prove equivalence or intentional drift

It should explicitly avoid bundling:

- UFM feature improvements
- certificate clause changes
- caption branching
- exhibit feature expansion
- insertions work

## End State

Successful completion means:

- one pagination authority
- one active flow-rule authority
- geometry/export/package all consume the same paginated source
- page/line references come from the same engine everywhere
