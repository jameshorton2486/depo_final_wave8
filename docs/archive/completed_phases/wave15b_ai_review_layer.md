> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 15b — AI Review Layer

Status: **SPEC + BUILT.**

## 1. What this is

A narrow, isolated, suggestion-only AI layer. It calls Claude via the
Anthropic API to do the few things the deterministic engine cannot —
and it never writes the transcript. Every AI output is a *suggestion*
that a human reporter approves or rejects.

## 2. Non-negotiable principles

- **Suggestion-only.** AI output lands in a review queue. Nothing
  reaches the WORKING transcript without explicit reporter approval.
- **Isolated.** `backend/ai_review/` is a separate package. The
  deterministic correction engine never imports it. AI is downstream
  and optional.
- **The four-part test.** AI may only *suggest a correction* when all
  four hold: (a) clear STT artifact, (b) intended wording unambiguous,
  (c) meaning unchanged, (d) a reasonable scopist would agree. A
  suggestion that cannot assert all four is downgraded to a FLAG.
- **Hard gate.** `SpeakerMapUnverifiedError` — corrections never run on
  an unverified speaker map.
- **Graceful degradation.** No `ANTHROPIC_API_KEY` -> the layer is
  inert; the app and the deterministic engine are unaffected.
- **Cost control.** AI calls are explicit and on-demand (reporter
  action), never automatic on every render.

## 3. Scope — what the AI layer does

Exactly four tasks (AI Processing Reference):

1. **Speaker-map generation** (SPK-01). AI reads the opening blocks and
   returns a role JSON *suggestion* that prefills the Wave 11 speaker
   panel. The reporter still confirms.
2. **Fuzzy boundary detection** — pre-record / off-record boundaries
   *only* when the spoken marker is garbled beyond regex. Clean markers
   stay deterministic (Stage S).
3. **Non-enumerable garble suggestions** — garbles not covered by Stage
   X's finite tables. Always a suggestion + flag.
4. **Flag generation** — ambiguous items surfaced for human review.

What it does NOT do: fix transcripts, format Q/A, resolve enumerable
garbles (Stage X does that), or touch RAW.

## 4. Modules

    backend/ai_review/
      __init__.py
      client.py        -- Anthropic API client; graceful no-key mode
      four_part_test.py-- the permitted-correction gate
      speaker_map.py   -- SPK-01 speaker-map generation
      suggestions.py   -- Suggestion model + the review queue
      review_queue.py  -- persist / approve / reject suggestions
    backend/db/schema_v6.sql      -- ai_suggestions table
    backend/api/ai_review.py      -- endpoints

## 5. The Suggestion model

    Suggestion:
      suggestion_id, job_id, kind, target_utterance_id,
      before_text, after_text, reason,
      four_part_pass (bool), status (pending|approved|rejected),
      created_at

`kind`: speaker_map | boundary | garble | flag.
A suggestion with `four_part_pass = False` renders as a FLAG, not an
applicable edit.

## 6. Review queue

`ai_suggestions` table (schema_v6). Endpoints:

    POST /api/ai-review/jobs/{job_id}/speaker-map   generate map suggestion
    GET  /api/ai-review/jobs/{job_id}/suggestions   list the queue
    POST /api/ai-review/suggestions/{id}/approve    approve one
    POST /api/ai-review/suggestions/{id}/reject     reject one

Approval is the ONLY path from a suggestion to the transcript.

## 7. Anthropic client

`client.py` reads `ANTHROPIC_API_KEY` from the environment. Missing key
-> `is_available()` returns False and all generators return empty
results with a logged notice. Model string is config (`AI_MODEL`),
defaulting to a current Claude model.

## 8. Out of scope

Confidence scoring as a numeric model output, batch AI re-processing,
and automatic (non-reporter-triggered) AI calls. Deferred.
