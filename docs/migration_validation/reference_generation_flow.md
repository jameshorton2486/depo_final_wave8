# Reference Generation Flow

## Current Flow

### Transcript page/line references

`Stage S RenderLine`
-> pagination
-> `PhysicalLine.source_render_line_id`
-> `build_page_reference_map()`
-> first `(page, slot)` per render line
-> `IndexEntry(page, line)`
-> `IndexEntry.reference`

### Exhibit references

`transcript_exhibits.anchor_utterance_id`
-> snapshot exhibit state
-> `anchor_utterance_id -> render_line_id`
-> `ExhibitEvent.render_line_id`
-> `build_page_reference_map()`
-> `IndexEntry(page, line)`
-> `Exhibit.reference`

## Current Ownership Reality

There are two layers already:

### Stable-ish semantic layer

- `render_line_id`
- `anchor_utterance_id`
- snapshot identity

### Visible citation layer

- `page`
- `line`
- `"Page N, Line M"`

The problem is that the code treats the visible citation layer as if it
were the owned identity.

## Proposed Ownership Flow (Hybrid)

### Transcript lines

Owned internal reference:

`transcript_snapshot_id + render_line_id`

Derived visible citation:

`authoritative pagination -> page,line -> "Page N, Line M"`

### Exhibits

Owned internal reference:

`transcript_snapshot_id + anchor_utterance_id`

Bridge reference:

`reference_render_line_id`

Derived visible citation:

`authoritative pagination -> page,line -> "Page N, Line M"`

## Why This Matters

If pagination authority changes:

- internal ownership remains stable
- derived visible citations can be recomputed
- consumer drift becomes explicit and traceable

Without that split:

- page-map drift looks like identity drift
- every pagination change becomes a legal-reference migration

## Ownership Boundary

Recommended boundary:

- transcript/exhibit layer owns semantic anchors
- pagination owns placement only
- packaging owns citation rendering, not underlying reference identity
