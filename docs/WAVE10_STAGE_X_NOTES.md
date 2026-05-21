# Wave 10 — Stage X (Legal Lexicon) Delivery

This drop adds **Stage X** to the correction engine — §22 step 10, the first
of the three structural stages.

## Install

This drop **replaces the whole `backend/corrections/` and `tests/corrections/`
folders**. Two existing files changed (`patterns.py`, `pipeline.py`); one new
file added (`legal_phrases.py`); one new test file (`test_legal_phrases.py`).
Overwriting both folders is the clean way to apply it.

```powershell
$zip  = "C:\Users\james\Downloads\depo-pro-wave10-stage-x.zip"
$proj = "C:\Users\james\PycharmProjects\PythonProject\depo_final_wave8"

Expand-Archive -Path $zip -DestinationPath "$env:TEMP\w10x" -Force
Copy-Item "$env:TEMP\w10x\backend\corrections" "$proj\backend\" -Recurse -Force
Copy-Item "$env:TEMP\w10x\tests\corrections"   "$proj\tests\"   -Recurse -Force
```

Verify:

```powershell
cd $proj
.venv\Scripts\activate
python -m pytest -q
```

Expect **213 passed, 3 skipped**.

## What Stage X does

Stage X is deterministic and no-AI. It is deliberately narrow because of a
hard limit established from your `Permitted_Corrections.docx`:

> Correcting a real-word garble back to its intended legal phrase
> ("circulation" -> "speculation") needs semantic context. The garble is a
> valid English word, so no regex can safely distinguish it from a
> correctly-heard word. That is an AI-tier task (List 2) and is deferred.

So Stage X does exactly two safe things:

**LEX-01 — legal-term formatting.** Casing/spacing normalisation of legal
terms of art — never a word swap. Seeded conservatively: Latin terms
lowercased (`Voir Dire` -> `voir dire`, `In Camera` -> `in camera`), `Bates`
capitalised. Idempotent and substring-safe.

**FLAG-03 — garbled-objection detection.** Known garbled objection lead-ins
raise a `[SCOPIST: FLAG]` for the reporter to verify against audio. The garble
is left **verbatim** — Stage X never rewrites it.

Stage X runs in **Full Mode only**. Parity Mode (spec 3A) skips it — verified
by test.

## The lexicon table is yours to expand

`backend/corrections/patterns.py` has two Stage X tables, both seeded
minimally and clearly commented:

- `LEGAL_PHRASE_LEXICON` — LEX-01 formatting entries. **Rule for adding:** the
  two sides of an entry must be the *same words*, differing only in
  casing/spacing. A word substitution does not belong here — that is a garble
  fix, which is AI-tier.
- `OBJECTION_GARBLE_DETECT` — FLAG-03 garble patterns -> verification hints.
  Add the garbles you see recurring in real Deepgram output.

I seeded these conservatively rather than inventing entries — which garbles
recur, and their canonical forms, is your court-reporting domain knowledge.
Grow both tables from real data.

## Known cosmetic note

When two garble patterns overlap on the same phrase (e.g. both "action calls
for" and "calls for circulation" match), two flags are raised on nearly the
same text and their inline markers can appear out of numeric order. Not a
defect — both are legitimate signals — but if it reads as noisy, tune
`OBJECTION_GARBLE_DETECT` so patterns don't overlap.

## A bug this drop fixed

Building Stage X surfaced a real defect in the Stage G false-start guard. The
old pattern `\b\w+\s*-- ` consumed the *word before* the false-start dash —
so in "Voir Dire -- the", the word "Dire" was hidden inside a guard sentinel
and Stage X could not see "Voir Dire" as a unit to reformat. Fixed: the guard
now uses a lookbehind `(?<=\w)\s*--\s` — it still protects the false-start
dash but no longer swallows the preceding word. All guard tests still pass.

## Test status

- New: **10 Stage X tests**. Full corrections suite: 56 tests.
- Full project: **213 passed, 3 skipped** — no regressions.

## Next steps

Per the §22 build order, with the honest deterministic scope you approved:

1. **Stage S** — off-record / pre-record / post-record structuring +
   parenthetical insertion. Genuinely deterministic (the regexes and the
   parenthetical-forms table are in your Script & Regex Reference).
2. **Stage Q** — Q/A / colloquy line formatting by confirmed role, with the
   UFM tab shapes. Role-based formatting only; merged-block *splitting* is
   AI-tier and deferred.
3. **Wave 11** — the Workspace speaker panel; wires the completed engine into
   the app.
