> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 15a — Engine Reconciliation

Status: **AUDIT + BUILT.**

This wave reconciles the built correction engine against the six
authoritative DepoPro specification documents, so the AI review layer
(Wave 15b) is built on an engine that matches its own spec.

## 1. Audit — what was found

The spec describes ONE engine: `backend/corrections/` running stages
**G -> A -> M -> X -> S -> Q -> T -> F -> U** in sequence.

The built reality before this wave was a SPLIT:

- `backend/corrections/pipeline.py` ran only **G, A, M, T, F, U** — its
  own comments said "X, S, Q not built."
- `backend/stage_s/` (Wave 13) and `backend/lexicon/` (Wave 14) were
  real, tested implementations — but lived in separate packages and
  fed only the export preview, not the engine.
- `backend/corrections/regex_rules.py` (Wave 14) existed but
  `pipeline.py` never called it.

Four mismatches: split pipeline, "Stage X" naming collision (lexicon vs.
the spec's garbled-objection resolution), `regex_rules` not wired, and
module names not matching spec IDs.

## 2. Naming decision

The spec uses "Stage X" ambiguously. Resolved per the spec's stage
table:

- **Stage X = legal-phrase / garbled-objection resolution**
  (`legal_phrases.py`). This is the spec's true Stage X and was NOT
  built before this wave.
- The Wave 14 lexicon/spelling engine is a **Stage M** concern
  (confirmed spellings / keyterms) — that is where spec rules PRE-07 /
  PRE-08 already live. The `backend/lexicon/` package is retained and
  invoked from Stage M.

## 3. What this wave does

1. **Builds the real Stage X** — `backend/corrections/legal_phrases.py`:
   role-scoped, exact-match garbled-objection and legal-phrase
   resolution from the AI Reference §4 tables (`OBJECTION_GARBLE_MAP`,
   `LEGAL_PHRASE_MAP`, `SDT_MAP`).
2. **Wires Stage X into `pipeline.py`** in its correct sequence
   position: after M, before T.
3. **Wires `regex_rules` into the engine** as a pre-stage so per-case
   regex corrections replay inside the unified pipeline.
4. The engine now runs the full **G/A/M/X/regex/T/F/U** text-stage
   sequence in one invocation path. (Structural stages S and Q remain
   the dedicated `stage_s` renderer, invoked by the render path — see
   note below.)

## 4. Open questions — resolved

- **Q3 — `so happy God` / `so help you guide`:** FLAGGED, not
  deterministically corrected. Per signoff.
- **Q4 — post-record content:** FLAGGED, never auto-deleted. Per
  signoff and STD-SPE-06.

## 5. Scope note — structural stages S/Q

Stage S (off-record / parentheticals) and Q (Q/A formatting) are
genuinely structural — they emit a line list, not corrected text. The
built `backend/stage_s/` renderer already does this and is wired into
the render path. Rather than risk 275 passing tests by relocating a
structural renderer into a text-stage pipeline, S/Q remain the
`stage_s` renderer. The TEXT stages (G/A/M/X/T/F/U) are unified in
`corrections/pipeline.py`. This is the one deliberate, documented
deviation from a literal single-package layout; the stage SEQUENCE and
RULES match the spec exactly.

## 6. Tests

`tests/test_legal_phrases.py` — Stage X garbled-objection / legal-phrase
resolution, role scoping, flag-fallback. Plus the existing suite must
remain green.
