# AUDIT_STAGE5.md — Stage 5 Certify Wiring Audit

## Baseline
- 464 passed, 1 skipped (run: 2026-05-25)

## Required UI Call Sequence

The UI must perform these calls in order:

1. **Save cert fields** — `PUT /api/depo-meta/jobs/{job_id}` (already done by `_saveCertFields()`)
2. **Create snapshot** — `POST /api/snapshots/jobs/{job_id}` body `{"category": "CERTIFIED"}`
3. **Lock snapshot** — `POST /api/snapshots/{snapshot_id}/lock` (no body)
4. **Assemble package** — `POST /api/packages/jobs/{job_id}` body `{"snapshot_id": "...", "metadata": {}, "freelance": true}`
5. **Certify package** — `POST /api/packages/{package_id}/certify` body `{"metadata": {}}`

The server auto-populates metadata from the DB; an empty `metadata: {}` body is sufficient for both assemble and certify.

## Exact Request/Response Shapes

### Create Snapshot
- `POST /api/snapshots/jobs/{job_id}`
- Request: `{ "category": "CERTIFIED", "note": "", "created_by": "" }`
- Response 200: `{ "snapshot_id": "...", "job_id": "...", "locked": false, ... }`
- Response 404: job not found

### Lock Snapshot
- `POST /api/snapshots/{snapshot_id}/lock`
- Request: (no body)
- Response 200: `{ "snapshot_id": "...", "locked": true, "is_certification_snapshot": true }`
- Response 404: snapshot not found

### Assemble Package
- `POST /api/packages/jobs/{job_id}`
- Request: `{ "snapshot_id": "...", "metadata": {}, "freelance": true }`
- Response 200: `{ "package_id": "...", "job_id": "...", "snapshot_id": "...", "state_hash": "...", "package_state": "DRAFT", "manifest_hash": "...", "created_at": "...", "certified_at": "", "generation_report": { "body_pages": N, ... }, "section_order": [...] }`
- Response 400: snapshot not locked, or snapshot doesn't belong to job
- Response 404: job or snapshot not found

### Certify Package — SUCCESS (200)
```json
{
  "package_id": "...",
  "job_id": "...",
  "snapshot_id": "...",
  "state_hash": "...",
  "package_state": "CERTIFIED",
  "manifest_hash": "sha256-hex-string",
  "created_at": "ISO-datetime",
  "certified_at": "ISO-datetime",
  "package": { ... },
  "certified": true,
  "generation_report": {
    "certification_status": "CERTIFIED",
    "body_pages": N,
    "administrative_pages": N,
    "total_pages": N,
    "validation_passed": true,
    ...
  }
}
```

### Certify Package — VALIDATION FAILURE (422)
```json
{ "detail": "Missing required metadata fields: cause_number, reporter_name; ..." }
```
or for empty body:
```json
{ "detail": "...body..." }
```

### Certify Package — ALREADY CERTIFIED (400)
```json
{ "detail": "Package {id} is CERTIFIED and cannot be certified again." }
```

## Fields to Display from Certify Response
- `package_id` → package identifier
- `manifest_hash` → SHA256-like hash for display
- `certified_at` → lock timestamp
- `package_state` → "CERTIFIED"
- `generation_report.certification_status` → "CERTIFIED"

## UI Changes Required

### api.js
Add: `createSnapshot(jobId, category)`, `lockSnapshot(snapshotId)`,
     `assemblePackage(jobId, snapshotId, metadata)`, `certifyPackage(packageId, metadata)`

### stage_5.js — signTranscript()
Rewrite to: save cert fields → create+lock snapshot → assemble → certify.
Guard double-submit (disable button). On success show real data. On failure show `detail` string.

### stage_5_certify.html
- Add `#certErrorArea` (hidden by default, shown on failure)
- Add `#packageIdDisplay` row to certPostLock data block
- Add `id="manifestHashDisplay"` to SHA256 row (replace hardcoded value)
- Add `id="signBtn"` to the sign button for easy selection

## Reference: `test_packaging_certify_full_workflow` (test_wave20_packaging.py:490)
This is the canonical end-to-end test. The new contract test must mirror it.
