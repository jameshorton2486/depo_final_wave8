# Documentation Usage Report

Audit basis: all tracked `*.md` files. Runtime code does not import Markdown, so this report classifies documents by governance, audit, and historical value rather than interpreter reachability.

## Summary

- Tracked Markdown files: **79**
- Runtime-required Markdown files: **0**
- Governance-required: active control/spec docs
- Audit-required: audit logs, checkpoints, cleanup/UFM investigations
- Historical-reference: archived phase notes and scratch investigations
- Obsolete with proof: **none**

## Governance Required

These are actively referenced by governance or active specs and should be kept.

### Root / top-level

- `CLAUDE.md`
- `README.md`
- `development_workflow.md`

### Active docs

- `docs/ACTIVE_SPEC_REGISTRY.md`
- `docs/BLOCKERS.md`
- `docs/DEPO-PRO_Field_Template_Matrix.md`
- `docs/DEPO-PRO_UFM_Data_Dictionary_v2.md`
- `docs/EXPORT_AND_CERTIFICATION_PIPELINE.md`
- `docs/GOVERNANCE_MAINTENANCE_RULES.md`
- `docs/SYSTEM_OWNERSHIP.md`
- `docs/TRANSCRIPT_ORCHESTRATION.md`
- `docs/development_workflow.md`
- `docs/nod_parser_spec.md`
- `docs/ufm_schema_v1.md`
- `docs/wave19_ufm_layout.md`
- `docs/wave20_packaging.md`
- `docs/wave_status_report.md`

### Architecture specs

- `docs/architecture/transcript_engine/README.md`
- `docs/architecture/transcript_engine/TRANSCRIPT_ENGINE_RULES.md`
- `docs/architecture/transcript_engine/deterministic_correction_engine_spec.md`
- `docs/architecture/transcript_engine/transcript_diff_harness_spec.md`

### Governance-evidence references

- `backend/corrections/WAVE10_FOUNDATION_NOTES.md`

Evidence:

- `CLAUDE.md` explicitly distinguishes `development_workflow.md` vs `docs/development_workflow.md`
- `docs/ACTIVE_SPEC_REGISTRY.md` references `development_workflow.md`, `docs/development_workflow.md`, and `backend/corrections/WAVE10_FOUNDATION_NOTES.md`

## Audit Required

These docs record active audits, findings, or handoff/re-entry state and are safe to track.

### Current audit folders

- `docs/audits/*.md`
- `docs/ufm_audit/*.md`
- `docs/ufm_audit/reference_templates/README.md`

### Why keep them

- They capture current UFM/cert-pipeline findings
- They document remediation order and open questions
- They are synthetic governance/audit artifacts, not runtime clutter

## Historical Reference

These files are not runtime-required, but they are intentionally retained project history.

### Archived phase history

- `docs/archive/completed_phases/*.md`
- `docs/archive/investigations/*.md`
- `docs/archive/ui_scratch/*.md`
- `docs/archive/README.md`

### Example docs

- `docs/examples/README.md`

Recommendation:

- KEEP in archive unless you deliberately move them to external documentation storage

## Obsolete

No tracked Markdown file met the proof bar for `OBSOLETE`.

Notes on common “looks duplicate” cases:

- `development_workflow.md` vs `docs/development_workflow.md`
  - not duplicates; they own different concerns and are explicitly distinguished in `CLAUDE.md`
- `backend/corrections/WAVE10_FOUNDATION_NOTES.md` vs `docs/archive/completed_phases/WAVE10_FOUNDATION_NOTES.md`
  - near-duplicate content family; archive copy is historical, backend copy is still explicitly referenced by active spec registry

## Documentation Recommendations

- KEEP active governance/spec docs
- KEEP current audit docs
- KEEP archive docs unless you intentionally archive them outside the repo
- Do not delete Markdown purely because it is not runtime-loaded; most value here is governance/historical
