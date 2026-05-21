# Wave 5 — Canonical Models + Case Workspace

Status: complete

## Why

The frontend, the database, and the parsers each spoke a slightly different
vocabulary for the same data (`ufmCause` vs `case_number_value` vs prototype
shapes). Wave 5 introduces one canonical vocabulary and a real on-disk
workspace, without destabilizing the working parsers or persistence.

## What was built

### 1. Canonical data models — `backend/models/canonical.py`

Pydantic models that are the single source of truth for domain entity shapes:
`CaseIdentity`, `Participant`, `ReporterCredentials`, `DepositionSession`,
`KeyTerm`, and the `WorkspaceState` enum. Two composites — `CaseWorkspacePacket`
and `SessionPacket` — are assembled FROM these pieces (deliberately not giant
nested mega-objects). The base model forbids unknown fields, so schema drift
is caught immediately instead of silently spreading.

`WorkspaceState`: draft -> active -> processing -> review -> certified -> archived.

### 2. Parsers return canonical models

`ParsedNOD` gained a `to_canonical()` method that re-shapes already-extracted
fields into the canonical models. No parsing logic changed — `to_frontend_dict()`
still works exactly as before for the existing frontend code path. All 86
pre-existing tests stay green.

### 3. Workspace service — `backend/services/workspace.py`

Owns the on-disk artifact store. The SQLite database remains the index/source
of truth for *records*; the folder tree is the source of truth for *files*.

Tree layout:

    Documents/DEPO-PRO/
      <Reporter_Name>/
        <YYYY>/
          <YYYY-MM>/
            <case_slug>/
              case_packet.json
              <YYYY-MM-DD - witness-slug>/
                session.json
                raw/  working/  final/  exhibits/  logs/

- Root defaults to `Documents/DEPO-PRO` (outside the app install dir, so
  transcripts survive reinstalls). Configurable later via Settings.
- `initialize_case_workspace()` — called on first Save. Builds the tree,
  writes canonical `case_packet.json` + `session.json`, creates empty
  manifests, sets `workspace_state = draft`.
- `activate_session_workspace()` — called on "Proceed to Transcripts Engine".
  Transitions draft -> active, initializes transcript-processing manifests.
- `write_keyterms_file()` — writes `keyterms.json` into the session's `raw/`
  folder (the immutable source layer). Closes the Stage 2 blocker.
- `archive_workspace()` — soft-archive only. Workspaces are NEVER hard-deleted;
  full archival is a documented stub for a later wave.

Slug sanitization strips Windows-illegal characters, avoids reserved device
names (CON, LPT1, ...), caps length for path-safety, and appends `(2)`/`(3)`
suffixes when the same witness is deposed twice on the same date.

### 4. Workspace API — `POST /api/intake/workspace`

Creates the workspace tree on Save: accepts the frontend's UFM form state,
builds canonical models, writes the tree + packets, and drops `keyterms.json`
into the session `raw/` folder. Returns the created paths and `workspace_state`.

## Design decisions held

- Parsers never write files directly — file output routes through the
  workspace service.
- Every packet JSON carries `case_id` / `session_id`, so a folder renamed in
  the OS file explorer can still be re-linked to its database record.
- `api.js`'s translation layer is kept as-is — documented as the known seam
  to collapse later, once both ends speak canonical names.

## Testing

`tests/test_workspace.py` — 24 tests: canonical model serialization and
validation, slug sanitization (illegal chars, reserved names, length caps,
versus handling), tree creation, manifest creation, draft->active transition,
collision suffixes, undated-session handling, archival, the keyterms file,
the NOD parser's `to_canonical()`, and the workspace API endpoint.

Full suite: 110 tests passing (86 prior + 24 new).
