# OVERNIGHT_BUILD.md — Autonomous Build Plan for DEPO-PRO

You are operating as a **disciplined senior engineer**, not an
architecture brainstormer. You will work through this plan
**sequentially and autonomously**, one subsystem at a time, and
**continue to the next subsystem automatically** without waiting for
new instructions. Do not stop until every subsystem is OPERATIONAL or
all remaining work is genuinely blocked.

This is a legally-sensitive court-transcript production system. Favor
correctness, determinism, and honesty over speed or volume.

---

## Phase 0 — AUDIT FIRST (always do this before building anything)

Before writing any code:

1. Run the full test suite (`python -m pytest tests/ -q`) and record
   the pass/fail count.
2. For each subsystem in the Work Order below, classify its TRUE state
   as exactly one of:
   - **MISSING** — no code exists.
   - **SPEC-ONLY** — a doc exists, no working code.
   - **PARTIAL** — some code exists but is incomplete.
   - **BUILT-NOT-WIRED** — code exists and tests pass, but nothing in
     the running app calls it.
   - **OPERATIONAL** — built, tested, AND wired end-to-end.
3. Determine "wired" with evidence, not assumption: is the subsystem's
   router registered in `backend/app.py`? Is its module imported by
   anything under `backend/api/` or `backend/services/`? If neither,
   it is BUILT-NOT-WIRED.
4. Write all findings to `AUDIT.md` at the repo root.

This audit is authoritative. It tells you what genuinely needs work.
**Skip any subsystem the audit finds already OPERATIONAL.**

---

## Completion criteria (STRICT — do not relax these)

A subsystem may be marked **OPERATIONAL** only if ALL of these are true:

- A single authoritative backend implementation exists.
- It is persisted where persistence is relevant.
- It is wired end-to-end — reachable from a registered API route or
  from a caller that is itself reachable.
- The **full** test suite is green.
- Its behavior is deterministic.

A subsystem is **NOT** complete merely because: UI exists, files exist,
a spec exists, or a unit test for the module alone passes. Wiring is
the bar.

---

## The per-subsystem loop

For each subsystem, in order:

1. **Audit** its current state (per Phase 0).
2. **Identify the one authoritative owner** of that concern.
3. **Find and remove or consolidate** any duplicate, parallel,
   placeholder, mock, or simulated implementation of the same concern.
4. **Implement** the missing backend authority.
5. **Wire it end-to-end** — register routes, connect callers, replace
   any naive/placeholder path with the authoritative one.
6. **Add persistence** if relevant.
7. **Add or extend tests** to cover the new behavior.
8. **Run the FULL test suite.** If anything is red, fix it before
   proceeding. Never continue with a red suite.
9. **Write the REAL status** to `PROGRESS.md` — what is now
   operational, what is partial, what is still missing.
10. **Commit to git:** `git add -A && git commit -m "<subsystem>: <what changed>"`.
11. **Continue automatically** to the next subsystem.

---

## Work Order (dependency order — skip any already OPERATIONAL)

1. **Transcript State Engine** — `backend/transcript_state/`. Snapshots,
   rollback, certification locking, state hashing, export-linked
   snapshots, append-only audit. Ensure `api/snapshots.py` is
   registered in `app.py`.

2. **Canonical Renderer Consolidation** — there must be exactly ONE
   render/pagination authority. Today `backend/transcript/export_render.py`
   runs its own naive 25-line paginator while `backend/pagination/`
   contains a separate Pagination Engine. Consolidate: the export and
   preview paths must consume the canonical render + the Pagination
   Engine, not a private paginator. Remove the duplicate.

3. **Filesystem-Native Export Engine** — `backend/export/`. Verify real
   DOCX and PDF generation, save destinations, and export records.
   Confirm the export endpoint and Export Preview share one builder.

4. **Pagination Engine** — `backend/pagination/`. Wire its output into
   the export and preview paths (it is currently called only by tests).

5. **Geometry Layer** — `backend/geometry/`. Today only the measurement
   profile (`profile.py`) exists. Build the missing geometry layer
   engine: a function that takes a paginated document + GeometryProfile
   and produces the format box, line numbers, page numbers, headers,
   and footers. Then wire it into the DOCX/PDF writers.

6. **Packaging Engine** — `backend/packaging/`. Add `backend/api/packaging.py`
   (mirror `api/snapshots.py`), register it in `app.py`, and wire the
   engine so a certified package can be assembled for a job via the API.

Do NOT build the AI Review Engine, new screens, animations, or
cosmetic changes. Stay strictly within this Work Order.

---

## Hard rules

- **One authority per concern.** Never create a second or parallel
  system. If you find duplicates, consolidate to one before continuing.
- **No fake completion.** Classify honestly. If something is partial,
  say so in `PROGRESS.md`.
- **Tests gate progress.** Full suite green after every subsystem.
- **Commit after every subsystem** so progress is recoverable.
- **Blockers do not stop the run.** If you hit a genuine blocker — a
  legal/UFM measurement decision, a missing API key, an ambiguous spec
  — do NOT halt. Log it in `BLOCKERS.md`, use the conservative default
  already present in the code (e.g. the proposed values in
  `geometry/profile.py`), mark that item PARTIAL, and continue to the
  next subsystem.
- **Never invent authoritative legal values.** UFM measurements,
  certificate wording, and required-field sets that are not confirmed
  must be flagged in `BLOCKERS.md`, not fabricated as final.

---

## Stop conditions

Stop only when one of these is true:
- Every subsystem in the Work Order is OPERATIONAL, OR
- Every remaining subsystem is blocked (all blockers logged in
  `BLOCKERS.md`).

When you stop, write a final summary to `PROGRESS.md`: what is now
operational, what remains partial, what is blocked and why, and the
recommended next step.

---

## Deliverables to maintain throughout

- `AUDIT.md` — the Phase 0 reality-state classification.
- `PROGRESS.md` — running log of real status after each subsystem.
- `BLOCKERS.md` — every decision or dependency that needs James.

Begin with Phase 0 now.
