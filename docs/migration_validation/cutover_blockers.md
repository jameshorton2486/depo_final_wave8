# Cutover Blockers

## Status

Pagination authority cutover remains blocked.

This blocker list combines:

- Phase 2A semantic drift findings
- Phase 2B downstream consumer analysis

## Blockers

### 1. Packaging indices are direct page-reference consumers

Severity: `CRITICAL`

Evidence:

- [backend/packaging/indices.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/indices.py)
- `build_page_reference_map()`
- `build_chronological_index()`
- `build_witness_index()`
- `build_exhibit_index()`

Why this blocks cutover:

- these consumers do not tolerate page-reference drift
- they are built on the current `PaginatedDocument` page map as ground truth
- semantic pagination already proved that page maps differ materially

### 2. Exhibit references are derived late and will drift immediately

Severity: `CRITICAL`

Evidence:

- `transcript_exhibits` stores `anchor_utterance_id`, not page refs
- [backend/api/packaging.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/api/packaging.py) maps anchor -> render line
- exhibit index resolution happens only after pagination

Why this blocks cutover:

- exhibit anchors themselves survive
- but package exhibit references do not
- Phase 2A already showed exhibit-discussion line ref drift

### 3. Export-visible page maps will change even if writers do not break

Severity: `HIGH`

Evidence:

- export writers emit `page.page_number` and `line.line_number`
- they do not compute their own refs

Why this blocks cutover:

- the code paths remain valid
- but the exported transcript’s citation map changes
- that affects any legal/user workflow depending on stable page/line identity

### 4. Certificate is not the blocker

Severity: `LOW`

Evidence:

- [backend/packaging/admin_pages.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/packaging/admin_pages.py)
- certificate page embeds no transcript body page refs or exhibit page refs

Why it matters:

- this narrows the migration scope
- the cutover blocker is the reference system, not the certificate wording

## Consumers That Must Move First

Before any authority switch:

1. `backend/packaging/indices.py`
2. package exhibit-reference generation
3. package/admin-page rendering of the three indices
4. validation fixtures asserting stable package references

## Consumers That Can Wait

Can be validated after reference consumers are stabilized:

- certificate generation
- general metadata validation
- exhibit CRUD storage
- export writer mechanics

## Minimum Safe Cutover Sequence

1. Establish the target reference policy:
   - preserve current live page map, or
   - adopt semantic page map and migrate all consumers
2. Update and validate package index generation against that policy.
3. Update and validate exhibit-reference derivation against that policy.
4. Diff package JSON and admin-page index outputs on real jobs.
5. Only after package references stabilize, evaluate export-visible authority cutover.

## Bottom Line

The cutover blocker chain is:

`pagination authority`
-> `page map`
-> `build_page_reference_map()`
-> `indices / exhibit references`
-> `package legality`

Until that chain is migrated deliberately, authority cutover is unsafe.
