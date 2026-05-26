> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# DEPO-PRO — Wave 11: Workspace Speaker Panel & Assign Speakers

**Build Specification**

Wave 11 · Builds on Wave 9 (Speaker Mapping) · Coordinates with the Wave 10
Deterministic Correction Engine. Repo location for this doc: `docs/`.

---

## 1. Purpose

Wave 9 added a dedicated **Step 2B — Speaker Mapping** screen: the user assigns
each detected Deepgram speaker to a role and a name before the Workspace opens.
Wave 11 makes that mapping **editable from inside the Workspace**, so a reporter
who notices a wrong attribution while reviewing the transcript can fix it on the
spot — without going back a step.

It also upgrades the name field from free text to a **dropdown of known case
names**, adds **add / remove participant** controls, and adds an explicit
**Assign Speakers** action that re-renders the transcript from the corrected
mapping.

This wave is primarily UI and workflow. The data layer (`transcript_participants`)
already exists from Wave 9 and is largely reused.

---

## 2. Background — What Exists Today

- **Step 2B — Speaker Mapping** (Wave 9): per-job screen. Lists each detected
  speaker cluster with a sample utterance, word/turn counts, a deterministically
  prefilled **role** dropdown, and a free-text **name** input. "Confirm Mapping &
  Continue" writes to `transcript_participants` and advances to the Workspace.
- **Workspace** has a "SPEAKERS & ROLES" side panel that currently only **lists**
  speakers (`Speaker 0 … Speaker 7`, each labelled "Speaker Block"). It is
  read-only and does not show the assigned role or name.
- `transcript_participants` table (Wave 9): `participant_id`, `job_id`, `name`,
  `role`, `speaker_indices` (JSON array of detected cluster indices), `is_prefill`,
  `sort_order`.

---

## 3. Core Concept — Clusters vs. Participants

This distinction governs the whole wave. Get it right and add/delete/merge all
fall out cleanly.

- A **detected speaker cluster** (`Speaker 0`, `Speaker 1`, …) is an *acoustic*
  grouping produced by Deepgram. Clusters are **fixed** — they come from RAW and
  cannot be created or destroyed by the user. One real person on a shifting
  microphone is often split across several clusters.
- A **participant** is a *person* — a role plus a name. Participants are what the
  user edits. A participant holds one or more clusters in its `speaker_indices`
  array. Putting two clusters under one participant **is** the merge mechanism
  Wave 9 already defined.

Therefore:

- **Add** creates a new *participant* — never a cluster.
- **Delete** removes a *participant*. Its clusters become **unmapped** — they are
  not erased (RAW is immutable; testimony is never lost). An unmapped cluster
  renders with its raw `Speaker N` label and a `[SCOPIST: FLAG]`, exactly as
  Wave 9 already handles unknown speakers.
- **Merge** = give two clusters the same participant (same role + name).

The panel shows **one row per participant**, plus any **unmapped clusters** as
greyed, flagged rows at the bottom.

---

## 4. The Workspace "Speakers & Roles" Panel

Replaces the current read-only list. One row per participant.

### 4.1 Row layout

Each participant row shows, left to right:

1. **Cluster indicator** — a coloured dot + the cluster label(s) the participant
   covers (`Speaker 1`, or `Speaker 3 + 4` when merged).
2. **Cluster stats** — word count and turn count (or "merged" when multiple).
3. **Role dropdown** — the nine Wave 9 roles (examining attorney, witness,
   defending attorney, co-counsel, court reporter, videographer, interpreter,
   off-record, other).
4. **Name dropdown** — see 4.3.
5. **Remove button** (trash icon) — deletes the participant (4.6).

Unmapped clusters appear as dashed, greyed rows beneath the participants, marked
`flagged`, with no role/name controls — they exist so the user can see what is
not yet assigned and choose to add a participant for them.

### 4.2 Role dropdown

Identical to Step 2B. Deterministically prefilled by the Wave 9 heuristic on
first load; freely changeable.

### 4.3 Name dropdown — formal speaker labels

This replaces the free-text name field. The dropdown lists **formal speaker
labels directly** — the exact string that will appear in the transcript — built
**deterministically** (no AI) from data the app already holds. See Section 6 for
the label-formatting rule.

The dropdown options for a given job are, for example:

- `MR. NUNEZ`, `MS. ZAHN` — attorneys, from the Wave 8 NOD parser;
- `MR. THOMAS` — the witness, from the NOD parser (surname) + honorific (4.3.1);
- `THE REPORTER`, `THE VIDEOGRAPHER`, `THE INTERPRETER` — court officers, fixed
  labels selected by role, no name;
- a final **"Other…"** option that reveals a small field where the reporter
  types a label directly (it is stored verbatim, so the reporter is responsible
  for formatting it `MR. SURNAME`).

The reporter picks the finished label — there is no separate "full name then
render" step. The stored participant `name` **is** the label string.

#### 4.3.1 Witness honorific

An attorney's honorific is normally in the NOD (`Mr.` / `Ms.`), so `MR. NUNEZ`
builds automatically. The **witness** honorific is not always in the NOD, so:

- if the NOD supplies the witness honorific, use it;
- otherwise the reporter sets it on the participant row — a small `MR. / MS. /
  MRS. / DR.` selector beside the witness name. The label is not finalised until
  the honorific is set.

The label is then `{HONORIFIC} {SURNAME}`, all-caps, **one space** after the
period (Section 6).

The dropdown options are delivered as a `candidate_names` list on the
speaker-mapping API payload (Section 8). Building this list needs no model — it
is a read from parsed metadata plus the role-to-label rule.

### 4.4 AI name suggestion — optional, deferred

*Pre-selecting* which candidate name belongs to which cluster is the only part of
this wave that would involve AI. It is **optional and deferred to the AI wave**.
The panel ships fully functional without it.

When the AI suggestion module is enabled (later wave), it may **pre-select** a
name in the dropdown and mark the row with a `name suggested` badge — styled like
the Wave 9 `PREFILLED GUESS — REVIEW` badge. Rules:

- A suggestion is only ever a **pre-selection the user reviews** — never applied
  silently, never locked.
- The user can change or clear it like any other dropdown value.
- If the suggestion module is off, the dropdown simply opens unselected (or on a
  best-effort deterministic guess — see below).

**Deterministic best-effort prefill (in scope, no AI):** appearance statements
follow a recognisable pattern — "`{name}` for the {defendant|plaintiff}…". A
deterministic regex can read the *first* utterance of a cluster and, when it
matches that pattern, pre-select the name. This catches the easy cases (e.g.
`Speaker 2` → "Lucia Zahn for the defendant…") with no model. Anything not
matching the pattern is left unselected for the user. This is best-effort only;
it never overrides a user choice and never guesses outside the pattern.

### 4.5 Add Speaker (+)

A "+ Add speaker" button below the rows creates a **new participant** — a blank
row with empty role and name dropdowns and no clusters yet. The user then either:

- assigns it one or more **unmapped clusters** (via a small cluster picker on the
  row), or
- leaves it cluster-less if they are pre-staging a participant.

Use case: the deterministic prefill produced fewer participants than there really
are (e.g. a co-counsel whose few words were folded into another cluster), and the
reporter wants an explicit participant for them.

### 4.6 Remove / Delete

The trash button removes a **participant**. On delete:

- the participant row disappears;
- its clusters become **unmapped** and reappear as dashed flagged rows;
- **no transcript text is deleted** — the affected utterances re-render with
  their raw `Speaker N` label and a `[SCOPIST: FLAG]` until reassigned.

A short confirmation ("Remove this participant? Its speakers become unmapped —
no testimony is deleted.") prevents accidental clicks. Delete is fully reversible
— re-add the participant or reassign the cluster.

### 4.7 Assign Speakers button

A primary **"Assign speakers & re-render"** button at the foot of the panel.
Pressing it:

1. saves the current participant list to `transcript_participants`;
2. triggers a re-render of the WORKING transcript from the new mapping;
3. if the Wave 10 correction engine is present, **re-runs the deterministic
   pipeline** (idempotent — Section 7).

The button is enabled whenever the panel has unsaved edits. After a successful
run it returns to a disabled "Assigned" state until the next edit.

---

## 5. One Source of Truth

Step 2B and the Workspace panel are **two views of the same data** —
`transcript_participants`, keyed by `job_id`. Editing in either place writes the
same rows. There is no separate copy and no sync logic to drift:

- Step 2B remains the **initial mapping gate** before the Workspace opens.
- The Workspace panel is for **corrections during review**.

Both call the same save endpoint. Whichever was edited last is current.

---

## 6. What Renders From the Mapping

Once participants are assigned:

- **Examining attorney** utterances render as `Q.` lines.
- **Witness** utterances render as `A.` lines.
- Every other role renders as **named colloquy** using the speaker label below.
- **Unmapped clusters** render as `Speaker N` colloquy + a flag.

No AI touches the record. The mapping is deterministic data; rendering is a
deterministic transform of it.

### 6.1 Speaker label formatting rule

The speaker label is derived deterministically from the participant's role and
name. Two forms:

- **Attorneys and the witness** — `{HONORIFIC} {SURNAME}`, all-caps, with
  **exactly one space** after the honorific period:
  `MR. NUNEZ`, `MR. THOMAS`, `MS. ZAHN`.
  Roles: examining attorney, defending attorney, co-counsel, witness.
- **Court officers** — a fixed `THE`-form label, no name:
  `THE REPORTER`, `THE VIDEOGRAPHER`, `THE INTERPRETER`.
  Roles: court reporter → `THE REPORTER` (never `THE COURT REPORTER`),
  videographer → `THE VIDEOGRAPHER`, interpreter → `THE INTERPRETER`.

Rules:

- **One space** after the honorific period — `MR. THOMAS`, never `MR.  THOMAS`.
  This is consistent with the correction engine's POST-03 decision; the two
  specs must agree.
- All-caps for the whole label.
- In a colloquy line the label is followed by a colon and **two** spaces before
  the text (`MR. NUNEZ:  Objection.`) — the two-space colon rule is separate
  from the one-space honorific rule and is unchanged.
- The label string is what the name dropdown offers (Section 4.3) and what is
  stored as the participant `name`.

**Cross-reference:** this rule is the Wave 11 statement of the correction
engine's STD-SPK-01 / STD-SPK-02 (speaker label format; `THE REPORTER` never
`THE COURT REPORTER`). The Legal Standards Reference must be updated to the
one-space honorific standard so all three documents agree (see also engine spec
Open Question Q2).

---

## 7. Execution Model — When the Rules Engine Runs

This answers the question directly: **the user does not click a button to make
the deterministic corrections happen the first time.**

### 7.1 First pass — automatic, background

```
Deepgram transcription completes      →  RAW saved (immutable)
Assembler builds canonical utterances
Step 2B Speaker Mapping confirmed      →  transcript_participants populated
        │
        ▼  (automatic trigger — no user action)
Deterministic correction engine runs in the background
        │
        ▼
Workspace opens — already showing the corrected WORKING transcript
```

The engine is triggered by **"speaker mapping confirmed"**, not by "transcription
finished" — its role-scoped stages need the confirmed roles to exist.
Transcription completing is not sufficient on its own.

It runs in the background because it is deterministic, fast (regex and dictionary
lookups, **no API calls**), idempotent, and reversible — there is no cost, risk,
or latency reason to gate it behind a click, and a mandatory button is a step
that gets forgotten.

### 7.2 Re-runs — explicit, triggered by input changes

The engine **re-runs** when an input it depends on changes. Each of these is a
trigger:

- **Assign Speakers** pressed in the Workspace panel (speaker mapping changed);
- `confirmed_spellings` edited;
- `deterministic_parity_mode` toggled.

A re-run is the same idempotent pipeline. Because the engine is idempotent,
re-running is always safe — running it twice equals running it once.

### 7.3 The "Execute Rules Engine" button

Any existing or planned "Execute Python Rules Engine" control is a **manual
re-run affordance** — equivalent to the re-run triggers above. It is never
required for the first pass. "Assign Speakers" is effectively a scoped re-run
button specific to speaker-mapping changes.

### 7.4 Summary

| Question | Answer |
|---|---|
| Does the user click a button for first-pass corrections? | **No** — automatic, background. |
| What triggers the first pass? | Speaker Mapping **confirmed** (not transcription alone). |
| What is "Execute Rules Engine" / "Assign Speakers" for? | **Re-running** after an input changes. |
| Is re-running safe? | Yes — the engine is idempotent and reversible. |

---

## 8. Data Model

`transcript_participants` (Wave 9) already supports add / delete / merge / role /
name. The participant `name` now stores the **finished speaker label** (`MR.
THOMAS`, `THE REPORTER`) — see Section 6.1. Wave 11 adds:

| Column | Type | Purpose |
|---|---|---|
| `name_source` | TEXT | `prefill_deterministic` \| `ai_suggested` \| `user_confirmed` — drives the row badge and lets the UI show what is a guess vs. confirmed. |
| `honorific` | TEXT | `MR` \| `MS` \| `MRS` \| `DR` \| NULL — for attorney/witness rows. Sourced from the NOD when present, else set by the reporter on the row (Section 4.3.1). The label is rebuilt as `{honorific}. {surname}` whenever this or the surname changes. NULL for court-officer roles. |
| `cluster_unmapped` | — | Not a column; "unmapped" is simply a cluster index present in RAW but absent from every participant's `speaker_indices`. Derived, not stored. |

Add/delete are INSERT/DELETE on existing rows; merge is a multi-element
`speaker_indices` array.

---

## 9. API Changes

- **`GET /api/transcripts/jobs/{job_id}/speaker-mapping`** — extend the response
  with `candidate_names: list[str]` (Section 4.3 — a list of finished label
  strings, e.g. `["MR. NUNEZ", "MS. ZAHN", "THE REPORTER", …]`) and, per
  participant, `name_source` and `honorific`.
- **`PUT /api/transcripts/jobs/{job_id}/speaker-mapping`** — already exists;
  accepts the full participant list, so add and delete are just a changed list.
  No new endpoint needed for editing.
- **`POST /api/transcripts/jobs/{job_id}/speaker-mapping/apply`** — new. The
  "Assign Speakers" action: persists the participant list, re-renders the WORKING
  transcript, and (if present) re-runs the Wave 10 correction engine. Returns the
  re-rendered content so the Workspace can refresh in place.

The Workspace already receives `participants` on `GET .../content` (Wave 9), so
the panel has its data on load.

---

## 10. Build Steps

1. **Schema** — add `name_source` and `honorific` to `transcript_participants`;
   migration picks them up via the existing `schema_v*.sql` glob.
2. **Label builder** — a deterministic function `participant_label(role, surname,
   honorific)` implementing Section 6.1: `{HONORIFIC}. {SURNAME}` (one space) for
   attorney/witness roles; fixed `THE …` label for court-officer roles. Used by
   both the candidate-names builder and the renderer so they cannot diverge.
3. **Candidate names** — a `candidate_names` builder reading NOD-parsed metadata
   + `reporter_name` + `confirmed_spellings`, passing each through the label
   builder so the dropdown offers finished labels.
4. **Witness honorific selector** — the `MR. / MS. / MRS. / DR.` control on the
   row (Section 4.3.1); pre-set from the NOD when available, else reporter-set;
   rebuilds the label on change.
5. **Deterministic name prefill** — the appearance-statement regex (Section 4.4);
   sets `name_source = prefill_deterministic` on a match.
6. **Workspace panel** — rebuild the "SPEAKERS & ROLES" panel as the editable
   participant list: rows, role + name dropdowns, remove button, unmapped-cluster
   rows.
7. **Add / remove** — "+ Add speaker" and the per-row remove with confirmation.
8. **Apply endpoint** — `POST .../speaker-mapping/apply`: save → re-render →
   re-run engine if present.
9. **Assign Speakers button** — wire to the apply endpoint; enable/disable on
   dirty state; refresh the transcript view on success.
10. **Execution trigger** — make Speaker Mapping confirmation auto-invoke the
   correction engine in the background (Section 7.1).
11. **Tests** — label builder (one-space honorific, `THE` labels); add/delete
   participant; merge; unmapped cluster renders flagged and loses no words;
   apply re-renders; idempotent re-run.

The AI name-suggestion module (Section 4.4) is **not** in this build list — it is
deferred to the AI wave.

---

## 11. Open Decisions

1. **W11-Q1 — AI name suggestion: include or defer?** This wave is designed to
   ship fully deterministic, with AI name suggestion as a later optional module.
   Confirm that — or, if you want AI pre-selection in this wave, it becomes an
   AI-dependent wave and should be sequenced after the AI work.
2. **W11-Q2 — Wave number / sequencing.** Numbered Wave 11 here, following Wave 9
   (speaker mapping) and the Wave 10 correction-engine specs. This wave is mostly
   independent of the correction engine and could be built before it — the
   "Assign Speakers" button degrades gracefully (re-renders Q/A even if the
   engine is not yet built). Confirm the number and whether it precedes or
   follows the Wave 10 build.
3. **W11-Q3 — Step 2B vs. Workspace.** This spec keeps **both**: Step 2B as the
   initial gate, the Workspace panel for corrections. Confirm you want to keep
   the Step 2B screen, or whether it should eventually be absorbed entirely into
   the Workspace.
4. **W11-Q4 — Add-speaker cluster picker.** When a new participant is added, it
   needs a way to claim unmapped clusters. Confirm a small inline cluster picker
   on the row is acceptable, vs. a separate dialog.

---

## 12. Out of Scope / Non-Goals

- **No change to RAW or to diarization.** Clusters are fixed; the wave only edits
  the participant layer above them.
- **No AI in the build.** The deterministic panel, dropdowns, and prefill ship
  with no model dependency. AI name suggestion is deferred (W11-Q1).
- **No sub-cluster splitting.** If Deepgram merged two people into one acoustic
  cluster, this wave cannot split that cluster mid-stream — that is a separate,
  harder problem. The user can still relabel or flag it.
- **No legal-correctness judgement.** The panel assigns identity; it does not
  decide whether testimony is right.

---

*End of Wave 11 specification. Pair with `docs/wave9_speaker_mapping.md` and the
`docs/architecture/transcript_engine/` correction-engine specs.*
