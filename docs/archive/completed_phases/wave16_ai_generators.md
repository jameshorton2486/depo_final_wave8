> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 16 — AI Review-Queue Panel + Three AI Generators

Status: **BUILT.**

Completes the AI review layer started in Wave 15b: the reporter-facing
review-queue panel, and the three remaining AI generators.

## 1. AI review-queue frontend panel

A panel in the Workspace screen (Stage 3), under "Speakers & Roles".

- **Status indicator** — shows whether the AI layer is live (key set)
  or inert. Inert disables the trigger buttons.
- **"Suggest speaker map"** — calls the Wave 15b speaker-map generator.
- **"Analyze transcript"** — runs all three Wave 16 generators.
- **Suggestion cards** — each pending suggestion shows its kind, an
  EDIT vs. FLAG badge (from `is_applicable_edit`), the reason, a
  before/after or the proposed speaker map, and Approve / Reject.

The panel only talks to the `/api/ai-review` endpoints. Approval is the
only path from a suggestion to the transcript; rejection discards it.

## 2. The three AI generators

`backend/ai_review/generators.py` — each reuses the Wave 15b machinery
(`client`, `Suggestion`, `four_part_test`, `review_queue`):

- **`generate_boundary_suggestions`** (AI Ref 2.2) — fuzzy off/on-record
  boundaries the deterministic regex missed. Kind `boundary`; the
  reporter confirms (not four-part gated — structural, not a text edit).
- **`generate_garble_suggestions`** (AI Ref 4) — non-enumerable garbles
  not in Stage X's fixed tables. **Four-part gated**: a candidate that
  passes is kind `garble` (an applicable edit); one that fails is
  downgraded to kind `flag` with the failed conditions appended to the
  reason.
- **`generate_flag_suggestions`** (AI Ref 8) — review flags for
  ambiguous entities, speakers, dates, numbers, exhibits. Always kind
  `flag`, never an applicable edit.

Every generator returns an empty list when no API key is configured.

## 3. API

`POST /api/ai-review/jobs/{job_id}/analyze?kinds=boundaries,garbles,flags`
— runs the requested generators (all three if `kinds` omitted), saves
their suggestions to the review queue, returns per-kind counts. 404 on
unknown job; `available: false` when the AI layer is inert.

## 4. Tests

`tests/test_wave16_generators.py` — offline degradation, JSON-array
parsing, the generator registry, the analyze endpoint. The full suite
remains green (342 tests).

## 5. Known follow-ups

- The generators are built against the documented Anthropic Messages
  API. A live call has not been run from the build environment; if the
  request shape needs adjustment it is a one-line fix in `client.py`
  that corrects all four generators at once.
- Approving a `speaker_map` suggestion records the approval but does
  not yet auto-prefill the Wave 11 panel fields — that wiring is a
  small follow-up.
