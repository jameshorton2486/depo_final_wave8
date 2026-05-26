> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 9 — Canonical Participant Layer (Speaker Mapping)

## Why this wave exists

Deepgram diarization emits speaker indices (0, 1, 2, …). Those are
**acoustic clusters, not people.** On real depositions one person is
routinely split across several indices — a witness on a failing
microphone becomes Speaker 2 *and* Speaker 3 — and an attorney's
objections may cluster separately from their examination. This is
intrinsic to all ASR diarization; no request parameter fixes it. Even a
clean Deepgram run cannot be certified by mapping a raw index straight to
a role.

Diagnosis confirmed the DEPO-PRO pipeline was **not** corrupting
transcripts: the Deepgram request (`diarize_model=latest`), the assembler,
and the frontend renderer were all faithful. The single real defect was
the `speaker_index === 0 ? "Q" : "A"` heuristic, which mislabels whoever
Deepgram happens to put at index 0 (often the court reporter).

Wave 9 adds the missing layer: a **canonical participant identity**
between raw diarization and transcript rendering.

## What was built

### 1. `transcript_participants` table (`schema_v3.sql`)
One row per real person/role. `speaker_indices` is a JSON array of every
raw diarization index that collapses onto that participant. Raw
`transcript_speakers` / `_utterances` / `_words` rows are never mutated;
participants sit on top of them.

### 2. `backend/services/speaker_mapping.py`
- `ROLES` — the full deposition role set: examining attorney, witness,
  defending attorney, co-counsel, court reporter, videographer,
  interpreter, off-record, other.
- `prefill_participants()` — a **deterministic** first guess (counting and
  string matching only; no AI, no model call). Picks the best index for
  each primary role — court reporter by on/off-record phrasing, examiner
  by question-shaped utterances, witness by word volume, defender by
  objection density — then folds leftover indices onto the role they most
  resemble.
- `build_speaker_directory()` — collapses a confirmed participant list
  into a `{speaker_index → role/label/qa}` lookup for the renderer.

### 3. API (`/api/transcripts`)
- `GET  /jobs/{job_id}/speaker-mapping` — detected raw speakers (with a
  transcript sample and word/turn counts) plus a participant list. When
  no mapping is saved yet, the deterministic prefill is returned with
  `is_prefill=true`.
- `PUT  /jobs/{job_id}/speaker-mapping` — persists the reporter-confirmed
  mapping (`is_prefill=0`). Roles validated against the fixed set.
- `GET  /jobs/{job_id}/content` now also returns `participants`.

### 4. Speaker Mapping step (Stage 2b)
A dedicated screen between transcription and the Workspace. Lists each
detected raw speaker with a sample; the reporter assigns a role and name.
Two speakers given the **same role + name** collapse into one
participant. On confirm, the mapping is saved per job and the Workspace
transcript is rebuilt.

### 5. Q/A retired from the heuristic
`stage_2.js` no longer derives Q/A from `speaker_index === 0`. It builds
the transcript from the confirmed participant directory: examining
attorney → `Q.`, witness → `A.`, every other role → named colloquy.
Before a mapping is confirmed, lines render as neutral colloquy — the app
never guesses Q/A.

### 6. Assembler hardening
`_merge_consecutive_speaker_utterances` no longer merges utterances whose
speaker index is `None`. Previously, a response with no diarization data
(`None == None`) collapsed the entire transcript into one paragraph.

## No AI in the certified path

The certified record depends on exactly two auditable things: Deepgram's
verbatim words, and the reporter's own speaker assignments. The prefill is
a plain heuristic the reporter confirms or overrides. No language model
touches the transcript body or the speaker identities.

## Tests
`tests/test_speaker_mapping.py` (12 tests) covers the prefill heuristic,
fragmented-speaker consolidation, the render directory, and the API
endpoints. `tests/test_assembler.py` gains a regression test for the
no-speaker-field collapse. Full suite: 144 passed, 3 skipped.

## Deferred
Block classification (colloquy / off-record / examination / stipulation)
is intentionally a separate future wave. It is worth doing — and can be
done deterministically with phrase anchors — but it is cleanly separable
and should not gate the participant layer.
