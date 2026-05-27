> DOCUMENT STATUS: TEMPORARY OPERATIONAL DOCUMENT
> Scope: human validation checklist for current workflow testing.
> This document is an operational checklist, not architecture authority.

# MVP Workflow Validation Checklist

Date: 2026-05-25  
Repository: DEPO-PRO  
Purpose: Human browser-level validation of the stabilized MVP workflow without changing transcript authority, snapshot authority, or raw transcript immutability.

## Scope

This checklist is for manual workflow validation after the Stage 1, Stage 2, and Stage 3 stabilization passes.

Primary goals:

- Confirm deterministic persistence
- Confirm transcript lineage and legal integrity
- Confirm save/reload clarity
- Confirm snapshot and certification authority
- Confirm export behavior matches the intended authority

## Validation Rules

- Use realistic case/session data whenever possible.
- Do not validate against mocked transcript expectations alone.
- Treat RAW transcript state as immutable throughout.
- Treat the WORKING transcript as the only editable transcript layer.
- Treat locked certification snapshots as the only certified authority.
- Record defects with exact stage, action, observed result, expected result, and timestamp.

## Test Environment Prep

Before starting:

- Start the DEPO-PRO backend successfully.
- Confirm the frontend loads and stage navigation works.
- Confirm the current database has migrations through `schema_v12`.
- Confirm a test case can be created and a session can be saved.
- Confirm at least one test audio file and one realistic NOD/sample intake note are available.
- Confirm a writable export destination is available.

## Stage 1 — Intake Metadata

### Metadata Save / Reload

- Create a new case and fill all primary Stage 1 fields.
- Save Stage 1.
- Reload the app.
- Reopen the same case.
- Verify all saved metadata reloads correctly.
- Verify raw intake notes reload correctly.
- Verify Stage 1 keyterms reload correctly.
- Verify parser metadata reloads correctly.

Expected:

- Case/session/reporter data reloads exactly.
- No stale values from another case appear.
- Save status and case binding remain coherent downstream.

### Case Switching

- Open Case A.
- Open Case B.
- Return to Case A.
- Verify Stage 1 values match the correct case each time.

Expected:

- No cross-case contamination.
- No stale reporter/session/keyterm values bleed across cases.

### NOD Parsing

- Upload or parse a realistic NOD.
- Verify parsed witness, caption, cause number, attorneys, firms, and location metadata populate as expected.

Expected:

- Parsed metadata is applied only to the active case.
- No parser result silently disappears after save/reload.

### Keyterm Persistence

- Save Stage 1 after parsing.
- Verify the canonical case keyterms file exists and reloads downstream.
- Proceed to Stage 2/3 and verify terminology context follows the case.

Expected:

- Keyterms persist in the authoritative case path.
- No duplicate or malformed keyterm behavior appears after reload.

## Stage 2 — Transcript Generation

### Transcript Generation

- Upload one transcript file with a valid saved case and session.
- Verify the upload is accepted only when case/session are valid.
- Wait for completion.

Expected:

- Transcript job binds to the intended case and session.
- Transcript job completes without losing metadata context.

### Deepgram Terminology Recognition

- Use a transcript with known keyterms, names, firms, and legal terms.
- Verify the resulting transcript reflects expected terminology quality.

Expected:

- Stage 1 keyterms clearly influence terminology handling where available.
- No evidence of a missing keyterm path.

### Session Binding

- Attempt upload with no case/session.
- Attempt upload with mismatched case/session.
- Attempt upload with valid binding.

Expected:

- Invalid uploads are blocked with explicit errors.
- Valid upload proceeds normally.

### Diarization Quality

- Verify speaker counts and raw speaker IDs appear after ingestion.
- Open the completed transcript in Stage 3.

Expected:

- Raw diarization data is preserved.
- No speaker-authority actions occur in Stage 2.

## Stage 3 — Workspace

### Editing

- Open a transcript in Stage 3.
- Edit multiple lines.
- Verify visible save status transitions through unsaved, saving, and saved.
- Use the explicit `Save Transcript` button.
- Use `Ctrl+S`.

Expected:

- Save state is obvious at all times.
- Edits persist to the working transcript layer.

### Save / Reload

- Make edits and save.
- Reload transcript from the Stage 3 reload control.
- Reload the browser/app.
- Reopen the same transcript.

Expected:

- Saved edits reload identically.
- Reload behavior is clearly distinguishable from snapshot restore.

### Unsaved Change Protection

- Make an edit without saving.
- Try browser refresh.
- Try case switch.
- Try transcript switch.
- Try leaving Stage 3.

Expected:

- User receives an unsaved-changes warning only when applicable.
- No silent loss of unsaved work.

### Snapshots

- Create a manual snapshot.
- Make further edits.
- Restore the earlier snapshot.
- Verify a new rollback snapshot is recorded.

Expected:

- Snapshot history is visible.
- Snapshot restore rolls back the working transcript and speaker mapping.
- Restore events appear in provenance.

### AI Approve / Apply

- Generate or load AI suggestions.
- Approve a suggestion.
- Verify transcript text does not change.
- Apply the approved suggestion explicitly.
- Reload transcript.

Expected:

- Approval alone does not mutate text.
- Apply changes only the working transcript.
- Raw transcript remains unchanged.
- Provenance records both approval and apply events.

### Speaker Mapping

- Load speaker mapping.
- Save reporter-confirmed names/roles.
- Reload transcript and reopen the workspace.

Expected:

- Speaker mappings persist and remain authoritative.
- Raw speaker IDs remain intact internally.

### Provenance

- Review the provenance panel after manual edits, regex edits, snapshot create/restore, AI apply, and export.
- Reload the workspace.

Expected:

- Provenance reloads from durable backend state.
- Major transcript mutations are auditable.

### Export Preview

- Refresh export preview before and after Stage 3 edits.
- Verify preview reflects saved working transcript changes.

Expected:

- Preview tracks current working transcript authority.
- Preview clearly distinguishes working-state context from certified export authority.

## Stage 4 — Exhibits

### Exhibit Persistence

- Add or modify exhibit-related data.
- Navigate away and back.

Expected:

- Exhibit state behaves consistently with the current implementation.
- No Stage 3 transcript corruption occurs due to exhibit actions.

### Pagination Interactions

- Review transcript/exhibit workflow after Stage 3 edits and speaker changes.

Expected:

- No malformed transcript structure appears when moving between stages.

## Stage 5 — Certification

### Certification Freeze

- Complete Stage 5 certification with a valid transcript.
- Verify a certification snapshot is created and locked.
- Verify package certification succeeds.

Expected:

- Certification binds to a locked snapshot.
- Certified state becomes immutable.

### Snapshot Locking

- Inspect snapshot history after certification.

Expected:

- Certification snapshot is visibly locked and distinguishable from manual snapshots.

### Rollback Protection

- Attempt to continue editing after certification.
- Verify any protected workflow messaging behaves correctly.

Expected:

- Certified authority is not confused with working authority.

## Stage 6 — Export

### DOCX Export

- Export DOCX from a stabilized transcript.
- Verify file is produced successfully.

Expected:

- Export path is valid.
- Output corresponds to the expected authority source.

### PDF Export

- Export PDF after certification.

Expected:

- Export completes without mutating transcript state.

### Formatting Consistency

- Compare Stage 3 transcript state, export preview, and exported file.
- Review Q/A indentation, line structure, spacing, and pagination behavior.

Expected:

- Export uses backend formatting authority.
- No obvious preview/export divergence beyond intentionally labeled working-vs-certified differences.

### Certified Export Validation

- After certification, export again.
- Verify whether export is using the locked snapshot authority.

Expected:

- Certified snapshot export is clearly identified.
- No drift from the locked snapshot body.

## Sign-Off Matrix

Use this for each validation pass:

| Area | Tester | Date | Pass/Fail | Notes |
| --- | --- | --- | --- | --- |
| Stage 1 |  |  |  |  |
| Stage 2 |  |  |  |  |
| Stage 3 |  |  |  |  |
| Stage 4 |  |  |  |  |
| Stage 5 |  |  |  |  |
| Stage 6 |  |  |  |  |

## Defect Logging Minimum

For every defect found, capture:

- Stage
- Case ID
- Session ID
- Transcript job ID
- Snapshot ID if relevant
- Exact user action
- Expected result
- Actual result
- Whether RAW, WORKING, SNAPSHOT, or EXPORT authority was affected
- Screenshot or console log when available
