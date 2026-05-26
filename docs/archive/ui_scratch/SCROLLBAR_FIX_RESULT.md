> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# SCROLLBAR_FIX_RESULT.md — Phase 2 result

## Root cause (one)

Five of the seven stage screens — stage_1, stage_2, stage_4, stage_5,
stage_6 — use `overflow-y: auto` on their `.stage-panel` root. With `auto`,
the browser only paints the scrollbar (and only consumes the ~6 px gutter
defined in `app.css`) when content actually overflows. Because content
length differs by route, the gutter appeared on long screens and vanished on
short ones, shifting the inner layout sideways. Stage_5 made this most
visible: its root uses `items-center justify-center`, so the centered card
jumped horizontally between routes.

Stages 3 and 2b use `overflow-hidden` at the root by design — they own
internal scroll regions (sidebar / column layouts). They are not part of
the same family and are not the source of the inconsistency.

## The one fix applied

Added a single rule to `frontend/assets/css/app.css`:

```css
.stage-panel {
    scrollbar-gutter: stable;
}
```

`scrollbar-gutter: stable` reserves the gutter on any element with
scrolling overflow, whether or not the scrollbar is currently painted. It
is a no-op on `overflow: hidden` elements, so stage_3 (which also carries
`.stage-panel`) is unaffected. Stage_2b has no `.stage-panel` class and is
also untouched.

Behavior after the fix:

- Stages 1, 2, 4, 5, 6 reserve the scrollbar gutter at all times. The
  scrollbar itself still only paints when content overflows (per the spec,
  `auto` is preferred over forced-always `scroll`). No layout shift between
  routes; stage_5's centered card no longer jumps.
- Stages 3 and 2b keep their internal-scroll layouts exactly as before.
- No horizontal scrollbar on any screen (no rule added or removed that
  would affect horizontal overflow).

## Files touched

| File | Change |
|---|---|
| `frontend/assets/css/app.css` | +8 lines (one CSS block, comment + rule) |

No JavaScript, no markup, no backend, no tests, no other CSS rules touched.
`git diff --stat` confirms a single file changed.

## Verification

- `git diff --stat` shows 1 file, +8 / -0 — only CSS.
- No JS file was modified, so `node --check` is not applicable.
- Changes are **uncommitted**, left staged for user review.

## Manual check (required — visual fix)

A scrollbar/layout fix can only be confirmed by eye. Hard-refresh the app
(`Ctrl+Shift+R`) and click through the stages in order:

1. **Stage 1 — Intake** — long content, vertical scroll on right gutter.
2. **Stage 2 — Transcripts** — long content, vertical scroll on right
   gutter, in the same position as stage 1.
3. **Stage 2b — Speakers** — internal scroll only; no top-level right
   scrollbar (unchanged by this fix).
4. **Stage 3 — Workspace** — internal scroll only inside the sidebar /
   main column; no top-level right scrollbar (unchanged).
5. **Stage 4 — Insertions** — long content, vertical scroll on right
   gutter, same position.
6. **Stage 5 — Certify** — short centered card. The card should sit in
   the same horizontal position as on long screens — it should **not**
   jump sideways when navigating from stage 4 or 6.
7. **Stage 6 — Export** — long content, vertical scroll on right gutter,
   same position.

Confirm:
- No horizontal scrollbar appears on any screen.
- The right-edge scrollbar gutter is visually consistent across stages
  1, 2, 4, 5, 6 (its width is reserved even when stage 5 doesn't need to
  scroll).
- Stages 2b and 3 still scroll internally without a top-level scrollbar.

## Follow-ups (none)

Audit found a single root cause; one rule resolves it. No secondary
issues were observed.
