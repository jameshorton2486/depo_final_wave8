# Wave 20 — Transcript Packaging Engine & Administrative Pages

Status: **BUILT (engine core) — revised per James's two review passes.**
The packaging engine core is implemented under `backend/packaging/`
with a 35-test suite. DOCX rendering of pages and API/DB wiring are the
next pass (see Build Status below).

Companion to `docs/roadmap_ufm_production.md` and
`docs/wave19_ufm_layout.md`. Primary reference:
`docs/ufm_administrative_pages.md`.

## 0. Certified Package Lifecycle Principles

Wave 20 governs **certified transcript package lifecycle generation**:

- package assembly
- administrative page generation
- certification structures
- package reproducibility
- package integrity
- package auditability

**It does NOT alter transcript semantics, rendering, or pagination.**
The canonical renderer decided what the transcript says; Wave 19
decided where every line sits. Wave 20 wraps that finished body into a
legal artifact and manages that artifact through its lifecycle.

    semantic rendering        -> canonical renderer (done)
    physical page production  -> Wave 19 (done/in progress)
    certified-package lifecycle -> Wave 20 (this wave)

## 1. The Certified Transcript Package

Wave 18 generates a *file*. Wave 20 produces a *legal artifact*:

    export    = generate a file from a body
    packaging = assemble a complete certified legal record

**The DOCX is merely the container the package is written into — the
package is the legally meaningful unit.** The Certified Transcript
Package consists of: the paginated transcript body; the administrative
pages; the indices; the manifest; associated case and certification
metadata; and the export/pagination state it was produced from.

## 2. The Package Composition Pipeline

    Transcript Snapshot          (Wave 18.5 — locked, versioned state)
      -> Canonical Renderer      (semantic body)
      -> Pagination Engine       (Wave 19A — line placement)
      -> Geometry Layer          (Wave 19B — page furniture)
      -> Index Generation        (Wave 20 — page/line references)
      -> Administrative Page Generators   (Wave 20 — template-driven)
      -> Packaging Engine        (Wave 20 — ordered assembly)
      -> Certified Transcript Package

Index generation runs strictly after pagination is frozen.

## 3. Foundational principles

**Package Reproducibility.** The same locked snapshot always assembles
to an identical package — identical section order, identical identity,
identical manifest hash. *Implemented:* `package_id` and
`manifest_hash` are derived deterministically; the manifest hash
excludes the wall-clock timestamp.

**Immutable Certified Artifact.** A certified package is immutable once
finalized. Any subsequent change creates a new package version, never
mutates the original. *Implemented:* `TranscriptPackage` enforces an
`IMMUTABLE_STATES` guard and a one-directional state graph.

**Index Dependency.** Index generation occurs only after the Wave 19
pagination state is frozen; an entry's page number is knowable only
once pagination is final.

**Stable Cross-References.** Once certified, all page/line/exhibit/
witness references remain stable. *Implemented:* indices resolve every
event against the frozen `PaginatedDocument` to a stable
"Page N, Line M" reference.

**Structured data in.** Administrative page generators and the Index
Generation Engine consume structured metadata and structured tracking
events — never parsed transcript text.

## 4. Package State, Identity & Integrity

**Package State** (`backend/packaging/model.py`). The lifecycle state
of a package: `DRAFT → REVIEW → CERTIFIED → EXPORTED`, plus `AMENDED`,
`SUPERSEDED`, `SEALED`. Transitions are governed by a legal-transition
graph; a certified package cannot revert to draft.

**Package Identity.** Every package carries a `PackageIdentity`:
`package_id`, `transcript_snapshot_id`, `state_hash`,
`package_version`, `certification_id`, `export_id` — all derived
deterministically so re-assembly reproduces the same identity.

**Package Manifest.** A self-describing record of what produced the
package (snapshot id, engine versions, indices, exhibits, template
versions, geometry profile). Its `manifest_hash` is the integrity
anchor.

**Package Integrity Verification.** `verify_package_integrity()`
confirms the manifest hash recomputes, the identity is consistent, and
the package is bound to the expected snapshot and state hash.

**Certificate Binding.** The Reporter's Certificate page embeds the
package id, certification id, snapshot id, and state hash, so the
certificate cannot be detached from the record it certifies.

## 5. The Transcript Packaging Engine

`assemble_package()` orchestrates: validate → generate indices → build
administrative pages → order → build manifest → generation report →
`TranscriptPackage`. `certify_package()` runs the pre-certification
validation pass and performs the one-way `CERTIFIED` transition.

**Package Ordering Authority.** A single `SECTION_ORDER` tuple is the
sole authority for package structure — caption first, certificate last,
body between the front-matter indices and the back matter.

**Package Generation Report.** Every assembly emits a `GenerationReport`
— body/administrative page counts, exhibits and witnesses indexed,
unresolved flags, warnings, AI-review summary, certification status.

## 6. Administrative pages

Five template-driven generators (`backend/packaging/admin_pages.py`):
Title/Caption, Appearances, Indices (chronological, witness, exhibit),
Corrections/Signature (freelance only), Reporter's Certificate.

Template wording is the proposed standard Texas-UFM phrasing pending
James's confirmation (Q20-2), data-driven behind a template-versioning
seam. Administrative pages reuse the Wave 19 geometry system, while
supporting page-type-specific pagination rules where they differ from
the body.

## 7. The Index Generation Engine

`backend/packaging/indices.py`. Consumes structured `WitnessEvent` and
`ExhibitEvent` records plus the frozen `PaginatedDocument`; builds a
RenderLine→(page,line) map and produces the chronological,
alphabetical-witness, and exhibit indices. Also returns `Exhibit`
identity records — the seam later exhibit-document packaging attaches
to.

## 8. The Package Validation Pipeline

`backend/packaging/validation.py`. Validates required metadata
(`REQUIRED_METADATA_FIELDS` — Q20-6), index page-reference resolution,
and body presence. Errors block certification; warnings inform.
Packaging fails gracefully rather than certifying a package with blank
mandatory fields.

## 9. Build Status

**Built this wave (`backend/packaging/`, 35 tests):** the package
model and state machine; the Index Generation Engine; the five
administrative page generators; the manifest builder, deterministic
hashing, and integrity verification; the validation pipeline; the
Packaging Engine (`assemble_package`, `certify_package`) with the
Package Ordering Authority.

**Next pass (not built — depends on the Wave 19 geometry-into-DOCX
wiring):** rendering package sections to a real DOCX/PDF; an
`/api/packaging` router and persistence (mirroring `api/snapshots.py`);
sourcing `metadata` and tracking events from real job/intake data.

## 10. Future scope (acknowledged, not built)

Amended-package workflow and errata-linked supersession; the package
container layer (ZIP/litigation bundles); multi-volume strategy; the
document relationship graph linking transcripts, exhibits, audio,
errata, and certifications; non-certified package profiles.

## 11. Open questions for James

- **Q20-2.** Exact UFM template wording for caption, appearances, and
  certificate pages — supplied, or confirm the proposed standard?
- **Q20-3.** Confirm the freelance trigger — a per-case flag at intake?
- **Q20-5.** Manifest — embedded in the package or a sidecar file?
- **Q20-6.** Confirm the exact `REQUIRED_METADATA_FIELDS` set.
- **Q20-8 (new).** Confirm the Package State set and transition graph
  in `model.py` matches the intended legal lifecycle.

## 12. Tests

`tests/test_wave20_packaging.py` — 35 tests: state transitions,
metadata validation, index generation (page-reference map, alphabetical
and numeric ordering, stable references, determinism), administrative
page generation, ordering authority (caption first / certificate last),
reproducibility (deterministic id and manifest hash), generation
report, certification, immutability, and integrity verification.
