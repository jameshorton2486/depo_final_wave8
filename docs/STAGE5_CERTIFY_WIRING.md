# STAGE5_CERTIFY_WIRING.md — Autonomous Build Plan

## Mission

Wire the Stage 5 Certify screen to the real Wave 20 packaging engine.
Today `signTranscript()` saves certificate fields, flips a local flag,
and shows a toast — it never calls the packaging API, so no real
TranscriptPackage is assembled, validated, certified, or locked. Fix
that: the Certify button must produce a real certified package, and
must honestly surface validation failures instead of faking success.

You are a disciplined senior engineer. Work sequentially and
autonomously. Continue to the next phase automatically. Stop only when
the mission is complete or genuinely blocked.

## Scope — strict

IN scope: `frontend/assets/js/screens/stage_5.js`,
`frontend/screens/stage_5_certify.html`, `frontend/assets/js/api.js`,
and a backend contract test.

OUT of scope — DO NOT MODIFY: the packaging engine
(`backend/packaging/`), the packaging API (`backend/api/packaging.py`),
the snapshot system, the correction engine, or any other screen. The
backend is already built and tested — this task only makes the UI
*call* it. If a backend change seems required, stop and log it in
`BLOCKERS_STAGE5.md` instead of making it.

## Phase 0 — Audit first (no code yet)

1. Run `python -m pytest tests/ -q`; record the baseline (expect
   464 passed, 1 skipped).
2. Read `backend/api/packaging.py` and determine the EXACT contract:
   - the assemble endpoint `POST /api/packages/jobs/{job_id}` — its
     request model (does it require a `snapshot_id`? a `metadata`
     body?) and its response shape (`package_id`, `package_state`,
     `generation_report`, etc.).
   - the certify endpoint `POST /api/packages/{package_id}/certify` —
     its request model and BOTH its success and failure responses
     (what status code and body come back when validation fails).
3. If assemble requires a locked snapshot, read
   `backend/api/snapshots.py` for the create + lock endpoints.
4. Read `tests/test_wave20_packaging.py` — the existing
   `test_packaging_certify_full_workflow` already performs the correct
   call sequence. Treat it as the reference for what the UI must do.
5. Read the current `frontend/assets/js/screens/stage_5.js`,
   `stage_5_certify.html`, and `api.js` — learn the existing code
   style, how `api.js` methods are written, and how the active job id
   is obtained (`state.jobId`).
6. Write findings to `AUDIT_STAGE5.md`: the exact call sequence the UI
   must perform, every request/response shape, and the failure-response
   shape. Do NOT write feature code until this is done.

## Completion criteria — strict

COMPLETE only when ALL hold:
- `api.js` has methods for every packaging call the UI needs.
- `signTranscript()` performs the real sequence: save cert fields ->
  (snapshot if required) -> assemble package -> certify package.
- On success, the screen shows REAL data from the API response — the
  package id, the manifest/state hash, the certified state, the lock
  timestamp — not a local flag.
- On validation failure, the screen shows the actual reasons returned
  by the API and does NOT display "certified". The certified badge
  appears ONLY on a real CERTIFIED response.
- A backend contract test performs the exact UI call sequence and
  asserts it works end-to-end.
- The full pytest suite is green; `node --check` passes on the changed
  JS files.

A screen that flips a local flag, or that shows "certified" without a
CERTIFIED response, does NOT count as complete.

## Phase 1 — API client

- Add methods to `frontend/assets/js/api.js`, matching its existing
  style, for: assemble package, certify package, and (if Phase 0 found
  them required) create snapshot + lock snapshot. Each returns parsed
  JSON and surfaces non-OK responses so callers can read the error.

## Phase 2 — Wire signTranscript()

- Rewrite `signTranscript()` to perform the real sequence found in
  Phase 0. Keep the existing pre-checks (signature present, all three
  acknowledgement checkboxes) and the existing `_saveCertFields()`
  call. After fields are saved, assemble then certify via the API.
- Make it async and guard against double-submission (disable the
  button while the request is in flight).

## Phase 3 — Honest result + failure handling

- On a real CERTIFIED response: reveal the post-lock UI using values
  from the response (package id, hash, timestamp, state).
- On a validation failure or any non-OK response: show the actual
  reasons (a clear list), keep the screen in its pre-lock state, and
  do NOT show the certified badge. Add a visible error area to
  `stage_5_certify.html` if one does not exist.
- Record the real outcome to the provenance log either way.

## Phase 4 — Test + verify

- Add `tests/test_stage5_certify_contract.py`: a backend test that
  performs the EXACT sequence the UI now calls (using a fully
  populated job, e.g. the `sample_job_with_content` fixture) and
  asserts a CERTIFIED package; also assert that an under-populated job
  returns the failure response shape the UI depends on.
- Run the full suite; run `node --check` on the changed JS files.
- Write a short manual smoke-test checklist to `PROGRESS_STAGE5.md`
  (there is no JS test runner in this repo — be honest about that).

## Rules

- Do not invent or change the API contract — discover it in Phase 0
  and build to it exactly.
- Run the full pytest suite after Phases 1, 2, 3, 4. Never proceed on
  red.
- `git add -A && git commit` after every phase with a clear message.
- If a real blocker appears (the API genuinely cannot support the UI
  flow, an ambiguous contract, a missing endpoint), do NOT stop the
  whole run: log it in `BLOCKERS_STAGE5.md`, implement the most
  reasonable partial version, mark it PARTIAL, and continue.
- Maintain `AUDIT_STAGE5.md` and `PROGRESS_STAGE5.md` throughout.

## Stop conditions

Stop when the Certify screen performs a real assemble + certify, shows
real package data on success, honestly shows reasons on failure, the
contract test passes, and the suite is green — or when remaining work
is blocked. Write a final summary to `PROGRESS_STAGE5.md`: what is
complete, what is partial, what is blocked, plus the manual smoke-test
checklist.

Begin with Phase 0 now.
