# Pagination Migration Test Impact

Audit date: 2026-05-30  
Mode: read-only planning

## Test Classification

| Test File | Classification | Why |
|---|---|---|
| `tests/test_wave18_export.py` | `MAJOR UPDATE` | export output path currently depends on `export_render` private pagination; switching authority may change page/line allocation and output shape |
| `tests/test_wave19_pagination_geometry.py` | `MINOR UPDATE` | already tests canonical paginator + geometry directly; likely gains authority assertions but core engine tests should remain valid |
| `tests/test_wave20_packaging.py` | `MINOR UPDATE` | already uses `paginate(...)` in fixtures, so it is closer to the target architecture than runtime is |

## Additional Likely Affected Areas

These were not required in the prompt’s minimum set, but are likely to feel migration fallout:

| Test Area | Expected Impact | Why |
|---|---|---|
| export preview / transcript API tests | `MINOR UPDATE` | preview/build path wiring changes in `backend/api/transcripts.py` |
| export validation tests | `MINOR UPDATE` | validation uses paginated documents and may need authority-alignment assertions |
| packaging/certification path tests | `MINOR UPDATE` | packaging path may consume different page allocation behavior if switched to canonical paginator |

## Expected Failure Modes During Migration

1. **Page numbering drift**
   - output page breaks change relative to current export fixtures

2. **Line numbering drift**
   - packaging/index assertions tied to `(page, line)` may shift

3. **Continuation behavior appearing where runtime never had it**
   - tests that implicitly assume no continuation metadata may need updates

4. **Preview/export mismatch during intermediate steps**
   - if one path migrates before the other

5. **Formatting drift from wrapping authority changes**
   - if canonical wrapping differs from the private preformatted stream logic

## Expected Test Strategy in the Later Build Pass

Recommended pattern:

- keep `tests/test_wave19_pagination_geometry.py` as the canonical paginator truth set
- update `tests/test_wave18_export.py` to validate export output under canonical pagination
- update `tests/test_wave20_packaging.py` only where runtime wiring changes alter assumptions, not to weaken packaging expectations

## Bottom Line

The highest test churn risk sits in export-path tests, not in the canonical paginator tests themselves.
