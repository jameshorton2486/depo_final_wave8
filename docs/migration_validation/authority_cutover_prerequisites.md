# Authority Cutover Prerequisites

## Decision

Before pagination authority cutover, DEPO-PRO should adopt the
**hybrid reference ownership model** conceptually, even if the code
implementation lands later in staged passes.

## Why this is a prerequisite

Phase 2A proved:

- semantic pagination changes page maps materially

Phase 2B proved:

- packaging indices and exhibit references directly consume those page maps

Phase 2C now adds:

- the current system has stable semantic anchors available
- but it has not declared them as the owned reference identity

Without that ownership normalization, any cutover remains a reference
identity change, not merely a pagination implementation change.

## Prerequisites Before Cutover

### 1. Reference ownership policy must be explicit

Adopt the policy:

- stable internal reference is authoritative
- page/line citation is derived

### 2. Packaging models must be evaluated against that policy

Especially:

- `IndexEntry`
- `Exhibit`
- package JSON consumers

### 3. Exhibit bridge must be treated as semantic, not page-owned

The true exhibit identity should remain:

- snapshot-bound anchor

not:

- whatever page the current paginator assigns

### 4. Downstream package/index diffing must compare both layers

Future validation should compare:

- stable identity continuity
- visible citation continuity

not visible citation alone

## Minimum Safe Sequence

1. Adopt Option C conceptually in the migration plan.
2. Update audit/validation expectations to distinguish:
   - stable identity drift
   - visible citation drift
3. Re-run pagination comparison with that ownership model in mind.
4. Only then design any authority cutover or packaging migration pass.

## Recommendation

Do **not** proceed from Phase 2B directly to authority cutover planning.

First normalize the reference ownership model conceptually around:

- snapshot-bound stable semantic identity
- derived visible page citations

That is the prerequisite that turns cutover from “unsafe ref rewrite” into
“controlled citation migration.”
