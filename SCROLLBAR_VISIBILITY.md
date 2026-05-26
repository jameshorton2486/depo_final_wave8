# SCROLLBAR_VISIBILITY.md — Make the scrollbar visible on dark screens

## Mission

The earlier fix (`scrollbar-gutter: stable` on `.stage-panel`) made the
layout stop shifting — that part works and is committed. But on the
dark stage screens the scrollbar itself is hard or impossible to SEE,
so a user cannot tell a screen scrolls (e.g. the Stage 5 Certify screen
has content below the fold with no visible scroll cue).

Make the custom scrollbar clearly visible against the dark UI, without
changing its width or the layout.

## Scope — strict

IN scope: `frontend/assets/css/app.css` ONLY — specifically the
existing `::-webkit-scrollbar` rule block (the 6px-wide custom
scrollbar) and, if needed, a matching `scrollbar-color` for Firefox.

OUT of scope — DO NOT TOUCH: any HTML, any JS, any backend, any test,
any other CSS rule. Do not change the scrollbar WIDTH (keep 6px). Do
not change `scrollbar-gutter`. Do not restyle anything else.

## Phase 0 — Audit first (no change yet)

1. Find the `::-webkit-scrollbar`, `::-webkit-scrollbar-track`, and
   `::-webkit-scrollbar-thumb` rules in `app.css`. Quote them.
2. Identify exactly why the thumb is hard to see — most likely the
   thumb color is too close to the dark panel background, or has low
   opacity, or no color set at all.
3. Note the dark panel background color used by the stage screens so
   the new thumb color can be chosen to contrast with it.
4. Write findings briefly to `SCROLLBAR_VIS_AUDIT.md`.

## Phase 1 — Minimal fix

- Give `::-webkit-scrollbar-thumb` a color that is clearly visible
  against the dark panels — a mid-grey that contrasts but is not
  harsh (it should read as a subtle but unmistakable scrollbar, not
  a bright bar). A `:hover` state slightly lighter is good.
- Give `::-webkit-scrollbar-track` a subtle treatment so the gutter
  reads as a track, or leave it transparent — whichever looks
  cleaner against the panels.
- Add a Firefox fallback: `scrollbar-color: <thumb> <track>;` and
  `scrollbar-width: thin;` on the scrolling elements (`.stage-panel`),
  matching the webkit colors.
- Keep the width at 6px. Change only color/visibility.

## Phase 2 — Verify

- `git diff --stat` — confirm ONLY `app.css` changed.
- Write `SCROLLBAR_VIS_RESULT.md`: the root cause, the exact rule
  changes, and a manual check note.
- Do NOT commit — leave staged for the user to review.

## Manual check (required — visual)

The user must hard-refresh (Ctrl+Shift+R) and look at the stage
screens, especially Stage 5 Certify: a scrollbar should now be
clearly visible on screens whose content overflows, and absent on
screens that fit. No layout shift (that was the earlier fix and must
still hold).

## Rules

- Audit before changing. One file, color/visibility only.
- Do not commit. Do not touch width, layout, JS, HTML, or backend.
- If the cause turns out to be more than a color issue, write the
  audit, change nothing, and explain in SCROLLBAR_VIS_RESULT.md.
