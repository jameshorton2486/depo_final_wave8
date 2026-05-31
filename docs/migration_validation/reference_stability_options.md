# Reference Stability Options

## Option A — Maintain page-number ownership

### Definition

Treat:

- `Page N`
- `Page N, Line M`

as the authoritative reference identity.

### Pros

- no conceptual model change
- aligned with current package/index behavior

### Cons

- pagination changes become identity changes
- blocks safe authority migration
- keeps indices and exhibit refs fragile

### Fit

Good only if DEPO-PRO commits to one page map forever.

## Option B — Stable identity only

### Definition

Own references purely through stable transcript/exhibit identity, such as:

- `render_line_id`
- `anchor_utterance_id`
- snapshot-bound transcript identity

### Pros

- robust against page-map changes
- clean internal architecture

### Cons

- does not map directly to user/legal citation needs
- requires substantial consumer redesign

### Fit

Architecturally pure, but not practical as the immediate next move.

## Option C — Hybrid model

### Definition

Own stable internal identity separately from the visible citation.

Internal ownership:

- transcript lines: `snapshot_id + render_line_id`
- exhibits: `snapshot_id + anchor_utterance_id`

Rendered citation:

- `page`
- `line`
- `"Page N, Line M"`

### Pros

- preserves legal usability
- survives pagination migration
- matches existing code seams
- makes downstream drift explicit rather than implicit

### Cons

- requires package/index model augmentation
- requires migration planning before cutover

### Fit

Best fit for DEPO-PRO.

## Recommended Option

Recommend: **Option C — Hybrid model**

### Why

DEPO-PRO is not just a transcript renderer; it is also a certified
package generator. That means it needs:

1. stable internal ownership for engineering correctness
2. visible page/line citations for legal output

A hybrid model is the only one that satisfies both simultaneously.
