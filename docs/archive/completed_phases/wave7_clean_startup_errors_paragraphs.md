> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 7 — Clean Startup, Error Surfacing, Transcript Paragraphs

Status: complete
Builds on: Wave 6 (`wave6_merge_transcripts_and_workspace.md`).

Three independent fixes requested together.

## 1. No mock data on startup

The app shipped with placeholder/sample data baked into several places.
It looked like real case data and was confusing. All of it is removed;
fields now start empty.

### What was removed

- **`app.js` — `initialRawNotesSeed`.** A hardcoded fake scheduling note
  (Dr. Donald Leifer / Sarah Jenkins / Nexus Pharma) was injected into the
  Stage 1 raw-notes textarea on every load. The constant, the
  `seedRawIntakeNotes()` function, and all three call sites are gone.
- **`state.js` — seeded `caseInfo.caption`.** Was
  `"SARAH JENKINS vs. NEXUS PHARMA INC."`; now empty. This value was being
  pushed into the Stage 1 caption field on load.
- **`state.js` — seeded `transcriptLines`.** Nine fake Vance/Leifer Q&A
  lines that filled the Stage 3 workspace before any real transcript was
  loaded. Now an empty array — the workspace is blank until a real
  transcript is ingested.
- **`state.js` — seeded `exhibits`, `correctionsMemory`, `provenance`.**
  All emptied. The provenance log now starts empty and records only real
  events.
- **`stage_2_transcripts.html` — Zoom credentials.** `zoomMeetingId` and
  `zoomPasscode` had hardcoded `value="847-9201-3855"` / `••••••••`. Now
  empty, with hint placeholders.
- **`stage_1_intake.html` — State default + caption placeholder.** The
  State field had `value="Texas"`; it is now empty with a `Texas` hint
  placeholder. The caption field's placeholder was the fictional case
  name; it is now a generic `PLAINTIFF NAME vs. DEFENDANT NAME` hint.

### Bug fixed: "New case" did not clear the form

`hydrateUFMFormFromState()` only wrote a field when its value was truthy
(`if (val)`). So when `newCase()` reset `caseInfo` to empty strings, the
empty values were skipped and the input boxes kept their old text. The
guard is removed — fields are now always assigned, so "+ New case"
genuinely blanks the form. `newCase()` also clears the raw-notes textarea
(which is not part of `caseInfo`) and no longer pre-fills State.

### Note on startup behavior

On launch the app still calls `hydrateFromServer()`, which loads your
most recently saved case if one exists. That is real saved data, not mock
data — it lets you resume work. For a blank slate, use the **+ New case**
button in the header. If you would prefer the app to always start blank
and never auto-resume, that is a one-line change — say the word.

## 2. Error handling, logging, and user-visible failures

Failures used to land silently in the browser console or the server log.
The user now gets told.

### Frontend

- **Global error surface (`app.js`).** `window` listeners for `error` and
  `unhandledrejection` now show a red toast when an uncaught error or a
  rejected promise occurs, instead of the UI silently freezing. The full
  detail still goes to the console (F12).
- **Backend-unreachable detection (`api.js`).** `fetch()` rejects (rather
  than returning an error status) when the server is down or on the wrong
  port. Both the JSON client and the file-upload path now catch this and
  raise a clear message — "Cannot reach the DEPO-PRO backend. Make sure
  the server is running…" — instead of an opaque "Failed to fetch".

### Backend

- **Global exception handler (`app.py`).** A catch-all handler logs the
  full traceback via loguru and returns a clean JSON `{"detail": ...}`
  with status 500. FastAPI still handles ordinary 400/404/422 responses
  itself — this only fires for genuinely unexpected errors, so the
  frontend always receives a usable `detail` string.
- **Startup logging.** The lifespan hook logs start, "Backend ready",
  and shutdown. Database initialization failures are logged with a full
  traceback and then re-raised so startup fails loudly instead of
  limping along with a broken database.

## 3. Transcript paragraphs grouped like the Deepgram Playground

### The problem

The application transcript fragmented every short pause onto its own
line. A witness reading an address aloud —

    A. 12135
    A. Stoney Glen,
    A. San Antonio, Texas
    A. 78247.

— became four lines, where the Deepgram Playground shows one:

    Speaker 2: 12135 Stoney Glen, San Antonio, Texas 78247.

### Cause

Deepgram's batch response splits `results.utterances[]` at short pauses,
so a single uninterrupted speaker turn arrives as several short
utterances. The assembler emitted one transcript line per Deepgram
utterance, with no regrouping.

### The fix

`backend/transcript/assembler.py` gained
`_merge_consecutive_speaker_utterances()`. Before the canonical objects
are built, it walks the utterance list and concatenates any run of
consecutive utterances that share a speaker index into one paragraph —
exactly the grouping the Deepgram Playground performs. Word objects keep
their own fine-grained timing and are repointed to the merged turn. The
verbatim Deepgram JSON (`asr_response.json`) is untouched and remains the
ground-truth raw artifact.

The Stage 2 → Stage 3 workspace loader builds one line per canonical
utterance, so no frontend change was needed — grouped utterances render
as grouped paragraphs automatically.

### Known limitation (not addressed here)

This fixes the **paragraph grouping** the user asked about. It does not
fix **speaker labeling**. The workspace still maps speaker 0 → "Q" and
every other speaker → "A". A real deposition has more than two speakers
(this one had eight: court reporter, examining attorney, witness,
defense counsel, etc.), so the Q/A prefixes are frequently wrong. Proper
examiner/witness/colloquy labeling is a separate, larger task — a good
candidate for the next wave.

### Tests

`tests/test_assembler.py` (new) — 3 tests: consecutive same-speaker
utterances merge into one paragraph with a correct combined time span;
an alternating Q/A exchange is left unmerged; all word objects survive
the merge and are repointed to the merged utterance.

Full suite: 120 passing, 3 skipped.
