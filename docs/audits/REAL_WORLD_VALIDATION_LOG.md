> DOCUMENT STATUS: TEMPORARY OPERATIONAL DOCUMENT
> Scope: active human validation log and defect ledger for real-world MVP testing.
> This document records observations. It does not define architecture or subsystem ownership.

# REAL WORLD VALIDATION LOG

Purpose: operational MVP validation for DEPO-PRO after the Stage 4 / Stage 5 authority stabilization checkpoint.

Scope:
- real end-to-end reporter workflows
- legal lineage trust checks
- persistence and reload confidence
- certification and export validation

Rules:
- log defects against the exact stage where first observed
- record whether the issue affects legal trust or only UX clarity
- attach screenshots and console logs when available
- distinguish working-state behavior from certified-state behavior

## Stage 1

### Metadata Trust
- [ ] Create a new case and save Stage 1 metadata.
- [ ] Reload the case and confirm all saved metadata rehydrates correctly.
- [ ] Switch to another case and back again.
- [ ] Confirm no cross-case contamination appears in Stage 1 fields.

### NOD Parsing
- [ ] Parse representative NOD input.
- [ ] Verify parsed fields land in the expected Stage 1 form controls.
- [ ] Confirm parser metadata survives save and reload.

### Keyterm Validation
- [ ] Confirm keyterms persist after Stage 1 save.
- [ ] Confirm case-level keyterms are present for downstream use.
- [ ] Confirm terminology survives case reload and app restart.

### Operator Transparency
- [ ] Case-context banner: loading an existing case shows the EDITING
      banner with cause number and last-saved timestamp; clicking
      "Start New Case" clears state and re-renders as NEW CASE.
- [ ] Three-state badges: parser-populated fields render AUTO-POPULATED
      (amber); clicking "Confirm" promotes to ✓ CONFIRMED (green);
      editing a confirmed field reverts to AUTO-POPULATED; reloading
      preserves confirmations.
- [ ] Missing-field enumeration: validation summary lists each missing
      field by label and the header reads `{N} of 16 required fields
      populated` (no graded score / risk indicator).
- [ ] Deepgram Request Preview: opens read-only modal; `deepgram_request`
      matches `DEEPGRAM_PARAMS`; no Save / Apply affordance.
- [ ] UFM Payload Preview: opens read-only modal; shows `ufm_metadata`,
      `field_sources`, `field_confirmations`, `missing_required_fields`.

### Stage 1 UX Polish
- [ ] Save Intake button is visible on first paint of Stage 1
- [ ] Clicking Save Intake on a new case creates a backend record and
      updates banner from State A to State B
- [ ] Editing any field after save transitions banner from State B to
      State C; saving again returns to State B
- [ ] View UFM Payload on an unsaved case shows the inline Save Now
      message, not a 404 error
- [ ] Save Now inside the UFM modal completes the save and renders the
      preview without closing the modal
- [ ] Cancel inside the UFM modal closes without saving and without errors
- [ ] Pasted-notes placeholder is visible when the textarea is empty
- [ ] Helper text under the textarea is visible at all times
- [ ] Parsing notes with no labels shows exactly one informational toast
      (not three)
- [ ] Parsing notes with labels shows exactly one success toast with the
      field count
- [ ] Deepgram Preview modal still works on saved cases (regression check
      from Phase 4)
- [ ] Existing 3-state badges (AUTO · CONFIRM? / MISSING) are unchanged

## Stage 2

### Transcript Generation
- [ ] Upload audio with valid case/session binding.
- [ ] Confirm ingestion completes and transcript job persists.
- [ ] Confirm diarization summary appears without speaker-authority conflicts.

### Deepgram Terminology Quality
- [ ] Validate expected domain keyterms appear in transcript output.
- [ ] Confirm terminology comes from the authoritative keyterm pipeline.

### Session Binding
- [ ] Confirm uploads fail when case/session binding is invalid.
- [ ] Confirm successful uploads inherit the correct Stage 1 context.

## Stage 3

### Editing
- [ ] Edit transcript text in Workspace.
- [ ] Confirm explicit save works.
- [ ] Confirm unsaved warnings appear when leaving with dirty state.

### Save / Reload
- [ ] Save working transcript edits.
- [ ] Reload transcript and confirm edits persist.
- [ ] Reopen app and confirm edits persist.

### Snapshots
- [ ] Create manual snapshot.
- [ ] Make further edits.
- [ ] Restore snapshot and confirm transcript working state is restored.

### Provenance
- [ ] Confirm manual edits create durable provenance entries.
- [ ] Confirm snapshot restore creates provenance entries.

### AI Apply
- [ ] Approve an AI suggestion.
- [ ] Confirm approval alone does not mutate transcript text.
- [ ] Apply approved suggestion explicitly.
- [ ] Confirm working transcript changes and raw transcript remains unchanged.

### Speaker Mapping
- [ ] Save speaker mapping in Stage 3.
- [ ] Reload and confirm mapping persists.
- [ ] Confirm export uses saved mapping.

## Stage 4

### Exhibit Persistence
- [ ] Create exhibit anchors against transcript utterances.
- [ ] Reload Stage 4 and confirm exhibits persist.
- [ ] Restart app and confirm exhibits persist.

### Exhibit Anchors
- [ ] Jump from exhibit to transcript anchor.
- [ ] Edit transcript working text and confirm anchor remains stable.
- [ ] Confirm anchor survives pagination changes.

### Exhibit Rollback
- [ ] Create exhibit, capture snapshot, modify exhibits, rollback snapshot.
- [ ] Confirm exhibit set and ordering restore correctly.

### Exhibit Certification
- [ ] Certify a package with exhibits present.
- [ ] Confirm certified lineage preserves exhibit references.
- [ ] Confirm later exhibit edits do not mutate older certified packages.

## Stage 5

### Certification Freeze
- [ ] Create certification snapshot and certify package.
- [ ] Confirm Stage 5 clearly distinguishes working transcript from certified lineage.

### Recertification Lineage
- [ ] Edit working transcript after an existing certification.
- [ ] Create a new certification.
- [ ] Confirm older certified package remains immutable.
- [ ] Confirm newer certification appears as a separate lineage entry.

### Snapshot Locking
- [ ] Confirm locked snapshots remain immutable.
- [ ] Confirm rollback does not mutate older certified packages.

## Stage 6

### Working Export
- [ ] Export current working transcript.
- [ ] Confirm output reflects current working state.
- [ ] Confirm export is clearly labeled non-certified where applicable.

### Certified Export
- [ ] Export using certified snapshot source.
- [ ] Confirm output matches the locked certified snapshot.
- [ ] Confirm later working edits do not change prior certified export output.

### Export Consistency
- [ ] Compare export preview with actual working export.
- [ ] Compare certified export with certified package contents.

### Formatting Consistency
- [ ] Validate Q/A formatting.
- [ ] Validate pagination consistency.
- [ ] Validate exhibit index presence when exhibits exist.

## Defect Log Template

### Defect
- Stage:
- Title:
- Repro steps:
- Expected:
- Actual:
- Severity: `LOW` | `MEDIUM` | `HIGH` | `CRITICAL`
- Trust risk: `NONE` | `UX` | `DATA` | `LEGAL`
- Screenshot:
- Console logs:
- Notes:

## Session Notes

### Validation Session
- Date:
- Tester:
- Branch:
- Build / commit:
- Cases used:
- Transcript jobs used:
- Result summary:

### Validation Session
- Date: 2026-05-25
- Tester: Codex CLI
- Branch: `mvp-e2e-validation`
- Build / commit: `fd77194`
- Cases used: synthetic validation case via localhost API
- Transcript jobs used: synthetic upload attempt plus existing live job inventory check
- Result summary:
  - local FastAPI app started successfully on `http://127.0.0.1:8765`
  - `/api/health` returned healthy status
  - Stage 4/5 targeted verification suite passed locally before browser validation attempt
  - synthetic live upload validation was blocked because the environment used a real Deepgram provider and correctly rejected fake audio bytes as corrupt media
  - no Stage 4/5 regression was identified from that runtime limitation

### Defect
- Stage: `2`
- Title: Synthetic validation upload fails when live Deepgram key is active
- Repro steps:
  - start local app against real environment
  - upload fake/synthetic `.mp3` bytes intended only for offline fallback validation
- Expected:
  - offline fallback path for synthetic validation media
- Actual:
  - live Deepgram path was used and returned HTTP 400 corrupt/unsupported audio
- Severity: `LOW`
- Trust risk: `NONE`
- Screenshot:
- Console logs:
  - `DeepgramError: Deepgram API HTTP 400: Bad Request: failed to process audio: corrupt or unsupported data`
- Notes:
  - this is an environment/runtime validation constraint, not a Stage 4/5 authority regression
  - use a real audio sample or force offline provider mode for synthetic MVP smoke runs
