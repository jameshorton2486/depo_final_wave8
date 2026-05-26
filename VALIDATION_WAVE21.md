# VALIDATION_WAVE21.md — Wave 21 Self-Validation Pass

Date: 2026-05-25
Branch: `mvp-e2e-validation`

## Scope

This is a programmatic pre-flight validation pass for Wave 21.

It is **not** a substitute for James's real-data run. The offline
provider mode verifies workflow integrity, persistence, snapshotting,
certification refusal, and export authority without requiring a live
Deepgram key or real media. It does **not** validate real-audio quality,
real NOD nuance, or visual/operational reporter trust on its own.

## Verification Basis

Final suite result after Wave 21:
- `504 passed`
- `1 skipped`
- `33 warnings`

Representative evidence used in this self-pass:
- `tests/test_stage1_stabilization.py`
- `tests/test_nod_api.py`
- `tests/test_nod_parser.py`
- `tests/test_nod_intelligence.py`
- `tests/test_transcripts_api.py`
- `tests/test_speaker_mapping.py`
- `tests/test_exhibits_api.py`
- `tests/test_wave18_5_snapshots.py`
- `tests/test_stage5_certify_contract.py`
- `tests/test_wave20_packaging.py`
- `tests/test_wave17_offline_test_mode.py`

## Stage 1

### Metadata Trust
- `VERIFIED`
- Evidence:
  - cases, sessions, and reporters persistence tests pass
  - Stage 1 stabilization tests pass

### NOD Parsing
- `VERIFIED`
- Evidence:
  - parser API, parser core, and parser intelligence suites pass

### Keyterm Validation
- `VERIFIED`
- Evidence:
  - Stage 1 stabilization + transcript ingestion path loads case keyterms deterministically

## Stage 2

### Transcript Generation
- `VERIFIED`
- Evidence:
  - transcript upload / processing / persistence / reload API tests pass in offline mode

### Deepgram Terminology Quality
- `NEEDS-MANUAL`
- Reason:
  - offline mode validates workflow only, not live Deepgram recognition quality

### Session Binding
- `VERIFIED`
- Evidence:
  - upload requires valid case/session
  - legacy job re-bind path now exists and is tested

## Stage 3

### Editing
- `VERIFIED`
- Evidence:
  - working transcript save/reload tests pass

### Save / Reload
- `VERIFIED`
- Evidence:
  - authoritative working transcript persistence tests pass

### Snapshots
- `VERIFIED`
- Evidence:
  - snapshot capture and rollback tests pass

### Provenance
- `VERIFIED`
- Evidence:
  - working transcript, snapshot, packaging, and exhibit provenance tests pass

### AI Apply
- `VERIFIED`
- Evidence:
  - approval-vs-apply separation and working-only mutation tests pass

### Speaker Mapping
- `VERIFIED`
- Evidence:
  - speaker mapping persistence and apply tests pass

## Stage 4

### Exhibit Persistence
- `VERIFIED`
- Evidence:
  - exhibit CRUD + reload tests pass

### Exhibit Anchors
- `VERIFIED`
- Evidence:
  - anchor-by-utterance persistence and transcript-edit stability tests pass

### Exhibit Rollback
- `VERIFIED`
- Evidence:
  - snapshot restore returns the exhibit set and ordering

### Exhibit Certification
- `VERIFIED`
- Evidence:
  - packaging index generation uses frozen snapshot exhibit data

## Stage 5

### Certification Freeze
- `VERIFIED`
- Evidence:
  - snapshot lock + assemble + certify tests pass

### Recertification Lineage
- `VERIFIED`
- Evidence:
  - old certified package remains immutable while new certification creates new lineage

### Snapshot Locking
- `VERIFIED`
- Evidence:
  - locked snapshot package path remains deterministic

## Stage 6

### Working Export
- `VERIFIED`
- Evidence:
  - working export API tests pass

### Certified Export
- `VERIFIED`
- Evidence:
  - export-from-locked-snapshot tests pass

### Export Consistency
- `VERIFIED`
- Evidence:
  - packaging/export consistency tests pass

### Formatting Consistency
- `NEEDS-MANUAL`
- Reason:
  - visual DOCX/PDF judgment still requires human review against real output

## Offline Provider Safety

- `VERIFIED`
- Evidence:
  - explicit runtime provider switch forces offline mode even when a key is present
  - offline-produced jobs surface as non-authoritative
  - packaging/certification chain refuses offline validation transcripts

## Failed Items

None during the Wave 21 self-pass.

## Required Manual Follow-Up

These items still require James with real data:
- live Deepgram terminology quality
- representative real NOD parsing judgment
- browser-level UX trust and operator friction
- visual DOCX/PDF formatting review
- end-to-end court-reporter workflow confidence using real jobs and exhibits

## Overall Result

Wave 21 pre-flight status: `PASS`

Meaning:
- the repo is now operational for offline MVP workflow validation
- the legal trust boundaries are enforced programmatically
- the next step is a real-data manual validation run, not more speculative architecture work
