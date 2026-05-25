# SCROLLBAR_AUDIT.md — Phase 0 findings

## Shared layout container (the scroll host chain)

From `frontend/index.html`:

- `<body>`   → `h-screen flex flex-col overflow-hidden`
- `<main>`   → `flex-1 flex overflow-hidden`
- `<div id="appRoot">` → `flex-1 flex overflow-hidden`

Each stage screen is injected into `#appRoot` by `frontend/assets/js/router.js`
(`appRoot.innerHTML = html`). Because every ancestor up to `<body>` has
`overflow-hidden`, **scroll must happen on the screen's own root element**
(`#stagePanelN` / `.stage-panel`). That root is where the inconsistency lives.

## Per-screen root element

| Screen | Root classes (relevant bits) | Has `.stage-panel`? | Overflow model |
|---|---|---|---|
| stage_1_intake | `stage-panel flex-1 flex flex-col xl:flex-row p-4 gap-4 overflow-y-auto` | yes | `overflow-y: auto` |
| stage_2_transcripts | `stage-panel flex-1 flex flex-col xl:flex-row p-6 gap-6 overflow-y-auto` | yes | `overflow-y: auto` |
| stage_2b_speakers | `flex-1 flex flex-col overflow-hidden bg-slate-950` | **no** | `overflow: hidden` (manages internal scroll) |
| stage_3_workspace | `stage-panel flex-1 flex overflow-hidden` | yes | `overflow: hidden` (sidebar + columns scroll internally) |
| stage_4_insertions | `stage-panel flex-1 flex flex-col md:flex-row p-6 gap-6 overflow-y-auto` | yes | `overflow-y: auto` |
| stage_5_certify | `stage-panel flex-1 flex flex-col p-6 items-center justify-center overflow-y-auto` | yes | `overflow-y: auto` (also centers content) |
| stage_6_export | `stage-panel flex-1 flex flex-col md:flex-row p-6 gap-6 overflow-y-auto` | yes | `overflow-y: auto` |

`.stage-panel` has **no CSS rule** in `frontend/assets/css/app.css` — it is
currently only a marker class. All layout is per-screen Tailwind utilities.

## Two distinct categories — but only one is the inconsistency

**Category A — "auto" screens (1, 2, 4, 5, 6):** root scrolls vertically with
`overflow-y: auto`. The custom scrollbar in `app.css` is 6 px wide. With `auto`,
the gutter is **not reserved**: the scrollbar appears only when content
overflows, and the inner layout shifts ~6 px sideways depending on content
length. This is the source of the user-visible inconsistency. It is most
obvious on stage_5, whose root uses `items-center justify-center` — the
centered card visibly jumps when the gutter appears or vanishes.

**Category B — "hidden" screens (3, 2b):** these are intentionally
`overflow-hidden` at the root because they own their own internal scroll
regions (the workspace sidebar/columns in stage 3; the mapping table in
stage 2b). They never show a top-level scrollbar by design, and changing them
would break their column layouts. They are **not** in the same "auto" family
as A, so they are not part of the same root cause.

## Root cause (one)

For the five `.stage-panel ... overflow-y-auto` screens (1, 2, 4, 5, 6), the
scrollbar gutter is **not reserved**. `overflow-y: auto` only renders a
scrollbar — and consumes width — when the content actually overflows. Because
content length differs between screens (stage_5 is a short centered card,
stage_4/stage_6 are long forms), the gutter appears on some routes and
disappears on others. That is the single structural difference producing the
visible inconsistency.

## Planned fix (Phase 1)

The smallest possible change: add a single rule in `app.css` so the marker
class `.stage-panel` reserves its scrollbar gutter:

```css
.stage-panel { scrollbar-gutter: stable; }
```

This affects only elements with scrolling overflow, so:

- Screens 1, 2, 4, 5, 6 (`overflow-y: auto`) now always reserve the gutter →
  no layout shift, scrollbar position is identical across all of them, and
  it still only paints when content actually overflows (preferred per spec).
- Screen 3 (`.stage-panel overflow-hidden`) — `scrollbar-gutter` has no
  effect on a non-scrolling box, so its column layout is unchanged.
- Screen 2b — no `.stage-panel` class, untouched.

No screen markup, no per-screen overflow changes, no widths, no colors —
a single CSS rule on the existing marker class.
