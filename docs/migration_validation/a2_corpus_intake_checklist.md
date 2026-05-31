# A2 Corpus Intake - Matched Certified-Transcript Collection Checklist

> Purpose: collect the matched certified data the A2 gate needs, in a form that can actually decide
> the pagination-authority question. Hand this to whoever owns the reporter-side data handoff.
> No code. Companion to `A2_CERTIFIED_CORPUS_GATE.md`.

## What "matched" means (the whole point)

One **pair**, tied to the same deposition:
1. the **DEPO-PRO job** - its working transcript state (we have this), and
2. the **reporter-certified output** for that *same* deposition (this is what's missing).

Unmatched certified transcripts (e.g. the Shaw/Filpi references) cannot score our engines - they
were never processed by DEPO-PRO, so there is nothing to compare them against line-for-line.

## Pick the right deposition (not just any certified one)

A2 is decided where the engines disagree. Phase 4A showed disagreement concentrates in **continuations**
(0 vs 106) and **exhibit references** (13/13 shifted). So a tie-breaking corpus must exercise those.

Prefer a deposition that has, in order of importance:
1. **Multiple exhibits actively discussed** (not just marked) - the highest-drift area.
2. **Long answers that run across a page break** - exercises continuation handling.
3. **Colloquy and objections** - secondary drift areas.
4. Ideally **multiple examinations** (direct + cross) for index/section variety.

A short, low-exhibit depo will pass both engines and decide nothing - avoid it as the primary case.

Best existing targets (already in Phase 4A): `278122f3-7361-404f-8226-9ae7eb6214e7`,
`1914cc18-7f6e...c233a`. If their certified output can't be obtained, run a deposition through DEPO-PRO
for which the certified Myler output is already in hand - selected by the criteria above.

## Required artifacts (per matched job)

- [ ] **DEPO-PRO job id** + confirmation its working transcript state is persisted.
- [ ] **Certified transcript** - the final reporter-certified version, page-numbered, as the reporter
      filed it. PDF acceptable; **searchable/extractable text strongly preferred** (a scanned image
      PDF forces OCR and adds error - flag if that's all that exists).
- [ ] **Certified witness/appearance index** as printed in the certified transcript.
- [ ] **Certified exhibit index** as printed - number, description, and the page each is marked/referenced.
- [ ] **Certificate page(s)** - reporter's certificate (and further certification, if Texas).
- [ ] **Reporter + jurisdiction** noted (e.g. Texas freelance, Myler CSR) so format expectations are known.

## Capture the page map explicitly (this is what gets scored)

For the certified transcript, record - or confirm it's extractable - the **page and line** for:
- [ ] each page **break** (where does page N end / N+1 begin),
- [ ] each **continuation** (answer/colloquy carried across a page boundary),
- [ ] each **exhibit reference** (the page/line where each exhibit is discussed),
- [ ] **long-answer**, **colloquy**, and **objection** start points.

These are the nine scoring categories. If any can't be extracted, note it - partial is still useful,
but exhibit references and continuations are the must-haves.

## Provenance / integrity

- [ ] Source of the certified file (reporter, agency, court filing) recorded.
- [ ] Confirmed it is the **certified** version, not a rough draft or uncertified working copy.
- [ ] Stored read-only alongside the job id; **not** committed into the app's transcript pipeline
      (this is validation reference data, like the existing reference depos - keep it out of `frontend/`
      and out of the runtime corpus).

## Hand-off result

A folder per matched job containing the items above, plus a one-line note on which divergence areas it
exercises (exhibits / continuations / long answers). That is the input to step 2 of the A2 sequence -
inspect format -> write the harness prompt against the real shape -> score -> decide.

## Sequence reminder (unchanged)

1. Secure the matched certified corpus (**this checklist**).
2. Inspect its real format.
3. Write the scoring-harness prompt against that shape.
4. Score `export_render` vs `backend.pagination` vs certified.
5. Decide A2.

Do **not** build the harness before step 1 is done.
