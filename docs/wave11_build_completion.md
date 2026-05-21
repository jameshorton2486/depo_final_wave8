# Wave 11 — Build Completion Notes

Status: **BUILT** — paired with the specification in
`docs/wave11_workspace_speaker_panel.md`.

Wave 11 makes the Wave 9 speaker mapping editable from inside the
Workspace, adds finished-label name dropdowns, and introduces the first
canonical backend transcript renderer.

## Open decisions — resolved

- **W11-Q1 — AI name suggestion:** deferred. The wave ships fully
  deterministic. The appearance-statement regex prefill (in scope) covers
  the easy cases with no model.
- **W11-Q2 — sequencing:** built as Wave 11, before the correction
  engine's structural stages (X/S/Q).
- **W11-Q3 — Step 2B vs. Workspace:** both kept. Step 2B remains the
  initial mapping gate; the Workspace panel is for corrections during
  review. Both are views of the same `transcript_participants` rows.
- **W11-Q4 — add-speaker cluster picker:** inline on the row.

## What was built

### Backend

- `backend/db/schema_v4.sql` + `migrations.py` — `name_source` and
  `honorific` columns on `transcript_participants` (idempotent adds).
- `backend/services/speaker_mapping.py` — `participant_label()` (the
  one-space-honorific / fixed `THE …` label authority), plus
  `build_candidate_names()` and `prefill_name_from_appearance()`.
- `backend/transcript/render.py` — **NEW. The canonical WORKING
  transcript renderer.** Before Wave 11 no backend renderer existed; the
  frontend was the de-facto renderer. This module is now the single
  render authority: deterministic, RAW never touched, WORKING rebuilt
  from utterances + participant mapping. Unmapped clusters render flagged
  with no text loss.
- `backend/services/correction_trigger.py` — **NEW.** Bridges the
  participant mapping into the correction engine's `Utterance` shape and
  runs the pipeline. Defensive: a missing/failing engine is a no-op.
- `backend/api/transcripts.py` —
  - `GET .../speaker-mapping` now returns `candidate_names`.
  - `PUT .../speaker-mapping` accepts `name_source` + `honorific`, and
    auto-triggers the correction engine in a background task on confirm
    (spec section 7.1).
  - `POST .../speaker-mapping/apply` — **NEW.** Persist → re-render via
    the canonical renderer → run the correction engine. Returns the
    rendered lines so the Workspace refreshes in place.

### Frontend

- `frontend/assets/js/api.js` — `applySpeakerMapping()`.
- `frontend/screens/stage_3_workspace.html` — the Speakers panel gains
  "+ Add speaker" and "Assign speakers & re-render" controls.
- `frontend/assets/js/screens/stage_3.js` — the read-only speaker list is
  replaced by the editable participant panel: role + honorific + name
  dropdowns, add/remove with confirmation, unmapped-cluster rows, and the
  apply wiring.
- `frontend/assets/js/screens/stage_2.js` — loads the panel for the job
  when transcript results open in the Workspace.

### Tests

- `tests/test_wave11_speaker_panel.py` — 25 tests: label builder,
  candidate names, appearance prefill, the renderer (Q/A/colloquy/
  unmapped/merge/determinism/delete), the apply endpoint, and the
  correction-engine trigger.
- Full suite: **218 passing.**

## Known follow-ups (not Wave 11 scope)

1. **Initial-load consolidation.** `loadTranscriptResultsIntoWorkspace`
   in `stage_2.js` still builds transcript lines its own way on first
   load; only the Workspace "Assign speakers" path currently uses the
   backend renderer. Routing initial load through the renderer too would
   make the backend the sole authority everywhere. Small, deferred.
2. **Correction engine X/S/Q stages.** The engine still runs only
   G/A/M/T/F/U. `correction_trigger` runs the engine, but structural Q/A
   formatting (Stage Q) does not exist yet — the deterministic re-render
   handles Q/A line typing in the meantime. Build order: Stage X
   (lexicon) → Stage Q → Stage S.
