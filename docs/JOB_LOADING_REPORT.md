# JOB_LOADING_REPORT.md — Why Persisted Transcript Sessions Renders Empty

## TL;DR Verdict

**(B) Over-aggressive filter excludes all jobs.** The frontend sends
`state.caseId` as a query-string filter to `GET /api/transcripts/jobs`,
the backend applies a strict `WHERE case_id = ?` SQL filter, and every
one of the 16 ingested jobs in the database has `case_id IS NULL`. The
filtered query therefore returns zero rows, the panel renders the
"No transcripts ingested yet" placeholder, and no job can be opened.

A bare `GET /api/transcripts/jobs` (no query string) returns the
expected `{jobs: Array(16), count: 16}` — which is exactly what the
user observed when calling it directly. As soon as a case is loaded in
the UI, `state.caseId` becomes non-null, the frontend appends
`?case_id=<id>`, and the result collapses to `{jobs: [], count: 0}`.

The response-shape access is **correct** (`(listing && listing.jobs) || []`)
and the render function IS called on Stage 2 mount. The only break is
the implicit case scoping.

---

## 1. The persisted-sessions panel — DOM container, render function, when called

| Concern | Where | Notes |
| --- | --- | --- |
| DOM container | `frontend/screens/stage_2_transcripts.html:203` | `<div ... id="serverJobsList">` (inside "SECTION C: PERSISTED TRANSCRIPT SESSIONS", lines 191–206). |
| Placeholder text | `frontend/screens/stage_2_transcripts.html:204` | The "No transcripts ingested yet" markup is also re-emitted by `renderServerTranscriptJobs()` at `frontend/assets/js/screens/stage_2.js:437`. |
| Populator (fetch) | `frontend/assets/js/screens/stage_2.js:419-429` | `async function refreshServerTranscriptJobs()` — fetches, stores into `state.transcriptJobs`, then calls `renderServerTranscriptJobs()`. |
| Populator (render) | `frontend/assets/js/screens/stage_2.js:431-489` | `function renderServerTranscriptJobs()` — reads `state.transcriptJobs`, builds the cards. |
| Invocation: Stage 2 mount | `frontend/assets/js/app.js:355-356` | `screen:loaded` handler for `stageNum === 2` calls `renderServerTranscriptJobs()` then `refreshServerTranscriptJobs()`. |
| Invocation: "Refresh" button | `frontend/screens/stage_2_transcripts.html:198` | `onclick="refreshServerTranscriptJobs()"`. |
| Invocation: after ingest | `frontend/assets/js/screens/stage_2.js:274` | `await refreshServerTranscriptJobs();` at the tail of `startSequentialIngestion()`. |
| Invocation: after delete | `frontend/assets/js/screens/stage_2.js:518` | `await refreshServerTranscriptJobs();` inside `deleteServerTranscriptJob()`. |
| Exposed to global | `frontend/assets/js/screens/stage_2.js:766-767` | `window.refreshServerTranscriptJobs = …; window.renderServerTranscriptJobs = …;` |

So the function is correctly wired and **is** being called on every
sensible trigger. The container exists. The render function does run —
it just sees `state.transcriptJobs = []`.

---

## 2. The API call

`refreshServerTranscriptJobs()` calls (`stage_2.js:422`):

```js
const listing = await window.api.listTranscriptJobs(state.caseId || null);
```

Which resolves to (`frontend/assets/js/api.js:292-295`):

```js
listTranscriptJobs(caseId) {
    const q = caseId ? `?case_id=${encodeURIComponent(caseId)}` : '';
    return _fetch('GET', `/transcripts/jobs${q}`);
},
```

So the actual request is:

| `state.caseId` value | URL sent |
| --- | --- |
| `null` / falsy | `GET /api/transcripts/jobs` |
| `"abc-123"` | `GET /api/transcripts/jobs?case_id=abc-123` |

The endpoint exists (`backend/api/transcripts.py:169-177`):

```python
@router.get("/jobs", response_model=TranscriptJobList)
def list_jobs(
    case_id: str | None = Query(default=None, description="Filter to one case"),
) -> TranscriptJobList:
    rows = trepo.list_jobs(case_id=case_id)
    return TranscriptJobList(
        jobs=[TranscriptJob(**r) for r in rows],
        count=len(rows),
    )
```

And `trepo.list_jobs` (`backend/transcript/repository.py:133-149`):

```python
def list_jobs(case_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        if case_id:
            rows = conn.execute(
                f"SELECT {', '.join(_JOB_COLUMNS)} FROM transcript_jobs "
                "WHERE case_id = ? "
                "ORDER BY sequence_index ASC, created_at DESC, rowid DESC LIMIT ?",
                (case_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {', '.join(_JOB_COLUMNS)} FROM transcript_jobs "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_job_row_to_dict(r) for r in rows]
```

When `case_id` is provided, it filters strictly — there is **no
fallback for jobs with `case_id IS NULL`.**

---

## 3. Response shape — does the frontend read it correctly?

**Yes.** Line `stage_2.js:423`:

```js
state.transcriptJobs = (listing && listing.jobs) || [];
```

The backend returns the documented object `{jobs: [...], count: N}`
(see `TranscriptJobList`), and the frontend reads `.jobs` off it.
This is **not** the bug. (It is the obvious-looking bug — the prompt
specifically called it out — but the code defends against it.)

The empty-fallback `|| []` is what kicks in once the upstream filter
returns `{jobs: [], count: 0}`, and from there the renderer falls
straight into its placeholder branch (`stage_2.js:436-440`).

---

## 4. The render path

`renderServerTranscriptJobs()` at `stage_2.js:431-489`:

1. Reads `const jobs = state.transcriptJobs || [];` (line 435).
2. If empty → injects the placeholder HTML (`stage_2.js:437`), updates
   the engine-mode badge to neutral, and returns. **This is what the
   user sees.**
3. Otherwise → builds one card per job and appends to `serverJobsList`.

No status filter (`completed` / `failed` / `queued`) is applied at the
render layer — all statuses are rendered, with the "Open in Workspace"
button disabled (`stage_2.js:477`) for non-`completed` jobs. So the
empty list is **not** caused by every job being filtered out client-
side; the array is genuinely empty before the renderer ever sees it.

---

## 5. Case/session filtering — confirmed root cause

The frontend implicitly scopes the panel to the currently loaded case
by passing `state.caseId` as `case_id`. Live DB inspection
(`data/sqlite/depo_pro.db`) confirms the mismatch:

```text
total / case_id IS NULL / case_id NOT NULL : (16, 16, 0)
groups by case_id                          : [(None, 16)]
```

All 16 ingested jobs have `case_id = NULL`. They were ingested via the
"transcribe-first" path — `backend/api/transcripts.py:94`
(`case_id: str | None = Form(default=None)`) and the comment at lines
127-128 ("An absent case_id is allowed (transcribe-first).") explicitly
permit this.

The moment the user loads any case in Stage 1, `state.caseId` becomes
non-null. Every subsequent call from Stage 2's panel sends
`?case_id=<that case>`, and the SQL filter `WHERE case_id = ?` excludes
all 16 unlinked rows.

---

## 6. The "Refresh" button

`frontend/screens/stage_2_transcripts.html:198` →
`onclick="refreshServerTranscriptJobs()"`. That handler re-runs the
exact same API call (with the same `state.caseId` filter), so clicking
"Refresh" produces the same empty result. It is not a separate code
path; it cannot mask the bug.

---

## 7. Click-to-open path — is `viewTranscriptJob` sound?

Yes, but it is currently unreachable because no card is rendered. For
the record (`frontend/assets/js/screens/stage_2.js:506-511`):

```js
async function viewTranscriptJob(jobId) {
    showToast("Loading transcript…", "indigo");
    state.activeTranscriptJobIds = [jobId];
    await loadTranscriptResultsIntoWorkspace([jobId]);
    goToStage("2b");
}
```

That correctly:

1. Sets `state.activeTranscriptJobIds = [jobId]` — the source of truth
   read by `stage_6.js:_activeJobId()` and (now, after today's fix)
   `stage_5.js:_activeJobId()`.
2. Calls `loadTranscriptResultsIntoWorkspace`, which pulls content via
   `window.api.getTranscriptContent` and, on line 410, also calls
   `loadWorkspaceJobContext(jobIds[0])` to populate
   `state.workspaceJob.jobId`.
3. Navigates to Stage 2B (speaker mapping), from which the user
   proceeds into Stage 3.

So once the panel renders a card and the user clicks "Open in
Workspace", the entire downstream chain (`activeTranscriptJobIds` →
Stage 3 workspace job context → Stage 5 cert flow → Stage 6 export) is
already in place and was verified earlier today via Stage 5's
`_activeJobId()` fix. **The only break is the empty list.**

---

## 8. Verdict and proposed fix (NOT applied)

**Root cause:** (B) over-aggressive case-scoped filter. The panel is
the user's library of "everything I have ingested", but the frontend
treats it as "what belongs to this specific case", and unlinked jobs
(`case_id IS NULL`) are then invisible.

There are two clean places to fix this; **Option A is recommended.**

### Option A (recommended) — drop the implicit case scope on the listing call

Remove the `state.caseId` argument so the panel always shows the full
library. This is the simpler change and matches the panel's intent
("Open a completed session to load it into the Stage 3 Workspace" —
quote from `stage_2_transcripts.html:201`).

```diff
--- a/frontend/assets/js/screens/stage_2.js
+++ b/frontend/assets/js/screens/stage_2.js
@@ -419,7 +419,7 @@ async function refreshServerTranscriptJobs() {
 async function refreshServerTranscriptJobs() {
     if (!window.api) return;
     try {
-        const listing = await window.api.listTranscriptJobs(state.caseId || null);
+        const listing = await window.api.listTranscriptJobs(null);
         state.transcriptJobs = (listing && listing.jobs) || [];
     } catch (err) {
         console.warn("Could not load transcript jobs:", err);
```

Pros: minimal, frontend-only, no schema or API changes. Restores the
exact behaviour the user already validated by hitting
`/api/transcripts/jobs` directly.

Cons: the panel will show *all* ingested jobs, even those linked to a
different case. For a single-user / single-case workflow that is
desirable. If multi-case isolation is later required, switch to
Option B.

### Option B — make the backend filter include NULL case_id rows

Treat unlinked jobs as belonging to "any case" and surface them
alongside the case-matched ones:

```diff
--- a/backend/transcript/repository.py
+++ b/backend/transcript/repository.py
@@ -133,7 +133,7 @@ def list_jobs(case_id: Optional[str] = None, limit: int = 100) -> list[dict]:
     with get_connection() as conn:
         if case_id:
             rows = conn.execute(
                 f"SELECT {', '.join(_JOB_COLUMNS)} FROM transcript_jobs "
-                "WHERE case_id = ? "
+                "WHERE case_id = ? OR case_id IS NULL "
                 "ORDER BY sequence_index ASC, created_at DESC, rowid DESC LIMIT ?",
                 (case_id, limit),
             ).fetchall()
```

Pros: preserves case scoping for jobs that *are* linked to a case,
while still showing transcribe-first jobs that have no case yet.

Cons: changes documented endpoint semantics; existing tests
(`tests/test_transcripts_api.py`) may assume strict equality and would
need review. Not strictly necessary if Option A is taken.

### What NOT to fix

- The response-shape access (`listing.jobs`) is correct — leave it.
- The render function — it works; the bug is upstream of it.
- `viewTranscriptJob` — already correct and consistent with the rest
  of the wiring.

---

## 9. Files inspected (read-only)

- `frontend/screens/stage_2_transcripts.html` (Section C panel + Refresh button)
- `frontend/assets/js/screens/stage_2.js` (refresh/render/view paths)
- `frontend/assets/js/api.js` (`listTranscriptJobs` helper)
- `frontend/assets/js/app.js` (`screen:loaded` invocation)
- `backend/api/transcripts.py` (`/jobs` GET + ingest form)
- `backend/transcript/repository.py` (`list_jobs` SQL filter)
- `data/sqlite/depo_pro.db` (read-only `SELECT` to confirm the 16 rows
  all have `case_id IS NULL`)

No files were modified.
