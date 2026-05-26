> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 6 — Merge: Transcripts Engine + Canonical Workspace

Status: complete
Combines: `wave5_stage2_transcripts_engine.md` and
`wave5_canonical_models_workspace.md` — two Wave 5 tracks that were built
in parallel without knowledge of each other.

## Why this wave exists

Two separate Wave 5 efforts branched off the same Wave 4 base:

- **Wave 5 — Stage 2 Transcripts Engine** — the real transcription ingestion
  pipeline (Deepgram client, assembler, packets, repository, ingest
  orchestrator, `/api/transcripts/*` router) plus the rewritten Stage 2
  frontend.
- **Wave 5 — Canonical Models + Case Workspace** — one canonical domain
  vocabulary (`backend/models/canonical.py`), a `to_canonical()` method on the
  NOD parser, and an on-disk workspace service (`backend/services/workspace.py`)
  with a `/api/intake/workspace` endpoint.

Neither branch contained the other's work. Wave 6 merges them into one
codebase so "the current build" is unambiguous again.

## Merge outcome

The two branches were almost entirely non-overlapping — the transcripts work is
new packages plus frontend; the canonical work is models, a service, and parser
additions. The only files that needed reconciliation were three where the
transcripts branch made purely additive changes the canonical branch never
touched:

- `backend/app.py` — registers the transcripts router (one import, one
  `include_router`).
- `backend/api/__init__.py` — adds `transcripts` to the router package.
- `frontend/assets/js/app.js` — Stage 2 `screen:loaded` refreshes persisted
  transcript jobs.

There were no true conflicts. After merging, the full suite is **117 passing,
3 skipped** — both branch test suites (`test_transcripts_api.py` and
`test_workspace.py`) green together, plus all prior tests.

## Folder rename

The project folder is now `depo-pro/`, not `depo_final-wave4/`. The old name
was misleading — the codebase had been on Wave 5 for two tracks and is now on
Wave 6. "Wave N" is a changelog concept tracked in `docs/`, not a folder name.
No code referenced the folder name (all imports are relative to the project
root), so the rename is cosmetic and safe.

## Research-informed changes (Deepgram reuse report)

A deep-research report on Deepgram pre-recorded transcription was reviewed
during this merge. The concrete, low-risk findings were applied; the rest is
recorded as future work below.

### Applied

**Batch diarization now uses `diarize_model=latest`.** The Deepgram client
previously sent `diarize=true`. Current Deepgram pre-recorded docs (verified
May 2026) state that `diarize_model=latest` both enables diarization *and*
selects the newer v2 diarizer, while `diarize=true` on batch stays pinned to
the older v1 model. Deepgram reports the v2 diarizer is preferred ~3.3× over v1
in human evaluation — meaningfully better speaker separation, which matters
directly for deposition transcripts. A code comment records that a future
live/streaming path must use `diarize=true` instead, because `diarize_model`
is rejected on streaming requests.

**Keyterm normalization.** `backend/deepgram/client.py` gained a
`normalize_keyterms()` helper: it collapses whitespace, drops case-insensitive
duplicates, and caps the list at Deepgram's 100-term Keyterm Prompting limit.
Previously the code only sliced to 100 without de-duplicating.

**Formatting flags documented, not changed.** The report notes that
`smart_format`, `paragraphs`, `numerals`, and `filler_words` all change the
rendered transcript text. The client keeps `smart_format` and `paragraphs` on
and `filler_words` on (legal transcripts need verbatim "um"/"uh"). This is
safe because the **full Deepgram JSON is persisted verbatim** as the immutable
`raw.json` packet and `asr_response.json` archive — all downstream text is
derived from it and never overwrites it. The report explicitly endorses
"persist the immutable vendor JSON, render text downstream" as a sufficient
safeguard for a one-pass ingestion design, which is exactly the architecture
already in place. The client config now carries a comment explaining this.

### Confirmed (no change needed)

- **Preprocessing stays bypass-by-default.** The report cites Deepgram's own
  recommendation to *not* apply noise suppression to pre-recorded legal audio,
  because preprocessing often *reduces* accuracy. Wave 5's decision to keep
  preprocessing to a lightweight `ffprobe` duration check (no DSP, no Silero)
  is the correct default.
- **Raw/working packet split.** The report's recommended pattern — vendor JSON
  as immutable truth, canonical packet derived as a sibling — is already how
  `assembler.py` + `packet.py` work.

### Recorded as future work

- **Long-file job durability.** The report flags a Deepgram `504` risk when a
  single request exceeds ~10 minutes of processing, and recommends callbacks +
  a job queue. Deepgram callbacks need a publicly reachable URL, which a
  local-first desktop app does not have, so the current background-task model
  is the right fit — but very long deposition media is a real risk. A future
  wave should add chunked upload or a local worker-queue with retry/backoff
  around `408`/`429`/`5xx`.
- **Model/language-aware option validation.** `filler_words` is limited to
  English general models and `numerals` is language-bound. Encoding these as a
  validated transcription-profile contract pairs naturally with the canonical
  models from the other Wave 5 branch — a good candidate for the next wave.
- **`speaker_confidence` promotion.** Deepgram word objects carry a
  `speaker_confidence` field. It is already preserved inside the immutable raw
  JSON archive, but is not yet promoted into the structured `transcript_words`
  table. Promoting it (schema column + assembler + model) is a clean isolated
  follow-up.

## How to run

```
pip install -r backend/requirements.txt
uvicorn backend.app:app --port 8765
```

Open `http://127.0.0.1:8765`. The SQLite database and schema (v1 + v2) build
themselves on first launch. Set `DEEPGRAM_API_KEY` in a `.env` file for real
Nova-3 transcription; without it the pipeline runs a deterministic offline
fallback (also how the test suite runs).

## Testing

`python -m pytest` → 117 passing, 3 skipped. See the two Wave 5 docs for the
per-feature test breakdown.
