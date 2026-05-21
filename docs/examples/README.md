# Transcript Fixtures & Examples

Real transcript fixtures, known defects, and expected outputs. Used by the
correction engine tests (`tests/corrections/`) and the diff harness regression
suite (`tests/diagnostics/`).

These are **test inputs**, not production data. Keep them small, representative,
and committed with the code so tests are reproducible.

## Suggested contents

| File | Purpose |
|---|---|
| `heath_thomas_raw.txt` | Primary integration fixture — RAW utterances from the Heath Thomas deposition. Exercises off-record spans, garbled objections, embedded Q/A, honorifics, identifiers, and List-3 entities in one document. |
| `heath_thomas_expected.txt` | Expected Full-Mode rendered output for the above — the regression target. |
| `heath_thomas_expected_parity.txt` | Expected Parity-Mode output for the above. |
| `objection_examples.txt` | Isolated garbled-objection inputs and their LEX-01 expected outputs. |
| `off_record_examples.txt` | Clean and garbled off/on-record markers — exercises STR-01/02/03. |
| `verbatim_protection.txt` | Filler-, stutter-, false-start-, ellipsis-dense text — must pass through unchanged. |

## Rules for fixtures

- Keep each fixture focused on the rules it is meant to test.
- An "expected" file is a contract: if the engine's output diverges, either the
  engine has a defect or the fixture must be deliberately and reviewably updated.
- Do not put real case-confidential material in committed fixtures. Use the
  established test names (Heath Thomas / Delia Garza) which already serve as the
  project's standard examples.

---

*Wave 10. See `docs/architecture/transcript_engine/` for the specs these test.*
