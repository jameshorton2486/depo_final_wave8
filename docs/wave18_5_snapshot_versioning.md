# Wave 18.5 — Transcript State Engine (Snapshot Layer)

Status: **BUILT.**

Companion to `docs/roadmap_ufm_production.md`. Sequenced before Wave 19.

> **A certified transcript is not simply a file — it is a reproducible
> legal transcript state.** That sentence is the entire purpose of this
> wave.

## 1. What this wave really is

This was first drafted as "snapshot & versioning." That undersold it.
What is actually being designed is **legal transcript state
management** -- the subsystem that will eventually govern
certification, amendments, errata, export reproducibility, AI review
history, transcript provenance, and legal audit trails.

The subsystem is the **Transcript State Engine**. Snapshots are one
layer of it -- the layer this wave builds. The engine is named in full
now so later waves extend it rather than bolt parallel systems beside
it.

## 2. Transcript State Engine — principles

The Transcript State Engine exists to ensure:

- legal reproducibility
- auditability
- certification integrity
- deterministic export generation
- rollback safety
- AI review traceability
- transcript provenance preservation

Every design decision below serves one of these.

## 3. Foundational rules

**Append-Only Audit Principle.** Transcript history is append-only. No
snapshot is ever mutated or deleted. Rollback creates a NEW state
snapshot; it never destroys history. Legal audit trails must be
append-only.

**Export Reproducibility Contract.** The same snapshot must always
produce identical transcript structure, pagination, line numbering,
indices, geometry, and administrative pages. An export is a
deterministic function of a snapshot.

**Provenance preservation.** A transcript moves through a lineage --
RAW -> deterministic corrections -> AI suggestions -> human review ->
export -> certification. The State Engine preserves that lineage; any
snapshot can answer "how did the transcript reach this state."

## 4. What a snapshot captures

A snapshot is an immutable capture of the COMPLETE transcript state --
not just the visible lines. It preserves:

- **semantic state** -- the WORKING transcript render lines;
- **render state** -- speaker mappings, pagination inputs;
- **correction state** -- deterministic correction outputs, the
  active regex-rule set, the active lexicon state;
- **AI review state** -- accepted/rejected suggestion IDs, and the AI
  traceability fields below;
- **export state** -- references to exports made from this snapshot;
- **metadata** -- category, who, when, why.

Capturing only the visible lines would make later export
reproducibility and page rebuilding impossible -- hence the full
capture.

## 5. The Transcript State Hash

The state hash is what makes "the same state" a precise, checkable
claim. It is a deterministic hash computed over an explicitly defined
set of inputs:

**The Transcript State Hash includes:**
- transcript render lines
- speaker mapping
- accepted AI suggestions
- correction (deterministic engine) outputs
- lexicon state
- regex-rule state
- export profile
- pagination inputs

Two snapshots with the same hash are guaranteed to export identically.
A changed hash means the transcript state genuinely changed.

## 6. Snapshot categories

Snapshots are tagged by category, which is operationally important for
filtering, recovery, and audit:

`AUTO_SAVE` · `MANUAL` · `PRE_AI` · `POST_AI` · `POST_REVIEW` ·
`PRE_EXPORT` · `EXPORT` · `CERTIFIED`

## 7. Export references

Each snapshot tracks the exports produced from it. An export reference
records: `export_id`, `export_format`, `export_timestamp`,
`export_profile`, `export_hash`. This is what lets multiple exports,
amended exports, certified exports, and rough drafts all trace back to
a definite transcript state.

## 8. The Certification Snapshot

A **Certification Snapshot** is a formal, distinct concept: a snapshot
that is immutable, locked, export-referenced, legally reproducible, and
tied to the reporter's certificate page. Certification *locking* (the
mechanism) is built in this wave; the certificate *document* itself is
Wave 20.

Note for the future: **certification freeze** is distinct from
locking. Eventually a frozen certified state and a live editable state
must coexist, with an amendment chain linking them (amended
transcripts, errata). This wave builds locking; the amendment chain is
acknowledged future scope (section 11).

## 9. AI review traceability

So AI auditability does not weaken later, a snapshot's AI review state
records, per accepted/rejected suggestion: which AI model, which prompt
version, which confidence threshold, the suggestion IDs, and which
reviewer approved the change. This wave captures these fields; richer
AI-history tooling is future scope.

## 10. Scope of the buildable Wave 18.5

**In scope -- built this wave:**
- A `transcript_snapshots` table (schema_v7) capturing the full state
  of section 4, with category (section 6) and AI traceability fields
  (section 9).
- The Transcript State Hash (section 5), deterministic.
- Snapshot creation -- on demand, and automatically on export.
- Snapshot listing and retrieval.
- Rollback -- restores a prior state as a NEW snapshot (append-only).
- Certification locking -- mark a snapshot as a Certification
  Snapshot; locked snapshots are immutable.
- Export references (section 7).
- API endpoints; a minimal Workspace/Export panel to view, pick, and
  roll back snapshots.
- **Storage strategy: full snapshots.** Each snapshot is a complete
  state copy. This is simpler and safer than delta storage and is the
  correct starting point. Delta/compressed storage is deferred
  (section 11).

**Acknowledged but DEFERRED (future waves -- not built here):**
- **Diff Engine** -- visual transcript-state, export, and AI-suggestion
  comparisons. Genuinely valuable and likely soon, but a real
  subsystem; it earns its own wave rather than overpacking this one.
- **Delta-based snapshot storage** -- an optimization for when full
  snapshots of large depositions with many revisions become heavy.
- **Workspace recovery** -- crash recovery, interrupted-edit recovery
  built ON TOP of the snapshot layer.
- **Amendment chain / certification freeze** -- frozen certified state
  coexisting with live editable state for amended transcripts/errata.
- **Case Package references** -- snapshots knowing their associated
  exhibits, audio, exports, and certificates as one package.

The deferred items are real and listed so later waves extend the
Transcript State Engine deliberately. This wave builds the snapshot
layer they all stand on.

## 11. Open questions for James

- **Q18.5-1.** Auto-create a snapshot on every export, or only
  certified exports? *Recommended: every export -- "which state did
  this file come from" should always be answerable.*
- **Q18.5-2.** Confirm rollback is append-only (new snapshot, history
  never deleted). *Recommended: yes -- required for legal audit.*
- **Q18.5-3.** Certification locking mechanism here, certificate
  document in Wave 20 -- confirm.
- **Q18.5-4.** Is full-snapshot storage acceptable for now, with delta
  storage deferred? *Recommended: yes -- full is safer and simpler;
  optimize only if size becomes a real problem.*
- **Q18.5-5.** Should the Diff Engine be its own near-term wave (e.g.
  Wave 18.6) rather than fully deferred? Your review argued visual
  diffs will matter soon. *Recommended: build the snapshot layer
  first, then a focused Diff wave -- but happy to slot it in early.*

## 12. Tests

Snapshot capture is deterministic; the state hash is stable for
identical state and changes for any state change; rollback creates a
new snapshot and deletes nothing; a locked Certification Snapshot
cannot be mutated; export references attach correctly; endpoints 404
appropriately. Plus the full suite stays green.
