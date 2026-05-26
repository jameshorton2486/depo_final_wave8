> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 5 — Stage 2 Transcripts Engine

Status: complete
Supersedes: the mocked `stage_2.js` (setInterval fake progress, canned readback,
fabricated websocket simulator with no backend).

## Summary

This wave turns Stage 2 (Transcripts) from a visual prototype into a real
transcription ingestion engine. It implements Waves 1–3 of the Screen 2 build
plan: the canonical transcript pipeline, real UI wiring, and the readback
terminal. Wave 4 of that plan (realtime Zoom RTMS streaming) is deliberately
deferred and kept as a clearly-labelled UI simulation.

The architecture is built around **canonical word objects** and **immutable
transcript packets** — never giant transcript strings. Each ingested file
produces an immutable `raw` layer and an editable `working` layer.

## What was built

### New SQLite schema: `backend/db/schema_v2.sql`

Adds Layer 2/3 tables, picked up automatically by the migrations runner
(`schema_version` advances 1 → 2):

| Table | Purpose |
|---|---|
| `transcript_jobs` | One row per ingested media file: status lifecycle, source filename, packet paths, word/utterance/speaker counts, average confidence |
| `transcript_speakers` | Diarized speaker rows per job |
| `transcript_utterances` | Utterance/turn rows with speaker, timing, text |
| `transcript_words` | Word objects: `raw_text` (immutable), `working_text` (editable override, NULL = unedited), confidence, filler flag, reviewed flag |

Job status enum: `queued → preprocessing → transcribing → assembling →
completed` (or `failed` at any point).

### New backend packages

| Module | Responsibility |
|---|---|
| `backend/deepgram/client.py` | Deepgram Nova-3 REST call via the stdlib `urllib` (no SDK). Configured with `punctuate`, `paragraphs`, `diarize`, `filler_words`, `utterances`, `smart_format`, and keyterm injection. Falls back to a deterministic offline synthetic transcript when `DEEPGRAM_API_KEY` is unset |
| `backend/preprocessing/probe.py` | Lightweight `ffprobe` duration probe with graceful fallback when ffprobe is absent |
| `backend/transcript/assembler.py` | Normalizes a raw Deepgram response into words / utterances / speakers; handles both real and fallback response shapes |
| `backend/transcript/packet.py` | Builds and reads canonical transcript packets (`raw` and `working` layers) |
| `backend/transcript/repository.py` | SQL layer for jobs, transcript content, and readback search |
| `backend/transcript/ingest.py` | `process_job()` orchestrator: probe → transcribe → assemble → write packets → persist → finalize. Never raises; any failure sets status to `failed` |
| `backend/models/transcripts.py` | Pydantic response models |

### New endpoint group: `backend/api/transcripts.py` (`/api/transcripts`)

| Method + path | Purpose |
|---|---|
| `POST /upload` | Multipart audio/video upload. Validates extension + size, creates a job, saves audio to `data/audio/`, schedules background ingestion |
| `GET /jobs` | List jobs (optional `?case_id` filter) |
| `GET /jobs/{id}` | Single job status |
| `GET /jobs/{id}/content` | Canonical words / utterances / speakers |
| `GET /jobs/{id}/packet` | Working-layer packet |
| `GET /jobs/{id}/raw` | Immutable raw-layer packet |
| `DELETE /jobs/{id}` | Delete job and clean disk artifacts |
| `POST /readback` | Case-insensitive phrase search across utterances |

Limits: audio/video extensions only, 300 MB max upload.

### Immutable layer guarantee

`data/transcripts/{job_id}/` holds three files per job:

- `raw.json` — the immutable raw packet (never modified after ingestion)
- `working.json` — the editable working packet (all downstream edits land here)
- `asr_response.json` — the archived raw ASR response

The `transcript_words.raw_text` column is never overwritten; edits write to
`working_text` as an override.

## Frontend wiring

- `frontend/assets/js/screens/stage_2.js` — fully rewritten. The file queue now
  stores real `File` objects; `startSequentialIngestion()` uploads each file and
  polls its job to completion; completed transcripts load into the Stage 3
  workspace as canonical utterance lines; the readback search calls
  `POST /api/transcripts/readback`. The live Zoom panel is retained as a clearly
  labelled simulation.
- `frontend/assets/js/api.js` — added `uploadTranscriptFile()` plus
  `listTranscriptJobs`, `getTranscriptJob`, `getTranscriptContent`,
  `getTranscriptRawPacket`, `getTranscriptWorkingPacket`, `deleteTranscriptJob`,
  and `readbackSearch`.
- `frontend/assets/js/state.js` — added `transcriptJobs` and `readbackTimer`.
- `frontend/screens/stage_2_transcripts.html` — added an `engineModeBadge`
  (shows whether real Deepgram or the offline fallback is active), a new
  **Persisted Transcript Sessions** panel (`serverJobsList`) with job cards, and
  a `SIMULATION` label on the live Zoom section.
- `frontend/assets/js/app.js` — Stage 2 `screen:loaded` now refreshes persisted
  transcript jobs.
- `frontend/index.html` — script cache-busting bumped to `v=wave5-stage2`.

## Deepgram: real vs. offline fallback

Set `DEEPGRAM_API_KEY` in your environment or `.env` to enable real Nova-3
transcription. Without a key, the pipeline runs a deterministic offline
fallback that produces a synthetic 9-utterance deposition transcript. The
fallback is seeded by the filename hash, so the same file always yields the
same transcript — useful for development and for the test suite, which runs
fully offline. The active mode is surfaced in the Stage 2 `engineModeBadge`
and on every job card (`transcription_source`).

## What was intentionally NOT built

Per the Screen 2 build plan ("faithful transcript acquisition, not
transcript transformation"):

- **Realtime Zoom RTMS streaming.** The live panel is a UI simulation. Real
  dual-WebSocket routing (Zoom signaling → media socket → Deepgram live) is a
  future wave.
- **AI cleanup / legal formatting / transcript rewriting.** These belong to
  Stage 3 (Workspace) and later. Stage 2 only acquires and stores transcripts.
- **Audio preprocessing DSP** (FFmpeg high-pass, loudness normalization, Silero
  VAD, conditional RNNoise). The architecture spec describes it; this wave keeps
  preprocessing to a lightweight probe so ingestion has no heavy native/torch
  dependencies. Adding the full pipeline is a self-contained future milestone.

## Testing

`tests/test_transcripts_api.py` — 10 integration tests: upload + background
processing, bad-file-type rejection, empty-file rejection, canonical content
shape, raw + working packet retrieval, readback search, empty-query rejection,
job listing + case filtering, deletion, and 404 handling. All run offline via
the deterministic fallback.

Full suite: 94 passing, 2 skipped (pre-existing skips).

## New runtime dependencies

None. Deepgram is called via the stdlib `urllib`; `python-multipart` (already
present from Wave 4) covers multipart uploads.
