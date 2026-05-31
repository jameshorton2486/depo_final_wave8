# Phase 4A — Legal Page Map Validation

## Result

Phase 4A completed as a **validation-only** pass.

Runtime authority was **not** changed.

Current runtime remains:

`Transcript -> Stage S -> export_render private pagination -> Geometry/Export/Packaging`

Candidate evaluated:

`Transcript -> Stage S semantic line model -> backend.pagination.paginate() -> comparison only`

## Files

- [backend/pagination/legal_validation.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/backend/pagination/legal_validation.py)
- [tests/test_phase4a_legal_validation.py](/abs/path/C:/Users/james/PycharmProjects/PythonProject/depo_final_wave8/tests/test_phase4a_legal_validation.py)

## Corpus Used

Real persisted transcript jobs:

1. `278122f3-7361-404f-8226-9ae7eb6214e7`
2. `1914cc18-f7be-4494-a12d-fbb8de2c233a`

Both are the same real corpus previously used in Phase 2A semantic validation.

## Important Limitation

This repo does **not** currently contain an independently verified certified PDF
for either of the two real jobs above.

The local archived export sample in `docs/ufm_audit/samples/` is not linked to
either validation job, so it was **not** treated as legal ground truth for the
decision.

Therefore this pass can answer:

- how the two engines differ on real transcripts
- which transcript features drift materially

But it cannot conclusively answer:

- which page map is legally correct in certified Texas practice

without an external matched certified-transcript corpus.

## Method

For each real job:

1. Load the persisted working transcript and participant mapping.
2. Rebuild Stage S.
3. Build the live export-style page map using the exact runtime Stage S -> working-line mapping.
4. Build the semantic candidate page map using a calibrated semantic representation:
   - visible `Q.` / `A.` prefixes
   - blank-line cadence preserved
   - wrap width `54`
5. Compare:
   - total pages
   - continuation states
   - logical-line page reference drift
   - logical-line page-number drift
   - long answers
   - colloquy
   - objections
   - exhibit-discussion lines

## Measured Results

### Job `278122f3-7361-404f-8226-9ae7eb6214e7`

- source: `heath_thomas.mp3`
- logical lines: `809`
- live pages: `108`
- semantic pages: `107`
- live continuations: `0`
- semantic continuations: `106`
- logical lines with different `(page, slot)` references: `808 / 809`
- logical lines with different page numbers: `536 / 809`
- long answers with different page numbers: `19 / 26`
- colloquy lines with different page numbers: `67 / 114`
- objections with different page numbers: `31 / 37`
- exhibit-discussion lines with different page numbers: `8 / 13`
- exhibit-discussion lines with different `(page, slot)` references: `13 / 13`

### Job `1914cc18-f7be-4494-a12d-fbb8de2c233a`

- source: `heath_thomas.mp3`
- logical lines: `812`
- live pages: `108`
- semantic pages: `107`
- live continuations: `0`
- semantic continuations: `106`
- logical lines with different `(page, slot)` references: `802 / 812`
- logical lines with different page numbers: `424 / 812`
- long answers with different page numbers: `13 / 26`
- colloquy lines with different page numbers: `44 / 107`
- objections with different page numbers: `23 / 38`
- exhibit-discussion lines with different page numbers: `5 / 13`
- exhibit-discussion lines with different `(page, slot)` references: `13 / 13`

## Interpretation

### 1. The ownership and consumer problem remains solved

Phase 3A/3B work held. This pass did not expose any new reference-integrity
risk outside page-map semantics.

### 2. The remaining disagreement is still semantic pagination

The candidate semantic paginator consistently changes:

- total page count: `108 -> 107`
- continuation behavior: `0 -> 106`
- line references: material drift across most logical lines

That confirms the cutover question is now isolated to transcript-behavior
correctness, not architectural safety.

### 3. Exhibit discussion remains high-risk under cutover

Even without formal persisted exhibit-anchor scoring for these jobs, every
observed exhibit-discussion line changed `(page, slot)` reference in both runs.

That is still too much drift to justify authority cutover on engineering
grounds alone.

### 4. Local repo evidence is insufficient for the final legal decision

The repo can prove:

- the engines differ materially
- where they differ
- that the system can now survive those differences architecturally

The repo cannot prove:

- that `backend.pagination` is closer to certified Texas transcript output

because it lacks a matched independent certified-transcript corpus for the same
jobs.

## Decision

**Do not perform authority cutover yet.**

## Next Required Gate

Use actual certified transcript artifacts matched to the same transcript jobs
and score:

- page breaks
- long answers
- colloquy
- objections
- exhibit discussions
- continuation behavior

The next decision should be driven by certified transcript behavior, not by
architecture preference.
