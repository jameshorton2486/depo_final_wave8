> DOCUMENT STATUS: ACTIVE REFERENCE
> Scope: index of the active transcript-engine specs and related governance docs.
> Use this as a map, not as a second authority layer.

# Transcript Engine — Architecture Documents

Authoritative engineering documents for DEPO-PRO's transcript-processing system.
These are build specifications and architectural contracts — code is built *from*
them. They are versioned with the code. If code and a spec appear to conflict,
treat that as governance drift to audit against the live canonical docs and the
current implementation. Do not invent a parallel interpretation.

**The application does not read these files at runtime.** They are developer
architecture docs. Rules are hand-encoded in Python; the docs are never parsed,
loaded, or injected into prompts.

---

## Documents in this folder

| File | Status | Purpose |
|---|---|---|
| `TRANSCRIPT_ENGINE_RULES.md` | **Authoritative** | The constitution — the one-minute list of invariant rules. Read first. |
| `deterministic_correction_engine_spec.md` | **Authoritative · v1.1** | Complete build spec for `backend/corrections/` — the no-AI regex/script correction engine. |
| `transcript_diff_harness_spec.md` | **Authoritative · v1.1** | Complete build spec for `backend/diagnostics/` — the APP-vs-RAW measurement and regression tool. |

## Planned documents (not yet written)

Proposed in review; **not** created as stubs to avoid empty-file noise. Several
would overlap material that already exists — listed here so the structure is
known and the scope is honest:

| Proposed file | Note |
|---|---|
| `transcript_pipeline_overview.md` | Replaced in current governance by `docs/TRANSCRIPT_ORCHESTRATION.md`. |
| `transcript_object_model.md` | The canonical word/utterance/participant data model. Currently documented inline in the engine spec §4 and the Wave 9 schema. |
| `speaker_mapping_architecture.md` | Speaker-mapping authority now lives in `docs/SYSTEM_OWNERSHIP.md` and `docs/TRANSCRIPT_ORCHESTRATION.md`. A separate architecture note would be additive, not authoritative. |
| `parity_mode_spec.md` | **Redundant** — Parity Mode is fully specified in the engine spec §3A. A separate file would duplicate it. |
| `transcript_lifecycle.md` | Replaced in current governance by `docs/TRANSCRIPT_ORCHESTRATION.md`. |

Write these only when there is real content for them — not as placeholders.

---

## Build sequence

From the engine spec §22. Do not build the engine all at once:

```
patterns.py → guards.py → artifacts.py → metadata.py → log.py
   → typography.py → flags.py → pipeline.py        ← Parity Mode runnable here
   → backend/diagnostics/ (diff harness)           ← build before structural stages
   → legal_phrases.py → structure.py → qa_format.py
```

Reach a measurable Parity-Mode baseline and a working diff harness **before**
building the structural stages (X, S, Q).

## Related, outside this folder

- `docs/examples/` — transcript fixtures and expected outputs for tests.
- `docs/SYSTEM_OWNERSHIP.md` — current module ownership and anti-parallel-system rules.
- `docs/TRANSCRIPT_ORCHESTRATION.md` — current raw → working → certified lifecycle and mutation flow.
- Legal Standards Reference, UFM Transcript Templates — the source legal
  documents the engine spec consolidates.

---

*Wave 10. Maintained with the codebase.*
