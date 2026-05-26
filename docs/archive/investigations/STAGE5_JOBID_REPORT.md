> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# STAGE5_JOBID_REPORT.md — Why `state.jobId` Is Empty at Stage 5

## TL;DR Verdict

**(B) WIRING BUG.** `state.jobId` is read in three places in
`frontend/assets/js/screens/stage_5.js` but is **never assigned anywhere
in the repository**. Stage 2 stores the active transcript job id under
two other names — `state.activeTranscriptJobIds` (an array) and
`state.workspaceJob.jobId` — and Stage 5 reads neither. The certify
flow therefore always falls into the `if (!jobId)` branch on line 90 of
`stage_5.js` and toasts "No active job — cannot certify."

Stage 6 already solves the same problem correctly with a small
`_activeJobId()` helper (`stage_6.js:18-21`) that pulls
`state.activeTranscriptJobIds[0]`. Stage 5 should do the same.

---

## 1. Initial value of `state.jobId`

`frontend/assets/js/state.js` defines the global `state` object
(lines 1–67). **The key `jobId` does not appear in that object at all.**
Its initial value is therefore `undefined` — not `null`, just missing.

Relevant identifiers that DO exist in `state.js`:

| Field on `state` | Defined at | Initial value |
| --- | --- | --- |
| `caseId` | `state.js:8` | `null` |
| `sessionId` | `state.js:9` | `null` |
| `transcriptJobs` | `state.js:65` | `[]` |
| `jobId` | — (not declared) | `undefined` |
| `activeTranscriptJobIds` | — (lazily created at `stage_2.js:508`) | `[jobId]` once a job is opened |
| `workspaceJob` | — (lazily created at `stage_3.js:464-466`) | `{ jobId: null }` |

So Stage 5 starts life with `state.jobId === undefined`, and nothing in
the entire frontend ever changes that.

---

## 2. Every write site for `state.jobId`

A repo-wide grep for `state.jobId =` (and `state\.jobId\s*=` across the
whole project) returns **zero matches**.

| File | Line | Function | Triggering user action |
| --- | --- | --- | --- |
| _none_ | — | — | — |

There is no code path — in `app.js`, in any `stage_*.js`, in `api.js`,
or anywhere else — that assigns `state.jobId`. The field is read but
never written. This is the gap.

For comparison, the writes that DO happen when a transcription job is
opened are:

| File:line | What it sets | Triggering user action |
| --- | --- | --- |
| `stage_2.js:224` | `item.jobId = job.job_id;` (on the local `fileQueue` entry only) | Clicking "Process Queue" in Stage 2 — sets a per-file-queue-row id, not `state.jobId`. |
| `stage_2.js:508` | `state.activeTranscriptJobIds = [jobId];` | Clicking the "view" action on a server-side transcript job in Stage 2's job list (`viewTranscriptJob(jobId)`). |
| `stage_2.js:410` | calls `loadWorkspaceJobContext(jobIds[0])` after a transcript loads into the Workspace | End of `loadTranscriptResultsIntoWorkspace()` — runs after Stage 2B → workspace handoff. |
| `stage_3.js:465` | `state.workspaceJob = { jobId: null };` (initial shape) | Lazy initialization the first time `_workspaceJob()` is called. |
| `stage_3.js:474` | `wj.jobId = jobId;` (where `wj === state.workspaceJob`) | Inside `loadWorkspaceJobContext(jobId)` — called from `stage_2.js:410`. |

None of these touches `state.jobId`. They write to **different
variables on `state`** (`activeTranscriptJobIds`, `workspaceJob.jobId`).

---

## 3. Every read site for `state.jobId`

| File:line | Function | What it gates |
| --- | --- | --- |
| `stage_5.js:14` | `_saveCertFields()` | Persisting certificate metadata via `PUT /api/depo-meta/jobs/{jobId}`. |
| `stage_5.js:50` | `loadCertFields()` | Loading existing certificate metadata via `GET /api/depo-meta/jobs/{jobId}`. |
| `stage_5.js:89` | `signTranscript()` | The whole certify chain — snapshot → lock → assemble → certify. This is the read that produces the "No active job — cannot certify." toast on line 91. |

All three reads are in Stage 5, and all three use the same idiom
`const jobId = state && state.jobId;` followed by `if (!jobId) return;`
(or a toast). Because `state.jobId` is permanently `undefined`, every
one of these short-circuits.

---

## 4. The intended flow — and where it breaks

The "active job" lifecycle today:

1. **Stage 2 (ingest or open):**
   - On batch processing, each fileQueue row gets its own `item.jobId`
     (`stage_2.js:224`). This is a UI-row id, never copied to `state`.
   - On opening an existing server job, `viewTranscriptJob(jobId)` sets
     `state.activeTranscriptJobIds = [jobId]` (`stage_2.js:508`) and
     calls `loadTranscriptResultsIntoWorkspace([jobId])`.
   - At the end of `loadTranscriptResultsIntoWorkspace()`,
     `loadWorkspaceJobContext(jobIds[0])` is called
     (`stage_2.js:409-411`).

2. **Stage 3 (workspace):**
   - `loadWorkspaceJobContext(jobId)` sets
     `state.workspaceJob.jobId = jobId` (`stage_3.js:472-474`). All
     Stage 3 AI-review calls read it back via `_workspaceJob()`
     (e.g. `stage_3.js:558, 586, 666, 677`).
   - `_workspaceJob()` is a Stage-3-private holder. The id stored
     inside it is **never copied to `state.jobId`**.

3. **Stage 5 (certify):**
   - Reads `state.jobId` — which nothing ever set. Always falsy.
   - Falls into the "No active job — cannot certify." branch.

4. **Stage 6 (export) — for contrast:**
   - Uses a local helper:
     ```js
     function _activeJobId() {
         const ids = state.activeTranscriptJobIds || [];
         return ids.length > 0 ? ids[0] : null;
     }
     ```
     (`stage_6.js:18-21`). This works because Stage 2 actually does set
     `state.activeTranscriptJobIds`. Stage 5 was written against a
     different (nonexistent) source of truth.

**Variable mismatch summary**

| Source of truth                         | Set by                          | Read by                       |
| --- | --- | --- |
| `state.activeTranscriptJobIds[0]`       | `stage_2.js:508`                | `stage_6.js:19` (via `_activeJobId`) |
| `state.workspaceJob.jobId`              | `stage_3.js:474`                | `stage_3.js:558, 586, 666, 677` |
| `state.jobId`                           | **nobody — never written**      | `stage_5.js:14, 50, 89`       |

Stage 5 reads the only one of these three names that has no writer.

---

## 5. Case vs job — does selecting a case set `state.jobId`?

No. A repo-wide grep for `state.jobId =` returns zero matches in
`app.js` (case dropdown lives there) or anywhere else. Selecting a case
touches `state.caseId` / `state.caseInfo` (declared in `state.js:8`
and `state.js:13-33`) but never `state.jobId`. This is the correct
behaviour — a case is not a transcription job — and is **not** the
source of the bug. The bug would still occur even if the user opened a
transcription job correctly, because nothing on the job-open path sets
`state.jobId` either.

---

## 6. The actual gap — Verdict

**(B) WIRING BUG.**

Specifically: Stage 5 was written assuming a top-level `state.jobId`
field that nothing in the codebase ever populates. The closest existing
sources of truth are `state.activeTranscriptJobIds[0]` (used by Stage 6)
and `state.workspaceJob.jobId` (used by Stage 3's AI review queue).

Evidence:

- `state.js:1-67` — no `jobId` key in the initial `state` object.
- Grep `state\.jobId\s*=` across the repo — **0 hits**.
- Grep `state.jobId` — 3 hits, all reads, all in `stage_5.js`.
- `stage_2.js:508` writes `state.activeTranscriptJobIds`, not
  `state.jobId`.
- `stage_3.js:474` writes `state.workspaceJob.jobId`, not
  `state.jobId`.
- `stage_6.js:18-21` already reads `state.activeTranscriptJobIds[0]`
  correctly — proving that field is the established "active job" anchor.

This is not a user-flow problem: even when a user has fully ingested,
opened, mapped speakers, and walked through Stage 3 into Stage 5, the
field Stage 5 checks remains `undefined`.

---

## 7. Proposed fix (NOT applied)

Two equivalent options — option **A** is the smallest, lowest-risk
change and matches the pattern Stage 6 already established.

### Option A (recommended) — add an `_activeJobId()` helper in `stage_5.js`

Mirror `stage_6.js:18-21`. Replace the three `state.jobId` reads in
`stage_5.js` (lines 14, 50, 89) with calls to a local helper that pulls
from the source of truth Stage 2 already sets.

```diff
--- a/frontend/assets/js/screens/stage_5.js
+++ b/frontend/assets/js/screens/stage_5.js
@@ -1,6 +1,11 @@
         function _parseTimePerParty(raw) {
             ...
         }

+        function _activeJobId() {
+            const ids = (state && state.activeTranscriptJobIds) || [];
+            return ids.length > 0 ? ids[0] : null;
+        }
+
         async function _saveCertFields() {
-            const jobId = state && state.jobId;
+            const jobId = _activeJobId();
             if (!jobId) return;
             ...
         }

         async function loadCertFields() {
-            const jobId = state && state.jobId;
+            const jobId = _activeJobId();
             if (!jobId) return;
             ...
         }

         async function signTranscript() {
             ...
-            const jobId = state && state.jobId;
+            const jobId = _activeJobId();
             if (!jobId) {
                 showToast("No active job — cannot certify.", "red");
                 return;
             }
```

Pros: zero new global state, identical idiom to Stage 6, no risk of
divergence between "the job Stage 5 certifies" and "the job Stage 6
exports."

### Option B — populate `state.jobId` centrally

Add a single assignment to Stage 2's job-open path so the top-level
`state.jobId` mirrors `state.activeTranscriptJobIds[0]`, e.g. in
`viewTranscriptJob` (`stage_2.js:508`):

```diff
 async function viewTranscriptJob(jobId) {
     showToast("Loading transcript…", "indigo");
+    state.jobId = jobId;
     state.activeTranscriptJobIds = [jobId];
     await loadTranscriptResultsIntoWorkspace([jobId]);
     goToStage("2b");
 }
```

…and similarly at the end of the batch-processing pipeline where
`loadWorkspaceJobContext(jobIds[0])` is called
(`stage_2.js:409-411`). Also declare `jobId: null` in the initial
`state` object in `state.js`.

Pros: keeps Stage 5's existing reads working as written.
Cons: introduces a fourth name for the same concept that has to stay
in sync with `activeTranscriptJobIds` and `workspaceJob.jobId`. Higher
ongoing risk of drift than Option A.

**Recommendation: Option A.** It removes a redundant source of truth
instead of adding one, and brings Stage 5 in line with Stage 6's
existing, working pattern.

---

## 8. Files inspected (read-only)

- `frontend/assets/js/state.js`
- `frontend/assets/js/screens/stage_5.js` (full)
- `frontend/assets/js/screens/stage_2.js` (relevant regions)
- `frontend/assets/js/screens/stage_3.js` (relevant regions)
- `frontend/assets/js/screens/stage_6.js` (head — for `_activeJobId` pattern)
- `frontend/assets/js/screens/stage_2b.js` (grep only)
- `frontend/assets/js/app.js` (grep only)
- `frontend/assets/js/api.js` (grep only)

No files were modified.
