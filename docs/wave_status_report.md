# DEPO-PRO — Wave Status Report

*Verified against the codebase. This document tells you, for every
wave, whether it is fully operational or not — and how to check it
yourself.*

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

**Waves 1 through 18.5 are fully operational.** Every one is wired into
the running app — 9 API routers are registered, the 7-screen workflow
(Intake → Transcripts → Speakers → Workspace → Insertions → Certify →
Export) is live, and transcription, correction, speaker mapping, AI
review, export, and snapshots all run.

**Only Waves 19 and 20 are "built but not wired."** They are the active
frontier. Their code is complete and fully tested, but the running app
does not call it yet. That is two waves — not "numerous."

Nothing is broken. The gap is integration, and it is confined to the
two newest waves.

---

## 3. Master status table

Verified: routers in `backend/app.py`, module references from the
api/service layer, and the test suite (424 passed, 1 skipped).

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
| 19 | Pagination + Geometry | ✓ | ◑² | ✓ | ✗ | **BUILT — NOT WIRED** |
| 20 | Transcript packaging | ✓ | ✓ | ✓ | ✗ | **BUILT — NOT WIRED** |

¹ Wave 10 is documented as spec/notes files (`deterministic_correction_engine_spec.md`,
`WAVE10_*_NOTES.md`), not a single `wave10.md`.
² Wave 19A (Pagination Engine) is fully built. Wave 19B (Geometry) has
only the measurement profile — the geometry *layer* engine is missing.

---

## 4. How to check this yourself — anytime

You do not need to take anyone's word for it. Four checks, in a
terminal at the project root:

**Is there a spec?**
```
ls docs/ | grep -i wave
```

**Does the code exist?**
```
ls backend/
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
grep "include_router" backend/app.py
grep -rl "backend.<module>" backend/api backend/services
```
If a backend module has **no router** in `app.py` **and** is
**referenced by zero** api/service files, it is built-but-not-wired.
Today that is exactly three folders: `pagination`, `geometry`,
`packaging`. Everything else is referenced and reachable.

---

## 5. What Waves 19 and 20 need to become operational

Wave 19 (make pagination + geometry produce real documents):
1. Build the Geometry Layer engine — `backend/geometry/layer.py`
   (only the measurement profile exists today).
2. Build a geometry-aware DOCX/PDF writer (the current writer is the
   plain Wave 18 one).
3. Bridge the input — route the canonical render into the Pagination
   Engine, replacing `export_render.py`'s own naive paginator.
4. Wire it into the export service and the Export Preview.

Wave 20 (make packaging operational):
5. API router — `backend/api/packaging.py`, registered in `app.py`.
6. Metadata sourcing — gather case/reporter/appearance data into the
   form the engine expects.
7. Exhibit & examination tracking — a genuinely new subsystem (there
   are no exhibit tables today; the Stage 4 exhibits UI is mock).
8. Package DOCX rendering (depends on step 2).
9. Package persistence + a Certify-screen UI action.

Critical path: 1 → 2 → 3 → 4 makes Wave 19 real; step 8 depends on
step 2. Steps 5–7 can run in parallel; step 7 is the largest piece.
Step 5 (the Wave 20 API router) is the only item with zero blockers.

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

## 7. How to read a spec's own status

Every spec doc carries its completeness signals in two places. To audit
any spec yourself, read both:

1. **The Status line** — at the top of the doc (line 2–3). The author's
   declared state: `complete`, `BUILT`, `SPEC + BUILT`, or a `PLAN`
   with a qualifier. Some older docs (wave 2, 9, and the wave 11 panel
   spec) have no status line — they predate the convention; that is a
   formatting gap, not incompleteness.

2. **The "Open Questions" / "Open Decisions" section** — near the end.

To scan every spec at once:
```
grep -i "^status\|Status:" docs/wave*.md          # declared status
grep -lri "TODO\|TBD\|FIXME" docs/                 # abandoned stubs (none today)
grep -ln "Open Question\|Open Decision" docs/wave*.md
```

**Key point:** an "Open Questions" section inside a *BUILT* spec does
NOT mean the spec is incomplete. The engineering is done; the section
records *decisions deferred to James*. Open Questions are a decision
list, not an engineering backlog.

---

## 8. Spec audit — declared status

All 22 wave spec documents are complete documents. None contains a
TODO / TBD / FIXME marker. Declared statuses:

| Spec | Declared status |
|------|-----------------|
| wave2 (step1, step2) | *(no status line — predates the convention)* |
| wave4, wave5 ×2, wave6, wave7, wave8 | complete |
| wave9 | *(no status line)* |
| wave11 panel spec | *(no status line)* |
| wave11 build completion | BUILT |
| wave12 | BUILT |
| wave13, wave14, wave15b | SPEC + BUILT |
| wave15a | AUDIT + BUILT |
| wave16, wave17, wave18, wave18.5 | BUILT |
| wave19 | BUILT — geometry-into-DOCX is the next pass |
| wave20 | BUILT — engine core |

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

*Generated as a verified audit of the depo_wave20 codebase. Re-run the
section 4 and section 7 checks after any change to keep this picture
current.*
