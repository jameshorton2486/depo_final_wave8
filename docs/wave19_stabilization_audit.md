# Wave 19 / 20 Stabilization Audit

Date: 2026-05-25

## Baseline

- Full suite rerun with workspace-local pytest temp root:
  - `.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=.codex_tmp/pytest-wave1920-baseline`
  - Result: `504 passed, 1 skipped`
- A plain `python -m pytest tests -q` run is currently misleading on this machine because pytest cannot create its temp root under `%LOCALAPPDATA%\Temp\pytest-of-james` and fails with `PermissionError [WinError 5]`. The codebase itself is green when `--basetemp` is pinned into the workspace.

## Reality Check Against The Prompt

The Wave 19 / 20 brief is partially stale. Most of the stabilization and trust-hardening work it describes is already built, wired, and covered by tests.

### Operational now

- Stage 1–6 workflow is wired through `backend/app.py`.
- Working transcript authority exists and persists through Stage 3.
- Snapshot creation, lock, rollback, and packaging are live.
- Certified package assembly renders from locked snapshot state.
- Exhibits persist, are snapshot-captured, and feed packaging index generation.
- Export preview, working export, and certified export paths exist.
- Geometry / pagination and Wave 20 packaging tests are already green.

### Still partial or missing

- The README had one stale architectural line: it still described the frontend as using Tailwind CDN. That has been corrected.
- The transcript diff harness remains **spec-only / partial**:
  - The spec exists in `docs/architecture/transcript_engine/transcript_diff_harness_spec.md`.
  - Notes exist in `docs/WAVE10_DIFF_HARNESS_NOTES.md`.
  - No `backend/diagnostics/` implementation is present in the repository.
- Raw transcript immutability is enforced by workflow and repository boundaries, but there is no persisted raw-packet hash verification on load yet.
- Mutation detection that blocks certification on unexplained text loss / speaker drift / timestamp drift is not present as a dedicated enforcement layer.

## Wave 19 Status

### 19A — Workflow Break Elimination

Status: largely operational

Evidence:
- Stage 1 persistence tests: `tests/test_stage1_stabilization.py`
- Stage 2 / transcript round-trip tests: `tests/test_transcripts_api.py`
- Stage 3 snapshot rollback tests: `tests/test_wave18_5_snapshots.py`
- Stage 5 certification path tests: `tests/test_stage5_certify_contract.py`
- Stage 6 export tests: `tests/test_wave18_export.py`, `tests/test_wave20_packaging.py`

Remaining validation need:
- Real human walkthrough remains valuable, but there is no current test evidence of a broad workflow break requiring immediate code changes.

### 19B — Transcript Integrity Protection

Status: partial

What exists:
- RAW vs WORKING layer separation
- Working overrides stored separately from canonical RAW utterances
- Snapshot state hashing for export-equivalent state
- Provenance events for working transcript saves, AI apply, snapshots, and export

What is still missing:
- persisted raw integrity hash checked on load
- implemented diff harness endpoint / tool
- explicit mutation-detection blocker on unexplained layer drift

### 19C — Workspace Stability

Status: operational with known observational audit history

Evidence:
- Stage 3 stabilization audit already exists:
  - `docs/audits/STAGE3_WORKSPACE_STABILIZATION_AUDIT_2026-05-25.md`
- Working transcript save / reload / rollback / export tests are green.

## Wave 20 Status

### 20A — Certification Integrity

Status: operational

Evidence:
- Locked snapshot enforcement in `backend/transcript_state/`
- Package state transitions in `backend/packaging/`
- Tests:
  - `tests/test_stage5_certify_contract.py`
  - `tests/test_wave20_packaging.py`

### 20B — Export Validation

Status: operational but not yet framed as a single explicit “validation system” module

Evidence:
- Preview and export share canonical render paths in `backend/api/transcripts.py`
- Pagination and geometry tests:
  - `tests/test_wave19_pagination_geometry.py`
- Export file tests:
  - `tests/test_wave18_export.py`
- Packaging validation tests:
  - `tests/test_wave20_packaging.py`

Gap:
- No single named “export validation pass” orchestrator exists. The guarantees are spread across the renderer, paginator, packaging validation, and tests.

### 20C — Deterministic UFM Formatting

Status: operational

Evidence:
- Geometry authority lives in `backend/geometry/profile.py`
- Pagination tests are green
- Export/package paths are green

Open decision remains:
- exact UFM measurement conflict already documented elsewhere; not a new break introduced by this audit.

## Immediate Conclusions

1. The repository is not in a “Wave 19/20 not yet built” state.
2. The highest-value missing subsystem from the prompt is the transcript diff / mutation-detection layer.
3. Before building that layer, the repo needed only a small documentation correction, not another broad workflow refactor.

## Recommended Next Step

If continuing under the Wave 19 / 20 brief, the next concrete engineering target should be:

1. add raw packet hash capture + verification
2. implement `backend/diagnostics/` per the transcript diff harness spec
3. add mutation-detection rules that can block certification when unexplained drift is present

That is the remaining trust-hardening work that is not already operational.
