# Wave 10 — Diff Harness + Test-Hygiene Fix

This drop adds the **transcript diff harness** (`backend/diagnostics/`) — §22
step 9 — and fixes the 6 pre-existing tests that failed when a real
`DEEPGRAM_API_KEY` was set.

## What's included

```
backend/diagnostics/
├── __init__.py        public entry point: run_diff(), write_artifacts()
├── model.py           DiffReport, WordDeltaResult
├── word_delta.py      the core word-conservation audit
├── metrics.py         advisory structural metrics
├── report.py          report assembly + JSON artifact serialisation
└── harness.py         run_diff() entry point

tests/diagnostics/
├── test_word_delta.py   the fidelity audit
└── test_harness.py      report, parity gate, metrics, artifacts

tests/conftest.py        *** MODIFIED *** — see "The test-hygiene fix" below
```

## Two parts to this drop

### 1. The diff harness — purely additive

New `backend/diagnostics/` folder; nothing existing touched. It is a
developer / regression tool: it inspects a correction-engine run and proves
the output is faithful to the RAW transcript.

The core gate is **word conservation**. The harness reconciles four counts:

```
unexplained = app_words - raw_words - logged_delta - flag_word_count
```

`unexplained` must be 0. Every word the engine removes is in the correction
log; every word it adds is a flag marker. Anything left over is a *silent*
edit — the exact defect this harness exists to catch. In Parity Mode the gate
also requires zero structural drift (one rendered line per utterance).

```python
from backend.corrections import run
from backend.diagnostics import run_diff, write_artifacts

result = run(raw_transcript, job_config)
report = run_diff(raw_transcript, result)
print(report.summary())          # [PASS] Parity Mode -- raw=26w app=44w ...
assert report.parity_gate_pass    # use as a regression gate

write_artifacts(report, result, "diagnostics_out/")
#   -> pipeline_snapshot.json   (counts, metrics, verdict)
#   -> correction_log.json      (every change, replayable)
```

### 2. The test-hygiene fix — ONE modified file: `tests/conftest.py`

**This drop replaces `tests/conftest.py`.** The change is purely additive
inside that file — one new autouse fixture, `_force_offline_transcription`,
and nothing else removed or altered. It clears `DEEPGRAM_API_KEY` for every
test so the suite always uses the deterministic offline transcription
fallback.

Why: the transcripts / speaker-mapping tests upload tiny synthetic audio.
With a real API key in `.env`, that fake audio was being sent to the live
Deepgram API, which rejected it (HTTP 400) and failed ~6 tests for a reason
unrelated to the code. Tests must not depend on the developer's environment.

After this fix the full suite passes **with or without** a key set — verified
both ways.

## Test status

- New: **13 harness tests**, all passing.
- Full project suite: **203 passed, 3 skipped** — confirmed identical with
  `DEEPGRAM_API_KEY` set and unset. The previous 6 environment failures are
  resolved.

Run them:

```
cd depo_final_wave8
.venv\Scripts\activate
python -m pytest tests/diagnostics -q     # the harness alone
python -m pytest -q                        # whole project — 203 passed
```

You no longer need the `$env:DEEPGRAM_API_KEY=""` workaround.

## Install (PowerShell)

`backend/diagnostics/` and `tests/diagnostics/` are new folders; `conftest.py`
overwrites the existing one.

```powershell
$zip  = "C:\Users\james\Downloads\depo-pro-wave10-diff-harness.zip"
$proj = "C:\Users\james\PycharmProjects\PythonProject\depo_final_wave8"

Expand-Archive -Path $zip -DestinationPath "$env:TEMP\w10h" -Force
Copy-Item "$env:TEMP\w10h\backend\diagnostics"  "$proj\backend\" -Recurse -Force
Copy-Item "$env:TEMP\w10h\tests\diagnostics"    "$proj\tests\"   -Recurse -Force
Copy-Item "$env:TEMP\w10h\tests\conftest.py"    "$proj\tests\"   -Force
```

Then verify:

```powershell
cd $proj
.venv\Scripts\activate
python -m pytest -q
```

Expect **203 passed, 3 skipped**.

## Scope — what is NOT in this drop

The harness inspects an *existing* engine run; it does not run the engine
itself (no recomputation, no drift). Per the harness spec, deliberately NOT
built: a composite "integrity score", audio-transition metrics, per-utterance
heatmaps. Confidence metrics are minimal — the foundation engine does not
thread per-word confidence into rendered lines yet; that can be added when
the structural stages do.

## Next steps

With the safety net in place, the remaining §22 build order is:

1. **Stage X** — legal lexicon / garbled-objection resolution (step 10)
2. **Stage S** — off-record structuring, parentheticals (step 11)
3. **Stage Q** — Q/A formatting, tab assignment (step 12)
4. **Wave 11** — the Workspace speaker panel; wires the engine into the app

Each structural stage can now be built and regression-checked against the
harness — word conservation is verified automatically as X/S/Q land.
