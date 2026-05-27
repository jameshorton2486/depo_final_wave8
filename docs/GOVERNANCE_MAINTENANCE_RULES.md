> DOCUMENT STATUS: CANONICAL CURRENT-STATE GOVERNANCE
> Scope: long-term documentation lifecycle control, governance-drift prevention, and AI-agent authority maintenance.
> Use this document to decide how DEPO-PRO docs are promoted, reviewed, downgraded, superseded, and archived.

# GOVERNANCE_MAINTENANCE_RULES.md

## Purpose

This document defines how DEPO-PRO documentation is maintained so governance
does not decay back into stale authority, accidental duplicate ownership, or
unsafe AI-agent guidance.

It is a lifecycle document, not a subsystem design spec.

## A. Document Lifecycle Rules

### Lifecycle stages

- **Draft**: a work-in-progress note that is not yet authority.
- **Active Reference**: setup, onboarding, commands, or operational guidance.
- **Active Subsystem Spec**: a live subsystem behavior/spec document that still
  governs implementation details.
- **Canonical Contract**: the current authoritative contract for a concern.
- **Temporary Operational Document**: a live checklist, validation log, or
  active investigation instrument.
- **Superseded Active Document**: retained in place for provenance but not safe
  as current authority.
- **Historical Archive**: material under `docs/archive/`; never current
  authority.

### Promotion rules

- Promote a document to **Canonical Contract** only when it owns one concern
  clearly and is reconciled against live code.
- Promote a document to **Active Subsystem Spec** only when it still governs a
  live subsystem and does not duplicate a canonical contract.
- Promote a document to **Active Reference** only when it helps setup or
  operations without asserting architecture authority.

### Downgrade rules

- Downgrade a document from **Canonical Contract** or **Active Subsystem Spec**
  when code has moved beyond it and another current document now owns the
  concern.
- Downgrade a document to **Superseded Active Document** when it still has
  provenance value but is unsafe as current truth.
- Downgrade a document to **Historical Archive** when it no longer guides any
  active workflow and is kept only for history.

### Archive rules

- Archive a document when its useful content is historical rather than
  operational.
- Archive via a governed archival pass, not ad hoc deletion.
- Never archive the only current owner of a concern without a replacement
  canonical contract already in place.

### Review expectations

- Canonical contracts and active subsystem specs must be reviewed whenever the
  owning subsystem changes materially.
- Temporary operational docs must be reviewed after the operational event they
  track.
- Superseded active docs must be reviewed periodically to determine whether
  they can move into `docs/archive/`.

## B. Governance Decay Rules

### Staleness indicators

Treat a document as drifting when it contains:

- stale status claims;
- stale test counts;
- stale API paths;
- stale schema versions;
- stale “next pass”, “not wired”, or “not started” language;
- stale ownership references;
- references to archived docs as if they were current;
- references to missing files or modules.

### Mandatory review triggers

Review the owning document when any of these happen:

- a router path changes;
- a canonical owner module changes;
- a snapshot/export/certification flow changes;
- a new transcript integrity gate is introduced;
- a temporary operational doc persists beyond the operational task it tracks;
- an AI agent or human audit identifies doc/code drift.

## C. Temporary Doc Expiration Rules

Temporary operational documents must not become architecture authority by
neglect.

- Validation logs, stabilization audits, and active investigation docs are
  temporary by default.
- When their tracked issue is resolved or replaced, review them for either:
  - continued operational use;
  - superseded-in-place marking; or
  - archival.
- A temporary operational document that starts to contradict current code must
  receive a superseded warning promptly, even if it is not yet archived.

## D. AI-Agent Safety Rules

### Authority discovery order

Agents must read in this order:

1. `CLAUDE.md`
2. `docs/ACTIVE_SPEC_REGISTRY.md`
3. the matching canonical contract
4. the matching active subsystem spec, if one exists
5. active references only for setup or operational context

### Non-authoritative material

- Temporary operational documents do not govern architecture.
- Superseded active documents do not govern code.
- Historical archive material never governs current implementation.

### Drift handling

If docs and code appear to conflict:

- audit the live code first;
- identify the owning canonical contract;
- do not invent a parallel interpretation;
- do not implement from stale assumptions.

### Forbidden AI behaviors

- treating archived docs as current authority;
- reviving historical subsystem ownership;
- inferring missing architecture from stale notes;
- building a second system because a doc is vague;
- weakening transcript-safety rules in the name of simplification.

## E. Canonical Update Rules

- Update a canonical contract when the owned behavior, owner module, or active
  authority boundary changes.
- Update the active spec registry whenever a document changes class.
- Update superseded banners when a document becomes unsafe as current truth.
- Record ownership changes in the matching canonical contract rather than in
  transient logs alone.

## F. Transcript Safety Governance

The documentation lifecycle must preserve these rules:

- raw transcripts are immutable after capture;
- transcript mutation must be attributable and auditable;
- pagination and formatting are deterministic backend authorities;
- certification lineage is immutable once finalized;
- AI may not silently rewrite transcript meaning;
- AI may not own formatting or pagination decisions;
- no document may authorize a duplicate transcript, export, packaging, or
  snapshot pipeline.
