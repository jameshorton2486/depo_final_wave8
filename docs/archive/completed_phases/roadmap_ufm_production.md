>  SUPERSEDED — FACTUALLY INACCURATE. This document describes an earlier,
> pre-backend state of DEPO-PRO and is WRONG about the current system. Do not
> use it for any decision. Current authority: CLAUDE.md at the repo root.

# Roadmap — Certified Legal Transcript Production (Waves 18-20)

Status: **PLAN — revised per James's review. Wave 18 is built; Waves
18.5, 19, 20 are not yet started.**

> **DEPO-PRO is transitioning from transcript rendering to certified
> legal transcript production.** Every architectural decision in this
> roadmap follows from that shift. A transcript *renderer* shows text;
> a transcript *production system* generates certified, reproducible,
> legally packaged documents. They are different systems with
> different guarantees.

## Where the project is today

DEPO-PRO can ingest audio, transcribe it, correct it deterministically
(Waves 1-15a), surface AI suggestions for human review (15b-16), and
produce real `.docx`/PDF/RTF/TXT files written to disk (Wave 18). What
it cannot yet do: lay out those files to UFM page geometry, or package
them with the mandatory administrative pages. This roadmap closes that
gap.

## Core engines — the architectural vocabulary

These documents formalize the system as a set of named engines, each
with one responsibility. This vocabulary is used throughout.

| Engine                | Responsibility                              |
|-----------------------|---------------------------------------------|
| Canonical Renderer    | semantic rendering of transcript structure  |
| Pagination Engine     | physical page layout (25-line pages, flow)  |
| Geometry Layer        | physical page furniture (box, numbers)      |
| Packaging Engine      | administrative-page assembly into a package |
| Export Engine         | file generation (DOCX/PDF/RTF/TXT)          |
| Index Generation Engine | witness/exhibit/page index construction   |
| AI Review Engine      | suggestions and human-gated review          |
| Audit Engine          | change history and traceability             |
| Transcript State Engine | transcript state, versioning, certification |

### Canonical Renderer

The canonical renderer is the single authoritative backend render
pipeline responsible for generating:

- Workspace transcript views
- Export previews
- DOCX/PDF transcript body output
- pagination inputs
- administrative-page references

**No frontend renderer or export path may bypass this renderer.** This
is the most important architectural principle in the project.

## Foundational principles

These rules are non-negotiable and apply to every wave below.

**1. No duplicate renderers.** No export path, preview path, or
frontend renderer may independently construct transcript structure
outside the canonical renderer. Every view of the transcript is the
same render, presented differently.

**2. Semantic rendering is not physical layout.** The canonical
renderer produces *semantic* structure -- speakers, Q/A roles,
objection isolation, parentheticals, off-record state. Physical page
geometry -- the format box, line numbers, page numbers, headers,
footers -- is a *separate* layer applied later. Objection isolation is
a semantic concern; line numbering is a geometry concern; they belong
to different engines. UFM geometry (the format box especially) is
**not transcript content and not semantic structure -- it is physical
page geometry**, a layout layer on top of the rendered body.

**3. Deterministic export pipeline.** Exports are deterministic
outputs from the canonical renderer and packaging pipeline. The same
transcript state always produces the same file.

**4. Export reproducibility.** The same transcript state must always
produce the same export -- identical pagination, identical line
numbering, identical indices, identical geometry, identical
administrative packaging. This matters for certified transcripts,
re-exports, appeals, errata, and auditability.

**5. AI is resolved before export.** AI suggestions are resolved
(accepted or rejected) *before* export rendering begins. Exports
consume accepted transcript state, never live AI interpretation. This
is what makes export reproducible.

**6. RAW is immutable.** The RAW transcript is never mutated. The
WORKING transcript is render-driven. The deterministic engine is
authoritative over corrections.

## The end goal — a certified transcript package

The deliverable is not an "exported document." It is a **certified
transcript package** -- the testimony body, laid out to UFM geometry,
wrapped with the administrative pages (caption, appearances, indices,
corrections/signature, reporter's certificate), exhibits attached,
produced deterministically and reproducibly. The project builds
*certified transcript packages*, not individual document exports.

## Why these waves, in this order

The order is forced by dependency:

- Real page *geometry* requires real binary document *generation*
  first -> Wave 18 precedes 19.
- Reliable export and packaging require a stable, versioned transcript
  *state* -> Wave 18.5 precedes 19 and 20.
- Administrative pages should match the finished body geometry ->
  Wave 19 precedes 20.

---

## Wave 18 — Export Engine, Menu & Real File Generation  *(BUILT)*

**Goal:** make Export produce real files, in real formats, at real
disk locations.

**Delivered:**
- An export menu (format + destination) on the Export screen.
- Real `.docx` (`python-docx`), PDF (`reportlab`), RTF, and TXT/ASCII
  generation.
- Destinations: TXT/ASCII -> Downloads; DOCX/PDF/RTF -> native Save As
  dialog; case workspace folder selectable for any format.
- The PyWebView blob-download failure is fixed -- the backend writes
  the file and returns the path.
- Export and Export Preview share one canonical document builder.

**Wave 18's `.docx` is a clean, real, structurally formatted Word
document** -- correct caption block, Q/A paragraphs, colloquy,
page breaks. **True UFM pagination and page geometry are introduced in
Wave 19**, not here.

## Wave 18.5 — Transcript Snapshot & Versioning  *(PLANNED)*

**Goal:** give the transcript a versioned, lockable state model before
export and packaging depend on it.

**Responsibilities:**
- export snapshots -- a captured transcript state an export was made
  from;
- transcript rollback to a prior state;
- certified-state locking (see Certification Locking below);
- audit history of render states;
- AI suggestion history;
- render-state history.

**Why now, not later:** export reproducibility (principle 4) and
certification both require a stable notion of "the transcript state as
of X." Building export/packaging on an unversioned transcript bakes in
a problem that errata, appeals, and amended transcripts later make
expensive. The Transcript State Engine should exist before Waves 19-20 lean on
it.

**Certification Locking** (introduced here, may extend into a later
wave): a certified transcript export becomes an immutable transcript
snapshot associated with a certification timestamp, an export version,
the reporter's certificate, and a transcript state hash.

## Wave 19 — Physical Transcript Production  *(PLANNED)*

Wave 19 is two engines in a strict pipeline. Pagination is the
**primary** engine; geometry **decorates its output**:

    Canonical Renderer -> Pagination Engine -> Geometry Layer -> Export

### Wave 19A — Pagination Engine

The primary engine -- deciding deterministically what content lands on
which page:
- exactly 25 PageSlots per page;
- the RenderLine -> PhysicalLine -> PageSlot mapping (page-aware
  wrapping);
- continuation handling via explicit Continuation State Objects;
- Transcript Flow Rules (split/keep-together/minimum-context);
- overflow balancing.

Pagination is built FIRST -- geometry decorates a paginated result.

### Wave 19B — Geometry Layer

The physical page furniture, decorating the paginated pages (from
`docs/ufm_layout_spec.md`):
- **The Format Box** -- solid top/bottom/left/right marginal lines.
- **Line Numbers** -- 1-25, left of the format box, every page.
- **Page Numbers** -- top-right, flush to the right margin.
- **Headers** -- page headings above line 1, outside the box.
- **Footers** -- information lines below line 25.
- **Time Stamping (optional)** -- left of line numbers, or right of
  the right marginal line.
- **Tab stops** -- the horizontal positions Q/A and colloquy align to.

The format box is not transcript content -- it is page furniture.

**Depends on:** Wave 18 (real documents), Wave 18.5 (stable snapshot
state for deterministic, reproducible pagination). See
`docs/wave19_ufm_layout.md` for the full revised plan.

## Wave 20 — Transcript Packaging Engine  *(PLANNED)*

**Goal:** assemble the certified transcript package.

Export and packaging are different operations. **Export** generates a
file from a body. **Packaging** assembles a complete certified
document: body + administrative pages + indices + certificate +
exhibits.

### The Transcript Packaging Engine

Responsibilities:
- assemble the transcript body (from the canonical renderer);
- attach administrative pages;
- build indices (via the Index Generation Engine);
- attach the certificate page;
- package exhibits;
- generate the final export structure.

### Administrative pages (from `docs/ufm_administrative_pages.md`)

- **Title / Caption Page** -- case style, cause number, court, date,
  location.
- **Appearances Page** -- attorneys, firms, parties represented.
- **Indices** -- chronological, alphabetical witness, exhibit.
- **Corrections / Signature Page** -- for freelance depositions.
- **Reporter's Certificate Page** -- always last; sworn certification.

**Administrative pages derive their data from:** intake metadata, case
configuration, speaker mappings, exhibit tracking, transcript indices,
and certification metadata. They are template-driven generators, never
hardcoded HTML.

### Index Generation Engine

Index construction is a real subsystem, not a formatting afterthought.
It handles witness tracking, exhibit tracking, page references,
examination tracking, and volume tracking, and produces the
chronological, alphabetical-witness, and exhibit indices the
administrative pages consume.

**Depends on:** Waves 18, 18.5, and 19.

---

## Open questions for James

- **[BLOCKER for 18.5] Q-SNAP.** Approve inserting Wave 18.5
  (Transcript Snapshot & Versioning) before Wave 19? *Recommended:
  yes -- export reproducibility and certification depend on it.*

- **[BLOCKER for TXT] Q-ASCII.** Court-reporting "ASCII" is often a
  fixed-width, CAT-compatible, legacy litigation-support format -- NOT
  a generic text file. **ASCII export requirements must be confirmed
  before implementation, because legal-industry ASCII may differ
  significantly from plain TXT export.** Wave 18 currently treats
  ASCII as plain `.txt`. Is that acceptable, or is true CAT-compatible
  ASCII needed -- and if so, in which wave?

- **[SEQUENCING] Q-PROFILE.** Current implementation targets Texas UFM
  exclusively. A future export-profile architecture may support
  additional jurisdictions (California, arbitration, rough draft).
  Confirm Texas-UFM-only for now, profiles deferred? *Recommended:
  yes -- build UFM directly, keep the seam clean for later profiles.*

## Future scope (acknowledged, not yet planned in detail)

Beyond Wave 20: large-deposition scalability (chunked/streaming
rendering), advanced search and navigation, realtime-vs-final
transcript separation, and full multi-jurisdiction export profiles.
These are real and tracked, but not specified here.

## Approval

Wave 18 is built. The next document to act on is the Wave 18.5 spec
(if Q-SNAP is approved) or the Wave 19 spec. No wave begins without its
own reviewed spec document.
