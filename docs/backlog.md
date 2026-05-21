# Phase A Complete

## What's done
- Static HTML/CSS/JS workspace
- PyWebView desktop shell with local HTTP server
- Six-screen navigation via client-side router
- Modular JS (state, ui, provenance, router, per-screen, app)
- Single-file CSS
- In-memory mock data, no persistence
- Canonical schema documented in ufm_schema_v1.md
- Four-layer architecture documented in architecture.md

## What's deferred to Phase B
- FastAPI backend
- SQLite persistence per ufm_schema_v1.md
- Real case load/save/list endpoints
- Form template support (S.A. Legal Solutions default)
- Paste-and-parse intake parser
- Notice of Deposition (NOD) parser per docs/nod_parser_spec.md
- Session creation flow (case → session relationship in UI)

## What's deferred to Phase C
- Deepgram streaming integration
- Deepgram batch ingestion
- AI cleanup pass (Anthropic Claude API)
- DOCX/PDF export via real templates
- Keyterm JSON generation from parsed UFM

## What's deferred to Phase D
- Word-level audio sync (highlight word during playback)
- Certification cryptographic chain
- Diff-based revision history
- Multi-reviewer workflow
- Production hardening (error reporting, crash recovery)

## Known issues from polish pass

### Fixed
- `validateUFMField` referenced legacy DOM nodes `caseCaption` and `caseDeponent` that no longer exist in the Phase A.1 shell. Calls silently no-op'd today but threw uncaught exceptions before the prior cleanup; now guarded with explicit null checks (`ui/assets/js/screens/stage_1.js`).
- Stage 1 form did not rehydrate from `state.caseInfo` when revisited after navigating away. Added `hydrateUFMFormFromState()` invoked from the `screen:loaded` handler so previously-entered values reappear (`ui/assets/js/screens/stage_1.js`, `ui/assets/js/app.js`).
- Stage 5 re-rendered the pre-lock sign card on revisit even after the transcript had been certified. The `screen:loaded` handler now checks `state.caseInfo.certified` and shows the sealed card with the persisted signatory (`ui/assets/js/app.js`).
- Stage 6 export ignored the format dropdown and always wrote a `.docx`-named blob with `text/plain` MIME. Now reads `exportFormatSelect.value`, maps to the correct MIME, and writes the file with the matching extension (`ui/assets/js/screens/stage_6.js`).
- Stage 1 carried duplicate copies of `goToStage`, `getStageName`, and `triggerFileInput` that re-overwrote the canonical versions from `ui.js`/`app.js`. Removed (`ui/assets/js/screens/stage_1.js`).

### Deferred to Phase B (require backend / persistent store)
- Cross-screen state persistence — refresh or process restart wipes `state.caseInfo`, `transcriptLines`, `exhibits`, `correctionsMemory`, etc. Needs SQLite-backed reads/writes (real `simulateSave` instead of a toast).
- The "Request Certification Unlock" button on Stage 6 navigates back to Stage 5 but cannot actually unlock — no provenance trail, no co-signer flow. Needs a real unlock workflow tied to the certification chain.
- Stage 2 streaming uses canned `liveSentences`. Wiring a real Deepgram WebSocket is Phase C, but even the simulated stream lacks a persistence path back to a case file — every reload starts blank.
- Stage 2 "Test Input Level" simulates dBFS values via `Math.random()`. Real `getUserMedia` capture path exists in `requestMicPermissions()` but is never invoked from the diagnostic button.
- Stage 3 regex pipeline mutates `state.transcriptLines` in place with no undo and no diff record beyond a single provenance line. A real review layer (per `ufm_schema_v1.md`) would track word-level provenance.
- Stage 4 `quickJumpToLine` matches by `ex.line` (line index), not by `block_id`. Schema-aligned linking is a Phase B task once exhibits become FK rows.
- Stage 6 export concatenates strings to fake a `.docx`. Real DOCX generation needs `python-docx` (or a templated approach) in Phase C.
