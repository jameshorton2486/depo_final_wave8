# Phase 2A — Semantic Pagination Validation

## Scope

This was a read-only validation pass against **real persisted transcripts**.

Authority was **not** cut over.

Current runtime remained:

`Transcript -> Stage S -> export_render private pagination -> Geometry -> Export`

Candidate semantic path evaluated:

`Transcript -> Stage S logical lines -> backend.pagination.paginate() -> comparison only`

## Corpus Used

Two real jobs with usable participant mapping and strong pagination stress:

1. `278122f3-7361-404f-8226-9ae7eb6214e7`
   - source: `heath_thomas.mp3`
   - participants: `5`
   - Stage S lines: `809`
   - long lines `> 40` words: `74`
   - objections isolated by Stage S: `39`
   - colloquy lines: `114`
   - exhibit-discussion mentions in transcript text: `13`

2. `1914cc18-f7be-4494-a12d-fbb8de2c233a`
   - source: `heath_thomas.mp3`
   - participants: `4`
   - Stage S lines: `812`
   - long lines `> 40` words: `75`
   - objections isolated by Stage S: `39`
   - colloquy lines: `107`
   - exhibit-discussion mentions in transcript text: `13`

## Corpus Limits

The available real corpus did **not** exercise:

- Stage S `parenthetical` lines
- off-record spans / resume parentheticals
- persisted `transcript_exhibits` anchor rows

So this pass is strong on:

- long answers
- long objections
- long colloquy
- exhibit discussion text
- page-boundary stress

But not on formal exhibit-anchor persistence or parenthetical-specific flow.

## Method

For each real job:

1. Rebuild the same Stage S line set used by transcript export.
2. Build the authoritative export-render pagination result.
3. Build a semantic candidate path from Stage S logical lines and run
   `backend.pagination.paginate()` directly.
4. Compare:
   - `ContinuationState`
   - Q/A tether outcomes at page boundaries
   - `can_start_on_page` effect
   - logical line page references
   - exhibit-discussion line page references

Important limitation:

The semantic candidate path still requires an evaluation shim because the live
runtime flattening path does not preserve a direct one-to-one logical-line
reference model. That means this pass can reliably identify **material drift**,
but it is not yet a cutover-ready proof of parity.

## Measured Results

### Job 278122f3-7361-404f-8226-9ae7eb6214e7

- authoritative pages: `108`
- semantic candidate pages: `107`
- authoritative continuations: `0`
- semantic candidate continuations: `106`
- logical lines with different `(page, slot)` references: `701 / 809`
- logical lines with different page numbers: `392 / 809`
- stranded `Q -> A` page-boundary pairs:
  - authoritative: `0`
  - semantic candidate: `0`
- exhibit-discussion lines with different page references: `11 / 13`

### Job 1914cc18-f7be-4494-a12d-fbb8de2c233a

- authoritative pages: `108`
- semantic candidate pages: `107`
- authoritative continuations: `0`
- semantic candidate continuations: `106`
- logical lines with different `(page, slot)` references: `706 / 812`
- logical lines with different page numbers: `415 / 812`
- stranded `Q -> A` page-boundary pairs:
  - authoritative: `0`
  - semantic candidate: `0`
- exhibit-discussion lines with different page references: `11 / 13`

## Semantic Feature Classification

| Feature | Classification | Evidence |
| ---- | ---- | ---- |
| ContinuationState generation | MATERIAL DIFFERENCE | Live runtime emits `0` continuations on both real jobs; semantic paginator emits `106` on both. |
| Q/A tether behavior | NO DIFFERENCE | No stranded `Q` at end-of-page with `A` opening next page was observed in either path on either real job. |
| `can_start_on_page` behavior | NO DIFFERENCE | Current `flow_rules.can_start_on_page()` is effectively “start whenever a slot remains”; no observed live divergence attributable to start-on-page gating. |
| Page-reference stability | MATERIAL DIFFERENCE | `701/809` and `706/812` logical lines changed `(page, slot)` references; `392` and `415` logical lines changed page numbers. |
| Exhibit-reference stability | MATERIAL DIFFERENCE | No persisted exhibit anchors existed, but `11/13` exhibit-discussion lines shifted page references on both jobs, indicating high anchor-risk if cut over now. |

## Interpretation

### 1. Continuation is the real live semantic gap

This pass confirmed the architectural suspicion from Phase 1:

- `export_render` is flattening the transcript into already-physical lines
- live runtime therefore records **no** continuation ownership
- the semantic paginator does record it, and does so extensively on real jobs

That is not a cosmetic difference. It changes the page model.

### 2. Q/A tether is not currently the blocking difference

The richer paginator did **not** surface a new Q/A tether outcome on the two
real mapped transcripts. That means Q/A tether alone is not the reason to stop
cutover.

### 3. Page references are not stable enough for cutover

The large reference drift is material:

- hundreds of logical lines move to different `(page, slot)` coordinates
- roughly half the logical lines move to different page numbers entirely
- exhibit-discussion lines drift heavily as well

Even where the page-count delta is only `108 -> 107`, the reference drift is
large enough to affect:

- index generation
- exhibit references
- downstream certification/package references

## Recommendation

Authority cutover is **not recommended** after Phase 2A.

Reason:

Material differences remain **explained but unresolved**:

1. live runtime has no continuation ownership model
2. semantic pagination materially changes page references on real transcripts
3. exhibit-reference stability is still high-risk even before formal anchors are compared

The next safe step is **not** cutover. The next safe step is a governed
adapter/normalization pass that makes the semantic paginator and the live
export formatter operate over the same logical structure before page-reference
parity is judged again.

## Bottom Line

- `ContinuationState generation`: **MATERIAL DIFFERENCE**
- `Q/A tether behavior`: **NO DIFFERENCE**
- `can_start_on_page behavior`: **NO DIFFERENCE**
- `Page-reference stability`: **MATERIAL DIFFERENCE**
- `Exhibit-reference stability`: **MATERIAL DIFFERENCE**

Therefore:

**Do not cut over authority yet.**
