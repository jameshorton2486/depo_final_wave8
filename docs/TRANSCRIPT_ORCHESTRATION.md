> DOCUMENT STATUS: CANONICAL CURRENT-STATE GOVERNANCE
> Scope: transcript lifecycle, mutation flow, provenance flow, and certification gating.
> This document describes the current raw → working → certified orchestration as implemented in the live code.

# TRANSCRIPT_ORCHESTRATION.md

## Purpose

This document defines how transcript state moves through DEPO-PRO and which
steps are allowed to mutate which layer.

## Lifecycle

1. **Audio / media ingestion**
   - `backend/api/transcripts.py` accepts the upload.
   - `backend/transcript/ingest.py` runs transcription through the configured
     provider path.
2. **RAW capture**
   - `backend/transcript/assembler.py` assembles canonical utterances/words.
   - `backend/transcript/integrity.py` writes and verifies the immutable raw
     packet.
   - RAW is persisted through `backend/transcript/repository.py`.
3. **WORKING state**
   - Stage 3 edits persist only through
     `PUT /api/transcripts/jobs/{job_id}/working-transcript`.
   - `backend/transcript/working_state.py` writes utterance-level working
     overrides and syncs the working packet.
4. **Deterministic correction / structural render**
   - `backend/corrections/` and `backend/stage_s/` operate on working-layer
     inputs or derived working copies.
   - These do not mutate RAW.
5. **Snapshots**
   - `backend/transcript_state/snapshot_service.py` captures working
     transcript state, speaker mapping, exhibits, lexicon/regex inputs, export
     metadata, and related lineage state.
   - Rollback restores the captured working authority.
6. **Certification / packaging**
   - Locked snapshots are the only certification source.
   - `backend/api/packaging.py` rebuilds package inputs from snapshot state,
     not from mutable live rows.
7. **Export**
   - Working export renders from current authoritative working transcript.
   - Certified export renders from a locked certification snapshot.

## Mutation Rules

- RAW is immutable after capture.
- WORKING is the only editable transcript layer.
- Speaker mapping is authoritative only through the persisted participant map.
- Diagnostics are read-only.
- Mutation detection consumes diagnostic output but does not mutate transcript
  text.
- Certification never mutates the certified snapshot or a previously certified
  package.

## Accepted AI Edit Flow

1. AI review generates suggestions only.
2. Approval alone does not mutate transcript text.
3. Application writes to the working layer only.
4. Applied changes are provenance-recorded and diff-auditable.

## Provenance Flow

Durable lineage events are recorded in `transcript_provenance_events` for major
working-layer mutations, snapshot actions, export actions, package assembly,
certification freeze, mutation-detection warnings/blocks, and recertification.

Nothing in the working/certification chain should rely on silent state changes.

## Certification Gating

Certification requires:

- a locked snapshot;
- raw transcript integrity verification;
- certification/package validation;
- mutation detection pass over raw vs frozen working snapshot state;
- refusal of non-authoritative offline transcripts.

Unexplained transcript drift blocks certification.

## Pagination / Export Flow

- Transcript semantics are rendered first.
- Pagination and geometry are deterministic backend authorities.
- Export preview and written export must derive from the same canonical render
  path for a given source state.
- Snapshot-based certified export must remain frozen even when the working
  transcript later evolves.
