> DOCUMENT STATUS: SUPERSEDED ACTIVE DOCUMENT
> Scope: historical Wave 10 foundation delivery note retained beside the code for provenance.
> Warning: this document predates later correction-engine, diagnostics, and mutation-detection work. It is useful for history but not safe as current subsystem authority.
> Current authority: `CLAUDE.md`, `docs/ACTIVE_SPEC_REGISTRY.md`, `docs/architecture/transcript_engine/*.md`, `docs/SYSTEM_OWNERSHIP.md`, and `docs/TRANSCRIPT_ORCHESTRATION.md`.

# Wave 10 — Correction Engine: Foundation Delivery

This drop adds the **deterministic correction engine foundation** to DEPO-PRO.
It is steps 1–8 of the build order in
`docs/architecture/transcript_engine/deterministic_correction_engine_spec.md` §22
— a runnable, fully tested **Parity-Mode** engine.

## What's included

```
backend/corrections/
├── __init__.py        public entry point: run(), Utterance
├── model.py           Utterance, CorrectionResult, CorrectionLogEntry, Flag, ...
├── patterns.py        every compiled regex + constant, one place (spec 17.6)
├── guards.py          Stage G (verbatim guards) + Stage U (unguard)
├── artifacts.py       Stage A — Deepgram artifact removal (PRE-04/05/06/10)
├── metadata.py        Stage M — exact-match substitution (PRE-01/02/07/08/09)
├── typography.py      Stage T — spacing / honorifics / time (POST-01..08)
├── flags.py           Stage F — flag registry + FLAG-02 / FLAG-06
├── log.py             the correction log (spec 17.1 / Q6)
└── pipeline.py        the orchestrator: run() -> CorrectionResult

tests/corrections/
├── test_guards.py
├── test_artifacts_metadata.py
├── test_typography_flags.py
└── test_pipeline.py   end-to-end, idempotency, verbatim, parity, gate
```

## Test status

- Historical note: the counts in this section are the foundation-drop counts at
  the time this note was written, not the current repository totals.

Run them:

```
cd depo_final_wave8
.venv\Scripts\activate
python -m pytest tests/corrections -q     # the engine alone
python -m pytest -q                        # whole project
```

## How to use it

```python
from backend.corrections import run, Utterance

transcript = [
    Utterance(utterance_id="u1", speaker_index=1,
              role="examining_attorney",
              text="Doctor. Smith, state your name. Thank you."),
    # ... one Utterance per working-layer utterance, each with its
    #     confirmed Wave 9 role
]
job_config = {
    "reporter_name": "Miah Bardot",
    "confirmed_spellings": {"Home Depot": "Home Depot U.S.A., Inc."},
    "deepgram_keyterms": ["Ballymore"],
    "deterministic_parity_mode": False,
}

result = run(transcript, job_config)          # CorrectionResult
result.lines    # corrected RenderedLine list
result.log      # CorrectionLogEntry list — every change, auditable
result.flags    # Flag list — what was deferred to the reporter
```

## Wiring into the app (historical note)

At the time of this note the engine was not yet wired into the app. The live
repository now invokes deterministic correction through the current transcript
and speaker-mapping orchestration; use the active specs and governance docs for
current behavior rather than this historical wiring note.

```python
from backend.transcript import repository as trepo
from backend.services.speaker_mapping import build_speaker_directory
from backend.corrections import run, Utterance

def build_engine_input(job_id: str) -> list[Utterance]:
    utterances   = trepo.get_utterances(job_id)
    participants = trepo.get_participants(job_id)
    directory    = build_speaker_directory(participants)   # {idx -> {role,...}}
    out = []
    for u in utterances:
        info = directory.get(u.get("speaker_index"))
        out.append(Utterance(
            utterance_id  = u["utterance_id"],
            speaker_index = u.get("speaker_index"),
            role          = (info or {}).get("role", "other"),
            text          = u.get("text") or "",
            start_time    = u.get("start_time", 0.0),
            end_time      = u.get("end_time", 0.0),
        ))
    return out
```

`job_config` for the engine is assembled from the case `keyterms`, the NOD-parsed
entities (`confirmed_spellings`), and the reporter name — the same sources Wave 11
§4.3 describes.

## Scope — what is NOT in this drop

Historical note: this section reflects the foundation-drop scope at the time of
writing. Later work added diagnostics, mutation detection, and broader
orchestration beyond this initial drop.

- **Stage X** — legal lexicon (garbled-objection resolution)
- **Stage S** — off-record structuring / parentheticals
- **Stage Q** — Q/A formatting, tab assignment

Until they exist, Full Mode and Parity Mode are identical (the engine runs
G·A·M·T·F·U either way). The `deterministic_parity_mode` flag is already wired,
so the moment X/S/Q land, the mode switch works with no further change.

Also deferred (later flag stages): FLAG-01 (unverified proper nouns), FLAG-03
(residual garble), FLAG-04 (boundary — emitted by Stage S), FLAG-05 (ambiguous
date/number). The flag *registry* and sequential numbering are complete; FLAG-02
and FLAG-06 are live.

## One small spec addition

`model.py` is not in the spec's §18 module list. It holds the engine's input/output
data types (the contract described in spec §4). Adding it keeps the package
self-contained and testable in isolation from the app's pydantic models — worth a
one-line note in §18 when the spec is next revised.

## Next steps

1. Review this foundation.
2. Build the diff harness (`backend/diagnostics/`) — §22 step 9 — so RAW fidelity
   is measurable before structural work.
3. Build Stages X, S, Q (§22 steps 10–12).
4. Then Wave 11 on top.
