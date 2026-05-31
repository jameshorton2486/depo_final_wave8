# Phase 1 Adapter Design

## Scope

Phase 1 adds a validation-only adapter layer between the live
`export_render` preformatted stream and `backend.pagination.paginate()`.
It does **not** change pagination authority.

Authoritative runtime remains:

`Transcript -> Stage S -> export_render private pagination -> Geometry -> Export`

Validation-only path added:

`Transcript -> Stage S -> export_render formatted stream -> adapter -> backend.pagination.paginate()`

## Interface Mismatch

The runtime export path currently paginates a flattened, pre-wrapped stream:

- input shape: `list[tuple[text, kind]]`
- each tuple is already one intended physical line
- indentation is embedded in the text itself

The canonical paginator expects semantic Stage S lines:

- input shape: `list[RenderLine]`
- wrapping happens inside `backend.pagination.wrapping.wrap_render_line()`
- continuation behavior is derived from logical line structure

That mismatch is why this pass is an **adapter** pass, not a cutover pass.

## Implemented Adapter

Location:

- [backend/pagination/validation.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/pagination/validation.py)

Design:

1. Take the authoritative formatted stream from `export_render`.
2. Convert each `(text, kind)` entry into one synthetic `RenderLine`.
3. Preserve stable source ids as `export-{i}` so page references can be compared.
4. Set `wrap_width` to the longest formatted line in the current stream so the
   candidate paginator preserves the live one-entry-to-one-physical-line contract.
5. Run `backend.pagination.paginate()` on those synthetic lines.
6. Compare the resulting `PaginatedDocument` to the authoritative runtime
   `PaginatedDocument`.

Synthetic `RenderLine` properties:

- `line_id = export-{index}`
- `line_type = kind`
- `text = formatted text`
- `tab_level = 0`

## Why Runtime Output Stays Unchanged

`render_export_with_layout()` still:

- builds the same formatted stream
- paginates it with `_paginate_formatted_stream()`
- returns the same `(ExportDocument, PaginatedDocument)` contract

The new candidate paginator run is validation-only:

- it executes after the authoritative pagination
- it does not alter the returned export document
- it does not alter the authoritative paginated document
- it only logs if comparison differences are detected

## Known Limitation

This adapter validates **page allocation parity**, not full semantic parity.

Because it starts from a **pre-wrapped physical stream**, it cannot yet prove:

- Q/A tether parity
- semantic continuation parity
- logical-structure continuation ownership

Those remain Phase 2 concerns before any authority cutover.
