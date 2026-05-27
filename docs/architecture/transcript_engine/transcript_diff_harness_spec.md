> DOCUMENT STATUS: CANONICAL SUBSYSTEM SPEC
> Scope: transcript diffing, diagnostics artifacts, and mutation-detection input contract.
> `backend/diagnostics/` remains read-only, but its output now feeds mutation-detection enforcement in the certification path.

# DEPO-PRO — Transcript Diff Harness

**Build Specification — Debugging & Regression Tool**

Version 1.2 · Wave 10 · Companion to the Deterministic Correction Engine spec.
Source: the "Transcript Parity Harness" recommendation in the Wave-10 planning
review. Authoritative architecture document — see
`docs/architecture/transcript_engine/`.

---

## 1. Purpose

The Diff Harness answers one question deterministically: **did a transformation
change the transcript in a way we did not intend?**

It exists because, during development, a transcript defect could originate in any
of several layers — the Deepgram response itself, the assembler, the Wave 9
speaker mapping, or the correction engine. Without a measurement tool you are
guessing. The harness turns "the transcript looks worse" into specific numbers:
*N utterances lost, M words dropped, K speakers collapsed.*

It is a **developer and regression tool**, not part of the certified production
pipeline. It reads transcripts; it never writes to RAW or WORKING.

---

## 2. What It Compares — and the Honesty Point

The harness works with up to three artifacts for a given job:

| Artifact | What it is | Trust level |
|---|---|---|
| **RAW** | The immutable Deepgram response the app itself received (`data/transcripts/{job_id}/raw.json`) | **Ground truth** |
| **APP** | The transcript DEPO-PRO rendered from that RAW (ideally in Parity Mode) | The thing under test |
| **REF** | A transcript exported from the Deepgram Playground for the same audio | **Advisory only** |

### 2.1 APP-vs-RAW is the authoritative comparison

This is the real regression signal. Both sides derive from the **same Deepgram
response**, so any difference is caused by DEPO-PRO's own code — the assembler,
the speaker mapping, or the correction engine. If APP-vs-RAW shows drift,
DEPO-PRO changed something. That is a definite, actionable finding.

### 2.2 APP-vs-REF is advisory, not a pass/fail gate

It is tempting to treat "match the Playground" as the goal. It is not a reliable
goal, and the harness must say so plainly. The Playground transcript comes from a
**separate Deepgram run**. Deepgram diarization is not bit-identical run to run,
especially on poor audio — two runs of the same file can legitimately produce
different speaker counts and different utterance groupings. (This was confirmed
earlier in the project: the app run and the Playground run of the Heath Thomas
deposition diarized differently, and neither was a bug.)

Therefore:

- APP-vs-REF differences are a **sanity check**, useful for spotting gross
  divergence, never a definition of "correct."
- The harness reports APP-vs-REF metrics clearly **labeled "advisory"** and never
  fails a build on them.
- The authoritative baseline for regression is APP-vs-RAW.

REF is optional — the harness runs fully with just RAW and APP.

---

## 3. Generated Artifacts

For every job the harness processes, it writes a folder
`data/diff/{job_id}/` containing:

| File | Contents |
|---|---|
| `raw_deepgram.json` | Copy of the immutable Deepgram response (reference convenience) |
| `raw_utterances.txt` | RAW utterances, one per line, `[spkN] text` — the un-transformed baseline |
| `app_rendered.txt` | The APP transcript as rendered lines |
| `playground_reference.txt` | The REF transcript, if supplied (else absent) |
| `correction_log.json` | Copy of the correction engine's log for this run — rule ID, before/after, stage, per change (Correction Engine §17.1) |
| `pipeline_snapshot.json` | Provenance for this run — see 3.1 |
| `diff_report.txt` | Human-readable metrics + per-utterance diff (Section 5) |
| `diff_metrics.json` | The same metrics as machine-readable JSON (for regression snapshots) |

All artifacts are derived and disposable — the folder can be deleted and
regenerated at any time. None of them is the certified record.

### 3.1 Pipeline snapshot (provenance)

`pipeline_snapshot.json` records *how* this transcript was produced, so a diff
result can be interpreted later without guessing at settings. It is the harness's
answer to a real risk: the harness's APP-vs-RAW comparison assumes RAW is a
faithful Deepgram response, but a defect could originate upstream — in the
Deepgram request parameters or in preprocessing — and produce a "clean" diff that
is nonetheless wrong at the source. The snapshot makes those upstream settings
visible. Example:

```json
{
  "run_mode": "parity",
  "deepgram": {
    "model": "nova-3",
    "diarize_model": "latest",
    "utterances": true,
    "smart_format": true,
    "paragraphs": true,
    "utt_split": 0.8
  },
  "preprocessing": { "denoise": false, "vad_trim": false, "snr_db": 22.1 },
  "correction_engine_version": "1.1",
  "speaker_map_confirmed": true
}
```

The harness does not compute these values — it copies them from the job record.
It is a serializer, not an analyzer.

### 3.2 Stage snapshots (optional, debug)

When run with `--snapshots`, the harness also writes one file per correction-engine
stage — `after_G.txt`, `after_A.txt`, `after_M.txt`, `after_X.txt`, `after_S.txt`,
`after_Q.txt`, `after_T.txt` — capturing the WORKING text as it leaves each stage.
This lets a developer see exactly which stage introduced a given change. It is
**off by default** (production runs do not need it and the files add clutter);
it is a debugging aid, enabled per-run.

---

## 4. Metrics

All metrics are computed deterministically. Each is reported for **APP-vs-RAW**
(authoritative) and, when REF is present, for **APP-vs-REF** (advisory).

### 4.0 Core metrics

| Metric | Definition | What a delta means |
|---|---|---|
| `utterance_count` | number of utterances / rendered lines on each side | assembly or merge drift |
| `speaker_count` | distinct speaker indices on each side | diarization or mapping drift |
| `word_count` | total word tokens on each side | **transcript damage** — see 4.1 |
| `avg_utterance_words` | mean words per utterance | merge problems (too high) / fragmentation (too low) |
| `longest_utterance_words` | largest single block | over-merging of distinct speakers |
| `duplicate_line_rate` | share of lines that are exact duplicates of an adjacent line | overlap / repetition artifacts |
| `unmatched_utterances` | utterances on one side with no aligned counterpart on the other | assembly corruption |
| `word_delta` | `app_word_count − raw_word_count` | should be ≈ 0 in Parity Mode (see 4.1) |

### 4.1 The word_delta rule (most important)

The verbatim mandate means the correction engine **never adds or removes words of
testimony**. In **Parity Mode**, where the structural stages (X, S, Q) are
skipped, `word_delta` between APP and RAW must be **0** — the only permitted
differences are intra-word character substitutions (e.g. `K.` → `Okay.` is a
token change, not a word *count* change; duplicate collapse removes a mechanical
artifact, which is a deliberate, logged exception).

The harness therefore computes `word_delta` two ways:

- **gross** — raw token count difference;
- **net of logged corrections** — `word_delta` minus the word-count effect of
  every entry in the correction log (Correction Engine §17.1).

**Net `word_delta` must be 0 in Parity Mode.** A non-zero net delta means words
were lost or invented outside the logged, intended corrections — a serious
defect. This is the harness's single most important assertion and the basis of
its regression gate (Section 7).

### 4.2 Structural drift metrics (Full Mode)

These count what the structural stages did. They are read directly from the
correction log — the harness aggregates, it does not re-derive. They are most
useful in Full Mode, where they should match expectations for a given transcript.

| Metric | Source | Flags |
|---|---|---|
| `qa_split_count` | QA-03 log entries | over-aggressive Q/A splitting |
| `objection_isolation_count` | QA-04 log entries | structural objection edits |
| `parenthetical_insertions` | STR-04 log entries | off-record reconstruction volume |
| `garble_resolutions` | LEX-01/02/03 log entries | how much lexicon correction fired |
| `flag_count` (by category) | flag registry | how much was deferred to human review |

### 4.3 Speaker fragmentation metric

`speaker_fragments` — for each RAW speaker index, the number of separate,
non-contiguous runs it appears in. A witness who is acoustically split across
indices 2 and 3, or whose index alternates, shows high fragmentation. Example:

```json
"speaker_fragments": { "0": 6, "1": 38, "2": 44, "3": 41 }
```

High fragmentation diagnoses diarization instability — useful context for a
transcript that needed heavy Wave 9 mapping work. Computed from RAW only;
reported, never gated.

### 4.4 Confidence metrics (advisory)

Deepgram returns per-word confidence in RAW. The harness summarizes it:

```json
"confidence": { "avg": 0.88, "low_confidence_words": 442, "threshold": 0.6 }
```

This is advisory context — low confidence often co-locates with the regions a
reporter must check against audio. It is never a gate.

---

## 5. The Diff Report

`diff_report.txt` has three sections:

### 5.1 Summary block
```
JOB:            {job_id}   ({source_filename})
MODE:           parity | full
REF SUPPLIED:   yes | no

                            RAW        APP      Δ (APP−RAW)
utterance_count             318        318       0
speaker_count                 8          8       0
word_count                12,440     12,438     -2   (net of log: 0  ✅)
avg_utterance_words          39.1       39.1
longest_utterance_words       412        412
duplicate_line_rate          0.6%       0.0%
unmatched_utterances           —          0

APP-vs-REF (ADVISORY — separate Deepgram run, not a correctness gate)
utterance_count             318        301      -17
speaker_count                 8          8        0
```

### 5.2 Per-utterance diff
A unified-diff-style listing of every utterance whose text differs between RAW
and APP, annotated with the correction-log rule ID responsible:

```
~ utt 0042  [PRE-04]  duplicate collapse
  RAW: and then the witness witness said
  APP: and then the witness said

~ utt 0108  [POST-01] two-space rule
  RAW: I do. Thank you.
  APP: I do.  Thank you.

! utt 0211  UNEXPLAINED — no correction-log entry
  RAW: I worked there for about two years.
  APP: I worked there for two years.
```

Lines marked `!` (a change with no matching correction-log entry) are the
defects the harness exists to catch. A clean run has zero `!` lines.

### 5.3 Flag summary
A count of `[SCOPIST: FLAG]` entries the correction engine emitted, by category,
so the reviewer sees how much was deferred to human judgment.

---

## 6. Pairing with Parity Mode

The harness is most precise when APP is rendered in the correction engine's
**Parity Mode** (`deterministic_parity_mode: true`). In Parity Mode the
structural stages are off, so APP still aligns utterance-for-utterance with RAW,
and the word_delta rule (4.1) applies cleanly.

Recommended workflow:

1. Transcribe the job normally.
2. Render APP once in **Parity Mode** → the harness's authoritative comparison.
3. Optionally render APP again in **Full Mode** → a second `diff_report` showing
   what the structural stages (X, S, Q) changed, each line annotated with its
   rule ID. This is how you review the structural stages' behavior in isolation.
4. Optionally drop a Playground export in as REF for an advisory cross-check.

Full Mode is expected to show many structural differences from RAW — that is the
engine working. The harness's job there is to confirm **every** difference is
explained by a correction-log entry; an unexplained `!` line is the bug signal.

---

## 7. Regression Use

`diff_metrics.json` is a snapshot. The harness supports a regression gate for CI
or pre-release checks:

- Keep a committed baseline `diff_metrics.json` for a set of fixture jobs
  (the Heath Thomas deposition is the primary fixture).
- On each change to the assembler, speaker mapping, or correction engine,
  re-run the harness and compare to the baseline.

**Gate (fails the build):**

- net `word_delta` ≠ 0 in Parity Mode;
- any `!` (unexplained) per-utterance change;
- `utterance_count` or `speaker_count` drift in **APP-vs-RAW** beyond a
  configured tolerance (default 0).

**Never gates the build:**

- any APP-vs-REF metric (advisory only, per Section 2.2).

---

## 8. Module / File Layout

The harness is a self-contained developer tool, kept out of the production
request path:

```
backend/diagnostics/
├── __init__.py
├── diff_harness.py     # orchestrator: load RAW/APP/REF, compute, write artifacts
├── metrics.py          # the deterministic metric functions (Section 4)
├── align.py            # utterance alignment (for unmatched_utterances + per-utt diff)
├── report.py           # renders diff_report.txt + diff_metrics.json
└── ref_import.py       # normalize a pasted/uploaded/Speaker-N export into the canonical REF structure

tools/
└── run_diff.py         # CLI: `python -m tools.run_diff {job_id} [--ref path] [--mode parity|full]`

tests/diagnostics/
├── test_metrics.py
├── test_align.py
└── test_diff_harness.py   # end-to-end on a fixture job
```

CLI entry point:

```
python -m tools.run_diff {job_id} --mode parity [--ref playground_export.txt] [--snapshots]
```

writes `data/diff/{job_id}/` and prints the summary block to stdout. `--snapshots`
additionally writes the per-stage `after_*.txt` files (§3.2).

### 8.1 Alignment note

`align.py` aligns RAW utterances to APP rendered lines so the per-utterance diff
and `unmatched_utterances` are meaningful. Use a standard sequence alignment
(e.g. difflib `SequenceMatcher` over normalized utterance text). Alignment is
itself deterministic — no model. In Full Mode, where one RAW utterance may become
a `Q.` line plus an `A.` line, alignment is one-to-many; the harness records that
as an expected split (cross-checked against the correction log), not as a
mismatch.

---

## 9. What the Harness Does NOT Do

- It does **not** modify any transcript, RAW or WORKING.
- It does **not** judge transcript *legal* correctness — only structural drift
  and word-count integrity. Legal correctness is the reporter's certification.
- It does **not** treat the Playground (REF) as a correctness oracle (Section 2.2).
- It does **not** call any model. Every metric is arithmetic over token lists.

### 9.1 Deliberately excluded — and why

These were proposed in review and are **not** specified here, on purpose:

- **Composite "integrity score."** A single blended number (speaker stability +
  word delta + duplication + …) hides *which* component moved — the opposite of
  what a diagnostic should do. The individual metrics in Section 4 are kept
  separate so a regression points at a specific cause. A composite score can be
  added later for at-a-glance dashboards, but it must never replace the
  components or drive the regression gate.
- **Audio-transition metrics** (reconnects, silence gaps, mic switches, packet
  loss). Valuable — and directly relevant to the Zoom use case — but they come
  from **audio analysis, not transcript diff**. They belong in a preprocessing /
  audio-diagnostics spec with access to the waveform, not in this harness, which
  by design only sees transcripts. Cross-referenced here so the idea is not lost.
- **Transcript heatmaps / visualizations.** A future presentation layer over the
  metrics this harness already produces. Out of scope for the harness itself; it
  emits `diff_metrics.json`, and a separate tool can visualize it.

---

## 10. Open Questions — Status

All four resolved by the reporter. Decisions recorded below and reflected in the
spec body.

1. **DH-Q1 — REF import format. RESOLVED.** `ref_import.py` accepts pasted text,
   an uploaded `.txt`, and plain `Speaker N:` exports — and **normalizes every
   input into one canonical REF structure** internally. The harness does **not**
   depend on Playground JSON (its shape is not guaranteed stable). All downstream
   comparison logic sees only the canonical REF form.
2. **DH-Q2 — diff artifact retention. RESOLVED.** `data/diff/{job_id}/` is purged
   when the associated transcript job is deleted (alongside the existing
   `delete_job` cleanup of `data/transcripts/{job_id}`). A Settings option —
   "retain debug artifacts" — lets a developer keep the folder for long-term
   regression jobs.
3. **DH-Q3 — regression fixture set. RESOLVED.** Three fixtures, for graded
   coverage: (1) the **Heath Thomas** deposition — worst case: poor audio,
   speaker drift, Zoom instability; (2) one **clean, simple** deposition —
   normal case: minimal overlap, stable mics, straightforward Q/A; (3) one
   **medical / technical-terminology** deposition — keyterm-heavy case. Fixtures
   1 and 2 are committed first; fixture 3 is added when a suitable transcript is
   available.
4. **DH-Q4 — CLI vs UI. RESOLVED.** Build the **CLI first** — it remains the
   authoritative regression and testing tool. A read-only Workspace diff viewer
   is added later: diagnostic only, non-editable, comparison-focused, and
   explicitly **not** part of the certified transcript flow.

---

*End of specification. Companion document to
`deterministic_correction_engine_spec.md` — the harness consumes that engine's
Parity Mode output and correction log. Repo location:
`docs/architecture/transcript_engine/`.*
