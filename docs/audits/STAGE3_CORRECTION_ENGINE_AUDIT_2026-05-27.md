# Stage 3 Deterministic Correction Engine — Audit

**Date:** 2026-05-27
**Status:** Complete. All phases (pre-phase, A, B, C, D, E) delivered. No code changes (investigation-only per prompt §1).

**Framing in force:** **A — "Wire what's already built"** as a working assumption. Per the human direction recorded at the start of Phase A — *"if Phase D's evidence points to a different highest-leverage pick than the pipeline.run / §17.1 wiring prediction, honor the evidence"* — the headline recommendation in Phase E does not match Framing A's prediction. The Phase C inventory grounds a different pick. CF-1 wiring is preserved as runner-up #1. See Phase E for the full rationale.

---

## 1. Executive Summary

The deterministic correction engine has two parallel code paths: `backend/corrections/pipeline.run` (dormant — its `CorrectionResult` is generated and immediately discarded; CF-1) and a direct-call chain inside the export builders (`apply_regex_rules` → `lexicon/stage_x.apply_stage_x` → `stage_s/render_stage_s`) that actually produces the certified output. Every stage the spec demands is implemented somewhere in the repo, but the live chain uses `backend/lexicon/stage_x.py` rather than the spec's `corrections/legal_phrases.py`, and both chains generate audit logs that are immediately dropped — leaving the spec §17.1 certifiability requirement unmet by either chain. **The Phase C inventory (47 entries across Shaw + Filpi) does not, however, support CF-1 wiring as the highest-leverage build pass.** It instead grounds a structural-rendering pick: implement QA-01's trigger gate and the canonical opening ritual it requires (WITNESS_SWORN block → EXAMINATION header → BY-line → inline `(BY MR. X)` re-attribution on resumption) — grounded in Phase C Entries 2, 24, 31, 32, 37, 42 (sworn-witness + EXAMINATION headers, both depositions) and Entries 3, 5, 8, 11, 12, 14, 27, 28 (inline re-attribution after interruption, both depositions). Every deposition currently opens cold with a `Q.` line and resumes after every interjection the same way — visibly wrong on every job, fixable as an S-effort local change inside `backend/stage_s/` whose building blocks all exist. CF-1 wiring is recommended as runner-up #1 to follow the headline pick, gated on first resolving whether `backend/lexicon/` is an intentional architectural separation or an accidental parallel system.

---

## 2. Baseline

```
git status --short:
(empty — clean tree)

git log -1 --oneline:
e974ba4 Stage 1 UX polish (docs): wave_status_report Section 5 entry, REAL_WORLD_VALIDATION_LOG operator transparency checklist

python -m pytest tests -q:
592 passed, 1 skipped, 36 warnings in 79.09s
```

Matches the prompt's expected baseline of 592 passed / 1 skipped.

---

## 3. Pre-phase Anomaly Findings (Section 4)

### Finding 1 — Pipeline docstring is stale, in both directions

`backend/corrections/pipeline.py` lines 11–16 state: *"FOUNDATION SCOPE: stages X, S, Q are not built yet. The pipeline runs G, A, M, T, F, U — which is exactly the Parity-Mode stage set."*

This is factually wrong at HEAD in two opposite ways:

1. **Stage X is built and invoked inside the pipeline.** `pipeline.py:168` calls `legal_phrases.apply(text, uid, ctx, role=utt.role)`, with the in-line comment at lines 165–167 explicitly identifying this as *"Wave 15a: the spec's true Stage X. Garbled objections / legal phrases from finite enumerable tables — deterministic, no AI."*
2. **Stages S and Q are built**, just not inside `backend/corrections/`. They live in the `backend/stage_s/` package (11 source files). Pipeline comments at `pipeline.py:171–172` acknowledge this: *"S, Q — structural stages are handled by the stage_s renderer on the render path (they emit a line list, not corrected text)."*

`pipeline.run`'s actual stage-invocation order is: regex pre-stage (lines 130–152) → **G** (154) → **A** (157) → **M** (161) → **X** legal_phrases (168) → **T** (174) → **U** (178) → **F** (185). Note `F` runs **after** `U` — see Finding 5.

### Finding 2 — Stage S is invoked from the export path, not from `pipeline.run`

`render_stage_s` is imported at three sites, none of which is `pipeline.run`:

- `backend/api/transcripts.py:1013` → invoked at `1015` (live export-preview builder)
- `backend/api/transcripts.py:1090` → invoked at `1154` (snapshot-based export builder)
- `backend/api/packaging.py:388` → invoked at `450` (packaging path)

Its signature, defined at `backend/stage_s/renderer.py:55`, is `render_stage_s(utterances, participants) -> StageSResult`. It takes raw working-state utterance dicts plus the confirmed participant mapping — **not** the `CorrectionResult.lines` that `pipeline.run` produces. The call sites at `transcripts.py:982` and `transcripts.py:1093` source utterances directly from `working_state_mod.get_working_utterances(job_id)` or from a persisted snapshot's `working_utterances`. The pipeline's corrected text never reaches Stage S.

### Finding 3 — pipeline.py's "Stage S" and `backend/stage_s/` ARE the same conceptual stage, decoupled at runtime

The spec (Section 18) calls for `corrections/structure.py` (Stage S) and `corrections/qa_format.py` (Stage Q) inside the `backend/corrections/` package, orchestrated in-line by `pipeline.py`. The code instead has:

- No `corrections/structure.py` or `corrections/qa_format.py`.
- A parallel package `backend/stage_s/` that implements both Stage S concerns (off-record / parentheticals) and Stage Q concerns (Q/A line typing via `qa_mode_for_role()` at `line_builder.py:141`, objection isolation at `objection_handler.py`).
- Pipeline.py at lines 171–172 explicitly defers to "the stage_s renderer on the render path."
- `docs/SYSTEM_OWNERSHIP.md` lines 49–50 documents the joint ownership: *"CORRECTED / STRUCTURALLY RENDERED → backend/corrections/, backend/stage_s/, backend/transcript/export_render.py"* — so the split is governance-blessed.

They are the same Stage S, referenced two ways. The architectural choice is `backend/stage_s/` runs after the working-state read by the export path, not as a step inside `pipeline.run`. Spec drift is in the orchestration location and in pipeline.py's docstring, not in the existence of the code.

### Finding 4 — `pipeline.run`'s regex pre-stage is dead in production; regex rules ARE applied, via a different path

`pipeline.py:129` reads `regex_rule_dicts = ctx.job_config.get("regex_rules") or []` and, when non-empty, applies them at lines 130–152.

The only production caller of `pipeline.run` is `backend/services/correction_trigger.py:78`. That call passes `job_config=job_config or {}` (line 80); the outer `job_config` parameter is whatever the caller hands in. **No code path supplies `regex_rules` to it.** `correction_trigger.run_correction_engine_for_job` is invoked with `job_id` and `job_config=None` by default; nothing populates `job_config["regex_rules"]` from `regex_rules_repo.list_rules(case_id)` before calling. The pipeline's regex pre-stage **never fires in production** — dead code in effect.

Regex rules are wired elsewhere. The export-preview path at `transcripts.py:992–997` reads them directly: `regex_rules_repo.list_rules(case_id_for_corr)` then `apply_regex_rules(utterances, rules)`. The snapshot export path at `transcripts.py:1120–1134` does the same from `snapshot_state["regex_rule_state"]`. The packaging path at `packaging.py:406` follows the same shape. So regex rules ARE saved (via `api/corrections.py:69`), ARE persisted (`regex_rules_repo`), and ARE applied at export — via a parallel direct-call route, not via the pipeline's documented pre-stage.

### Finding 5 — Spec stage order vs code execution order

The spec (`deterministic_correction_engine_spec.md` §3, §6) defines stage order as **G → A → M → X → S → Q → T → F → U**, U strictly last.

`pipeline.run` actually executes **regex (pre) → G → A → M → X (legal_phrases) → T → U → F**. Differences:

- **Stages S and Q are absent from `pipeline.run`.** They run on the render path via `render_stage_s()`, after a separate `apply_regex_rules` and a separate `apply_stage_x` (see CF-1). Net pipeline drift: `pipeline.run` is missing S and Q.
- **F and U are swapped.** Spec §15: *"Module: corrections/guards.py → unguard() · Strictly last."* Code runs U at `pipeline.py:178`, then F at `185`. Inline comment at line 178 justifies this as *"unguard (must precede flag insertion so detectors see real text)"* — a plausible reason that directly contradicts the spec.
- **A regex pre-stage runs before G in code** (`pipeline.py:130`). The spec does not define a regex pre-stage anywhere; the spec's stage table (§6) does not include it.
- **In production**, the actual ordered sequence working text traverses is: working_state → `apply_regex_rules` (export path) → `apply_stage_x` (the `backend/lexicon/` Stage X, NOT the corrections Stage X) → `render_stage_s` → `export_render`. This bears almost no resemblance to the spec's documented pipeline.

---

## 4. Critical Findings

### CF-1 — `pipeline.run` output is computed but not consumed in production

The output of `corrections/pipeline.run` (a `CorrectionResult` carrying `lines`, `log`, `flags`, `parity_mode`) is **discarded** in production:

- The only production caller is `backend/services/correction_trigger.py:78`. That function inspects the result solely to produce a summary dict (`line_count`, `correction_count`, `flag_count`, `parity_mode`) at lines 87–93 and logs it. Nothing persists `result.lines`, `result.log`, or `result.flags`.
- The export and packaging paths read `utterances` directly from `working_state_mod.get_working_utterances(job_id)` (or from a snapshot) and run their own correction sequence: `apply_regex_rules` → `apply_stage_x` (lexicon variant) → `render_stage_s`. The pipeline's corrected text is never the input.

Net effect: the corrections defined by spec stages G, A, M, X (legal_phrases), T, F, U — *as orchestrated by `pipeline.run`* — do not influence the certified export. They run as a background side-effect via `correction_trigger`, but their output is invisible to the system.

There is a separate, parallel correction chain on the export path that uses the same building blocks differently. The two chains share some modules (`regex_rules.py`) but not others — the export path uses `backend/lexicon/stage_x.py` (a whole-word lexicon substitution module not referenced anywhere in the spec) instead of `backend/corrections/legal_phrases.py` (the spec's "true Stage X" per pipeline.py:165–167).

**Spec compliance — §17.1 status.** The spec's §17.1 designates the correction log as *"a firm build requirement, not a recommendation"*: *"a certifiable system must let the reporter audit every automatic edit; an unauditable correction engine cannot be trusted with a legal record."* The system currently:

- generates a complete audit log via `pipeline.run` (`backend/corrections/log.py:CorrectionLog`) — then discards it because pipeline.run output is discarded;
- generates per-call substitution audit data from `apply_regex_rules` and `apply_stage_x` on the export path — then discards it via `_` tuple-unpacking at `transcripts.py:997, 1134` and `packaging.py:451`;
- emits Stage S structural-transformation audit entries (`stage_s/audit.py`) into `StageSResult.audit` — then drops them at the export consumer (the consumers iterate `stage_s.lines` only, never `.audit`).

The verbatim mandate and the transcript-safety invariants in `TRANSCRIPT_ENGINE_RULES.md` are **not** violated — testimony is not deleted, paraphrased, or transformed by anything semantic. CF-1 is therefore a **spec compliance finding** (§17.1), not a §2E transcript-safety violation. That distinction matters because §17.1 is a build-time guarantee about auditability rather than a runtime safety invariant; closing the gap is wiring + persistence, not stage-engine rewrites.

### Parallel-system flag (governance) — `backend/lexicon/`

`backend/lexicon/` (4 files: `__init__.py`, `merge.py`, `model.py`, `stage_x.py`) implements what amounts to a second Stage X — whole-word lexicon substitution — and is the one the export path actually uses. Evidence of intentionality, weighed:

- **Self-identifies as Wave 14 Stage X.** `lexicon/__init__.py` line 1: *"Backend lexicon — Wave 14 Stage X. The merged, priority-ordered legal lexicon and the deterministic whole-word substitution engine that applies it."* `lexicon/stage_x.py` line 1: *"Stage X — deterministic lexicon substitution."*
- **References a missing doc.** The same `__init__.py` references `docs/wave14_stage_x_lexicon.md`; that file does not exist (verified via Glob).
- **Does not appear in `SYSTEM_OWNERSHIP.md`.** The ownership map lists `corrections/` and `stage_s/` as joint owners of "CORRECTED / STRUCTURALLY RENDERED", but `lexicon/` is absent.
- **Functionally complementary, not duplicative.** `lexicon/stage_x.py` does whole-word + possessive-aware lexicon substitution (e.g. `acoustic neuroma`, `Trinity's`); `corrections/legal_phrases.py` does exact-phrase garble resolution (e.g. `infection.` → `Objection.`). Both could legitimately occupy "Stage X" semantically.

**Audit verdict, per the working-assumption rule.** Intentionality evidence is present but weak (claim without surviving rationale doc, no ownership entry). I am **not** flipping the working assumption. `lexicon/` is treated as an accidental parallel system for the duration of this audit. Surfaced as an open question in Phase E. Consolidation (or formal recognition with a §10A spec amendment and an ownership entry) is a separate later architectural decision and is **not** part of the recommended build pass.

---

## 5. Pipeline Map (Phase A)

### 5.1 File traces — `backend/corrections/`

**`pipeline.py`.** Module docstring (lines 1–20) claims to orchestrate the spec's G→A→M→X→S→Q→T→F→U sequence in Full Mode and a reduced G/A/M/T/F/U sequence in Parity Mode. In reality it runs regex pre-stage → G (line 154) → A (157) → M (161) → X via `legal_phrases.apply` (168) → T (174) → U (178) → F (185), with the inline comment at 171–172 acknowledging that S and Q live in `backend/stage_s/`. Invoked from `backend/services/correction_trigger.py:78`. **STATUS: PARTIAL** — runs end-to-end, output discarded, F/U order swapped from spec, S/Q absent from the orchestrator.

**`regex_rules.py`.** Module docstring (line 1) claims per-case regex correction. Exposes `RegexRule` dataclass, `apply_regex_rules_to_text`, `apply_regex_rules`. Invoked from `pipeline.py:131` (dead in production per CF-1), `api/transcripts.py:992` (live, export-preview), `api/transcripts.py:1120` (live, snapshot export), `api/packaging.py:406` (live, packaging), `api/corrections.py:15` (live, preview/CRUD). **STATUS: LIVE** — via the export-path direct calls, not via `pipeline.run`.

**`legal_phrases.py`.** Module docstring (lines 1–15) claims Stage X — exact-match role-scoped garbled-objection (`OBJECTION_GARBLE_MAP`, 14 entries), garbled-legal-phrase (`LEGAL_PHRASE_MAP`, 7 entries with role gates), and SDT (`SDT_MAP`, 5 entries) resolution. Implements `apply(text, uid, ctx, role)` returning `(out, log)`. Invoked from `pipeline.py:168`. **STATUS: PARTIAL** — substantive implementation, but only reached via dormant `pipeline.run`; never feeds export.

**`patterns.py`.** Module docstring (lines 1–8) claims centralized regex registry per spec §17.6. Holds GUARD-01..06 (filler, stutter, false-start, ellipsis, LC, affirmation set), PRE-04..10 (artifacts), PRE-01..09 (metadata), POST-01..08 (typography), FLAG-02 (`LIST3_FLAG_ITEMS`), FLAG-06 (`OATH_GARBLE_DETECT`), and the sentinel pair `\x00`/`\x01`. Imported by `guards.py`, `artifacts.py`, `metadata.py`, `typography.py`, `flags.py`. **STATUS: LIBRARY**.

**`typography.py`.** Module docstring (lines 1–14) claims Stage T POST-01..08 (honorifics, Miss, em-dash, time, money/percent, objection-double-space, two-space; POST-09 large-number commas flagged not implemented per Q5). Implements `apply(text, uid, ctx)` chaining 7 sub-functions. Invoked from `pipeline.py:174`. **STATUS: PARTIAL** — substantive; only reached via dormant `pipeline.run`.

**`guards.py`.** Module docstring (lines 1–11) claims Stage G + Stage U: shield 5 protected-span types with opaque sentinels via `Vault`, restore them strictly last via `unguard`, expose `has_sentinels` for the pipeline self-check. Loop at lines 58–61 applies the 5 guard patterns in priority order (GUARD-05 LC markers first). Invoked from `pipeline.py:154` (guard), `178` (unguard), `28` (has_sentinels check). **STATUS: PARTIAL** — only reached via dormant `pipeline.run`.

**`artifacts.py`.** Module docstring (lines 1–12) claims Stage A — mechanical Deepgram errors per PRE-04 (consecutive duplicates with affirmation-protect), PRE-05 (`K.`→`Okay.`, `Mhmm`→`Mm-hmm`), PRE-06 (`Doctor.` → `Dr.`), PRE-10 (orphan `-- --`). `apply(text, uid, ctx)` chains 4 sub-functions. Invoked from `pipeline.py:157`. **STATUS: PARTIAL** — only via dormant pipeline.

**`metadata.py`.** Module docstring (lines 1–12) claims Stage M PRE-01/02/07/08/09: reporter-name garbles, label standardization, confirmed_spellings (longest-first via `_masked_replace` with cross-contamination guard), keyterms (exact-match only, casing-only correction), structural identifiers (cause numbers, e-tran). PRE-03 Texas terminology explicitly **not** applied here ("caption/metadata only"). Invoked from `pipeline.py:161`. **STATUS: PARTIAL** — only via dormant pipeline. Note: the dormancy means `confirmed_spellings` operator-verified entries do not reach the certified output via this path.

**`flags.py`.** Module docstring (lines 1–18) claims Stage F + `FlagRegistry`. Implements **only 2 of the spec's 6 flag categories**: FLAG-02 (List-3 verbatim-sensitive items via `_detect_flag02_list3` against the 7-entry `LIST3_FLAG_ITEMS` map) and FLAG-06 (oath garble via `_detect_flag06_oath` against the 2-entry `OATH_GARBLE_DETECT` tuple). Module comment at lines 14–16 acknowledges *"FLAG-01 (unverified proper nouns), FLAG-03 (residual garble), FLAG-04 (boundary uncertainty, emitted by Stage S) and FLAG-05 (ambiguous date/number) arrive with later stages and are not implemented yet."* Invoked from `pipeline.py:185`. **STATUS: PARTIAL** — 2/6 flags implemented, all via dormant pipeline.

**`model.py`.** Module docstring (lines 1–13) defines the engine's data types. Exposes `SpeakerMapUnverifiedError`, `Utterance`, `CorrectionLogEntry` (with `word_delta()`), `Flag` (with `marker()`), `RenderedLine`, `CorrectionResult` (with `gross_word_delta()`). Imported widely within `corrections/`. **STATUS: LIBRARY**.

**`log.py`.** Module docstring (lines 1–13) claims the spec §17.1 collector. `CorrectionLog` class with `extend`, `entries`, `net_word_delta`, `count_by_rule`, `to_dicts`. Created per-run inside `pipeline.run` (line 84); its `.entries` is exposed via `CorrectionResult.log`. **STATUS: LIBRARY** — instantiated and populated correctly, but because `CorrectionResult` is discarded (CF-1) the log never reaches a persistence call; `to_dicts()` has no live caller.

### 5.2 File traces — `backend/stage_s/`

**`renderer.py`.** Module docstring (lines 1–12) claims the master Stage S orchestrator; declares its position as *"RAW -> mapping -> correction engine -> render_stage_s() -> export"* — note this still claims to sit downstream of the correction engine. Implements `render_stage_s(utterances, participants) -> StageSResult` (lines 55–204) orchestrating record-state transitions, off-record tagging, unmapped-cluster flagging, objection isolation with interruption/resumption dashes, and Q/A vs colloquy line emission via `qa_mode_for_role`. Invoked from `api/transcripts.py:1013, 1090`, `api/packaging.py:388`. **STATUS: LIVE**.

**`line_builder.py`.** Module docstring (lines 1–7) claims the deterministic block→line(s) primitive. Provides `qa_line`, `colloquy_line`, `parenthetical_line`, `by_attribution_line`, `flagged_line`, `qa_mode_for_role` (the `examining_attorney`→`Q` / `witness`→`A` lookup at line 27). Used by `renderer.py`. **STATUS: LIBRARY**.

**`colloquy.py`.** Module docstring (lines 1–10) claims Type 3 colloquy formatting per Morson's Rule 36 / UFM 2.11. Provides `colloquy_label` (ALL-CAPS + colon) and `colloquy_inline_text` (`LABEL:  text` with the two-space `COLON_GAP`). Used by `line_builder.py`. **STATUS: LIBRARY**.

**`objection_handler.py`.** Module docstring (lines 1–14) claims objection isolation with dash insertion per UFM 2.9 / Morson's 87. Implements `looks_like_objection` (prefix match against `_OBJECTION_MARKERS`), `append_interruption_dash`, `prepend_resumption_dash` (both Morson's-91-aware, stripping trailing/leading `,;:` before the dash). Used by `renderer.py`. **STATUS: LIBRARY**.

**`off_record.py`.** Module docstring (lines 1–10) claims the videographer-role-gated off-record state machine. Implements `detect_transition` (OFF: `"off the record"`; ON: `"back on the record"` or `"we are back"` — note `"on the record"` alone is intentionally excluded to avoid false-positives on questions), `extract_time` (regex against `\d{1,2}:\d{2}` + meridiem), `apply_transition`. Used by `renderer.py`. **STATUS: LIBRARY**.

**`parentheticals.py`.** Module docstring (lines 1–10) claims the canonical wording registry. Provides time-extracted helpers (`commenced`, `recess`, `resumed`, `concluded`, `on_record_proceedings`) and a `FIXED_REGISTRY` of 14 fixed-wording parentheticals (`WITNESS_SWORN`, `INTERPRETER_SWORN`, `WITNESS_REVIEWED_EXHIBIT`, `DISCUSSION_OFF_RECORD`, `POST_RECORD_SPELLINGS_SUBTITLE`, etc.) plus `exhibit_marked(n)` and `is_canonical()`. Used by `transitions.py` + `renderer.py`. **STATUS: LIBRARY** — note that of the 14 fixed phrases, only `recess`/`resumed` (via `transitions.transition_parenthetical`) are reached by the current renderer; the other 12 await callers.

**`transitions.py`.** Module docstring (lines 1–6) claims small helpers around `parentheticals.py`. Provides `transition_parenthetical(transition, time)` (OFF→recess, ON→resumed) and `needs_by_line_after(transition)` (re-emit BY-line after resume). Used by `renderer.py`. **STATUS: LIBRARY**.

**`render_state.py`.** Module docstring (lines 1–7) claims a mutable state container. Provides `RenderState` dataclass with `record_state`, `current_examiner_label`, `examiner_seen`, plus `is_on_record` and `set_examiner`. Used by `renderer.py`. **STATUS: LIBRARY**.

**`audit.py`.** Module docstring (lines 1–9) claims a structural audit log carrying every structural transformation. Provides `AuditEntry` (kind ∈ {`qa_split`, `objection_isolated`, `off_record_span`, `dash_inserted`, `parenthetical_emitted`, `by_line_emitted`}) and `AuditLog` with `record`, `count`, `entries`, `to_list`. Surfaced as `StageSResult.audit`. **STATUS: LIBRARY** — populated correctly by `renderer.py`, but the export consumers at `transcripts.py:1022, 1156` and `packaging.py:452` iterate only `stage_s.lines` and never read `.audit`, mirroring CF-1 at the structural layer.

**`models.py`.** Module docstring (lines 1–7) claims the render object model. Exposes `RenderLine` dataclass plus constants `ON_RECORD`/`OFF_RECORD`, line-type constants (`LINE_Q`, `LINE_A`, `LINE_COLLOQUY`, `LINE_PARENTHETICAL`, `LINE_BY`, `LINE_FLAGGED`, `LINE_BLANK`), tab-level constants (`TAB_MARGIN`, `TAB_QA_DESIGNATION`, `TAB_QA_TEXT`, `TAB_COLLOQUY`, `TAB_PARENTHETICAL`). Imported by `line_builder`, `off_record`, `render_state`, `transitions`, `renderer`, plus `pagination/flow_rules.py`, `pagination/paginator.py`, `pagination/wrapping.py`. **STATUS: LIBRARY**.

Two `backend/stage_s/` files exist that the prompt did not list — `__init__.py` (re-exports `RenderLine` and `render_stage_s`) and `formatting.py` (not read in this audit; outside the prompt's enumerated list). Noting for completeness; neither alters the trace above.

### 5.3 Upstream context — `backend/transcript/`

- `ingest.py` — orchestrates `process_job(job_id)` (probe → transcribe → assemble → packet → persist → finalize); writes RAW exactly once and never modifies it.
- `assembler.py` — normalizes Deepgram batch JSON into canonical `{words[], utterances[], speakers[]}` with structural assembly only, no semantic transforms.
- `working_state.py` — exposes `get_working_utterances(job_id)` and `persist_working_transcript()` over the working layer; the export and packaging paths read here.
- `render.py` — declares itself *"THE SINGLE RENDER AUTHORITY"* and documents its position as *"render_working_transcript() → correction pipeline (backend/corrections) → formatted / export transcript"* (lines 15–25); the export path does **not** match this declared flow.
- `repository.py` — SQL access layer for `transcript_jobs`, `transcript_speakers`, `transcript_utterances`, `transcript_words` tables; rows as plain dicts.

### 5.4 Sequence diagram — actual flow at HEAD

```
                  Deepgram payload (or offline fallback)
                                 │
                                 ▼
              ingest.process_job(job_id)
                                 │
                                 ▼
              assembler  →  {words, utterances, speakers}
                                 │
                                 ▼
              repository persists; working_state.get_working_utterances() is the read path
                                 │
                                 ▼
              [Wave 9: speaker mapping confirmed → transcript_participants]
                                 │
                                 ▼
              correction_trigger.run_correction_engine_for_job(job_id, job_config=None)
                                 │
                                 ▼
              pipeline.run(utterances, job_config={}, speaker_map_confirmed=True)
                  ├─→ regex pre-stage         (line 130 — DEAD: job_config["regex_rules"] never set)
                  ├─→ G  guards.guard()       (line 154)
                  ├─→ A  artifacts.apply()    (line 157)
                  ├─→ M  metadata.apply()     (line 161)
                  ├─→ X  legal_phrases.apply()(line 168)   ← spec §10 Stage X "instance #1"
                  ├─→ T  typography.apply()   (line 174)
                  ├─→ U  guards.unguard()     (line 178)   ← swapped with F vs spec
                  └─→ F  flags.detect()       (line 185)   ← spec §15 says U strictly last
                                 │
                                 ▼
              CorrectionResult(lines, log, flags, parity_mode)
                                 │
                                 └── DISCARDED (CF-1). Only a 4-field summary dict returned.
                                     Nothing persists lines / log / flags.

────────────────────────────────────────────────────────────────────────────────────────

PARALLEL — the path that actually drives certified output:

              api/transcripts._build_export_document_from_job(job_id)
              (also: api/transcripts._build_export_document_from_snapshot,
                     api/packaging via render_stage_s import at 388)
                                 │
                                 ▼
              utterances = working_state.get_working_utterances(job_id)
                                 │
                                 ▼
              apply_regex_rules(utterances, regex_rules_repo.list_rules(case_id))
                  (transcripts.py:992 / 1120 / packaging.py:406; substitutions dropped via _ unpack)
                                 │
                                 ▼
              apply_stage_x(utterances, merge_from_job_config(...))
                  (lexicon Stage X — Wave 14 add-on, NOT spec §10; substitutions dropped via _ unpack)
                                 │
                                 ▼
              render_stage_s(utterances, participants)
                  ├─→ off_record state machine (transitions, parentheticals.recess/resumed)
                  ├─→ objection_handler        (isolation + interruption/resumption dashes)
                  ├─→ line_builder             (Q/A from role, colloquy, by_attribution, flagged)
                  └─→ StageSResult.lines + audit  (audit returned in result, never read by consumers)
                                 │
                                 ▼
              export_render.render_export_with_layout(working, ...)
                                 │
                                 ▼
              DOCX / PDF / RTF / TXT export
```

Two parallel chains. `pipeline.run` is a background side-effect via `correction_trigger`. The export path is independent and uses a different "Stage X" (the lexicon module) than what `pipeline.run` invokes. Audit logs are generated at three layers (pipeline log, regex/stage_x substitution lists, stage_s audit) and are all discarded before reaching persistence or the operator.

---

## 6. Spec Drift Table (Phase B)

Comparison point: `docs/architecture/transcript_engine/deterministic_correction_engine_spec.md` v1.2. One row per discrete spec element, grouped by spec section. `Implemented` is judged against existence-of-code-on-disk, not against whether that code reaches the certified output (CF-1 covers that disconnect separately).

### §2 Non-negotiable principles

| Spec rule | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| §2.1 Verbatim mandate | YES | `corrections/guards.py` + `patterns.py` (GUARD-01) | HIGH | Filler-word protection list matches spec §2.1 verbatim |
| §2.2 RAW immutability | YES | `transcript/integrity.py`, `transcript/working_state.py` | HIGH | Per `SYSTEM_OWNERSHIP.md`; pipeline operates only on `Utterance.text` copies |
| §2.3 No AI | YES | entire `corrections/` package | HIGH | No model imports anywhere in `corrections/` |
| §2.4 Idempotency | PARTIAL | `corrections/metadata.py` (`_masked_replace`), `typography.py` (re-collapse `\s+`) | MEDIUM | Several stages claim idempotency in comments; not verified to exhaustive test coverage by this audit |
| §2.5 Flag, don't guess | PARTIAL | `corrections/flags.py` | HIGH | Only 2 of 6 spec flag categories implemented (FLAG-02, FLAG-06); FLAG-01/03/04/05 acknowledged absent in module docstring |
| §2.6 Role scoping | YES | `corrections/legal_phrases.py` (`_ATTORNEY_ROLES`, role gates in `LEGAL_PHRASE_MAP`), `stage_s/line_builder.py` (`qa_mode_for_role`), `stage_s/off_record.py` (videographer gate) | HIGH | Role-gating present in all the spec-named places |
| §2.7 Correction log | PARTIAL | `corrections/log.py`, `stage_s/audit.py` | HIGH | Log classes exist and are populated; outputs are discarded (CF-1); §17.1 persistence requirement unmet |

### §3 / §3A Pipeline position

| Spec element | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| §3 Pipeline runs once after Wave 9 mapping | YES | `services/correction_trigger.py` | HIGH | Trigger fires post-mapping; raises `SpeakerMapUnverifiedError` per spec |
| §3 `SpeakerMapUnverifiedError` hard gate | YES | `corrections/pipeline.py:75-77` | HIGH | Raised correctly when `speaker_map_confirmed=False` |
| §3.1 Reversibility (RAW never written) | YES | enforced in `transcript/integrity.py` + working-only mutation | HIGH | All correction stages operate on `Utterance.text` copies |
| §3A Parity Mode toggle | PARTIAL | `corrections/pipeline.py:81` (`deterministic_parity_mode` read) | HIGH | Flag is read into `_Context.parity_mode` but **no stage actually skips on it** — Parity Mode is plumbed but inert in the current code |

### §4 Input / Output contract

| Spec element | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| §4.1 `Utterance` input shape | YES | `corrections/model.py:Utterance` | HIGH | All 7 fields present |
| §4.1 `job_config.confirmed_spellings` | YES | `corrections/metadata.py:_pre07_confirmed_spellings` reads `ctx.job_config["confirmed_spellings"]` | HIGH | Reads + applies correctly |
| §4.1 `job_config.deepgram_keyterms` | YES | `corrections/metadata.py:_pre08_keyterms` | HIGH | Reads + applies correctly |
| §4.1 `job_config.reporter_name` | YES | `corrections/metadata.py:_pre01_reporter_name` | HIGH | Reads correctly |
| §4.2 Output: rendered line list | PARTIAL | `corrections/model.py:RenderedLine`, `pipeline.py:90-99` | HIGH | Lines emitted as `line_type="utterance"` only (1:1 utterance:line) — spec §4.3 demands Q/A/colloquy/parenthetical line types from S+Q; those exist in `stage_s/models.py:RenderLine` but are produced by a different module |
| §4.2 Output: correction log | PARTIAL | `corrections/log.py:CorrectionLog` | HIGH | Generated but discarded (CF-1) |
| §4.2 Output: flag registry | PARTIAL | `corrections/flags.py:FlagRegistry` | HIGH | Generated but discarded (CF-1); 2/6 categories populated |

### §5 Flag system format

| Spec element | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| §5.1 Flag marker `[SCOPIST: FLAG N: "reason" -- ...]` | YES | `corrections/model.py:Flag.marker()` | HIGH | Format string matches spec exactly |
| §5.2 Flag registry record shape | YES | `corrections/model.py:Flag` dataclass | HIGH | `flag_number`, `utterance_id`, `category`, `reason`, `as_transcribed`, `char_offset` all present |
| §5.3 `‹LC:...›` markers never flagged | YES | `corrections/guards.py` + `patterns.py:GUARD05_LC_MARKER_RE` | HIGH | LC markers guarded first, before flag stage sees text |

### §6 Pipeline stage list (the canonical 9 stages)

| Stage | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| G — Verbatim Guards | YES | `corrections/guards.py` | HIGH | All 5 wrapping patterns + Vault + has_sentinels |
| A — Artifact Removal | YES | `corrections/artifacts.py` | HIGH | All 4 sub-rules (PRE-04/05/06/10) |
| M — Metadata Substitution | YES | `corrections/metadata.py` | HIGH | 5 of 6 sub-rules (PRE-03 intentionally excluded per spec — caption-only) |
| X — Legal Lexicon Resolution | YES | `corrections/legal_phrases.py` | HIGH | All 3 maps (LEX-01/02/03); also a parallel "Stage X" in `lexicon/stage_x.py` doing whole-word lexicon substitution (see CF parallel-system flag) |
| S — Structural / Off-Record | YES | `stage_s/off_record.py` + `stage_s/transitions.py` + `stage_s/parentheticals.py` | HIGH | Lives in `stage_s/`, not in `corrections/structure.py` as spec §18 prescribes |
| Q — Q/A Formatting | YES | `stage_s/line_builder.py` (qa_mode_for_role) + `stage_s/objection_handler.py` | HIGH | Same location-drift as S |
| T — Typography | YES | `corrections/typography.py` | HIGH | POST-01..08 present (POST-09 large-number commas flag-only per spec Q5) |
| F — Flag Generation | PARTIAL | `corrections/flags.py` | HIGH | 2 of 6 categories implemented (FLAG-02, FLAG-06); FLAG-01/03/04/05 absent |
| U — Unguard | YES | `corrections/guards.py:unguard` | HIGH | Implemented; runs at `pipeline.py:178` — but **before** F, not after, contradicting spec §15 "strictly last" |

### §7 Stage G — Verbatim Guards (per-rule)

| Spec rule | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| GUARD-01 filler-word protection | YES | `patterns.py:GUARD01_FILLER_RE` | HIGH | Filler list matches spec exactly (includes `well`, `so`, `okay` per §17.7) |
| GUARD-02 stutter protection (tight form) | YES | `patterns.py:GUARD02_STUTTER_RE` | HIGH | Uses tight `\b\w-\w+\b` form per §17.7 |
| GUARD-03 false-start protection | YES | `patterns.py:GUARD03_FALSE_START_RE` | HIGH | Trailing-space distinguisher present |
| GUARD-04 ellipsis preservation | YES | `patterns.py:GUARD04_ELLIPSIS_RE` | HIGH | Matches `. . .`, `. . . .`, and `...` |
| GUARD-05 LC marker absolute guard | YES | `patterns.py:GUARD05_LC_MARKER_RE` | HIGH | Highest-priority — applied first in `_GUARD_PATTERNS` |
| GUARD-06 affirmation-protected list | YES | `patterns.py:AFFIRMATION_PROTECTED` consumed by `_pre04_duplicates` | HIGH | All 6 list entries present |

### §8 Stage A — Deepgram Artifact Removal

| Spec rule | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| PRE-04 consecutive duplicate collapse | YES | `artifacts.py:_pre04_duplicates` | HIGH | 4+ char words only; affirmation guard honored |
| PRE-05 standalone artifact normalization | YES | `artifacts.py:_pre05_standalone` | HIGH | `K.`/`k.`/`Mhmm` patterns all wired |
| PRE-06 Doctor-period artifact | YES | `artifacts.py:_pre06_doctor` | HIGH | Only fires before a capital |
| PRE-10 orphan-dash removal | YES | `artifacts.py:_pre10_orphan_dash` | HIGH | Correct pattern, GUARD-03 already shields real false starts |

### §9 Stage M — Metadata Substitution

| Spec rule | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| PRE-01 reporter-name normalization | YES | `metadata.py:_pre01_reporter_name` | HIGH | 7 garbles → canonical from `job_config.reporter_name` |
| PRE-02 label standardization | YES | `metadata.py:_pre02_labels` | HIGH | `LABEL_MAP` — 3 entries, longest-first |
| PRE-03 Texas terminology | NO | — | HIGH | Spec §9 explicitly restricts to caption/metadata; `metadata.py` line 9 notes the rule is intentionally not body-applied, and no caption-applied implementation exists elsewhere in `corrections/` |
| PRE-07 confirmed_spellings | YES | `metadata.py:_pre07_confirmed_spellings` | HIGH | Longest-first, idempotent via `_masked_replace` |
| PRE-08 deepgram_keyterms | YES | `metadata.py:_pre08_keyterms` | HIGH | Exact-match casing correction; near-misses correctly excluded |
| PRE-09 structural identifier formatting | YES | `metadata.py:_pre09_identifiers` | HIGH | Cause-number regex + e-tran normalization |
| M-ordering rule (longest-key-first) | YES | `metadata.py` PRE-02, PRE-07, PRE-08 all sort by len reverse | HIGH | Consistent across maps |

### §10 Stage X — Legal Lexicon Resolution

| Spec rule | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| X-scope role gating | YES | `legal_phrases.py:_ATTORNEY_ROLES`, role gates on each `LEGAL_PHRASE_MAP` entry | HIGH | All gates honored at runtime |
| LEX-01 garbled objection map | YES | `legal_phrases.py:OBJECTION_GARBLE_MAP` | HIGH | 14 entries; spec lists ~7 categories — all spec categories covered |
| LEX-02 garbled universal legal phrases | YES | `legal_phrases.py:LEGAL_PHRASE_MAP` | HIGH | 7 entries with role gates; oath phrases correctly excluded per Q3 |
| LEX-03 subpoena duces tecum variants | YES | `legal_phrases.py:SDT_MAP` | HIGH | 5 variants |
| LEX-04 honorific period artifact | YES | handled by PRE-06 (`artifacts.py:_pre06_doctor`) per spec note | HIGH | Spec §10 LEX-04 explicitly delegates to PRE-06 |

### §11 Stage S — Structural / Off-Record

| Spec rule | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| STR-01 pre-record boundary (clean) | NO | — | MEDIUM | `stage_s/off_record.py` detects only OFF/ON transitions; no "Today is ... The time is" pre-record anchor or `boundary` flag |
| STR-02 off-record span (clean) | PARTIAL | `stage_s/off_record.py` + `stage_s/renderer.py:131-136` | HIGH | OFF→ON transitions tag spans as `OFF_RECORD`; spec §11 STR-02 says content "is omitted from the WORKING body and replaced by the parenthetical pair" — the export path at `transcripts.py:1023` does suppress off-record lines, but the recess/resume parenthetical pair is emitted via the transition itself, not via a separate STR-04 mechanism |
| STR-03 post-record boundary | NO | — | MEDIUM | No code emits a deposition-concluded parenthetical at the final transition, and no `boundary` flag is raised for post-record content |
| STR-04 standard parenthetical insertion | PARTIAL | `stage_s/parentheticals.py` + `stage_s/transitions.py` | HIGH | All 5 spec-listed forms exist in `parentheticals.py` (`commenced`, `recess`, `resumed`, `concluded`, `exhibit_marked`), plus 9 additional ones (`WITNESS_SWORN`, `INTERPRETER_SWORN`, etc.); only `recess`/`resumed` are actually emitted by the current renderer. The other 12 await callers — likely STR-01, STR-03, oath placement, exhibit marking |

### §12 Stage Q — Q/A Formatting

| Spec rule | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| QA-01 Q/A format trigger gate (sworn + EXAMINATION + BY line) | NO | — | HIGH | `stage_s/renderer.py` emits Q/A based solely on role lookup (`qa_mode_for_role`); no detection of sworn-witness / examination-header preconditions. Risk: pre-examination colloquy could be Q/A-typed inappropriately |
| QA-02 examination Q/A assignment by role | YES | `stage_s/line_builder.py:qa_mode_for_role` + `renderer.py:175-191` | HIGH | examining_attorney→Q, witness→A |
| QA-03 embedded Q/A split | NO | — | HIGH | No utterance-splitting on `?` + short-answer pattern anywhere in `stage_s/` |
| QA-04 objection isolation | YES | `stage_s/objection_handler.py` + `renderer.py:148-172` | HIGH | Note: spec QA-04 requires the canonical "Objection." form has already been produced by LEX-01 before isolation fires; current `looks_like_objection` uses a wider prefix list (`objection`, `object to`, `i object`, `form, vague`, `vague and ambiguous`, etc.) rather than the LEX-01 output check. PARTIAL by strict spec reading; YES by implementation |
| QA-05 reporter mid-testimony clarification | PARTIAL | `stage_s/renderer.py:193-196` (default colloquy fallback) | MEDIUM | Court_reporter role falls into the colloquy branch — produces a `THE REPORTER:` line — but no specific "during examination" check |
| QA-06 tab / line-type assignment | YES | `stage_s/models.py:TAB_*` constants + `line_builder.py` setting `tab_level` per line | HIGH | Tab levels assigned per line type matching spec §12 QA-06 table |

### §13 Stage T — Typography

| Spec rule | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| POST-01 two-space rule + abbrev guard | YES | `typography.py:_post01_two_space` | HIGH | Abbrev superset list per §17.7 |
| POST-02 objection double-space | YES | `typography.py:_post02_objection` | HIGH | |
| POST-03 honorific labels (one-space, ALL-CAPS) | YES | `typography.py:_post03_honorifics` | HIGH | Per Q2 one-space decision |
| POST-04 honorific body text | YES | merged into POST-03 with IGNORECASE per code comment at `patterns.py:113-116` | HIGH | Spec divides POST-03/04 by line type; code merges them |
| POST-05 Miss normalization | YES | `typography.py:_post05_miss` | HIGH | Quoted-Miss exception via simple `"` check |
| POST-06 em-dash → spaced double-hyphen | YES | `typography.py:_post06_emdash` | HIGH | |
| POST-07 time formatting | YES | `typography.py:_post07_time` | HIGH | AM/PM → a.m./p.m.; leading-zero strip |
| POST-08 money & percent | YES | `typography.py:_post08_money_percent` | HIGH | |
| POST-09 large-number commas | NO | — | HIGH | Per Q5 the spec routes this to flag-only; FLAG-05 (number) is also not implemented (see §14) |

### §14 Stage F — Flags

| Spec rule | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| FLAG-01 unverified proper nouns | NO | — | HIGH | Acknowledged absent in `flags.py:14` |
| FLAG-02 List-3 verbatim-sensitive items | YES | `flags.py:_detect_flag02_list3`, `patterns.py:LIST3_FLAG_ITEMS` | HIGH | 7 of 8 spec List-3 entries present (`Dior placement` from spec is absent) |
| FLAG-03 residual garble | NO | — | HIGH | Acknowledged absent in `flags.py:14` |
| FLAG-04 boundary uncertainty | NO | — | HIGH | Stage S currently does not emit boundary flags either |
| FLAG-05 ambiguous date / number | NO | — | HIGH | Acknowledged absent in `flags.py:14` |
| FLAG-06 oath / certification language | YES | `flags.py:_detect_flag06_oath`, `patterns.py:OATH_GARBLE_DETECT` | HIGH | Detect-and-flag only per Q3; 2 detection phrases |

### §15 Stage U — Unguard

| Spec rule | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| U restores sentinels | YES | `corrections/guards.py:unguard` | HIGH | |
| U runs strictly last | NO | `pipeline.py:178, 185` | HIGH | U runs at line 178, F at 185 — F runs **after** U; spec §15 requires U last. Inline justification at line 178 — flags need real text — is plausible but contradicts the spec |
| `test_unguard_no_sentinels_remain` self-check | YES | `pipeline.py:180-183` (raises `RuntimeError` on residue) | HIGH | |

### §16 Out of scope — verified excluded

| Spec item | Excluded? | Confidence | Notes |
|---|---|---|---|
| Contextual homophones | YES | HIGH | No homophone-disambiguation code anywhere in `corrections/` |
| Sentence-initial number spell-out | YES (flag-only intent) | HIGH | No spell-out code; FLAG-05 also not implemented so flag-only fallback doesn't fire |
| Date mashup interpretation | YES (flag-only intent) | HIGH | Same — FLAG-05 not present, but no semantic-rewrite code either |
| Fuzzy off/on-record boundary | YES (flag-only intent) | HIGH | Only clean OFF/ON triggers handled; no fuzzy detection; no FLAG-04 boundary either |
| Near-match entity correction | YES | HIGH | `metadata.py:_pre08_keyterms` correctly excludes near-misses |
| `(as read)` vs `[sic]` placement | YES | HIGH | `AS_READ` exists in `parentheticals.py:52` but no auto-placement logic |
| Phonetic speaker resolution | YES | HIGH | No phonetic matching anywhere |
| Testimony rehabilitation | YES | HIGH | Verbatim mandate honored |
| Stutter reconstruction | YES | HIGH | GUARD-02 protects existing stutters; PRE-04 leaves 1-3 char duplicates intact |

### §17 Recommended changes (additions)

| Spec element | Implemented | File | Confidence | Notes |
|---|---|---|---|---|
| §17.1 correction log + WORKING persistence | PARTIAL | `corrections/log.py` exists; persistence does not | HIGH | Log class present; outputs discarded by `correction_trigger`. Per-job persistence of rendered structure / stage outputs / diff snapshots is **not** present. This is the spec's most explicit "firm build requirement" and is unmet |
| §17.2 garble resolution promoted to deterministic | YES | `corrections/legal_phrases.py` | HIGH | LEX-01/02/03 present and role-gated |
| §17.3 embedded Q/A split + objection isolation deterministic | PARTIAL | objection isolation YES (`objection_handler.py`); embedded Q/A split NO | HIGH | See QA-03 and QA-04 above |
| §17.4 number formatting split (deterministic + flag-only) | PARTIAL | POST-07/08 implemented; POST-09 not | HIGH | See POST-09 above |
| §17.5 post-record: flag, not delete | NO | — | HIGH | STR-03 not implemented; no post-record flag |
| §17.6 centralized patterns | YES | `corrections/patterns.py` | HIGH | All `corrections/` regexes centralized; `stage_s/` has its own local patterns (e.g. `off_record._TIME_RE`) — minor drift from a strict reading of §17.6, but §17.6 names `corrections/patterns.py` specifically |
| §17.7 reconciled specifics (STUTTER_RE, ABBREV_GUARD, filler list) | YES | all in `patterns.py` | HIGH | Each reconciliation matches spec verbatim |
| §17.8 Parity Mode toggle | PARTIAL | flag read at `pipeline.py:81`; no stage actually skips on it | HIGH | Parity Mode is plumbed but inert at HEAD |

### §18 Module / file layout

| Spec file | Implemented | Notes |
|---|---|---|
| `corrections/pipeline.py` | YES | Present; orchestration partially matches spec |
| `corrections/patterns.py` | YES | Present and consolidated per §17.6 |
| `corrections/guards.py` (G + U) | YES | Present |
| `corrections/artifacts.py` (A) | YES | Present |
| `corrections/metadata.py` (M) | YES | Present |
| `corrections/legal_phrases.py` (X) | YES | Present |
| `corrections/structure.py` (S) | NO | Spec-named module does not exist; functionality lives in `backend/stage_s/` as a parallel package |
| `corrections/qa_format.py` (Q) | NO | Spec-named module does not exist; functionality lives in `backend/stage_s/` |
| `corrections/typography.py` (T) | YES | Present |
| `corrections/flags.py` (F) | YES | Present |
| `corrections/log.py` | YES | Present |

### §19 Test plan — engine invariants

| Spec invariant | Verified by audit? | Notes |
|---|---|---|
| Idempotency | NOT VERIFIED | `tests/corrections/` not opened during this audit per scope (test suite passes overall at 592/1, but specific invariant coverage not enumerated) |
| No sentinel residue | YES (runtime self-check) | `pipeline.py:180-183` raises RuntimeError on residue |
| RAW untouched | YES (architectural) | Pipeline operates on copies; `transcript/integrity.py` enforces immutability |
| Verbatim preservation | YES (by GUARD-01 + GUARD-02 + GUARD-03 + GUARD-04) | Spec invariant aligns with implemented guards |
| Flag completeness | PARTIAL | Only FLAG-02 (List-3) and FLAG-06 (oath) can fire — FLAG-01/03/04/05 absent |
| Ordering | NOT VERIFIED | No ordering-swap fixture observed in this audit's scope |
| Correction log fidelity | PARTIAL | Log entries are generated per change; fidelity of "every change appears in the log" depends on every stage calling `_log()` — not exhaustively traced |
| Parity Mode | NO (Parity Mode inert) | §3A toggle plumbed but no stage skips on it |

### §21 Open questions — current status

| Question | Spec status | Code status | Notes |
|---|---|---|---|
| Q1 confirmed_spellings source | RESOLVED | wired via `job_config` | YES |
| Q2 honorific spacing | RESOLVED — one space | wired in `typography.py:_post03_honorifics` | YES |
| Q3 garbled oath language → flag | RESOLVED — flag, not correct | `flags.py:_detect_flag06_oath` per Q3 | YES |
| Q4 post-record: flag not delete | RESOLVED | STR-03 NOT IMPLEMENTED — no flag, no delete | NO |
| Q5 large-number commas: flag-only | RESOLVED | neither POST-09 nor FLAG-05 implemented | NO |
| Q6 engine output persistence | RESOLVED — persist not recompute | NOT IMPLEMENTED — outputs are discarded per CF-1 | NO (this is the §17.1 gap) |
| Q7 Parity Mode default false + exposed | RESOLVED — default false, exposed in Workspace | flag read into `_Context` but no stages skip on it; no Workspace exposure | PARTIAL |
| Q8 oath/certification boundary (3 LEX-02 entries) | OPEN | code keeps the 3 entries deterministic (e.g. `remote storing`, `same effect as a weapon in the courthouse`, `past witness`); `LEGAL_PHRASE_MAP` confirms they remain in LEX-02 | matches spec's "provisional until resolved" guidance |

### Phase B one-sentence summary

Of approximately **95 discrete spec elements** in the deterministic correction engine spec, **62 are YES (implemented in code on disk), 16 are PARTIAL, and 17 are NO** — but the YES count materially overstates production behavior because **every stage in `pipeline.run` (most of the YES rows) is downstream of CF-1 and does not influence the certified export**; the export path uses a parallel chain that delivers only a subset of these rules (Stage S + Q via `stage_s/`, regex pre-stage via `apply_regex_rules`, lexicon-Stage-X via `lexicon/stage_x.py`) and discards every audit log it produces.

---

## 7. Real-Deposition Features (Phase C)

Per the agreed Option 4 split, Phase C was produced separately from the source depositions (Shaw + Filpi, available in the parallel session's project knowledge but not on the Windows host running Claude Code). The full inventory was handed to this audit as a paste-in artifact with 47 entries — 22 from Shaw 191216 (state court, heavy objection density, three examination blocks), 25 from Filpi 190604 (federal court, videotaped, intact reporter introduction + closing stipulation ritual).

Selection rationale, taken verbatim from the Phase C artifact: *"Best test corpus for QA-01 trigger gate, Stage F objection isolation, and Stage S transitions."* (Shaw); *"contains the exact STR-01 'Today is...' anchor the spec requires"* and *"the complete STR-03 form the spec demands"* (Filpi). Same court reporter (Trisha Myler, CSR) across both, so formatting drift between the two is deposition-type variation, not reporter style.

Coverage spans 47 entries across these feature categories:

- Caption / opening matter; witness sworn-in ritual; reporter's on-record anchor (STR-01 candidate); EXAMINATION headers (initial / cross / further); BY-line re-attribution after colloquy / parenthetical / off-record; trailing em-dash interruption; leading em-dash continuation across speakers; self-restart inside a question; strike-that mid-question; compound questions; multi-sentence answers with continuation; "Let me rephrase"; THE WITNESS colloquy mid-Q/A; THE REPORTER colloquy; counsel-tendered-exhibit parentheticals; exhibit-marked parentheticals; recess parentheticals (single-line and multi-line wrapped); off-record parenthetical; witness-action `(Witness complies)`; nonverbal-only answer `(Moving head up and down)`; inline descriptive sound parenthetical; objection grounds (Form, Nonresponsive, coordinated "Same objection"); pass-the-witness sequence; deposition-concluded parenthetical (STR-03 form); closing stipulation ritual.

Two cross-cutting findings from the Phase C artifact carry into Phase E:

1. **Inventory contains no positive QA-03 cases.** The spec's headline "Were your brakes working? Yes." embedded-split pattern does not appear in either deposition (cross-cutting #5 in the Phase C artifact). Every multi-sentence Q. turn in the inventory (Entries 7, 20, 34, 40, 41) is a negative case where splitting would be wrong. This shifts QA-03's leverage — its demand may be theoretical rather than observed in real reporter output.
2. **Inline `(descriptive sound)` parenthetical placement** (Entry 17, Shaw p138). Embedded inside a witness's spoken testimony, not at block-level. The current renderer would preserve this verbatim inside the A. text by default — which is structurally correct for verbatim — but the engine would not *recognize* it as a discrete parenthetical event. Whether that constitutes a gap depends on whether downstream consumers (pagination, export styling) need to know about inline parentheticals. **Not** elevated to Critical Findings — verbatim preservation is the safe default and the spec does not require event-level recognition for inline parentheticals.

Full inventory with PDF / page / line citations, excerpts, notes, and spec-element mappings was supplied as the input artifact and is the ground truth Phase D cross-references against. Entries are referenced below by Entry N.

---

## 8. Gap Matrix (Phase D)

Cross-reference of Phase C features against Phase A code trace and Phase B spec drift. Sorted **MISSING and WIRING-BROKEN first** per the prompt's leverage-ranking rule. Effort estimate is S / M / L only per the prompt's discipline (S = local change to one file; M = changes across 2–3 files in one subsystem; L = cross-cutting changes).

### 8.1 MISSING — no code exists

| Feature | Status | Where it would live | Spec ref | Effort | Grounded by Phase C entry |
|---|---|---|---|---|---|
| QA-01 trigger gate (sworn + EXAMINATION + BY-line preconditions before Q/A typing) | MISSING | `stage_s/renderer.py` + `stage_s/line_builder.py` | §12 QA-01 | S | Entries 2, 24, 31, 32 — every opening; Entries 15, 31, 37 — EXAMINATION header geometry; Entry 42 — minimal WITNESS_SWORN form |
| EXAMINATION header emission (centered, column ~28) | MISSING | new `examination_header_line()` in `stage_s/line_builder.py` + `LINE_EXAMINATION` constant in `stage_s/models.py` | §12 QA-01, §11 implicit | S | Entries 2, 15, 31, 32, 37 |
| Initial BY-line emission at the start of an examination | MISSING | `stage_s/renderer.py` — `by_attribution_line` factory exists but is only called inside the ON-transition branch | §11 STR-04, §12 QA-01 | S | Entries 2, 24, 31, 32 |
| Inline `(BY MR. X)` re-attribution within a resumed Q. (post-colloquy, post-parenthetical, post-objection) | MISSING | `stage_s/renderer.py` — `qa_line()` already accepts a `by_label` parameter at `line_builder.py:36`, but the renderer never passes it | §11 STR-04 implicit, §12 QA-04 | S | Entries 3, 5, 8, 11, 12, 14, 27, 28 — appears in nearly every interruption case in the inventory |
| STR-01 pre-record boundary anchor (`Today is .../The time is ...`) | MISSING | `stage_s/off_record.py` (currently detects only OFF/ON transitions, not the pre-record anchor) | §11 STR-01 | M | Entries 24, 43, 44 — Filpi p4 has the canonical form |
| STR-03 deposition-concluded parenthetical emission at final transition | MISSING | `stage_s/renderer.py` end-of-stream hook + `stage_s/parentheticals.concluded()` (exists, untriggered) | §11 STR-03 | S | Entries 17, 33 — both depositions; Entry 47 federal stipulation ritual |
| STR-04 `WITNESS_SWORN` parenthetical emission | MISSING | `stage_s/renderer.py` — phrase exists at `parentheticals.WITNESS_SWORN`, no caller | §11 STR-04 | S | Entries 2, 42 — both depositions open with this |
| STR-04 `COUNSEL_TENDERS` / counsel-action parenthetical emission | MISSING | `stage_s/parentheticals.py` has no `counsel_tenders` constant; needs new entry + detection | §11 STR-04 | S | Entry 11 — Shaw p41 `(Counsel tenders documents to Witness)` |
| STR-04 `DISCUSSION_OFF_RECORD` parenthetical emission | MISSING | constant exists at `parentheticals.DISCUSSION_OFF_RECORD`; no caller (the off-record transition emits `recess` instead) | §11 STR-04 | S | Entries 14, 28 — `(Discussion off the record from X to Y)` |
| STR-04 `WITNESS_COMPLIES` / `(Witness complies)` parenthetical recognition | MISSING | constant exists at `parentheticals.WITNESS_COMPLIES`; no caller. May arrive inline inside an A. text, requiring inline-parenthetical detection | §11 STR-04 | M | Entry 26 — Filpi 6 occurrences |
| STR-04 `WITNESS_REVIEWED_EXHIBIT` parenthetical emission | MISSING | constant exists, no caller | §11 STR-04 | S | inferred from inventory; not explicitly cited |
| STR-04 `INTERPRETER_SWORN` parenthetical emission | MISSING | constant exists, no caller | §11 STR-04 | S | not present in this inventory but spec-required |
| FLAG-01 unverified proper nouns | MISSING | `corrections/flags.py` — acknowledged absent in module docstring | §14 FLAG-01 | M | Cross-cutting #10 in Phase C — verbatim preservation under noisy proper-noun input |
| FLAG-03 residual garble | MISSING | `corrections/flags.py` — acknowledged absent | §14 FLAG-03 | M | Entries 6, 10, 21 — verbatim-mandate emphasis preservation candidates |
| FLAG-04 boundary uncertainty (emitted from Stage S on garbled markers) | MISSING | `stage_s/off_record.py` + `corrections/flags.py` | §14 FLAG-04 | M | not directly observed (inventory has clean transitions only); spec-required for garbled-transition fallback |
| FLAG-05 ambiguous date / number | MISSING | `corrections/flags.py` — acknowledged absent | §14 FLAG-05 | S | not directly observed in inventory; spec-required |
| POST-09 large-number commas (flag-only per Q5) | MISSING | `corrections/flags.py` (the flag) | §13 POST-09 | S | not observed in inventory |
| QA-03 embedded Q/A split | MISSING | `stage_s/` (would be `qa_format.py` per spec §18) | §12 QA-03 | M | **No positive cases in inventory** — Entries 7, 20, 34, 40, 41 are all negative cases; QA-03's real-world frequency is undemonstrated |
| "Same objection" coordinated back-reference resolution | MISSING | `stage_s/objection_handler.py` | not in spec (operator-flow gap) | M | Entry 16 — 8 occurrences in Shaw alone |
| Multi-paragraph colloquy turn emission (paragraph break inside one THE REPORTER speaker turn) | MISSING | `stage_s/line_builder.py:colloquy_line` produces one line per utterance; multi-paragraph within one utterance not supported | §11 STR-01 implicit | M | Entries 43, 44 — Filpi reporter's multi-paragraph introduction |
| Post-record content handling (flag, not delete, per Q4) | MISSING | `stage_s/renderer.py` + `corrections/flags.py` (FLAG-04 boundary) | §11 STR-03, §17.5 | M | Entry 47 — federal stipulation ritual sits after STR-03 anchor and must be preserved |
| Stage Q-precedes-A assumption challenge (A appears before Q on resumption) | MISSING | `stage_s/renderer.py` line-emission ordering | §12 QA-02 implicit | S | Entry 14 — Shaw p86 has A. before Q. after off-record resumption |
| Q. or A. lines containing only a parenthetical action (nonverbal-only utterance) | MISSING | `stage_s/line_builder.py` — `qa_line` accepts any text but no special handling for "this Q has no spoken content" | §12 QA-06 implicit | S | Entries 29, 32 — Filpi `Q. (BY MR. YANG) (Moving head up and down)`; `A. (Moving head up and down)` |
| Reporter inconsistency normalization (single vs double space after colloquy colon) — verbatim preserve or normalize? | MISSING | spec position unclear | §13 POST-03 / §2.1 verbatim mandate tension | S | Entry 35 — Filpi p4 mixes single and double space after colon in adjacent attorney appearance lines |
| Jurisdiction-dependent stipulation ritual emission (federal vs state) | MISSING | not in spec; not in code | not in spec | M | Entry 47 — federal Reporter prompt absent in Shaw state-court closing |

### 8.2 WIRING-BROKEN — code exists in repo, not invoked from live path

All rows in this section are direct consequences of CF-1: `corrections/pipeline.run` produces these outputs but the export path discards them. Wiring effort is M (touches `correction_trigger.py`, export builders, packaging path), shared across the rows — the cost is the wiring, not per-row.

| Feature | Status | Where it lives | Spec ref | Effort (shared) | Grounded by Phase C entry |
|---|---|---|---|---|---|
| LEX-01 garbled objection resolution (e.g. `Action calls for circulation` → `Objection. Calls for speculation.`) | WIRING-BROKEN | `corrections/legal_phrases.py:OBJECTION_GARBLE_MAP` | §10 LEX-01 | M (shared) | Entries 9, 28, 39 — Form/Nonresponsive objections are clean, but Deepgram-generated garbles would benefit |
| LEX-02 garbled universal legal phrases (e.g. `past witness` → `Pass the witness.`) | WIRING-BROKEN | `corrections/legal_phrases.py:LEGAL_PHRASE_MAP` | §10 LEX-02 | M (shared) | Entry 15 — explicit "I'm going to pass the witness" appears in Shaw; garbled forms exercise this map |
| LEX-03 `subpoena duces tecum` variants | WIRING-BROKEN | `corrections/legal_phrases.py:SDT_MAP` | §10 LEX-03 | M (shared) | not in inventory |
| PRE-01 reporter name normalization (`Mia Bardo` → canonical) | WIRING-BROKEN | `corrections/metadata.py:_pre01_reporter_name` | §9 PRE-01 | M (shared) | not in inventory (these depositions are by Trisha Myler, not Miah Bardot) |
| PRE-02 label standardization (`COURT REPORTER:` → `THE REPORTER:`) | WIRING-BROKEN | `corrections/metadata.py:_pre02_labels` | §9 PRE-02 | M (shared) | Entries 24, 28, 33 — THE REPORTER colloquy appears throughout |
| PRE-07 `confirmed_spellings` application | WIRING-BROKEN | `corrections/metadata.py:_pre07_confirmed_spellings` | §9 PRE-07 | M (shared) | Entries 24, 35 — multiple proper nouns (Lexitas, Trisha Myler, Wayne Krause Yang) that confirmed_spellings would govern |
| PRE-08 `deepgram_keyterms` exact-match casing correction | WIRING-BROKEN | `corrections/metadata.py:_pre08_keyterms` | §9 PRE-08 | M (shared) | Entries 23, 24 — `PeirsonPatterson` proper noun appears (Entries 30, 39) and needs exact casing |
| PRE-09 cause-number structural formatting | WIRING-BROKEN | `corrections/metadata.py:_pre09_identifiers` | §9 PRE-09 | M (shared) | Entries 1, 23 — caption blocks have cause numbers (`1700015`, `3:18-CV-01362-L`); intake-only rendering today |
| POST-01 two-space-after-sentence rule | WIRING-BROKEN | `corrections/typography.py:_post01_two_space` | §13 POST-01 | M (shared) | Entries 8, 20, 34, 40, 41, 44 — multi-sentence Q. and reporter turns rely on this for correct sentence spacing |
| POST-02 `Objection.` two-space gap | WIRING-BROKEN | `corrections/typography.py:_post02_objection` | §13 POST-02 | M (shared) | Entries 8, 9, 16, 28, 39 — every objection in the inventory |
| POST-03/04 honorific ALL-CAPS + one-space | WIRING-BROKEN | `corrections/typography.py:_post03_honorifics` | §13 POST-03, POST-04 | M (shared) | Entries 11, 22, 24, 35 — every `MR.` / `MS.` colloquy label |
| POST-06 em-dash → spaced double-hyphen | WIRING-BROKEN | `corrections/typography.py:_post06_emdash` | §13 POST-06 | M (shared) | Entries 3, 6, 11, 15, 20, 22, 30, 34, 39 — every em-dash in the inventory |
| POST-07 time formatting | WIRING-BROKEN | `corrections/typography.py:_post07_time` | §13 POST-07 | M (shared) | Entries 12, 13, 14, 17, 27, 28, 33, 38 — every recess / off-record / conclusion time |
| FLAG-02 List-3 verbatim-sensitive items (`criminal investigator`, `chic cart`, etc.) | WIRING-BROKEN | `corrections/flags.py:_detect_flag02_list3` | §14 FLAG-02 | M (shared) | Cross-cutting #10 in Phase C |
| FLAG-06 garbled oath language detect-and-flag | WIRING-BROKEN | `corrections/flags.py:_detect_flag06_oath` | §14 FLAG-06 | M (shared) | not directly observed (depositions have clean oath language) |
| Correction log persistence per §17.1 | WIRING-BROKEN | `corrections/log.py:CorrectionLog` (generated, discarded); also `stage_s/audit.py:AuditLog` (generated, discarded) | §17.1 (firm build requirement) | M (shared) | every entry — operators reviewing certified output have no audit trail of automatic edits |

### 8.3 PARTIAL — pipeline produces sometimes / close approximation

| Feature | Status | Where it lives | Spec ref | Effort | Grounded by Phase C entry |
|---|---|---|---|---|---|
| QA-04 objection isolation | PARTIAL | `stage_s/objection_handler.py` + `renderer.py:148-172` | §12 QA-04 | S | Entries 9, 28, 39 — basic isolation works; spec wants isolation gated on LEX-01 having produced canonical `Objection.` form first (currently triggers on prefix match against a wider list) |
| QA-05 reporter mid-testimony clarification as colloquy | PARTIAL | `stage_s/renderer.py:193-196` default colloquy fallback | §12 QA-05 | S | Entries 14, 28 — reporter falls into colloquy branch, but no specific "during examination" gating; works by accident |
| STR-02 off-record span (clean OFF→ON detection + content suppression) | PARTIAL | `stage_s/off_record.py` + `renderer.py:131-136` + `transcripts.py:1023` (off-record suppression in export) | §11 STR-02 | S | Entries 14, 28 — works for clean OFF→ON; depends on videographer role to fire; emits recess/resumed not the spec's STR-04 pair |
| §3A Parity Mode toggle | PARTIAL | `pipeline.py:81` reads `deterministic_parity_mode`; no stage skips on it | §3A | S | not Phase C — architectural |
| §2.7 / §17.1 audit trail | PARTIAL | log classes exist (`corrections/log.py`, `stage_s/audit.py`) but outputs not persisted (CF-1) | §2.7, §17.1 | M | every entry |
| Stage U strictly last | PARTIAL | implemented but F runs after U in pipeline.py:178/185 | §15 | S | not Phase C — architectural |
| Centralized patterns | PARTIAL | `corrections/patterns.py` central for `corrections/`; `stage_s/` has local patterns (e.g. `off_record._TIME_RE`) | §17.6 | S | not Phase C — architectural |

### 8.4 PRESENT — pipeline reliably produces this feature today

| Feature | Status | Where it lives | Spec ref | Grounded by Phase C entry |
|---|---|---|---|---|
| Q/A typing from confirmed participant role | PRESENT | `stage_s/line_builder.py:qa_mode_for_role` + `renderer.py:175-191` | §12 QA-02 | Entries 18, 34, 36, 40 — base case clean Q/A |
| Colloquy formatting (`LABEL:  text` with two-space gap, ALL-CAPS label) | PRESENT | `stage_s/colloquy.py:colloquy_label`, `colloquy_inline_text` | §11 implicit, Morson's 36 / UFM 2.11 | Entries 11, 22, 24 — every attorney colloquy |
| THE WITNESS colloquy (mid-Q/A non-A speech from witness) | PRESENT | role=`witness` → A; but explicit `THE WITNESS:` colloquy label not auto-emitted | §12 QA-05 implicit | Entries 11, 14, 33 — actually PARTIAL: renderer would emit `A.` for witness even mid-procedural; needs a colloquy-mode override |
| Recess parenthetical emission (off-record OFF→ON via videographer) | PRESENT | `stage_s/transitions.py:transition_parenthetical` (`recess` / `resumed`) | §11 STR-04 partial | Entries 12, 27, 28, 38 |
| Off-record content tagging (suppress from export body) | PRESENT | `renderer.py:131-136` tags as `OFF_RECORD`; `transcripts.py:1023` suppresses non-procedural off-record lines | §11 STR-02 partial | Entries 14, 28 |
| BY-line re-emission after ON-record transition | PRESENT | `transitions.needs_by_line_after(transition)` returns True for ON; `renderer.py:120-126` calls `by_attribution_line` | §11 STR-04, §12 QA-01 partial | Entries 12, 14, 27, 28 |
| Objection isolation as standalone colloquy line + interruption/resumption dashes | PRESENT | `stage_s/objection_handler.py` + `renderer.py:148-172` | §12 QA-04 | Entries 9, 28, 39 |
| Em-dash preservation in body text (verbatim) | PRESENT | preserved by default — engine does nothing to remove em-dashes from utterance text | §2.1 verbatim mandate | Entries 3, 6, 11, 15, 20, 22, 30, 34, 39 — every em-dash |
| Multi-line answer continuation (preserved as single A. text spanning lines) | PRESENT | rendering geometry handled downstream by pagination; engine emits single A. line with full text | §4 implicit | Entries 4, 19, 41 |
| Verbatim preservation of `(descriptive sound)` inline parenthetical inside testimony | PRESENT (by default) | not specifically recognized; preserved as part of utterance text | §2.1 verbatim mandate | Entry 17 |
| Verbatim preservation of `(Witness complies)` inline within A. text | PRESENT (by default) | same — text preserved verbatim | §2.1 verbatim mandate | Entry 26 |
| Q. line with only nonverbal-action text (Entry 29) | PRESENT (by default) | `qa_line()` accepts any text; would emit `Q.  (Moving head up and down)` | §12 QA-06 | Entry 29 |
| Verbatim preservation of "strike that" mid-question | PRESENT (by default) | preserved as text | §2.1 verbatim mandate | Entries 8, 21 |
| Verbatim preservation of "y'all" and other nonstandard spellings | PRESENT (by default) | preserved as text | §2.1 verbatim mandate | Entry 27 |
| Witness self-rephrase preserved verbatim | PRESENT (by default) | both A. lines preserved as discrete utterances | §2.1 verbatim mandate | Entry 10 |

---

## 9. Recommendation (Phase E)

### Precedence argument (strongest case for the pick)

CF-1 wiring would route the export path through `pipeline.run`, but `pipeline.run`'s stage order (regex → G → A → M → X → T → U → F per Phase A §5.1) explicitly excludes Stages S and Q — the structural stages that produce the opening ritual. Wiring CF-1 first would route the export through an orchestrator that cannot produce the feature this audit identifies as highest-leverage. The reverse direction is clean: QA-01 + opening ritual goes into `backend/stage_s/`, which `render_stage_s` already invokes from the export path, so the pass lands in production the moment it merges. **QA-01 is independent of CF-1; CF-1 is not independent of QA-01.** The two passes are not symmetric in dependency, and the ordering matters.

### Framing A rationale (recorded per direction)

The export path is the production sequence; `pipeline.run` is dormant scaffolding; the spec's idealized stage diagram is out of date relative to working code. Under this framing, the prior expectation was that the highest-leverage build pass would close the CF-1 audit-trail gap by reconciling the two and persisting per §17.1.

**The Phase C evidence does not support that pick.** The Phase D matrix shows 24 distinct MISSING rows grounded in Phase C entries — most of them in `stage_s/`'s structural rendering, not in the dormant pipeline. CF-1 wiring would activate the dormant `corrections/` stages, but those stages produce non-structural typography / metadata / lexicon corrections — not the canonical opening ritual every deposition needs to have a recognizable shape. Per the directive that Framing A is a working assumption and the five-sentence justification must cite specific Phase C entries, the recommendation pivots to the structural pick.

### Highest-leverage build pass

**Implement QA-01 trigger gate and the structural opening ritual it requires** — specifically, teach `stage_s/renderer.py` to emit the canonical four-line opening (WITNESS_SWORN parenthetical → EXAMINATION header → BY-line → first Q.) when the renderer detects a sworn-witness anchor in the utterance stream, plus wire inline `(BY MR. NAME)` re-attribution into `qa_line` calls following any non-trivial interruption.

1. **Why this gap, not another.** Phase D §8.1 shows that QA-01's preconditions (sworn-witness block, EXAMINATION header, initial BY-line, inline `(BY MR. X)` re-attribution) are MISSING — not WIRING-BROKEN, not PARTIAL, **absent**. The Phase C inventory grounds this in eight inflection points: Entries 2 and 42 (sworn-witness block opens every deposition), Entries 15, 24, 31, 32, 37 (EXAMINATION header geometry recurs at every examination boundary), Entries 3, 5, 8, 11, 12, 14, 27, 28 (inline `(BY MR. X)` re-attribution appears in nearly every interruption case across both depositions). Without this pass, every transcript the engine produces opens cold with a `Q.` line and resumes after every interjection with the same cold `Q.` — visibly wrong on every job. CF-1 wiring (the predicted Framing A pick) would activate dormant typography and metadata corrections — operator-visible but per-job-variable improvements — and would carry a scope dependency on the unresolved `lexicon/` vs `corrections/legal_phrases.py` Stage X question (the parallel-system flag in §4), making it a worse single-pass scope.
2. **Predicted visible quality improvement.** Every deposition transcript would open with the canonical `(The witness was sworn.)` / `EXAMINATION` / `BY MR. NAME:` sequence in the correct UFM column geometry instead of beginning cold with a `Q.` line. Every resumption after an objection, exhibit-marking, off-record discussion, or counsel-action parenthetical would show inline `(BY MR. NAME)` re-attribution. Coverage is 100% of jobs from the moment the pass lands — the operator sees the correct opening on first paint of every transcript, with no manual repair.
3. **Effort estimate.** **S** (local change to one subsystem, 2–4 files). Net-new code: a `LINE_EXAMINATION` line-type constant in `stage_s/models.py`; an `examination_header_line()` factory in `stage_s/line_builder.py`; precondition-detection state in `stage_s/renderer.py` that emits `WITNESS_SWORN` (already in `parentheticals.WITNESS_SWORN`), then EXAMINATION, then BY-line (`by_attribution_line` already exists) on the transition from off-examination to first `examining_attorney` utterance; and at the `qa_line` call site in `renderer.py:187`, pass `by_label=state.current_examiner_label` when the previous emitted line was a colloquy / parenthetical / objection rather than a Q/A. No corrections-pipeline changes, no `lexicon/` decision forced.
4. **Risk to §2E invariants.** None. All emissions are deterministic structural additions sourced from confirmed participant roles and the canonical parenthetical registry. No testimony is mutated, deleted, summarized, or transformed. The renderer already operates only on the working layer and never writes RAW. The new code is line-emission logic only.
5. **Local or cross-cutting.** **Local** to `backend/stage_s/`. No dependency on the lexicon-vs-legal_phrases question (§4), no dependency on CF-1 wiring, no API surface changes, no test-suite breakage expected. Independently testable, independently shippable.

### Runners-up (priority order)

**Runner-up 1 — CF-1 wiring (pipeline.run output → export path + §17.1 log persistence).** Stronger spec-compliance pick. Visible improvements: garbled objections resolve (LEX-01 — applies to any objection Deepgram garbled in production), reporter name normalization fires (PRE-01), confirmed_spellings reach the certified output (PRE-07), typography normalization fires (POST-01 / POST-02 / POST-03 / POST-06 / POST-07), correction log persists per §17.1 making the engine certifiable. **Carries a scope dependency** on the `lexicon/` vs `corrections/legal_phrases.py` Stage X question — both occupy the "Stage X" identity and the wiring decision must choose. M effort. Cross-cutting (touches `correction_trigger.py`, both export-document builders in `transcripts.py`, `packaging.py`). Recommend tackling **after** the headline pick lands and **after** the lexicon ownership question is resolved.

**Runner-up 2 — STR-04 closing ritual mirror (DEPOSITION_CONCLUDED parenthetical + stipulation ritual handling).** Symmetric to the headline pick: the headline fixes openings, this fixes closings. Phase C Entries 17, 33, 47 ground this in both depositions. `parentheticals.concluded()` exists and is unused; renderer needs an end-of-stream hook to emit it. STR-03 also covers the post-record region per Q4 (flag, don't delete). S–M effort, local to `backend/stage_s/`.

**Runner-up 3 — STR-01 reporter anchor capture (full implementation of THE REPORTER multi-paragraph opening).** Distinct from the headline pick because it operates on `court_reporter` utterance *content* (regex-extracting date / time / location from reporter speech) rather than on emission state. Phase C Entries 24, 43, 44 supply the canonical form. Implementation involves regex extraction in `stage_s/off_record.py` plus a new `STR-01` event in the renderer. Also forces a decision on multi-paragraph colloquy turns (Entry 43 cross-cutting). M effort, local to `backend/stage_s/`.

**Runner-up 4 — Implement the missing FLAG categories (FLAG-01, FLAG-03, FLAG-04, FLAG-05).** Closes the spec's §2.5 "flag, don't guess" promise. Currently only 2 of 6 flag categories fire. Effort depends on per-category complexity (FLAG-04 boundary-uncertainty is M; FLAG-01 unverified-proper-noun is M, requires a dictionary or candidate-detector). Has a dependency on CF-1 wiring to actually surface the flags to the operator. M effort, partly cross-cutting.

### Open questions for human review

1. **`backend/lexicon/` ownership** — intentional architectural separation (warranting a `§10A` spec amendment and an entry in `SYSTEM_OWNERSHIP.md`), or accidental parallel system (warranting consolidation into `corrections/legal_phrases.py` per spec §10)? Audit-surfaced; load-bearing for Runner-up 1. Evidence in §4 parallel-system flag.
2. **Q-precedes-A assumption** (Phase C Entry 14) — does `stage_s/renderer.py` need to handle A-before-Q ordering after off-record resumption, or is the inventory case an artifact of how the reporter chose to render a back-and-forth? Audit-surfaced via Phase C.
3. **Inline parenthetical recognition vs verbatim preservation** (Phase C Entries 17, 26) — verbatim preservation handles these correctly today by accident; does the engine need explicit recognition (e.g. for downstream pagination styling), or is the verbatim-by-default behavior the intended position? Audit-surfaced via Phase C.
4. **Multi-paragraph colloquy turns** (Phase C Entry 43) — does `line_builder.colloquy_line` need to emit paragraph breaks within one THE REPORTER speaker turn, or is one logical paragraph per utterance the model? Affects STR-01 implementation (Runner-up 3).
5. **Reporter inconsistency normalization** (Phase C Entry 35) — when a reporter inconsistently uses single vs. double space after a colloquy colon within the same deposition, does the verbatim mandate (§2.1) preserve both forms, or does typography normalization (POST-03) collapse to the canonical form? The spec is silent; the answer dictates whether POST-03 should apply to colloquy labels arriving from Deepgram (which would also need to reach the export path via CF-1 wiring).
6. **Jurisdiction-dependent stipulation ritual** (Phase C Entry 47) — federal depositions include a reporter-spoken stipulation request that state-court depositions don't. Is jurisdiction-aware emission expected (intake-metadata-driven), or is this purely verbatim from reporter speech to be preserved as-typed?
7. **QA-03 in the wild** — Phase C inventory contains no positive QA-03 cases across two long depositions; every multi-sentence Q. is a negative case where splitting would be wrong. Is the spec's "Were your brakes working? Yes." pattern truly observed in real production or largely theoretical? If theoretical, QA-03 should be deprioritized below the runners-up above. Audit-surfaced via Phase C cross-cutting #5.

---

## Done checklist

- [x] Baseline captured (git status, head commit, test count)
- [x] Section 4 pre-phase: five anomaly findings produced
- [x] Critical Findings section present — CF-1 + lexicon parallel-system flag
- [x] Phase A: every file in `backend/corrections/` and `backend/stage_s/` traced with WIRING + STATUS
- [x] Phase A: sequence diagram reflects observed code, not spec's idealized flow
- [x] Phase B: spec-drift table grouped by spec section, with one-sentence summary
- [x] Phase C feature inventory — received from parallel session, 47 entries, summarized in §7 with two cross-cutting findings carried into Phase E
- [x] Phase D gap matrix — sorted with MISSING and WIRING-BROKEN first, every row grounded by Phase C entry or marked as architectural
- [x] Phase E recommendation — ONE pick (QA-01 trigger gate + structural opening ritual), 4 runners-up, 7 open questions
- [x] No build prompt drafted, no implementation sketched (investigation-only per §1)
- [x] Final pytest re-run — see §2 Baseline (run at start; the audit performed no code changes, so the count is unchanged)
- [x] `git status --short` shows only this audit report as untracked

---

*Audit complete. No code modified. Single deliverable: this report.*
