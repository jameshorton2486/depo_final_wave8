> DOCUMENT STATUS: CANONICAL CURRENT-STATE GOVERNANCE
> Scope: registry of live documentation classes and their current members.
> This file tells agents which docs govern code, which docs are references, and which docs are operational logs only.

# ACTIVE_SPEC_REGISTRY.md

## Canonical Root Authorities

- `CLAUDE.md`
- `README.md`
- `docs/wave_status_report.md`
- `docs/ufm_schema_v1.md`
- `docs/SYSTEM_OWNERSHIP.md`
- `docs/TRANSCRIPT_ORCHESTRATION.md`
- `docs/EXPORT_AND_CERTIFICATION_PIPELINE.md`
- `docs/ACTIVE_SPEC_REGISTRY.md`
- `docs/BLOCKERS.md`
- `docs/GOVERNANCE_MAINTENANCE_RULES.md`

## Canonical Subsystem Specs

- `docs/architecture/transcript_engine/TRANSCRIPT_ENGINE_RULES.md`
- `docs/architecture/transcript_engine/deterministic_correction_engine_spec.md`
- `docs/architecture/transcript_engine/transcript_diff_harness_spec.md`

## Active Subsystem Specs

- `docs/nod_parser_spec.md`
- `docs/DEPO-PRO_UFM_Data_Dictionary_v2.md`
- `docs/wave19_ufm_layout.md`
- `docs/wave20_packaging.md`

These remain live subsystem specs even though they retain some historical build
language. They should be reconciled against code before use when a section reads
as status reporting rather than behavior authority.

## Active References

- `development_workflow.md`
- `docs/development_workflow.md`
- `docs/DEPO-PRO_Field_Template_Matrix.md`
- `docs/architecture/transcript_engine/README.md`
- `docs/examples/README.md`

## Temporary Operational Documents

- `docs/audits/MVP_WORKFLOW_VALIDATION_CHECKLIST.md`
- `docs/audits/REAL_WORLD_VALIDATION_LOG.md`

These documents are operational instruments, not ownership or architecture
contracts. They must be reviewed after the workflow or stabilization activity
they track.

## Superseded Active Documents Still Present

- `docs/audits/STAGE3_WORKSPACE_STABILIZATION_AUDIT_2026-05-25.md`
- `backend/corrections/WAVE10_FOUNDATION_NOTES.md`

These remain in-place for provenance but are not safe current authority.

## Archived Documents

Everything under `docs/archive/` is historical only.

## Review Expectations

- Review **canonical root authorities** and **canonical subsystem specs** when
  their owned subsystem changes materially.
- Review **active subsystem specs** whenever a section starts reading like old
  status reporting instead of current behavior authority.
- Review **temporary operational documents** after the operational event they
  track; they should be superseded or archived once they stop serving a live
  workflow.
- Review **superseded active documents** periodically and move them to archive
  when they no longer need to remain in active locations for provenance.

## Usage Rule

When implementing or reviewing behavior:

1. read `CLAUDE.md`;
2. read the matching canonical root authority;
3. read the matching canonical subsystem spec or active subsystem spec;
4. use active references only for setup or operational context;
5. never use archived docs as current authority.

If code and docs diverge, reconcile against the live code and the matching
canonical contract before acting.
