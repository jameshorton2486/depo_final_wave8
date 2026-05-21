# Wave 4 — Real NOD Parser + Stage 1 Cleanup

Status: complete
Supersedes: the mock `simulateNODParsing` / `runAILegalParser` functions from Wave 3.

## Summary

This wave replaces the hardcoded mock parser with a real Notice of Deposition
(NOD) parser that reads uploaded PDF files and extracts UFM fields. It also
cleans up the Stage 1 (Intake) screen by removing dead UI elements.

Two passes were delivered together:

- **Pass A** — Stage 1 UI cleanup
- **Pass B** — Real NOD parser (backend + frontend wiring)

## Pass A — Stage 1 UI Cleanup

### Removed
- **Audio dropzone** ("Link Deposition Audio File"). Audio ingestion belongs on
  Stage 2 (Transcripts), where the queue and ingestion pipeline live. Keeping it
  on Stage 1 was redundant — Stage 2 already has its own audio upload. This is
  the only element removed from Stage 1.

### Kept
- **Deposition Notes dropzone.** Retained on Stage 1. The court reporter's own
  notes file is attached to the record here. Parsing its contents is a separate,
  future milestone (the format differs entirely from the NOD), but the dropzone
  and attachment behavior remain available.

### Changed
- The Stage 1 dropzone area is now a **2-up grid**: the NOD dropzone and the
  Deposition Notes dropzone side by side. The NOD dropzone gained clearer copy
  ("Drop Notice of Deposition (NOD) PDF") and is the primary extraction path.
- **Stage 5 (Certify)** gained `overflow-y-auto` on its panel. Previously it had
  no scroll wrapper and would clip content on shorter windows.
- The "Run AI Notes Parser" button was renamed "Run Text Parser on Pasted Notes"
  and is now a labelled placeholder — the text-paste path is not yet wired to a
  model. The PDF dropzone is the real extraction path.

### Side effect
- The earlier "case picker shows audio filename" bug is gone, because the audio
  dropzone that caused it no longer exists.

## Pass B — Real NOD Parser

### New backend package: `backend/services/nod_parser/`

| Module | Responsibility |
|---|---|
| `pdf_text.py` | Extract per-page text from a PDF via pdfplumber |
| `type_a_form.py` | Parse the S.A. Legal Solutions firm scheduling form |
| `type_b_pleading.py` | Parse the legal pleading body (the NOD itself) |
| `orchestrator.py` | Combine Type A + Type B into one canonical record |

### New endpoint: `POST /api/nod/parse`

Accepts a multipart PDF upload. Returns JSON with three keys:

- `fields` — flat dict matching the frontend's UFM field names
  (`ufmCause`, `ufmStyle`, `ufmWitness`, etc.)
- `metadata` — `detected_types`, `jurisdiction_type`, `location_type`,
  `additional_sessions`, `warnings`
- `keyterms` — suggested Deepgram keyterms with boost values and categories

Limits: `.pdf` only, 10 MB max. Errors return 400/413/422 with a `detail` message.

### What the parser handles

The parser was developed and tested against four real NOD packets:

1. **Federal pleading** — United States District Court, Western District of
   Texas. Detects `jurisdiction_type = federal`, `case_number_label =
   civil_action_no`. No county of venue (correct for federal).
2. **Texas state pleading** — judicial district + county of venue. Detects
   `cause_no`, the Nth Judicial District, and the county.
3. **Multi-deposition packet** — a single PDF containing two notices (e.g. two
   witnesses at 10am and 2pm). The parser detects all notices, imports the first
   as the primary session, and reports the rest in `additional_sessions` with a
   warning.
4. **Video form variant** — the S.A. Legal Solutions form has at least two
   layouts (standard and a video-focused variant with different field labels).
   Both are handled.

It also copes with several real-world PDF extraction quirks:

- Line-wrapped email addresses (`service@firm.co\nm`)
- HTML entities leaking from form fields (`&amp;`)
- Section-symbol (§) column tables interleaving party names with court headers
- Curly apostrophes (`\u2019`) in party names ("WOMEN'S HEALTH")
- pdfplumber collapsing spaces when text columns visually overlap

### Field extraction results

Against the four test documents, the parser populates all targeted fields:
cause number, caption/style, court (federal district or state judicial
district), county, witness name, date, start time, deposition address, and the
custodial (signing) attorney + their firm.

### Fields the parser intentionally leaves blank

The **Court Reporter (CSR) credentials** — name, license number, firm
registration, license expiration — are NOT extracted from the NOD. This is
correct: the reporting firm assigns the CSR *after* the booking, so this
information is not present in the notice. The user fills Block 3 in manually
after the reporter is assigned.

## Custodial attorney convention

When a notice is signed by co-counsel from multiple firms, the parser uses the
**signing attorney** (the one with `/s/` next to their name) as the custodial
attorney, and that attorney's firm as the requesting party. This matches the
"lead counsel of record" convention. If the legal pleading's signature block
can't be parsed, the parser falls back to the "Ordering Attorney" field from
the firm scheduling form.

## Known limitations / future work

- **Additional sessions are detected but not auto-imported.** When a packet
  contains multiple depositions, only the first becomes a session. The schema
  supports multiple sessions per case (`sessions.case_id`), but the UI does not
  yet expose a way to add the others. They are reported in `metadata.warnings`
  and the provenance log.
- **Jurisdiction is detected but not shown in the UI.** The parser correctly
  classifies federal vs. Texas state and stores it, but Stage 1 has no
  jurisdiction picker yet. Adding one is part of a future Stage 1 polish pass.
- **The text-paste parser is a placeholder.** Only the PDF dropzone does real
  extraction. Wiring the pasted-notes textarea to an LLM is future work.
- **Deposition Notes parsing is not implemented.** The court reporter's own
  notes template is a different document type and will get its own parser.
- **Keyterms are generated but not persisted.** The parser produces a keyterms
  list and the frontend displays it, but saving it as a Deepgram-ready file or
  API payload is a separate milestone.

## Testing

- `tests/test_nod_parser.py` — 24 unit tests covering jurisdiction detection,
  case identity, caption, deponent, date/time, signing attorney, multi-notice
  detection, and Type A form extraction. Uses extracted-text fixtures, not PDF
  binaries, so no client documents are committed.
- `tests/test_nod_api.py` — 4 integration tests covering the HTTP contract:
  file-type rejection, empty-file rejection, response shape, and cause-number
  extraction. Builds tiny PDFs in memory via reportlab.

Full suite: 61 tests passing (33 pre-existing + 28 new).

## New runtime dependencies

- `pdfplumber>=0.11,<1.0` — PDF text extraction
- `python-multipart>=0.0.12,<1.0` — required by FastAPI for file uploads

---

# Wave 4.1 — Text-Notes Parser (Stage 1 "Run Text Parser on Pasted Notes")

Status: complete
Follow-up to Wave 4.

## Problem addressed

On Wave 3, the parser button populated the schema with hardcoded mock data
(same values every time, regardless of input). Wave 4 replaced that with an
honest no-op placeholder — correct, but it left the "Run Text Parser on Pasted
Notes" button doing nothing. This follow-up makes that button actually work.

## What was built

- `backend/services/keyterms.py` — keyterm cleaning/prioritizing logic,
  salvaged and adapted from an earlier DEPO-PRO prototype's
  `keyterm_extractor.py` (the prototype's `core.config` / `app_logging`
  imports were replaced with local constants and the loguru logger).
- `backend/services/intake_text_parser.py` — parses free-text scheduling
  notes into UFM fields. Recognizes labelled lines ("Cause No:", "Deponent:",
  "Court Reporter:", "Deposition location:", etc.), unpacks composite lines
  (a "Court Reporter:" line containing name + license + expiration + firm
  registration), normalizes dates to ISO and times to "H:MM AM/PM", and
  extracts explicit keyterms from an "Acoustic spellings to sync:" line.
- `backend/api/intake.py` — `POST /api/intake/parse-text`, accepts JSON
  `{text}`, returns the same `{fields, metadata, keyterms}` shape as the NOD
  parser so the frontend reuses one field-application code path.
- `frontend/assets/js/screens/stage_1.js` — "Run Text Parser on Pasted Notes"
  now does a real fetch, applies parsed fields to the Schema Board, and seeds
  the keyterm dictionary.

## Important limitation

The parser only extracts what is actually in the pasted text. If the notes
do not mention a cause number, witness, or date, those fields stay blank —
the parser fills gaps, it never invents data. To populate the full schema,
combine pasted notes (good for CSR credentials and logistics) with a NOD PDF
(good for case identity, witness, and schedule).

## Testing

`tests/test_intake_text_parser.py` — 25 tests covering date/time
normalization, field extraction, composite-line unpacking, keyterm
generation, edge cases, and the API endpoint.

Full suite: 86 tests passing.
