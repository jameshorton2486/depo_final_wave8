# Wave 19 — Physical Transcript Production (Pagination + Geometry)

Status: **BUILT (Wave 19A Pagination Engine + Wave 19B Geometry profile). Geometry rendering into DOCX/PDF wires in the next pass.**

Companion to `docs/roadmap_ufm_production.md`. Primary formatting
reference: `docs/ufm_layout_spec.md`.

## 0. Physical Transcript Production Principles

Wave 19 governs **physical transcript production**:

- page placement
- pagination
- geometry
- line numbering
- continuation behavior
- physical transcript reproducibility

**It does NOT alter transcript semantics.** The canonical renderer has
already decided what the transcript says and how it is structured --
speakers, Q/A roles, objection isolation, parentheticals, off-record
state. Wave 19 decides only where that fixed content sits on a physical
page.

    semantic rendering        -> canonical renderer (done)
    physical page production  -> Wave 19 (this wave)

**The format box is not transcript content. It is page furniture.**
That distinction governs the whole wave: pagination and geometry
decorate a transcript whose meaning is already final and immutable.

## 1. The core reordering — Pagination is primary

The earlier draft treated Geometry and Pagination as siblings. They are
not. Pagination is the **primary** engine; geometry **decorates its
output**. The pipeline is strictly linear:

    Canonical Renderer
      -> Pagination Engine      (decides line placement)
      -> Geometry Layer         (decorates the placed lines)
      -> Export Engine          (writes the file)

Accordingly the wave parts are renamed so the names match the
dependency:

- **Wave 19A = Pagination Engine** (was 19B)
- **Wave 19B = Geometry Layer**    (was 19A)

Pagination is built first. Geometry decorates a paginated result;
building geometry on the current naive line-splitter would only need
redoing once real pagination lands.

## 2. The Page Composition Pipeline

Wave 19 formalizes a single linear pipeline. Every stage has one job:

    RenderLines          semantic transcript lines (from the renderer)
      -> WrappedLines    text wrapped to the box content width
      -> PhysicalLines   the actual printed lines
      -> PageSlots       numbered UFM line positions (1..25)
      -> Pages           assembled 25-slot pages
      -> Geometry Decoration   box, numbers, headers, footers
      -> Export          the written file

No stage may be skipped or bypassed; no export or preview path may
construct pages outside this pipeline.

## 3. Line-concept vocabulary (precise definitions)

Wrapping makes loose talk about "lines" ambiguous. Three distinct
concepts, used precisely throughout Wave 19:

| Concept       | Meaning                                            |
|---------------|----------------------------------------------------|
| RenderLine    | one semantic transcript line (a Q, an A, colloquy) |
| PhysicalLine  | one physically printed line on the page            |
| PageSlot      | one numbered UFM line position, 1..25, on a page   |

One RenderLine may wrap into multiple PhysicalLines, and therefore
occupy multiple PageSlots, possibly spanning a page boundary. The
Pagination Engine's job is precisely this mapping:
RenderLine -> PhysicalLines -> PageSlots -> Pages.

## 4. Foundational principles for Wave 19

**Layout Determinism.** The same snapshot state must always produce
identical page breaks, identical line wrapping, identical continuation
behavior, identical line numbering, and identical page counts. This is
required for legal reproducibility, certification, re-exports, appeals,
and errata. (It is the physical-layout counterpart of Wave 18.5's
Export Reproducibility Contract, and it is why Wave 19 depends on the
stable snapshot state from Wave 18.5.)

**python-docx is not a pagination engine.** Word reflows documents
dynamically -- its layout varies by printer driver, installed fonts,
rendering engine, and Windows version. DEPO-PRO therefore computes its
OWN deterministic pagination BEFORE document generation. The Pagination
Engine decides page breaks; `python-docx`/`reportlab` only render the
already-decided pages. We never delegate pagination to Word.

**DOCX and PDF are not independent pagination systems.** Both render
targets consume the SAME pagination state produced by the Pagination
Engine. DOCX is the canonical production source; PDF is generated from
the same canonical pagination state. They cannot drift because they do
not paginate independently.

**Export Preview = pagination authority.** The Export Preview consumes
the EXACT final pagination state -- the same Pages the export writes --
never an approximate rendering. What the reporter previews is what
exports.

## Wave 19A — Pagination Engine

**Goal:** deterministically decide what content lands on which page.

### Delivered

- **Exact 25-PageSlot pages** -- every body page has exactly 25
  numbered slots.
- **The RenderLine -> PhysicalLine -> PageSlot mapping**, including
  page-aware wrapping (wrapping that respects both box width and the
  25-slot limit together).
- **Continuation handling** via explicit **Continuation State
  Objects** -- see section 5.
- **Transcript Flow Rules** -- see section 6 (more than widow/orphan;
  real flow control).
- **Overflow balancing** -- content that does not fit is carried
  correctly, never dropped, never silently merged.
- Output: a definitive, ordered list of `Page` objects, each with 25
  filled-or-blank PageSlots, ready for geometry.

### 5. Continuation State Objects

When a structure crosses a page boundary, the break is represented by
an explicit state object, not inferred. The Continuation State Engine
(a component of the Pagination Engine) tracks:

- page continuation markers (a turn continues onto the next page);
- split-parenthetical state (a procedural parenthetical across a break);
- split-Q/A state (a question or answer across a break);
- colloquy continuation state.

Explicit objects make continuation testable and deterministic.

### 6. Transcript Flow Rules

Pagination is more than widow/orphan logic -- it is transcript flow
control. Certain structures have flow constraints:

- structures that **should not split** across a page (e.g. a short
  objection);
- structures that **prefer to stay together** (a short Q/A pair);
- structures that **require minimum context lines** when they do
  split (e.g. an exhibit colloquy must carry N lines of lead-in).

These rules are data-driven so UFM specifics can be set precisely.

## Wave 19B — Geometry Layer

**Goal:** decorate the paginated Pages with UFM physical furniture.

### Delivered (from `docs/ufm_layout_spec.md`)

- **The Format Box** -- solid top/bottom/left/right marginal lines.
- **Line Numbers** -- 1-25, left of the box, every body page (one per
  PageSlot).
- **Page Numbers** -- top-right, flush to the right margin.
- **Headers** -- page headings above line 1, outside the box.
- **Footers** -- information lines below line 25.
- **Time Stamping (optional)** -- left of line numbers, or right of
  the right marginal line.
- **Tab stops** -- fixed horizontal positions for Q/A, colloquy, and
  parentheticals.

### 7. Geometry Abstraction Layer

Geometry is built behind a `GeometryProfile` abstraction -- a single
named profile, `texas_ufm`, for now. Profiles are NOT built this wave;
only the abstraction seam, so that California / arbitration geometry
can later be added as additional profiles without reworking the
Geometry Layer.

### 8. Administrative Page Geometry Compatibility

The Geometry Layer is built so Wave 20's administrative pages reuse the
SAME geometry system, pagination logic, headers/footers, and export
reproducibility. Body pages and administrative pages must not diverge
visually -- they share one geometry engine.

## 9. Page Identity

Pages and lines become referenceable legal entities. The Pagination
Engine assigns each Page and each PageSlot a **stable identity**, so
"Page 42, Line 17" is a durable, reproducible reference. Stable page
and line identity is required for legal citation, indices (Wave 20),
and certification.

**Certification Reflow Risk.** Once a transcript is certified, its
geometry, page numbers, and line numbers must NOT shift. Stable page
identity plus Layout Determinism plus Wave 18.5 snapshot locking
together guarantee a certified transcript never silently re-flows.

## 10. Performance considerations (acknowledged, not built now)

Pagination is computationally expensive, especially for large
depositions, repeated re-renders, export previews, and re-pagination
after AI corrections. Future optimizations -- pagination caching,
incremental reflow, lazy re-pagination -- are acknowledged here but are
not built in Wave 19. Wave 19 targets correctness and determinism
first.

## 11. Open questions for James

- **Q19-1.** Confirm the rename and order: Wave 19A = Pagination
  Engine (built first), Wave 19B = Geometry Layer. *Recommended: yes
  -- per your review.*
- **Q19-2.** Exact UFM measurements -- margins, box dimensions, tab
  stop positions, font, point size. `docs/ufm_layout_spec.md` is
  qualitative; 19B needs exact numbers. Will you supply precise UFM
  measurements, or should the spec propose standard Texas-UFM values
  for your confirmation?
- **Q19-3.** Headers -- the page-heading text (witness, examination
  type) is dynamic. Confirm the data source: the confirmed speaker
  mapping plus examination tracking?
- **Q19-4.** Time stamping -- needed in the first 19B build, or
  deferred? It is optional in UFM.
- **Q19-5.** Transcript Flow Rules (section 6) -- do you have the
  precise UFM split/keep-together rules, or should the spec propose a
  conservative default set for your confirmation?

## 12. Tests

**Pagination:** every page has exactly 25 PageSlots; no RenderLine is
lost or duplicated; the RenderLine->PhysicalLine->PageSlot mapping is
correct; continuation state objects are produced at every boundary;
flow rules hold; pagination is deterministic across repeated runs of
the same snapshot.

**Geometry validation tests** (legally important): exact margins, tab
stop positions, format box coordinates, line-number positioning, page
overflow consistency, continuation placement.

Plus the full suite stays green.
