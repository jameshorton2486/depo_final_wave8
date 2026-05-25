# Stage 3 Workspace Stabilization Audit

Date: 2026-05-25  
Repository: `DEPO-PRO`  
Scope: Stage 3 Workspace  
Audit type: Observational, stabilization-focused, no runtime modifications

## Purpose

This audit documents the current Stage 3 Workspace architecture, identifies the authoritative transcript-state boundaries, validates correction and speaker-mapping safety, traces export and certification dependencies, and ranks transcript-corruption and workflow-stability risks.

This was not a rewrite pass. No architecture was renamed, no systems were replaced, and no transcript-engine behavior was modified as part of this audit.

## Executive Summary

Stage 3 is structurally central to the product, but it is only partially authoritative today.

The system is stable and authoritative in these areas:

- raw transcript acquisition and persistence
- speaker mapping persistence
- backend export preview and export rendering
- AI review queue isolation
- raw diarization preservation

The system is not yet fully authoritative in these areas:

- durable Stage 3 transcript-text persistence
- snapshot fidelity for full working transcript state
- certification/package rendering from locked snapshot state
- unification of frontend edit tools with backend working-state persistence

The highest-risk issue is that Stage 3 presents a persistent transcript-editing workspace, but the observed save path for freeform transcript edits does not currently persist to the backend working layer in a way that survives reload, rollback, export, and certification deterministically.

## Scope Reviewed

### Frontend

- `frontend/screens/stage_3_workspace.html`
- `frontend/assets/js/screens/stage_3.js`
- `frontend/assets/js/state.js`
- `frontend/assets/js/app.js`
- `frontend/assets/js/api.js`
- supporting Stage 2 and Stage 6 handoff files

### Backend

- `backend/api/transcripts.py`
- `backend/api/ai_review.py`
- `backend/api/corrections.py`
- `backend/api/packaging.py`
- `backend/api/snapshots.py`
- `backend/transcript/`
- `backend/transcript_state/`
- `backend/corrections/`
- `backend/ai_review/`
- `backend/stage_s/`
- `backend/export/`
- `backend/pagination/`
- `backend/services/correction_trigger.py`
- transcript schemas and related models

## 1. Complete Stage 3 Architecture Map

### UI Responsibilities

Stage 3 Workspace currently presents:

- transcript review canvas
- freeform line editing
- regex sandbox
- AI suggestion queue
- authoritative speaker mapping
- formatting utilities
- simulated audio sync
- provenance log
- correction memory display

Primary file:

- `frontend/screens/stage_3_workspace.html`

Notable UI declarations:

- transcript lines render into `transcriptLinesContainer`
- line bodies are `contenteditable`
- sidebar explicitly states Stage 3 is the sole speaker authority
- footer states `RAW IS IMMUTABLE` and `WORKING LAYER PERSISTENT`

### Frontend State Ownership

Primary file:

- `frontend/assets/js/state.js`

Observed Stage 3 state fields:

- `state.transcriptLines`
- `state.correctionsMemory`
- `state.provenance`
- `state.focusedLineId`
- `state.workspaceJob`
- `state.workspaceSpeakerMapping`
- playback state fields
- `state.activeTranscriptJobIds`

Important distinction:

- `state.transcriptLines` is the live frontend working view
- it is not, by itself, durable transcript authority

### Frontend Workflow

Primary file:

- `frontend/assets/js/screens/stage_3.js`

Stage 3 frontend behavior includes:

- rendering transcript lines from `state.transcriptLines`
- editing line text in browser memory
- accepting/rejecting local suggestions
- modifying Q/A line type locally
- inserting local page-break markers
- globally stripping filler words locally
- loading and saving speaker mapping through backend APIs
- loading AI suggestions from backend review queue

### API Boundary

Primary client surface:

- `frontend/assets/js/api.js`

Observed Stage 3 API usage:

- `GET /api/transcripts/jobs/{job_id}/content`
- `GET /api/transcripts/jobs/{job_id}/speaker-mapping`
- `PUT /api/transcripts/jobs/{job_id}/speaker-mapping`
- `POST /api/transcripts/jobs/{job_id}/speaker-mapping/apply`
- `GET /api/transcripts/jobs/{job_id}/export-preview`
- `POST /api/transcripts/export-preview/fallback`
- `GET /api/ai-review/status`
- `POST /api/ai-review/jobs/{job_id}/speaker-map`
- `POST /api/ai-review/jobs/{job_id}/analyze`
- `GET /api/ai-review/jobs/{job_id}/suggestions`
- `POST /api/ai-review/suggestions/{id}/approve`
- `POST /api/ai-review/suggestions/{id}/reject`
- snapshot endpoints

No active Stage 3 API was found that durably saves arbitrary transcript text edits back into the canonical working transcript layer.

### Backend Service Flow

Observed backend path:

`/content`  
-> `backend/transcript/repository.py`  
-> transcript jobs, speakers, utterances, words, participants  
-> Stage 3 load into frontend state

Speaker mapping path:

`/speaker-mapping`  
-> `backend/api/transcripts.py`  
-> `backend/services/speaker_mapping.py`  
-> `transcript_participants`

Export path:

job  
-> utterances + participants  
-> regex rules and Stage X lexicon working-copy transforms  
-> `backend/stage_s/renderer.py`  
-> `backend/transcript/export_render.py`  
-> `backend/pagination/*`  
-> `backend/export/*`

Snapshot path:

job  
-> `backend/transcript_state/snapshot_service.py`  
-> `transcript_snapshots`

## 2. Authoritative Transcript State Owner

### Raw Transcript Truth

The strongest durable transcript authority today is the raw persisted ingestion layer:

- `transcript_utterances.text`
- `transcript_words.raw_text`
- `data/transcripts/{job_id}/raw.json`

Primary owners:

- `backend/transcript/assembler.py`
- `backend/transcript/repository.py`
- `backend/transcript/ingest.py`

### Speaker Identity Truth

The authoritative speaker-identity layer is:

- `transcript_participants`

This is used by:

- Stage 3 speaker mapping UI
- backend transcript render logic
- export speaker resolution
- packaging
- snapshots
- rollback for speaker mapping

### Intended Working Transcript Truth

Schema intent clearly exists for a working layer:

- `transcript_words.working_text`
- `working.json`

Reference:

- `backend/db/schema_v2.sql`

But the observed implementation does not currently show a live write path from Stage 3 freeform edits into that working layer.

### Practical Conclusion

Current practical authority is split:

- raw transcript text is authoritative and durable
- speaker mapping is authoritative and durable
- Stage 3 freeform transcript edits are not yet durably authoritative

## 3. Transcript Lifecycle Map

### Lifecycle

Audio  
-> Deepgram batch ASR or offline fallback  
-> `backend/transcript/assembler.py` normalization  
-> canonical words, utterances, speakers  
-> SQLite persistence  
-> raw and working packet creation at ingest  
-> Stage 2 load into `state.transcriptLines`  
-> Stage 3 review and local mutation  
-> speaker mapping persistence  
-> AI review queue annotation  
-> export preview render  
-> export file generation  
-> snapshot creation  
-> package assembly  
-> certification

### Mutation Risk by Step

- Audio to ASR: `LOW`
- Assembler structural grouping: `MEDIUM`
- DB persistence: `LOW`
- Stage 3 frontend local editing: `CRITICAL`
- speaker mapping persistence: `LOW`
- AI review queue: `LOW`
- export working-copy transforms: `MEDIUM`
- snapshot capture: `HIGH`
- certification/package render from live DB rather than locked snapshot: `CRITICAL`

## 4. Transcript Load Integrity

### Verified Safe Behaviors

Opening a transcript through `/api/transcripts/jobs/{job_id}/content` preserves:

- utterance ordering
- word ordering
- speaker indices
- timestamps
- confidences
- raw diarization labels
- participant mappings when present

### Observed Load-Time Transform

`backend/transcript/assembler.py` merges consecutive same-speaker utterances into a larger turn before persistence.

This is:

- deterministic
- documented in code
- not an arbitrary cleanup transform
- still a structural mutation relative to provider granularity

### Findings

The Stage 3 load path itself does not:

- auto-correct text
- remove filler
- collapse speakers
- silently rewrite testimony

Risk level:

- `LOW` for Stage 3 open
- `MEDIUM` for ingestion-time structural grouping

## 5. Transcript Persistence Audit

### What Persists Reliably

- transcript jobs
- raw packets
- working packet at ingest time
- speakers
- utterances
- words
- participants
- AI suggestion rows
- snapshot rows

### What Does Not Reliably Persist

Observed frontend-only transcript mutations in `frontend/assets/js/screens/stage_3.js`:

- `handleTextEdit()`
- `runCustomRegexRulePipeline()`
- `acceptSuggestion()`
- `rejectSuggestion()`
- `acceptAndRememberSuggestion()`
- `applyLinePrefix()`
- `forceManualPageBreak()`
- `removeFillerWordsGlobal()`

These mutate `state.transcriptLines`, provenance, or correction memory, but no corresponding durable backend write path was found.

### Autosave

No active Stage 3 autosave workflow was found.

Snapshot categories include `AUTO_SAVE`, but the active code path does not show Stage 3 transcript-edit autosave behavior.

### Reload / Reopen Behavior

Reliable after reload:

- speaker mapping
- AI review queue state
- raw transcript source content

Not reliably preserved after reload:

- free text edits
- manual page breaks
- locally forced Q/A typing
- local filler stripping
- local suggestion-acceptance changes

### Conclusion

Transcript persistence is stable for source content and speaker identity, but unstable for Stage 3 transcript-body editing.

## 6. Correction Pipeline Analysis

### Backend Deterministic Correction Engine

Primary file:

- `backend/corrections/pipeline.py`

Observed stages:

- Guards
- Artifacts
- Metadata
- Legal phrase resolution
- Typography
- Flags
- Unguard

### Deterministic Safe Properties

The backend deterministic engine:

- does not reorder utterances
- does not merge speakers
- does not hallucinate language
- does not use AI
- does not mutate RAW
- uses guard/unguard shielding for verbatim-sensitive spans

### Deterministic Mutators

Examples:

- duplicate-word collapse
- artifact normalization like `K.` -> `Okay.`
- reporter-name garble replacement
- exact confirmed-spelling replacement
- exact keyterm case correction
- objection and legal phrase normalization from finite maps
- typography and spacing normalization

### Advisory / Flag-Only

`backend/corrections/flags.py` inserts human-review markers and does not silently resolve uncertain cases.

### Unsafe or Sensitive Areas

Risk is not primarily in backend deterministic engine structure.

Main sensitivity points are:

- operator-authored regex rules
- confirmed spelling maps
- frontend local destructive editing tools

### Correction Safety Conclusion

Backend deterministic corrections are structurally conservative. The greater safety issue is not hidden backend mutation; it is parallel, partly local mutation authority.

## 7. AI Review Safety Analysis

### Current AI Review Model

Primary files:

- `backend/api/ai_review.py`
- `backend/ai_review/review_queue.py`
- `backend/ai_review/generators.py`
- `backend/ai_review/speaker_map.py`

### Verified Safe Behaviors

AI review:

- generates suggestions only
- persists suggestions in queue storage
- requires human approve/reject actions
- does not directly write transcript text
- remains inert without API key

### Important Observation

The router documentation says approval is the gate to the transcript, but current approve/reject handlers only update suggestion status.

That means:

- AI is safe from silent mutation
- transcript-application integration is incomplete or deferred

### Risk

- silent AI mutation risk: `LOW`
- workflow-clarity risk: `MEDIUM`

## 8. Speaker Mapping Analysis

### Authoritative Owner

Stage 3 is now the authoritative speaker-mapping workflow.

Primary persistence layer:

- `transcript_participants`

### Verified Stable Behaviors

Speaker mapping:

- persists correctly
- survives reload
- survives Stage 3 reopen
- flows into export speaker labels
- flows into packaging/certification speaker resolution
- is captured by snapshots
- is restored by snapshot rollback

### Raw Diarization Preservation

The system preserves:

- raw `speaker_index`
- `speaker_label`
- utterance timing
- word timing
- confidence
- raw Deepgram packet artifacts

Stage 3 maps:

raw speaker ids  
-> participant identities and roles

It does not destructively replace raw diarization data.

### Risk

- speaker mapping persistence risk: `LOW`
- speaker/export mismatch risk: `MEDIUM` when packaging renders from live state rather than locked snapshot state

## 9. Audio Sync Analysis

### Current Implementation

Primary file:

- `frontend/assets/js/screens/stage_3.js`

Observed behavior:

- playback is timer-driven
- waveform is static SVG
- playhead position is derived from transcript line index and duration
- no real audio element or media-backed seeking authority was found

### Conclusion

Audio sync currently appears simulated or approximated rather than fully synchronized to persisted media.

This does not mutate transcript state, but it does create workflow-trust risk.

Risk:

- `MEDIUM`

## 10. Formatting System Analysis

### Authorities

Working speaker/role render:

- `backend/transcript/render.py`

Structural transcript shaping:

- `backend/stage_s/renderer.py`

Pagination and page-slot layout:

- `backend/transcript/export_render.py`
- `backend/pagination/paginator.py`
- `backend/pagination/wrapping.py`
- `backend/pagination/flow_rules.py`

Writers:

- `backend/export/docx_writer.py`
- `backend/export/pdf_writer.py`
- `backend/export/rtf_writer.py`
- `backend/export/txt_writer.py`

### Strengths

- export preview and actual export share the same canonical render path
- pagination is deterministic
- Stage S preserves source-utterance traceability
- DOCX/PDF writers consume canonical export structures

### Overlap Risk

Stage 3 canvas formatting is not the same authority as backend export formatting.

Examples:

- local line-type forcing in frontend
- manual page-break insertion in frontend
- local canvas theme/layout toggles
- backend Stage S and export render operating independently of those local canvas mutations

### Conclusion

Formatting authority is strong on the backend export side and weak on the frontend workspace side.

## 11. Export Consistency Analysis

### Verified Strong Areas

Saved-job export preview and actual export share `_build_export_document()` in `backend/api/transcripts.py`.

That means:

- Stage 6 preview matches Stage 6 export for saved jobs
- export speaker labels are resolved from confirmed participants
- pagination and layout are centralized

### Important Divergence

Export preview for unsaved/transient transcript state uses:

- `POST /api/transcripts/export-preview/fallback`

That path renders from frontend-supplied lines and is explicitly approximate.

### Major Integrity Gap

Stage 3 local transcript edits do not appear to be durably saved, so authoritative export may render older backend state while Stage 3 visually shows newer local edits.

Risk:

- `HIGH`

## 12. Snapshot and Certification Integrity

### Snapshot Capture

Primary file:

- `backend/transcript_state/snapshot_service.py`

Observed capture includes:

- simplified render-line state
- speaker mapping
- AI approval trace
- placeholder correction and lexicon fields

### Rollback

Observed rollback restores:

- `transcript_participants`

Observed rollback does not restore:

- full edited transcript text
- working packet content
- `transcript_words.working_text`
- frontend-originated Stage 3 text mutations

### Certification / Packaging Gap

`backend/api/packaging.py` requires a locked snapshot, but the body it packages is rebuilt from current live job utterances and participants.

That means a package can be assembled from:

- locked snapshot metadata contract
- current live transcript body

instead of a single locked state artifact.

Risk:

- `CRITICAL`

## 13. Transcript Corruption Risks

### Critical

- Stage 3 freeform transcript edits are not durably authoritative
- snapshot rollback is not full transcript rollback
- packaging/certification body can diverge from locked snapshot state

### High

- frontend filler-stripping can remove testimony locally
- manual page-break insertion creates synthetic local system lines
- frontend/local and backend/export transcript views can diverge
- overlapping correction/render authorities create stale-state risk

### Medium

- ingestion merges consecutive same-speaker utterances
- export path uses partial working-copy transforms distinct from correction trigger path
- audio sync is simulated rather than media-authoritative
- AI approval semantics imply stronger transcript integration than currently implemented

### Low

- backend deterministic correction engine structural corruption risk
- AI silent rewrite risk
- raw diarization loss risk

## 14. Overlapping Responsibilities

| Concern | Authoritative Owner | Conflicting or Parallel Owner | Risk | Notes |
| --- | --- | --- | --- | --- |
| Raw transcript text | `transcript_utterances`, `transcript_words.raw_text` | none | Low | durable and clear |
| Working transcript text | no active durable owner observed | `state.transcriptLines` | Critical | schema intent exists, save path unclear |
| Speaker identity | `transcript_participants` | none meaningful | Low | stable |
| Transcript render for export | Stage S + export render | frontend canvas formatting | High | frontend can diverge |
| Corrections | backend deterministic engine | frontend regex and edit tools | High | parallel mutation systems |
| AI review | `ai_suggestions` queue | none | Low | advisory-only |
| Snapshots | transcript_state tables | implied full workspace snapshot | Critical | current capture is partial |
| Certification state | locked snapshot contract | live DB body render | Critical | state divergence risk |

## 15. Stage 3 Audit Matrix

| Feature | Status | Owner | Risk | Notes |
| ------- | ------ | ----- | ---- | ----- |
| Transcript load | Stable | ingest + transcript repository | Medium | ingest merges consecutive same-speaker utterances |
| Transcript save | Unstable | no durable Stage 3 text owner observed | Critical | local edits appear volatile |
| Autosave | Missing | none active | High | `AUTO_SAVE` category exists but no live flow found |
| Corrections | Partial | backend engine plus local tools | High | multiple mutation paths |
| AI review | Safe | AI queue | Low | no silent transcript mutation |
| Speaker mapping | Stable | `transcript_participants` | Low | authoritative and persistent |
| Audio sync | Partial | frontend timer simulation | Medium | not true media-authoritative sync |
| Formatting preview | Split | frontend canvas and backend export preview | High | divergent authorities |
| Pagination | Stable backend | export render + pagination engine | Medium | frontend manual breaks are local |
| Export preview | Stable for saved jobs | backend export pipeline | Medium | ignores unsaved local edits |
| Snapshots | Partial | transcript_state | Critical | rollback restores mapping only |
| Certification | Structurally risky | packaging + snapshot system | Critical | package body not bound to locked snapshot |

## 16. Highest Priority Fixes

1. Establish one durable Stage 3 transcript-edit persistence path into the working layer.
2. Make Workspace reload from that same durable working layer.
3. Make snapshots capture and rollback full working transcript state, not just speaker mapping and partial metadata.
4. Make packaging and certification render from the locked snapshot state artifact, not current live database state.
5. Either persist or temporarily disable clearly destructive frontend-only transcript tools until they are auditable and reload-safe.
6. Clarify whether the deterministic correction engine is advisory, background-only, or part of the authoritative working-text pipeline.

## 17. Safe Next Stabilization Steps

1. Add a visible Stage 3 save-state indicator:
   - saved
   - unsaved local edits
   - export reflects current saved state only

2. Add integration tests for:
   - edit -> save -> reload
   - edit -> snapshot -> rollback
   - locked snapshot -> packaging body equivalence
   - speaker mapping -> export -> certification consistency

3. Add structured mutation logging for any future working-text save path:
   - who changed it
   - what changed
   - which job
   - whether it affected exportable state

4. Reconcile frontend formatting tools with backend formatting authority:
   - either bind them to persisted working state
   - or relabel them as preview-only tools

## Conclusion

Stage 3 is already the authoritative speaker-mapping system and the operational heart of transcript review, but it is not yet the authoritative durable owner of transcript text.

The repository has solid backend foundations:

- immutable raw transcript persistence
- canonical participant mapping
- deterministic structural export rendering
- queue-based AI review isolation
- append-only snapshot infrastructure

The stabilization gap is not missing architecture. The gap is that the visible Stage 3 editing surface currently exceeds the durability guarantees of the underlying persistence and certification chain.

The next stabilization phase should focus on one question above all others:

How does a Stage 3 transcript edit become authoritative, reproducible, reload-safe, export-safe, and certification-safe?

Until that is resolved, Stage 3 remains authoritative for speaker identity and review workflow, but only partially authoritative for transcript-body state.
