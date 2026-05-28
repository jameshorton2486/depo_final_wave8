> DOCUMENT STATUS: CANONICAL CURRENT-STATE GOVERNANCE
> Scope: verified wave-by-wave operational status, current frontier, and current decision backlog.
> This document is current-state status authority only. It does not own architecture, transcript rules, or subsystem ownership. Historical `wave*.md` build records do not override it.

# DEPO-PRO — Wave Status Report

*Verified against the codebase. This document tells you, for every
wave, whether it is fully operational or not — and how to check it
yourself.*

For ownership, transcript lifecycle, and export/certification authority, defer
to `docs/SYSTEM_OWNERSHIP.md`, `docs/TRANSCRIPT_ORCHESTRATION.md`, and
`docs/EXPORT_AND_CERTIFICATION_PIPELINE.md`.

---

## 1. Why "complete" was ambiguous

A wave can be "done" at four different levels. They are not the same
thing, and that is the whole source of the confusion:

1. **Spec** — a design document exists in `docs/`.
2. **Built** — the code exists in `backend/`.
3. **Tested** — there is a passing test suite for it.
4. **Wired** — the running application actually *calls* that code.
   This is the only level that means a real person can *use* the
   feature.

A wave can be Built + Tested but **not Wired** — the code is correct
and proven, but nothing in the app invokes it yet. That is not
"broken." It is a normal state for the most recent waves, which are
always ahead of their integration. It only becomes a problem if you
*think* it is wired when it is not — which is exactly what happened
here.

---

## 2. The bottom line

**Waves 1 through 21 are now operational.** Every one is wired into
the running app — 12 API routers are registered, the 7-screen workflow
(Intake → Transcripts → Speakers → Workspace → Insertions → Certify →
Export) is live, and transcription, correction, speaker mapping, AI
review, export, snapshots, exhibits, certification lineage, packaging,
and offline validation all run.

The active frontier is no longer wiring. It is operational trust:
real-data validation, workflow clarity, and narrow hardening based on
what reporters find in actual use.

---

## 3. Master status table

Verified: routers in `backend/app.py`, module references from the
api/service layer, and the test suite (the full suite green (run `python -m pytest tests -q` for the current count)).

| Wave | Feature | Spec | Built | Tested | Wired | Status |
|------|---------|:----:|:-----:|:------:|:-----:|--------|
| 1 | Foundation — DB schema, cases/sessions/reporters | – | ✓ | ✓ | ✓ | **Operational** |
| 2 | Stage 1 intake persistence | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 3 | *(no spec doc — scope unknown)* | – | ✓ | – | ✓ | **Operational** (unverified scope) |
| 4 | Real NOD parser | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 5 | Canonical models + Stage 2 transcripts engine | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 6 | Merge transcripts + Workspace | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 7 | Clean startup, errors, paragraphs | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 8 | NOD parser intelligence | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 9 | Speaker mapping (Step 2B) | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 10 | Deterministic correction engine | ✓¹ | ✓ | ✓ | ✓ | **Operational** |
| 11 | Workspace speaker panel | ✓ | ✓ | ✓ | ✓ | **Operational** (redundant Workspace panel removed per request) |
| 12 | Export preview | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 13 | Stage S — structural rendering | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 14 | Stage X — lexicon | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 15a | Reconciliation | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 15b | AI review layer | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 16 | AI generators | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 17 | Test offline insulation | ✓ | ✓ | ✓ | n/a | **Operational** (test infrastructure) |
| 18 | Export engine + menu (real files) | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 18.5 | Transcript snapshots & versioning | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 19 | Pagination + Geometry | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 20 | Transcript packaging | ✓ | ✓ | ✓ | ✓ | **Operational** |
| 21 | MVP validation hardening | ✓ | ✓ | ✓ | ✓ | **Operational** |

¹ Wave 10 is documented as spec/notes files (`deterministic_correction_engine_spec.md`,
`WAVE10_*_NOTES.md`), not a single `wave10.md`.
## 4. How to check this yourself — anytime

You do not need to take anyone's word for it. Four checks, in a
terminal at the project root:

**Is there active documentation authority?**
```
Get-ChildItem docs -Recurse -Filter *.md
```

**Does the code exist?**
```
Get-ChildItem backend
```
Each wave maps to a folder: `corrections` (W10), `stage_s` (W13),
`lexicon` (W14), `ai_review` (W15b/16), `export` (W18),
`transcript_state` (W18.5), `pagination`+`geometry` (W19),
`packaging` (W20).

**Do its tests pass?**
```
python -m pytest tests/ -q
```
A green suite means every Built+Tested wave is correct.

**Is it wired into the running app?** — the decisive check. Two parts:
```
rg "include_router" backend/app.py
rg -l "backend\\.<module>" backend/api backend/services
```
If a backend module has **no router** in `app.py` **and** is
**referenced by zero** api/service files, it is built-but-not-wired.
As of 2026-05-25, the packaging router is registered, pagination and
geometry are used by live export flows, and the Wave 20 certification
chain is reachable from the running app.

---

## 5. Current Frontier

Wave 21 moved the project from integration work into MVP validation:
1. legacy transcript job re-binding for honest Stage 2 lineage
2. certification validation for Stage 5 statutory fields
3. explicit offline transcription mode for manual validation
4. documentation reconciliation with the verified codebase
5. Stage 1 operator transparency (Phases 1–4): case-context banner,
   three-state validation badges (MISSING / AUTO-POPULATED / CONFIRMED),
   deterministic missing-field enumeration, and derived Deepgram-request
   and UFM-payload preview endpoints. Additive — no transcript-engine
   modules touched.
6. Stage 1 UX polish (Save Intake button, saved/unsaved banner, UFM
   modal recovery, parser feedback) shipped on stage1/ux-polish.
7. Stage 2 audio-profile preset library (on stage2/audio-presets):
   `probe.probe_audio_profile` measures each file (rate, channels,
   loudness, voice-activity, silence gaps) and a deterministic
   `presets.classify_audio` picks one of four Deepgram presets
   (studio/courtroom/zoom_mixed/phone), tuning only the settings used to
   produce the immutable RAW. `filler_words=true` preserved on every path.

The next work should come from `docs/audits/REAL_WORLD_VALIDATION_LOG.md`,
not from assumptions that Waves 19–20 are still unwired.

---

## 6. Decisions needed before that work

- Exact UFM page measurements, and the margin/text-area conflict
  flagged in `backend/geometry/profile.py`.
- How exhibits and examination segments get captured — manual marking
  or transcript detection (this sizes step 7).
- Administrative-page template wording; the freelance trigger; the
  required-metadata field set; plain-`.txt` vs true CAT ASCII.

---

---

## 7. How to read an active spec's own status

Historical `wave*.md` build records now live under `docs/archive/`.
For active subsystem specs, read completeness and authority signals in
two places:

1. **The Status line** — at the top of the doc (line 2–3). The author's
   declared state: `complete`, `BUILT`, `SPEC + BUILT`, or a `PLAN`
   with a qualifier. Some older docs (wave 2, 9, and the wave 11 panel
   spec) have no status line — they predate the convention; that is a
   formatting gap, not incompleteness.

2. **The "Open Questions" / "Open Decisions" section** — near the end.

To scan active docs at once:
```
rg -n "^> DOCUMENT STATUS|^Status:" docs --glob "!docs/archive/**"
rg -l "TODO|TBD|FIXME" docs --glob "!docs/archive/**"
rg -n "Open Question|Open Decision|Open questions" docs --glob "!docs/archive/**"
```

**Key point:** an "Open Questions" section inside a *BUILT* spec does
NOT mean the spec is incomplete. The engineering is done; the section
records *decisions deferred to James*. Open Questions are a decision
list, not an engineering backlog.

---

## 8. Active-spec audit — declared status

The historical wave build records are archived. The active subsystem
specs still governing code today are:

| Spec | Current role |
|------|--------------|
| `docs/nod_parser_spec.md` | Active subsystem spec |
| `docs/wave19_ufm_layout.md` | Active subsystem spec |
| `docs/wave20_packaging.md` | Active subsystem spec |

### Outstanding decisions (the only spec-level "incomplete" items)

These are decisions parked for James. Resolved questions (e.g. Wave 11's
Step-2B-vs-Workspace question, settled by removing the Workspace panel)
are excluded.

- **Q19-2** — exact UFM measurements; resolve the margin/text-area
  conflict flagged in `geometry/profile.py`. *(Implies correctness work
  if the answer is non-default.)*
- **Q19-3 / Q19-4 / Q19-5** — header data source; time-stamping in the
  first geometry build; precise transcript flow rules.
- **Q20-2 / Q20-3 / Q20-5 / Q20-6 / Q20-8** — template wording;
  freelance trigger; manifest embedded vs. sidecar; required-metadata
  field set; package state graph.
- **Q-ASCII** — plain `.txt` (built) vs. true CAT-compatible ASCII.
  *(Implies real new work if CAT is required.)*
- **Q18.5-5** — whether the Diff Engine becomes its own near-term wave.

Most are confirmations; Q19-2 and Q-ASCII are the two with real
engineering consequences.

---

*Generated as a verified audit of the current DEPO-PRO codebase. Re-run the
section 4 and section 7 checks after any change to keep this picture
current.*

Maintenance expectation: update this file when wave status, current frontier,
or named open decisions materially change. Do not use it as a substitute for
canonical ownership or transcript-safety contracts.
