# Phase 1 Runtime Comparison

## Baseline

- Branch: `main`
- Pre-change pytest baseline: `669 passed, 1 skipped`
- Post-change pytest: `671 passed, 1 skipped`

## Compared Paths

Authoritative path:

`Transcript -> Stage S -> export_render private pagination -> Geometry -> Export`

Validation-only candidate path:

`Transcript -> Stage S -> export_render formatted stream -> adapter -> backend.pagination.paginate()`

## Comparison Fixture

- Transcript ID: `TEST-FIXTURE: phase1-synthetic-mixed-flow`
- Source shape: repeated Q/A + colloquy + flagged lines
- Stream entries: `198`

## Measured Output

| Metric | Authoritative | Candidate | Result |
| ---- | ---- | ---- | ---- |
| Total pages | 8 | 8 | MATCH |
| Placed lines | 198 | 198 | MATCH |
| Page breaks | export-{i} page refs | export-{i} page refs | MATCH |
| Line numbers | slot refs by export-{i} | slot refs by export-{i} | MATCH |
| Page references | `(page, slot)` by export-{i} | `(page, slot)` by export-{i} | MATCH |

Observed differences:

- none at page-allocation level

Continuation status:

- `authoritative=0 candidate=7 (semantic continuation parity not yet authoritative in Phase 1 adapter)`

## Interpretation

Phase 1 successfully proves that the candidate paginator can reproduce the
runtime page-allocation result **when given an adapted version of the same
preformatted stream**.

It does **not** yet prove that the candidate paginator is semantically
equivalent to the current live path for:

- continuation ownership
- Q/A tether decisions
- logical structure spanning behavior

That gap is expected from the audited interface mismatch.
