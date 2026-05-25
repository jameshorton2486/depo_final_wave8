# SCROLLBAR_FIX.md — Diagnose & Fix Scrollbar Inconsistency

## Mission

The 7 stage screens render inconsistently: some show a right-hand
vertical scrollbar, some do not. Find the ONE root cause and apply the
MINIMAL fix so every stage screen scrolls consistently.

You are a careful engineer. Audit first, fix second. This is a small,
contained task — do not expand its scope.

## Scope — strict

IN scope: `frontend/assets/css/app.css`, `frontend/index.html`, the 7
files `frontend/screens/stage_*.html`, and the screen-shell / router
code in `frontend/assets/js/router.js` or `app.js` ONLY if that is
where the layout container is defined.

OUT of scope — DO NOT TOUCH: any backend file, any test, the stage
JavaScript logic (`stage_*.js`), the certify/packaging wiring, or the
content/behavior of any screen. This task changes LAYOUT/OVERFLOW CSS
only — never logic, never markup meaning.

## Phase 0 — Audit first (no fix yet)

1. Identify the shared layout container every stage screen renders
   into (the scroll host). Find it in `index.html` / the router.
2. For EACH of the 7 `stage_*.html` screens, determine why it does or
   does not produce a scrollbar. Look specifically for:
   - per-screen `height`, `min-height`, `h-screen`, `h-full`,
     `overflow-*`, or fixed-height utility classes,
   - screens whose root element sets overflow/height while others do
     not,
   - a wrapper that has `overflow-hidden` on some routes but not
     others.
3. Determine the ONE root cause of the inconsistency — the single
   structural difference between scrollbar screens and non-scrollbar
   screens.
4. Write findings to `SCROLLBAR_AUDIT.md`: per-screen, what its root
   element does for height/overflow, and the identified root cause.

Do NOT change anything until the audit is written.

## Phase 1 — Minimal fix

- Apply the SMALLEST change that makes all 7 screens consistent.
  Strongly prefer ONE shared rule on the common scroll container
  (e.g. a consistent `overflow-y` and height on the screen shell) over
  editing 7 files separately.
- The target behavior: every stage screen uses the SAME scroll model —
  the shared container scrolls vertically when content overflows, and
  does not when it does not. No horizontal scrollbar on any screen.
- Avoid `overflow-y: scroll` forced always-on unless that is genuinely
  the cleanest consistent result; prefer `auto`.
- Do not introduce layout shift, do not change widths, do not restyle
  anything. Colors, spacing, fonts, components — all untouched.

## Phase 2 — Verify

- Run `node --check` on any `.js` file changed (if any).
- List every file changed and confirm it is only CSS/layout.
- Write `SCROLLBAR_FIX_RESULT.md`: the root cause, the one fix applied,
  the files touched, and a short manual check ("load each of the 7
  stages; confirm consistent vertical scroll, no horizontal bar").

## Rules

- Audit before fixing. One root cause, one minimal fix.
- Do NOT commit — leave changes staged for the user to review.
- If the inconsistency turns out to have MORE than one root cause,
  do not sprawl: fix the primary one, log the rest in
  `SCROLLBAR_FIX_RESULT.md` as follow-ups, and stop.
- Touch no logic, no backend, no tests.

## Stop conditions

Stop when all 7 stage screens share one consistent scroll model and
the result file is written — or when the cause is genuinely more
complex than a layout fix, in which case write the audit, apply
nothing, and explain in `SCROLLBAR_FIX_RESULT.md`.

Begin with Phase 0.
