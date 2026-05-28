> DOCUMENT STATUS: CANONICAL CURRENT-STATE GOVERNANCE
> Scope: authoritative module ownership for live DEPO-PRO subsystems.
> This document defines which module owns each concern and explicitly forbids parallel systems.

# SYSTEM_OWNERSHIP.md

## Purpose

This is the current-state ownership map for DEPO-PRO. It exists to stop
duplicate implementations, parallel pipelines, and “temporary” alternate paths
from drifting into production authority.

If a concern below already has an owner, extend that owner. Do not create a
second system beside it.

## Ownership Map

| Concern | Authoritative owner |
|---|---|
| Raw transcript integrity | `backend/transcript/integrity.py` |
| Transcript ingest + packet creation | `backend/transcript/ingest.py`, `backend/transcript/assembler.py`, `backend/transcript/packet.py` |
| Transcript persistence | `backend/transcript/repository.py` |
| Stage 3 working transcript authority | `backend/transcript/working_state.py`, `backend/api/transcripts.py` |
| Speaker mapping authority | `backend/services/speaker_mapping.py`, persisted in `transcript_participants` through `backend/api/transcripts.py` |
| Deterministic correction orchestration | `backend/corrections/pipeline.py` and `backend/services/correction_trigger.py` |
| Transcript diff / diagnostics | `backend/diagnostics/` |
| Mutation detection gate | `backend/transcript/mutation_detection.py`, enforced from `backend/api/packaging.py` |
| Snapshot capture / rollback / state hash | `backend/transcript_state/` |
| Pagination | `backend/pagination/` |
| Geometry | `backend/geometry/profile.py`, `backend/geometry/engine.py` |
| Export document rendering | `backend/transcript/export_render.py`, `backend/export/export_service.py` |
| Export validation orchestrator | `backend/export/export_validation.py` |
| Package assembly / validation / certification | `backend/packaging/`, `backend/api/packaging.py` |
| Exhibit authority | `backend/api/exhibits.py`, `backend/transcript/repository.py` (`transcript_exhibits`) |
| NOD parsing | `backend/services/nod_parser/`, surfaced by `backend/api/nod.py` |
| Stage 1 intake persistence + keyterms | `backend/api/intake.py`, `backend/services/intake_store.py`, `backend/services/keyterms.py` |
| AI review queue and suggestion generation | `backend/ai_review/`, `backend/api/ai_review.py` |
| Runtime transcription provider selection | `backend/config.py`, `backend/deepgram/client.py` |
| Audio retention sweep | `backend/transcript/audio_retention.py`, called from `backend/app.py` |

## Transcript Layer Ownership

The transcript layers are not interchangeable.

| Layer | Owner | Notes |
|---|---|---|
| RAW | `backend/transcript/integrity.py` + persisted raw packet + `transcript_utterances.text` / `transcript_words.raw_text` | Immutable after capture |
| WORKING | `backend/transcript/working_state.py` + `transcript_working_utterances` + working packet | Editable, persisted, snapshot-captured |
| CORRECTED / STRUCTURALLY RENDERED | `backend/corrections/`, `backend/stage_s/`, `backend/transcript/export_render.py` | Derived from working state; not a separate freeform persistence authority |
| CERTIFIED | `backend/transcript_state/` locked snapshot + `backend/packaging/` certified package lineage | Immutable after certification |

### Opening-ritual ownership (refinement, 2026-05-28)

The "CORRECTED / STRUCTURALLY RENDERED" row above establishes the general
principle that `backend/stage_s/` is a structural-rendering authority. This
entry **newly** settles a specific case under that principle — it is a fresh
assignment, not a pre-existing ruling:

- **`backend/stage_s/` is the sole owner of the deposition opening ritual** —
  the witness-sworn block, the `EXAMINATION` header, the `BY MR./MS. ___:`
  attribution line, and inline `Q. (BY MR./MS. ___)` re-attribution. These are
  emitted once, as structural render lines, by `backend/stage_s/renderer.py`.
- **`backend/transcript/export_render.py` owns document layout/pagination and
  no longer emits any opening ritual of its own.** It previously carried a
  parallel front-matter ritual (witness name + an unconditional
  "having been first duly sworn" line + an `EXAMINATION BY ___:` header); that
  parallel ritual is removed. export_render renders the stage_s ritual lines
  through to the page; it does not originate ritual content.

Rationale: the two parallel rituals produced a duplicate `EXAMINATION` header
and an unconditional witness-sworn assertion in the export preview and the
snapshot export document. Per the no-parallel-systems principle, ritual
ownership is consolidated to `backend/stage_s/`; `export_render.py` remains the
export-layout authority. The witness-sworn line is added back, gated
(detect/flag/attest), in a separate pass and never auto-asserted.

## Frontend / Backend Boundary

- The frontend may present, stage, preview, and submit edits.
- The backend owns persistence, snapshot state, export state, package state,
  and certification authority.
- Frontend-only preview aids are not authoritative unless the backend persists
  them through an owned path.

## Forbidden Parallel Systems

Do not create:

- a second working-transcript store;
- a second snapshot or rollback engine;
- a second pagination or geometry authority;
- a second package/certification pipeline;
- a second transcript diff or mutation-detection path;
- a second speaker-mapping authority;
- a second NOD parser or keyterm generation path.

If an existing owner is insufficient, that is a governance or architecture
decision. It is not permission to build a parallel implementation.
