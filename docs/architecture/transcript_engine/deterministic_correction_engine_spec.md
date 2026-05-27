> DOCUMENT STATUS: CANONICAL SUBSYSTEM SPEC
> Scope: deterministic correction-engine ownership, ordering, guards, flags, and working-layer mutation rules.
> This governs `backend/corrections/`. It does not authorize alternate correction pipelines.

# DEPO-PRO — Deterministic Transcript Correction Engine

**Build Specification — Regex & Script Layer (No AI)**

Version 1.2 · Wave 10 · Consolidates: Script & Regex Reference, Pipeline
Implementation Spec (GUARD/PRE/POST stages), Legal Standards Reference, AI
Processing Reference §4 (promoted rules), Permitted Corrections, UFM Transcript
Templates. Authoritative architecture document — see
`docs/architecture/transcript_engine/`. If code and this document conflict, this
document is correct; the code should be brought into line with it.

---

## 1. Purpose and Scope

This document specifies a **fully deterministic** correction engine for DEPO-PRO
deposition transcripts. It is the build reference for the `backend/corrections/`
package. Every rule here runs as Python regex or exact-match logic — **no language
model is invoked anywhere in this engine.**

### 1.1 What this engine does

It takes the verbatim Deepgram transcript (after Wave 9 speaker mapping is
confirmed) and applies mechanical corrections that need no semantic judgment:
verbatim protection, Deepgram artifact removal, metadata substitution, exact-match
legal-phrase resolution, off-record structuring, Q/A formatting, and UFM
typography. Anything it cannot do with certainty it does not guess — it inserts a
`[SCOPIST: FLAG]` for human review.

### 1.2 What this engine does NOT do

The source documents correctly route some corrections to AI because they require
reading meaning. This engine does **not** attempt them. They are listed in
**Section 16 (Out of Scope)** and are either deferred to the reporter in the
Workspace or surfaced as flags. Examples: contextual homophones (`know`/`no`,
`their`/`there`), sentence-initial number spell-out that needs true sentence
parsing, and fuzzy off-record boundary detection when the spoken marker is
garbled beyond pattern recognition.

### 1.3 The honest boundary

A correction is permitted **deterministically** only when **all** of the
following hold. This is the deterministic restatement of the source documents'
"four-part test":

1. The error is a clear speech-to-text or formatting artifact.
2. The corrected form is **enumerable** — a finite regex pattern or a fixed
   dictionary entry covers it with zero ambiguity.
3. The correction cannot alter the meaning of testimony.
4. Where context matters, the needed context is available as **structured data**
   (the confirmed speaker role from Wave 9, or `job_config` metadata) — never as
   a semantic inference.

If any condition fails, the engine flags instead of correcting.

---

## 2. Non-Negotiable Principles

These govern every rule. A rule that violates one of these is wrong, regardless
of convenience.

### 2.1 The Verbatim Mandate (highest priority)

Per the Legal Standards Reference (STD-VRB-01..05, Morson's Rules 4, 85, 270),
the transcript is a verbatim legal record. The engine must **never**:

- remove or normalize filler words (`uh`, `um`, `well`, `so`, `okay`, `yeah`…);
- normalize informal affirmations/negations (`uh-huh`, `yeah`, `nope`, `nah`)
  to `yes`/`no`;
- "clean up" stutters, false starts, or trailing thoughts;
- correct witness grammar, syntax, word choice, or pronunciation;
- alter attorney filler or hedging language.

These are protected by **Stage G** before any other stage runs.

### 2.2 RAW is immutable

The engine operates exclusively on the **WORKING** layer. The RAW Deepgram
packet (`data/transcripts/{job_id}/raw.json`) and the canonical
`transcript_words.raw_text` column are never written. Every correction is a
WORKING-layer transformation. This matches the existing DEPO-PRO architecture
(`raw_text` immutable, `working_text` editable).

### 2.3 No AI

No model call, no embedding, no probabilistic classifier. Every transformation is
a regex substitution, an exact dictionary lookup, or a structural rule over data
that is already known. This is what makes the output reproducible and
certifiable: the same input always produces the same output.

### 2.4 Idempotency

Running the engine twice must equal running it once. Every rule checks its target
state before firing (e.g., PRE-05 does not re-fire if `Okay.` is already present;
the two-space rule does not add a third space). Idempotency is a **build
requirement and a test requirement**, not an afterthought.

### 2.5 Flag, don't guess

When the engine detects a probable error it cannot fix within the rules above, it
inserts a numbered `[SCOPIST: FLAG]` (Section 5) at the point of uncertainty and
moves on. It never silently "best-guesses" an entity name, a date, or a speaker.

### 2.6 Role scoping (the Wave 9 dependency)

This engine runs **after** the Wave 9 Speaker Mapping step is confirmed. Every
utterance therefore carries a known participant **role** (examining attorney,
witness, defending attorney, court reporter, etc.). Many corrections that the
source documents assigned to AID "because context is needed" become safely
deterministic once the role is a known fact rather than an inference. Rules that
depend on role state their **Scope** explicitly.

### 2.7 Correction log (new — see Section 17.1)

Every change the engine makes is recorded: rule ID, utterance ID, before-text,
after-text. The log is persisted alongside the WORKING transcript so the reporter
can audit every automatic edit before certifying. Nothing the engine does is
invisible.

---

## 3. Pipeline Position

```
Deepgram ASR
   │
   ▼
Assembler  ──►  canonical words / utterances        (RAW — immutable)
   │
   ▼
Wave 9 Speaker Mapping  ──►  confirmed participant roles
   │
   ▼
┌─────────────────────────────────────────────────┐
│  DETERMINISTIC CORRECTION ENGINE  (this spec)    │
│  Stage G → A → M → X → S → Q → T → F → U         │
│  operates on the WORKING layer only              │
└─────────────────────────────────────────────────┘
   │
   ▼
UFM DOCX Build  (templates — separate spec)
   │
   ▼
Certify / Export
```

The engine is a single package, invoked once per job after speaker mapping is
confirmed and re-runnable at any time (idempotent). It must raise
`SpeakerMapUnverifiedError` and refuse to run if the Wave 9 mapping is not
confirmed — the same hard gate the Pipeline Spec defines as SPK-02.

### 3.1 Reversibility and sequencing

Every stage in this engine is deterministic and operates only on the WORKING
layer; RAW is never written. The engine is therefore **fully reversible** — at
any time the WORKING transcript can be discarded and regenerated from RAW plus
the confirmed speaker map. Nothing this engine does is destructive or one-way.

Sequencing relative to the AI work planned for **Wave 10**: this engine is built,
tested, and stabilized **first**. Wave 10's AI-assisted layer (the source
documents' "AI Format" stage — better named the **Legal Reconstruction Layer**)
sits strictly **downstream** of this engine and is itself optional and
reversible. The deterministic engine is the stable foundation; the AI layer is an
optional refinement on top of it, never a replacement for it and never upstream
of it.

---

## 3A. Parity Mode (Deterministic Baseline)

**Purpose.** Parity Mode produces an app transcript that is **structurally
comparable to the Deepgram Playground output** — useful as a known-good baseline
for debugging assembly, diarization, and segmentation, and as the left/right
input to the Transcript Diff Harness (separate spec). It exists so the build team
can isolate *where* a transcript defect originates without legal-formatting
transformations in the way.

**Mechanism.** A single boolean in `job_config`:

```json
{ "deterministic_parity_mode": true }
```

When `deterministic_parity_mode` is **true**, the pipeline runs a reduced stage
set:

| Stage | Full mode | Parity mode |
|---|---|---|
| G — Guards | ✅ run | ✅ run |
| A — Artifact Removal | ✅ run | ✅ run |
| M — Metadata Substitution | ✅ run | ✅ run |
| X — Legal Lexicon | ✅ run | ⏸ skipped |
| S — Structural / Off-Record | ✅ run | ⏸ skipped |
| Q — Q/A Formatting | ✅ run | ⏸ skipped |
| T — Typography | ✅ run | ✅ run |
| F — Flag Generation | ✅ run | ✅ run |
| U — Unguard | ✅ run | ✅ run |

**Rationale for the split.** Stages G, A, M, T, F, U are non-structural: they
preserve verbatim content, remove mechanical Deepgram artifacts, apply confirmed
metadata, normalize typography, and flag — none of them reorganize the
transcript. Their output still lines up utterance-for-utterance with the
Playground, so the comparison stays meaningful. Stages X, S, and Q are
**structural**: they resolve garbles, convert off-record spans to parentheticals,
and split/relabel utterances into Q/A and colloquy. Those are exactly the
transformations that make an app transcript diverge from a raw Playground dump —
so Parity Mode pauses them.

**This is a toggle, not a deletion.** Stages X, S, and Q remain fully specified,
built, and tested. Parity Mode merely skips them at run time. Full mode is the
default and the production path; Parity Mode is a debugging and
regression-baseline aid. The two modes share one codebase.

**Idempotency holds in both modes.** Running either mode twice equals running it
once.

**Relation to the Diff Harness.** Parity Mode is the natural input to the
Transcript Diff Harness (`DepoPro_Transcript_Diff_Harness_Spec.md`): render the
job in Parity Mode, place it beside the Playground export, and the harness
reports utterance / speaker / word drift with structural transformations removed
from the picture.

---

## 4. Input / Output Contract

### 4.1 Input

A **working transcript model**: an ordered list of utterance records, each:

```
{
  "utterance_id":   str,
  "speaker_index":  int,
  "role":           str,    # from Wave 9: examining_attorney | witness |
                            # defending_attorney | co_counsel | court_reporter |
                            # videographer | interpreter | off_record | other
  "participant_name": str | None,
  "text":           str,    # current WORKING text (starts == raw verbatim)
  "start_time":     float,
  "end_time":       float
}
```

Plus `job_config`:

- `confirmed_spellings: dict[str, str]` — verified entity spellings (garble/raw → canonical).
- `deepgram_keyterms: list[str]` — verified proper-noun keyterms.
- `reporter_name: str`, and `case_meta` (cause number, parties, witness name, CSR number).

`confirmed_spellings` and `deepgram_keyterms` are **authoritative metadata, not AI
guesses**. They are populated, in order, from: (1) the Wave 8 NOD parser, (2)
intake metadata, (3) Workspace participant review, (4) any manually confirmed
scopist/reporter edits. The Workspace must let the reporter or scopist **add,
edit, approve, and remove** confirmed spellings **before** the deterministic
engine runs — these values gate Stage M (PRE-07/08), so they must be settled
first.

### 4.2 Output

1. A **rendered line list** — the corrected WORKING transcript as typed lines:
   `Q.` lines, `A.` lines, speaker-label colloquy lines, and parenthetical lines,
   each carrying its source utterance IDs and tab level for the DOCX builder.
2. A **correction log** — one entry per change (Section 17.1).
3. A **flag registry** — all `[SCOPIST: FLAG N]` entries with location and reason.

### 4.3 Structural note

Most rules are text-level substitutions on `text`. Three stages change
**structure** rather than text: Stage S (off-record spans become parentheticals),
Stage Q (one utterance may split into a `Q.` line + an `A.` line), and Stage Q's
objection isolation (an embedded objection becomes its own colloquy line). The
engine therefore emits a new line list rather than mutating utterances in place.
RAW utterances are untouched; the line list is the WORKING product.

---

## 5. The Flag System

### 5.1 Format

```
[SCOPIST: FLAG N: "short reason" -- verify from audio or case materials]
```

`N` is sequential within the job, starting at 1. The flag is inserted inline at
the exact point of uncertainty. The text around it is left verbatim.

### 5.2 Flag registry

Each flag is also recorded:

```
{ "flag_number": int, "utterance_id": str, "char_offset": int,
  "category": str, "reason": str, "as_transcribed": str }
```

Categories: `entity` (proper noun not verified), `speaker` (identity uncertain),
`garble` (probable garble failing the deterministic test), `date` (ambiguous
date), `boundary` (off/on-record marker garbled), `number` (sentence-initial
number needing review), `oath` (garbled oath/certification language — never
auto-corrected, per FLAG-06).

### 5.3 Rule

`‹LC:...›` markers (U+2039 / U+203A — a separate coexisting system) are **never**
converted to flags and never altered. They are protected by GUARD-05.

---

## 6. Pipeline Stages — Overview

Run in this exact order. Order is load-bearing; rationale is given per stage.

| Stage | Name | Module | What it does | Parity |
|---|---|---|---|---|
| **G** | Verbatim Guards | `guards.py` | Sentinel-wrap protected tokens so no later stage can touch them | ✅ |
| **A** | Artifact Removal | `artifacts.py` | Remove mechanical Deepgram errors (dupes, orphan dashes, standalone artifacts) | ✅ |
| **M** | Metadata Substitution | `metadata.py` | Exact-match: reporter name, labels, confirmed_spellings, keyterms, identifiers | ✅ |
| **X** | Legal Lexicon Resolution | `legal_phrases.py` | Exact-match garbled objections & legal phrases — **role-scoped** | ⏸ |
| **S** | Structural / Off-Record | `structure.py` | Convert clean off-record spans to parentheticals; insert standard parentheticals | ⏸ |
| **Q** | Q/A Formatting | `qa_format.py` | Embedded Q/A split, objection isolation, tab/line-type assignment — **role-scoped, flag on doubt** | ⏸ |
| **T** | Typography | `typography.py` | Two-space rule, honorifics, time format, dashes, objection spacing | ✅ |
| **F** | Flag Generation | `flags.py` | Detect List-3 items; insert `[SCOPIST: FLAG]` | ✅ |
| **U** | Unguard | `guards.py` | Restore sentinel-wrapped tokens to their literal form | ✅ |

**Why this order:** Guards must wrap first or later stages would mangle protected
verbatim content. Artifact removal precedes everything textual so duplicate/garble
noise does not interfere with matching. Metadata and lexicon substitution run
before typography so spacing is applied to final words. Typography runs late so it
normalizes the finished text. Flags run after corrections so the engine only flags
what it genuinely could not fix. Unguard is strictly last.

**Parity column:** ✅ = always runs; ⏸ = skipped when `deterministic_parity_mode`
is true (see Section 3A). The skipped stages are the three structural ones; the
order of the stages that *do* run is unchanged.

---

## 7. Stage G — Verbatim Guards

**Module:** `corrections/guards.py` · **Runs:** first, before all else.

**Mechanism:** each guard finds protected spans and replaces them with an opaque
sentinel (e.g. `\x00G07\x00<index>\x00`). Sentinels survive every later stage
untouched; Stage U restores them. Guards never *change* text — they *shield* it.

### GUARD-01 — Filler Word Protection
- **Pattern:** `r'\b(?:uh-huh|uh-uh|uh|um|ah|well|so|okay|yeah|yep|yup|nope|nah|gonna|wanna|gotta|kinda|sorta)\b'` (case-insensitive)
- **Why:** STD-VRB-01 (Morson's Rule 4). These are verbatim; no later stage may delete or normalize them.
- **Exception:** none.
- **Test:** `test_guard01_filler_words_preserved`

### GUARD-02 — Stutter Protection
- **Pattern:** `r'\b\w-\w+\b'` — single character, hyphen, word (e.g. `b-b-bank`).
- **Why:** STD-VRB-03. The single-char-before-hyphen form matches genuine stutters and **not** compound words like `cross-examination`. (Source-doc reconciliation: the Permitted-Corrections note flagged `\b\w+-\w+\b` as too broad — `\b\w-\w+\b` is canonical.)
- **Test:** `test_guard02_stutter_protected_not_compound`

### GUARD-03 — False Start Protection
- **Pattern:** `r'\b\w+\s*-- '` — word followed by spaced double-hyphen **with trailing space**.
- **Why:** STD-VRB-03 / STD-MOR-02. The trailing space distinguishes a real false start from an orphaned-dash artifact (handled by A/PRE-10).
- **Test:** `test_guard03_false_start_preserved`

### GUARD-04 — Ellipsis Preservation
- **Pattern:** `r'(?:\.\s){2,}\.|\.\.\.'` — matches `. . .`, `. . . .`, and `...`.
- **Why:** STD-MOR-03 (Morson's 270-273). Three spaced periods = mid-sentence omission; four = end-of-sentence omission. Never deleted as orphan punctuation.
- **Test:** `test_guard04_ellipsis_not_removed`

### GUARD-05 — LC Marker Guard (absolute)
- **Pattern:** `r'\u2039LC:[^\u203A]+\u203A'`
- **Why:** `‹LC:...›` belongs to a separate coexisting system. Never strip, split, move, merge, or convert to a flag. Highest-priority guard.
- **Test:** `test_guard05_lc_marker_survives_all_passes`

### GUARD-06 — Affirmation Protection
- **List:** `AFFIRMATION_PROTECTED = ['correct','right','exactly','absolutely','yes','no']`
- **Why:** consumed as an exclusion list by A/PRE-04 (duplicate collapse). `correct correct` and `right right` are intentional verbatim affirmations and must not be collapsed.
- **Test:** `test_guard06_affirmation_not_collapsed`

---

## 8. Stage A — Deepgram Artifact Removal

**Module:** `corrections/artifacts.py` · Mechanical STT errors detectable by
pattern. Source IDs PRE-04, PRE-05, PRE-06, PRE-10 retained for traceability.

### PRE-04 — Consecutive Word Duplicate Collapse
- **Pattern:** `r'\b(\w{4,}) \1\b'` → `\1` (case-insensitive)
- **Scope:** all transcript body text.
- **Exception:** never collapse a word in `AFFIRMATION_PROTECTED` (GUARD-06). 1-3 character duplicates (`I I`, `the the`) are **left intact** — they may be stutter evidence for review.
- **In:** `the witness witness said` → **Out:** `the witness said`
- **Idempotency:** natural — no duplicate remains after one pass.
- **Test:** `test_pre04_duplicate_collapsed_not_affirmation`

### PRE-05 — Standalone Artifact Normalization
- **Map:** `r'\bK\.(?=\s|$)'` → `Okay.` · `r'\bk\.(?=\s|$)'` → `Okay.` · `r'\bMhmm\b'` → `Mm-hmm`
- **Scope:** standalone tokens only.
- **Exception:** idempotency check — skip if the target form is already present.
- **In:** `K. Go ahead. Mhmm.` → **Out:** `Okay.  Go ahead.  Mm-hmm.`
- **Test:** `test_pre05_standalone_artifact_normalized`

### PRE-06 — Doctor-Period Artifact Removal
- **Pattern:** `r'\bDoctor\.\s+(?=[A-Z])'` → `Dr. `
- **Scope:** only when `Doctor.` immediately precedes a capitalized name. Standalone `Doctor.` is left alone.
- **In:** `Doctor. Smith testified` → **Out:** `Dr. Smith testified`
- **Test:** `test_pre06_doctor_period_removed`

### PRE-10 — Orphaned Punctuation Removal
- **Pattern:** `r'\s+--\s+--\s+'` → single space
- **Scope:** double-dash sequences with no text content between/around them. Never removes a `--` that has text on at least one side (that is a protected false start — GUARD-03).
- **Test:** `test_pre10_orphaned_dash_removed`

---

## 9. Stage M — Metadata & Confirmed-Spelling Substitution

**Module:** `corrections/metadata.py` · Exact-match replacement from `job_config`
and fixed maps. **No phonetic matching at this layer** — exact strings only.
Source IDs PRE-01, PRE-02, PRE-03, PRE-07, PRE-08, PRE-09 retained.

### M-ordering rule
All dictionary substitutions apply **longest key first** to prevent partial-match
corruption. This applies to every map in this stage.

### PRE-01 — Reporter Name Normalization
- **Map** `REPORTER_NAME_MAP` (known garbles → canonical, from Script Ref §3.1):
  `Mia Bardo`, `Mia Bardell`, `Mia Bordeau`, `Mia Bardeau`, `Neobardeau`,
  `Miyamardeau`, `Lea Bardot` → `Miah Bardot`
- **CSR garble:** `number 1200129`, `12129. 9` → `CSR No. 12129`
- **Build note:** the reporter's canonical name comes from `job_config.reporter_name`; the garble list is the fixed map. Do not hardcode a reporter — read the canonical target from config.
- **Test:** `test_pre01_reporter_name_all_variants`

### PRE-02 — Label Standardization
- **Map** `LABEL_MAP`: `THE COURT REPORTER:` → `THE REPORTER:` · `COURT REPORTER:` → `THE REPORTER:` · `VIDEOGRAPHER:` → `THE VIDEOGRAPHER:`
- **Why:** STD-SPK-02 — the reporter is always `THE REPORTER:`, never `THE COURT REPORTER:`.
- **Test:** `test_pre02_court_reporter_label_corrected`

### PRE-03 — Texas Legal Terminology
- **Map** `TX_TERMS`: `Case Number` → `Cause Number` · `Case Name` → `Case Style`
- **Scope (critical):** caption / metadata fields **only**. Never apply inside transcript body testimony — a witness may say "case number" verbatim.
- **Test:** `test_pre03_texas_terminology_enforced`

### PRE-07 — confirmed_spellings Application
- **Source:** `job_config.confirmed_spellings` (dict, populated from the NOD / case file).
- **Pattern:** exact find-replace, `sorted(keys, key=len, reverse=True)`.
- **Exception:** never apply inside `‹LC:...›` markers (already guarded). Exact-match only — no phonetic similarity here.
- **Why this is safe:** these entities are **operator-verified** in `job_config`. The engine is applying a confirmed fact, not guessing. Unverified entities are handled by Stage F (flag).
- **Test:** `test_pre07_confirmed_spellings_applied_longest_first`

### PRE-08 — deepgram_keyterms Application
- **Source:** `job_config.deepgram_keyterms` (list).
- **Pattern:** exact-match only, in proper-noun token positions.
- **Exception:** a near-match (Levenshtein ≤ 2 but not exact) is **not** corrected — it is flagged by Stage F. Near-match correction is semantic and out of scope.
- **In:** `Home depot usa inc` → **Out:** `Home Depot U.S.A., Inc.` (only if that exact keyterm is configured)
- **Test:** `test_pre08_keyterms_exact_match_only`

### PRE-09 — Structural Identifier Formatting
- **Cause number:** `r'(\d{2})(CV)(\d{5})(\w{3})'` → `\1-\2-\3-\4` (e.g. `25CV00598OLG` → `25-CV-00598-OLG`)
- **Scope:** cause numbers, CSR numbers, docket identifiers only — never free body text.
- **etran:** `r'\be-?tran\b'` (case-insensitive) → `e-tran`
- **Test:** `test_pre09_identifiers_formatted`

---

## 10. Stage X — Legal Lexicon Resolution

**Module:** `corrections/legal_phrases.py`

> **SUGGESTION / CHANGE FROM SOURCE DOCS.** The AI Processing Reference §4 places
> garbled-objection and garbled-legal-phrase resolution on the **AI** list. I
> recommend promoting it to this **deterministic** engine, for two reasons: (1)
> §4 of that same document already supplies a **finite, exact garble→correct
> table** — an enumerated dictionary is deterministic by definition; (2) Wave 9
> gives us the **confirmed speaker role**, which supplies the only context the AI
> framing actually needed ("an attorney is speaking, examination is active").
> Scoping each entry to a role makes exact-match replacement safe. This is the
> single biggest no-AI gain available and it is included below. Entries that are
> *not* a closed set (case-specific names) stay out — they go to Stage F.

### X-scope rule
Every entry in this stage is gated by **speaker role**. A garbled-objection entry
fires only on an utterance whose role is `defending_attorney`, `co_counsel`, or
`examining_attorney`. A garbled-oath-phrase entry fires only on `court_reporter`
utterances. If the role does not match, the entry does not fire — it flags
(Stage F) instead.

### LEX-01 — Garbled Objection Resolution
- **Module:** `legal_phrases.py` → `OBJECTION_GARBLE_MAP`
- **Scope:** utterance role ∈ {defending_attorney, co_counsel, examining_attorney}.
- **Map (from AI Ref §4.1 — exact, case-insensitive whole-phrase match):**

  | Garbled input | Correct output |
  |---|---|
  | `Action calls for circulation` | `Objection.  Calls for speculation.` |
  | `Confection, vegan, ambiguous` | `Objection.  Vague and ambiguous.` |
  | `Correction. Calls for speculation.` | `Objection.  Calls for speculation.` |
  | `Big and bigos` / `Invigus` / `Being ambiguous` / `Big and biggest` | `Vague and ambiguous.` |
  | `I'm an objective, now I'm responsive` | `Objection.  Nonresponsive.` |
  | `Infection.` / `Perfection.` / `Dissection.` / `Detection.` / `Eviction.` / `Rejection.` | `Objection.` |
  | `Action.` (standalone, attorney role) | `Objection.` |

- **Idempotency:** the output forms (`Objection.  …`) are not themselves keys — re-running is a no-op.
- **Flag fallback:** a phrase that looks objection-like (contains `objection`/`vague`/`speculation` stems) but is **not** in the map is flagged `garble`, not corrected.
- **Test:** `test_lex01_garbled_objection_resolved`

### LEX-02 — Garbled Universal Legal Phrases
- **Module:** `legal_phrases.py` → `LEGAL_PHRASE_MAP`
- **Scope:** role-gated as noted per entry.
- **Map (from AI Ref §4.2):**

  | Garbled input | Correct output | Role gate |
  |---|---|---|
  | `tech rules of Texas Texas rules` | `Texas Rules of Civil Procedure` | any attorney/reporter |
  | `penalty of curtory` / `penalty of cursory` | `penalty of perjury` | any |
  | `notice and attorney` | `noticing attorney` | reporter |
  | `past witness` / `pass away` (as exam handoff) | `Pass the witness.` | examining_attorney |

- **Oath / certification language is excluded (Q3 decision).** Garbled oath
  phrases — `so help you guide` / `so happy God` → `so help you God` — are **not**
  corrected by this stage. Per the reporter's direction, the deterministic engine
  stays conservative in oath and certification contexts and does not silently
  normalize oath language even when the phrase is enumerable. Detection of
  garbled oath phrases moves to **FLAG-06** (Stage F): the engine flags them for
  human review instead of rewriting them.
- **Pending boundary question (Q8):** three further entries are oath/certification
  *adjacent* — `remote storing` → `remote swearing of the witness`,
  `same effect as a weapon in the courthouse` → `same force and effect as if
  given in open court`, and `They do.` → `I do.` (oath response). They currently
  remain deterministic, but the Q3 principle may extend to them. See Open
  Question Q8 — until resolved, the build should treat these three as
  provisional.
- **Test:** `test_lex02_legal_phrases_resolved`

### LEX-03 — Subpoena Duces Tecum Variants
- **Module:** `legal_phrases.py` → `SDT_MAP`
- **Map (AI Ref §4.3):** `subpoena deuces tikum`, `de sus tikum`, `deuceus tikum`, `due to stecum`, `duces take them` → `subpoena duces tecum`
- **Scope:** any role (legal term, unambiguous).
- **Test:** `test_lex03_subpoena_duces_tecum_variants`

### LEX-04 — Honorific Period Artifact
- `Doctor [Name]` with Deepgram-added period is handled by PRE-06. `Dr.` → `Dr.` in body text is left lowercase (see T/POST-04).

---

## 11. Stage S — Structural: Off-Record & Parentheticals

**Module:** `corrections/structure.py`

This stage converts off-record spans into the standard procedural parentheticals
and inserts the standard event parentheticals. It handles **clean markers only**;
garbled boundaries are flagged (Stage F, category `boundary`) and left for the
reporter.

### STR-01 — Pre-Record Boundary (clean)
- **Anchor:** `r'Today is \d{1,2}/\d{1,2}/\d{4}\.?\s+The time is \d{1,2}:\d{2}'`
- **Action:** the WORKING line list begins at the first anchor match. Content before it (greetings, sound checks, device troubleshooting) is omitted from the WORKING body. **RAW retains everything.**
- **If no clean anchor is found:** omit nothing; flag `boundary` at the transcript start for the reporter to set the opening manually.
- **Test:** `test_str01_prerecord_excluded_clean_anchor`

### STR-02 — Off-Record Span (clean)
- **Off anchor:** `r'[Tt]he time is (\d{1,2}:\d{2}\s*(?:[ap]\.?m\.?|[AP]M)).*?(?:we are|we\u2019?re) off the record'`
- **On anchor:** `r'[Tt]he time is (\d{1,2}:\d{2}\s*(?:[ap]\.?m\.?|[AP]M)).*?(?:we are|we\u2019?re) on the record'`
- **Action:** content strictly between a matched Off and its next matched On is omitted from the WORKING body and replaced by the parenthetical pair in STR-04.
- **Safety:** if an Off has no matching On (or vice versa), omit nothing for that span; flag `boundary`. Never omit on a one-sided match.
- **Test:** `test_str02_offrecord_span_to_parentheticals`

### STR-03 — Post-Record Boundary
- **Action:** at the final on-record → off-record transition, insert the deposition-concluded parenthetical (STR-04). Content after the final off-record marker is **not** auto-deleted — a `POST-RECORD SPELLINGS` block (STD-SPE-06) may legitimately follow. The engine flags the post-record region `boundary` for the reporter to handle in the Workspace.
- **Reconciliation note:** the Script Reference says "delete all text after the final off-record marker." That conflicts with STD-SPE-06 (post-record spellings are retained and specially formatted). This spec resolves the conflict in favor of STD-SPE-06: **do not auto-delete post-record content** — flag it. See Open Question Q4.
- **Test:** `test_str03_postrecord_flagged_not_deleted`

### STR-04 — Standard Parenthetical Insertion
- **Module:** `structure.py` → `PARENTHETICAL_FORMS`
- **Forms (Script Ref §2.3), all at Tab 4 (`\t\t\t\t`), period inside the paren:**

  | Situation | Parenthetical |
  |---|---|
  | Off-record span | `(Whereupon, a recess was taken at {time}.)` … `(Whereupon, the proceedings resumed at {time}.)` |
  | Witness sworn | `(The witness was sworn.)` |
  | Deposition opens | `(Whereupon, the deposition commenced at {time}.)` |
  | Deposition concluded | `(Whereupon, the deposition was concluded at {time}.)` |
  | Exhibit marked | `(Whereupon, Exhibit {n} was marked.)` |

- **`{time}` is taken from the matched anchor's capture group**, then normalized by T/STD-NUM-04 (time formatting).
- **Tense consistency (STD-SPE-08):** the engine emits **past tense** for every parenthetical, uniformly. It never mixes tense.
- **Multi-line parentheticals (STD-UFM-06):** continuation lines stay at Tab 4 — they do **not** return to the left margin. This is the exact opposite of Q/A wrapping (Stage Q).
- **Test:** `test_str04_parenthetical_forms_past_tense`

> **Build caution.** The exact placement of `(The witness was sworn.)` and the
> `EXAMINATION` / `BY MR. ___:` headers depends on locating oath completion. When
> the oath language is clean (`so help you God` / `I do`) the engine can place
> them deterministically. When it is garbled beyond LEX-02's map, the engine
> flags `boundary` and the reporter places the header in the Workspace. The
> engine never guesses the examination boundary.

---

## 12. Stage Q — Q/A Formatting

**Module:** `corrections/qa_format.py`

> **SUGGESTION / CHANGE FROM SOURCE DOCS.** The source places embedded-Q/A
> splitting and objection isolation on the AI list. With Wave 9 roles confirmed,
> both reduce to deterministic structural rules **with a flag-on-doubt fallback**.
> They are included here on that basis. Where the trigger is even slightly
> ambiguous, the engine does **not** split — it flags. This keeps the verbatim
> record safe: a missed split is a formatting nit a human fixes in seconds; a
> wrong split corrupts attribution.

### QA-01 — Q/A Format Trigger Gate
- **Rule (STD-SPK-05):** `Q.` / `A.` formatting begins **only** after all three:
  (a) the witness has been sworn, (b) an `EXAMINATION` header has been emitted,
  (c) a `BY MR./MS. ___:` line has been emitted.
- Before that point, **every** line uses speaker-label (colloquy) format — no
  `Q.`/`A.`. The reporter-administered oath, stipulations, and appearances are
  colloquy.
- **Test:** `test_qa01_qa_format_only_after_header`

### QA-02 — Examination Q/A Assignment
- Within the examination, an utterance whose role is `examining_attorney` →
  `Q.` line; role `witness` → `A.` line. (This is the rendering side of Wave 9 —
  deterministic role lookup, no inference.)
- Objections and reporter clarifications inside the examination keep
  speaker-label format (QA-04).
- **Test:** `test_qa02_examination_roles_to_qa`

### QA-03 — Embedded Q/A Split
- **Trigger:** a single utterance contains a `?`, immediately followed by one of
  the short-answer tokens — `Yes` / `No` / `Correct` / `I do` / `I don't` /
  `Right` / `Mm-hmm` / `That's right` — **AND** the remainder of the utterance
  after that token does **not** end in `?`.
- **Action:** split into a `Q.` line (through the `?`) and an `A.` line (the
  short answer). If more Q/A alternation follows in the same block, repeat.
- **Readback exception (mandatory):** do **not** split when the attorney is
  reading an answer back into the record — detect by the remainder ending in `?`
  (`"And you said yes, correct?"`). When the pattern is ambiguous, **do not split
  — flag** `garble`/review.
- **Role gate:** only applies inside the examination, on an `examining_attorney`
  utterance (the witness's answer was merged into the attorney's block by
  Deepgram).
- **In:** `Were your brakes working properly? Yes.`
  **Out:** `Q.  Were your brakes working properly?` / `A.  Yes.`
- **Test:** `test_qa03_embedded_answer_split_not_readback`

### QA-04 — Objection Isolation
- **Rule (STD-MOR-05, AI Ref §3.2):** an objection is **never** embedded in a
  `Q.` or `A.` line. When an objection phrase (post-LEX-01, so it is already the
  clean `Objection.  …` form) appears inside a `Q.` or `A.` block, it is lifted
  onto its own speaker-label colloquy line attributed to the objecting
  participant's role.
- **Safety:** isolation only fires when LEX-01 has already produced a canonical
  `Objection.` form **and** the objecting speaker's role is known. Otherwise the
  block is flagged, not split.
- **In (A. block):** `I was there.  Objection.  Vague and ambiguous.  I don't know.`
  **Out:** `A.  I was there.` / `MS.  ZAHN:  Objection.  Vague and ambiguous.` / `A.  I don't know.`
- **Test:** `test_qa04_objection_isolated_from_answer`

### QA-05 — Reporter Mid-Testimony Clarification
- An utterance whose role is `court_reporter` occurring inside the examination
  (e.g. "Sir, you're cutting out.") is rendered as a `THE REPORTER:` colloquy
  line, not folded into `Q.`/`A.`.
- **Test:** `test_qa05_reporter_clarification_is_colloquy`

### QA-06 — Tab / Line-Type Assignment
- **Module:** `qa_format.py` → `assign_tab_level()` — the final rendering step,
  applied after Stages S and Q have fixed every line's type.
- **Purpose:** every rendered line has a **line type**, and its tab prefix
  follows deterministically from that type. This is the **single authoritative
  tab map** — the parenthetical Tab 4 (STR-04) and the speaker-label `\t\t\t`
  prefix (POST-03) are instances of it, consolidated here so tab logic lives in
  one place.
- **Map (UFM § 2.10 tab stops, from the UFM Transcript Templates doc):**

  | Line type | Tab prefix | Tab stop |
  |---|---|---|
  | `EXAMINATION` / examination header | centered | — |
  | `BY MR./MS. ___:` attribution line | left margin | Tab 0 |
  | `Q.` / `A.` designator | `\t` | Tab 1 — 0.25" |
  | `Q.` / `A.` body text | `\t\t` | Tab 2 — 0.625" |
  | Speaker-label colloquy line | `\t\t\t` | Tab 3 — 1.0" |
  | Parenthetical | `\t\t\t\t` | Tab 4 — 1.5" |
  | Q/A continuation (wrapped line) | flush left margin | Tab 0 — hanging indent (STD-UFM-05) |
  | Speaker-label continuation | flush left margin | Tab 0 |
  | Parenthetical continuation | `\t\t\t\t` | Tab 4 — stays (STD-UFM-06) |

- **Determinism:** line type is already fixed by Stages S and Q from confirmed
  speaker roles — no judgment. The tab level is a pure lookup keyed on line type.
- **Output:** each rendered line carries an explicit `tab_level` integer; the
  DOCX builder maps `tab_level` to the Word tab stop. Whether the engine also
  emits literal `\t` characters or only the integer is an implementation choice —
  the integer is authoritative.
- **Wrap-direction caution (STD-UFM-05 vs STD-UFM-06):** Q/A and speaker-label
  continuation lines return **flush to the left margin** (hanging indent);
  parenthetical continuation lines **stay at Tab 4**. These are exact opposites —
  the builder must not confuse them.
- **Parity Mode:** QA-06 lives inside Stage Q, so it is skipped in Parity Mode
  (Section 3A). Parity output is therefore plain, un-tabbed colloquy text — which
  is exactly what the Diff Harness wants for Playground comparison.
- **Idempotency:** assignment is a pure function of line type — trivially idempotent.
- **Test:** `test_qa06_tab_levels_by_line_type`

---

## 13. Stage T — Typography & Spacing

**Module:** `corrections/typography.py` · Universal formatting, no judgment.
Source IDs POST-01..05 retained; deterministic NUM rules added (see suggestion).

### POST-01 — Two-Space Rule
- **Pattern:** `r'([.?!])\s+(?=[A-Z])'` → `\1  ` (two spaces)
- **Abbreviation guard (apply first):** do **not** add two spaces when the period
  belongs to an abbreviation —
  `ABBREV_GUARD = r'\b(Dr|Mr|Mrs|Ms|Jr|Sr|vs|No|Vol|Dept|Corp|Inc|Ltd|P\.C|PLLC|St|Blvd|Ave|Ste)\.$'`
  (superset reconciled from Pipeline POST-01 and Script §5.1).
- **Why:** STD-MOR-01 (Morson's Rules 1, 16).
- **Idempotency:** `\s+` collapses any existing run to exactly two — re-running is a no-op.
- **Test:** `test_post01_two_space_after_sentence`

### POST-02 — Objection Double-Space
- **Pattern:** `r'Objection\.\s+'` → `Objection.  `
- **Why:** STD-MOR-05 (Morson's p.628) — two spaces between `Objection.` and its basis.
- **Test:** `test_post02_objection_two_space`

### POST-03 — Honorific Formatting, Speaker Labels
- **Pattern (label lines only — the `\t\t\t` prefixed colloquy lines):**
  `r'\b(Mr|Ms|Mrs)\.\s+'` → `MR. ` / `MS. ` / `MRS. ` (ALL-CAPS, **one** space after the period) ; `Dr.` → `DR. `
- **Colon spacing is separate and unchanged:** a speaker label is still
  `MR. GARCIA:  Objection.` — **two** spaces after the *colon* (POST-02 / STD-SPK-01).
  This rule changes only the spacing after the honorific *period*.
- **Why:** house style per the reporter — one space after the honorific period.
  **Divergence flag:** STD-SPK-01 in the Legal Standards Reference currently
  specifies *two* spaces after the period; that source document should be updated
  to one space so the two stay consistent. See Open Question Q2.
- **Idempotency:** `\s+` collapses any run to exactly one space — re-running is a no-op.
- **Test:** `test_post03_honorific_caps_one_space_labels`

### POST-04 — Honorific Formatting, Body Text
- **Pattern (Q/A body text):** `r'\bMr\.\s+'` → `MR. ` ; `Ms.` → `MS. ` ; `Mrs.` → `MRS. ` (ALL-CAPS, **one** space after the period)
- **Exception:** `Dr.` in **body text** stays `Dr.` — lowercase, one space. Never `DR.` in body text.
- **Why:** house style per the reporter — ALL-CAPS `MR./MS./MRS.` with one space
  after the period, in body text as well as labels. Same divergence from
  STD-SPK-01 as POST-03.
- **Open Question Q2:** see Section 21.
- **Test:** `test_post04_honorific_body_text_mr_ms_mrs`

### POST-05 — `Miss` Normalization
- **Pattern:** `r'\bMiss\s+([A-Z])'` → `Ms. \1` (body) / `MS. \1` (labels — one space, per POST-03)
- **Exception:** preserve `Miss` when it is clearly a quoted term ("a real Miss Congeniality"). Deterministic proxy: skip when `Miss` is inside quotation marks.
- **Test:** `test_post05_miss_normalized_to_ms`

### POST-06 — Em Dash to Double Hyphen
- **Pattern:** `r'\s*\u2014\s*'` → ` -- ` (spaced double hyphen)
- **Why:** STD-MOR-02 / UFM §2.9 — interruptions use spaced double-hyphen, never an em dash.
- **Guard:** runs after GUARD-03; genuine false starts are already sentinel-wrapped.
- **Test:** `test_post06_em_dash_to_double_hyphen`

### Deterministic Number & Time Rules

> **SUGGESTION / CHANGE FROM SOURCE DOCS.** The AI Reference and Permitted-
> Corrections route all number formatting to AI. That is too broad. Several
> number rules are **purely mechanical** and belong here; only sentence-initial
> spell-out genuinely needs sentence parsing. The split below is the
> recommendation.

#### POST-07 — Time Formatting *(deterministic — STD-NUM-04)*
- `r'\b0(\d):(\d{2})'` → `\1:\2` (strip leading zero) ; `AM`/`PM` → `a.m.`/`p.m.` ; `01:31PM` → `1:31 p.m.`
- `12:00 p.m.` → `noon` ; `12:00 a.m.` → `midnight`
- **Test:** `test_post07_time_formatting`

#### POST-08 — Money & Percent *(deterministic — STD-NUM-02, STD-NUM-03)*
- `r'\$(\d[\d,]*)\.00\b'` → `$\1` (strip even-dollar trailing zeros)
- `r'(\d)%'` → `\1 percent` (symbol → spelled word; figure kept)
- **Test:** `test_post08_money_percent`

#### POST-09 — Large-Number Commas *(deterministic — STD-NUM-06)*
- Insert commas into integers of 4+ digits that are **not** part of a year,
  cause number, CSR number, address, or phone number. Because that exclusion set
  is hard to bound by regex alone, **scope POST-09 narrowly** or treat it as
  flag-only. **Recommendation:** flag, do not auto-insert. See Q5.

#### Sentence-initial spell-out — **OUT OF SCOPE** (Section 16)
Spelling out a sentence-initial number (STD-NUM-01) requires reliably knowing
where a sentence starts — genuinely semantic. The engine flags a digit in
apparent sentence-initial position (`number`) for reporter review; it does not
rewrite it.

---

## 14. Stage F — Flag Generation

**Module:** `corrections/flags.py` · Runs after all correction stages so it only
flags genuine residue. Inserts `[SCOPIST: FLAG N]` (Section 5) and registers each.

### FLAG-01 — Unverified Proper Nouns
- Any capitalized multi-word proper noun not present in `confirmed_spellings` or
  `deepgram_keyterms`, and not a dictionary word, is flagged `entity`.
- Liberal for proper nouns, conservative for ordinary words (per AI Ref §4.9 intent).

### FLAG-02 — Known List-3 Verbatim-Sensitive Items
The Permitted-Corrections List 3 enumerates items that must **never** be
auto-corrected. The engine flags each on sight (`entity`/`garble`), correcting
nothing:

| As transcribed | Flag reason |
|---|---|
| `criminal investigator` | verify vs case file — `civil investigator`? |
| `brothers Colorado` | verify vs NOD — `Brothers Alvarado`? |
| `Della Garza` / `Delia Garza` | verify spelling |
| `Sean Herbert` / `Shawn Herber` | verify vs case file |
| `Piazza and Cozor` | verify firm name — `Piazza, and Cozort`? |
| `Balletmore lift` | verify — `Ballymore`? |
| `Dior placement` | verify — testimony content |
| `chic cart` / `SheKart` | verify vs keyterms — `sheet cart`? |

**Important:** if any of these IS present in `confirmed_spellings`, PRE-07 has
already corrected it and FLAG-02 does not fire. The flag is the fallback for the
*unverified* state only.

### FLAG-03 — Residual Garble
A phrase matching a garble *shape* (objection-like, legal-phrase-like) that no
LEX map resolved is flagged `garble`.

### FLAG-04 — Boundary Uncertainty
Emitted by Stage S when an off/on/pre/post-record marker is garbled — `boundary`.

### FLAG-05 — Ambiguous Date / Number
Date mashups and sentence-initial numbers the engine will not rewrite — `date` / `number`.

### FLAG-06 — Oath / Certification Language
- **Module:** `flags.py` → `OATH_GARBLE_DETECT`
- **Rule (Q3 decision):** the deterministic engine does **not** normalize oath or
  certification language, even when the garble is enumerable. When a garbled oath
  phrase is detected on a `court_reporter` (or, for the oath response, `witness`)
  line, the engine inserts a flag — category `oath` — and changes nothing.
- **Detection set (detect-and-flag only — never a correction map):**
  `so help you guide`, `so happy God` (probable `so help you God`).
- **Why:** oath wording is the most sensitive language in the record. A
  human-reviewed flag is the only safe treatment; silent normalization is not
  permitted here regardless of how confident the match looks.
- **Note:** clean oath language (`so help you God`, `I do`) is still *recognized*
  for boundary placement in Stage S — FLAG-06 governs *correction*, not detection
  of where the oath occurs.
- **Test:** `test_flag06_garbled_oath_flagged_not_corrected`

- **Tests:** `test_flag02_list3_items_flagged_not_corrected`,
  `test_flag_numbering_sequential`

---

## 15. Stage U — Unguard

**Module:** `corrections/guards.py` → `unguard()` · Strictly last.
Restores every Stage-G sentinel to its original literal text. After Stage U the
WORKING line list contains the final corrected transcript. Assert that **zero**
sentinels remain — a leftover sentinel is a build error
(`test_unguard_no_sentinels_remain`).

---

## 16. Explicitly Out of Scope (Genuinely Needs Judgment)

The engine does **not** attempt these. They are deferred to the reporter in the
Workspace, or surfaced as flags. Listing them is itself part of the spec — the
build team must not "extend" the engine into these.

1. **Contextual homophones** — `know`/`no`, `their`/`there`, `pills`/`bills`.
   Pure semantics. (Permitted-Corrections List 2 §3.)
2. **Sentence-initial number spell-out** — needs reliable sentence segmentation
   (STD-NUM-01). Flagged, not rewritten.
3. **Date mashup interpretation** — `fourseventeentwenty 5` → `04/17/2025` is a
   guess about intended digits. Flagged.
4. **Fuzzy off/on-record boundary detection** — when the spoken marker is garbled
   past the STR anchors. Flagged.
5. **Near-match entity correction** — Levenshtein-close but not exact. Flagged,
   never auto-applied.
6. **`(as read)` vs `[sic]` placement** — requires detecting that a speaker is
   reading a document with errors (STD-MOR-06). Reporter decision.
7. **Phonetic speaker resolution** — `Ms. Sand` / `miss Son` / `miss Zhang` all
   meaning `MS. ZAHN`. Wave 9's mapping + `confirmed_spellings` handle the
   *confirmed* case; phonetic guessing is out.
8. **Testimony rehabilitation of any kind** — witness grammar, syntax, word
   choice, pronunciation, factual errors, internal inconsistencies (STD-VRB-04).
   Never touched, never flagged as "error" — flagging testimony as wrong is
   itself a verbatim violation.
9. **Stutter reconstruction** — converting a Deepgram-rendered repeated word
   (`the the the`) into hyphenated stutter notation (`th-th-the`) requires
   judging whether the repetition is a genuine stutter or deliberate emphasis.
   The engine does **not** reconstruct: PRE-04 deliberately leaves 1-3 character
   duplicates intact, and existing hyphenated stutters are protected verbatim by
   GUARD-02. There is nothing here for AI to do either — the verbatim mandate
   forbids "cleaning up" a stutter, so the only correct action is preservation,
   which is already deterministic.

---

## 17. Recommended Changes & Additions (Summary)

Collected here for review. Items marked **△** change the source documents.

### 17.1 Correction Log & Persisted WORKING Record **△ (addition — required)**

Not in the source docs. Every change is recorded — `rule_id`, `utterance_id`,
`before`, `after`, `stage`. Rationale: a certifiable system must let the reporter
audit every automatic edit; an unauditable correction engine cannot be trusted
with a legal record.

Per the Q6 decision this is a **firm build requirement, not a recommendation**,
and it extends beyond the log itself. The engine **persists its WORKING output**
rather than regenerating it from raw utterances on demand. Persisted, per job:

- the **rendered WORKING structure** (the line list — see Q6 / §4.2);
- the **correction log** (every change, as above);
- **stage outputs** (the WORKING text as it left each stage — the same data the
  Diff Harness `--snapshots` flag captures);
- **diff snapshots** (the harness `diff_metrics.json` for the run).

The principle is **no recomputation drift**: the reporter must be able to review
exactly what existed at each stage without the engine re-deriving it, because
re-derivation against changed inputs or code could silently differ from what was
reviewed. What was produced is what is stored; what is stored is what is
certified.

### 17.2 Promote garble resolution AI → deterministic **△**
Stage X. Justified because §4 of the AI Reference already supplies a finite
table and Wave 9 supplies the role context. Net effect: garbled objections and
standard legal phrases are fixed automatically and safely.

### 17.3 Promote embedded Q/A split & objection isolation AI → deterministic **△**
Stage Q, with a strict flag-on-ambiguity fallback. Justified by Wave 9 roles plus
the readback exception being itself a detectable pattern.

### 17.4 Split number formatting **△**
Time, money, and percent are deterministic (POST-07/08). Sentence-initial
spell-out and date mashups stay out (flag only). The source docs treated all
number work as AI — too broad.

### 17.5 Post-record: flag, do not delete **△**
Resolves the conflict between Script Ref ("delete after final off-record") and
STD-SPE-06 (post-record spellings retained). The engine flags the post-record
region; it never auto-deletes it.

### 17.6 Centralize patterns
All compiled regexes live in one `corrections/patterns.py`. No regex literal is
duplicated across modules — each has one definition, referenced by name. Makes
the engine auditable and testable.

### 17.7 Reconciled specifics
- `STUTTER_RE` = `r'\b\w-\w+\b'` (the tighter form).
- `ABBREV_GUARD` = the superset list (Section 13, POST-01).
- Filler list includes `well`, `so`, `okay` (per Permitted-Corrections fix).

### 17.8 New: Parity Mode toggle **△ (addition)**
Section 3A. A `deterministic_parity_mode` flag skips the three structural stages
(X, S, Q) so the app can render a transcript directly comparable to the Deepgram
Playground — a known-good baseline for debugging assembly and diarization. This
adopts the *useful* core of the "strip to a baseline" review note **without**
deleting Stages X/S/Q: they remain fully specified and tested, merely toggleable.
The structural stages are deterministic and role-gated — they are not the
semantic risk that note was warning against, so they are paused, not removed.
Parity Mode is the input to the separate Transcript Diff Harness spec.

---

## 18. Module / File Layout

Proposed package, consistent with the existing DEPO-PRO backend conventions:

```
backend/corrections/
├── __init__.py
├── pipeline.py         # orchestrator: runs G→A→M→X→S→Q→T→F→U in order
├── patterns.py         # ALL compiled regexes, one definition each
├── guards.py           # Stage G + Stage U  (GUARD-01..06, unguard)
├── artifacts.py        # Stage A            (PRE-04,05,06,10)
├── metadata.py         # Stage M            (PRE-01,02,03,07,08,09)
├── legal_phrases.py    # Stage X            (LEX-01,02,03)
├── structure.py        # Stage S            (STR-01..04)
├── qa_format.py        # Stage Q            (QA-01..06)
├── typography.py       # Stage T            (POST-01..09)
├── flags.py            # Stage F + flag registry (FLAG-01..06)
└── log.py              # correction log (Section 17.1)

tests/corrections/
├── test_guards.py
├── test_artifacts.py
├── test_metadata.py
├── test_legal_phrases.py
├── test_structure.py
├── test_qa_format.py
├── test_typography.py
├── test_flags.py
└── test_pipeline.py    # full-pipeline + idempotency + no-sentinel-residue
```

Engine entry point: `pipeline.run(working_transcript, job_config) -> CorrectionResult`
where `CorrectionResult` carries the rendered line list, the correction log, and
the flag registry. The pipeline raises `SpeakerMapUnverifiedError` if Wave 9
mapping is not confirmed. `pipeline.run` reads `job_config.deterministic_parity_mode`
(default `false`) and, when true, skips Stages X, S, and Q per Section 3A — the
stage list is the only behavioral difference between the two modes.

---

## 19. Test Plan

Every rule above names a test. In addition, `test_pipeline.py` must verify:

1. **Idempotency** — `run(run(x)) == run(x)` for a representative transcript.
2. **No sentinel residue** — zero Stage-G sentinels survive Stage U.
3. **RAW untouched** — RAW utterances are byte-identical before and after.
4. **Verbatim preservation** — a fixture dense with fillers, stutters, false
   starts, and ellipses passes through with every protected token intact.
5. **Flag completeness** — every List-3 item in a fixture is flagged; none is
   silently corrected.
6. **Ordering** — a fixture proving a stage-order swap breaks output (e.g.
   typography before metadata) confirms the order is load-bearing.
7. **Correction log fidelity** — every change in the output appears in the log.
8. **Parity mode** — with `deterministic_parity_mode: true`, Stages X, S, and Q
   produce zero changes (no garble resolution, no parentheticals, no Q/A split),
   while G, A, M, T, F still apply; and parity-mode output is itself idempotent.

Use the Heath Thomas / Delia Garza deposition as the primary integration fixture
— it exercises off-record spans, garbled objections, embedded Q/A, honorifics,
identifiers, and List-3 entities in one document.

---

## 20. Rule Traceability

| Rule | Stage | Legal basis | Source doc |
|---|---|---|---|
| GUARD-01..06 | G | STD-VRB-01,03 | Pipeline Spec; Script Ref §1 |
| PRE-04,05,06,10 | A | — (mechanical) | Pipeline Spec; Script Ref §4 |
| PRE-01,02,03,07,08,09 | M | STD-SPK-02 | Pipeline Spec; Script Ref §3 |
| LEX-01,02,03 | X | STD-MOR-05; STD-VRB-05 | AI Ref §4 (promoted) |
| STR-01..04 | S | STD-SPE-01,06,08; UFM §2.11,3.16 | Script Ref §2 |
| QA-01..06 | Q | STD-SPK-05; STD-MOR-05; UFM §2.10,2.11 | AI Ref §3 (promoted) |
| POST-01..06 | T | STD-MOR-01,02,05; STD-SPK-01 | Pipeline Spec; Script Ref §5 |
| POST-07,08,09 | T | STD-NUM-02,03,04,06 | Legal Std Ref (promoted) |
| FLAG-01..06 | F | STD-SPK-03; STD-VRB-04,05 | AI Ref §5; Permitted-Corrections L3 |

Use Rule IDs in code comments — e.g. `# implements LEX-01` — exactly as the
source documents instruct, so the engine stays cross-referenceable to the Legal
Standards Reference.

---

## 21. Open Questions — Status

Q1–Q7 were answered by the reporter and are **resolved**; their decisions are
recorded below and reflected in the spec body. Q8 is **newly open** — a boundary
question raised by the Q3 decision.

1. **Q1 — confirmed_spellings source. RESOLVED.** `confirmed_spellings:
   dict[str, str]` and `deepgram_keyterms: list[str]` live in `job_config`,
   populated from the Wave 8 NOD parser, intake metadata, Workspace participant
   review, and confirmed scopist/reporter edits. The Workspace must allow add /
   edit / approve / remove before the engine runs. See §4.1.
2. **Q2 — Honorific spacing. RESOLVED.** One space after the honorific period
   everywhere (`MR. GARCIA:`, `MS. ZAHN:`, `Dr. Smith`). The Legal Standards
   Reference (STD-SPK-01) and any conflicting docs must be updated to the
   single-space standard. See POST-03/04/05.
3. **Q3 — Garbled oath language. RESOLVED — flag, do not correct.** `so happy
   God` / `so help you guide` are **not** auto-corrected. The deterministic
   engine stays conservative in oath and certification contexts. Detection moved
   to FLAG-06 (Stage F); removed from LEX-02.
4. **Q4 — Post-record content. RESOLVED — flag, do not delete.** STR-03 flags
   the post-record region; it never auto-deletes it. Post-record spellings,
   clarifications, stipulations, and reporter notes may legitimately appear
   there — the Workspace/reporter decides final handling.
5. **Q5 — Large-number commas. RESOLVED — flag-only.** POST-09 does not
   auto-insert commas into 4+ digit numbers. The exclusion set (years,
   addresses, phone numbers, CSR numbers, cause numbers, exhibit identifiers,
   dates) is too dangerous to bound by regex; incorrect insertion could corrupt
   testimony or metadata.
6. **Q6 — Engine output persistence. RESOLVED — persist, do not recompute.** The
   rendered WORKING structure, stage outputs, correction log, and diff snapshots
   are persisted per job. No recomputation drift. See §17.1.
7. **Q7 — Parity Mode. RESOLVED.** Default `deterministic_parity_mode = false`
   (Full Mode is production). The toggle **is** exposed in the Workspace as an
   advanced/debug option so reporters and developers can compare RAW, APP,
   Playground, and corrected output without editing config by hand. See §3A.

**Open:**

8. **Q8 — Oath/certification boundary (raised by Q3).** The Q3 decision flags
   garbled oath language instead of correcting it. Three further LEX-02 entries
   are oath/certification *adjacent* and the same principle may apply:
   `remote storing` → `remote swearing of the witness`, `same effect as a weapon
   in the courthouse` → `same force and effect as if given in open court`, and
   `They do.` → `I do.` (oath response). **Decision needed:** do these three
   also move to FLAG-06 (flag, no correction), consistent with Q3 — or are they
   procedural enough to stay deterministic in LEX-02? Until resolved, the build
   should treat these three as provisional.

---

## 22. Recommended Build Order

The engine is specified here as a complete 9-stage pipeline. It should **not** be
built all at once. Build it in the order below — each step is independently
testable, and the sequence reaches a runnable Parity-Mode engine before the
structural stages are attempted.

| Step | Build | Why this order |
|---|---|---|
| 1 | `patterns.py` | Every regex and constant in one place first — nothing else can be written cleanly without it. |
| 2 | `guards.py` | Stage G + U. The verbatim foundation; every later stage depends on protected tokens being shielded. |
| 3 | `artifacts.py` | Stage A. The safest deterministic corrections — pure mechanical artifact removal. |
| 4 | `metadata.py` | Stage M. Exact-match substitution from `job_config`. |
| 5 | `log.py` | The correction log (§17.1). Build it **before** any structural stage so every later edit is auditable from day one. |
| 6 | `typography.py` | Stage T. Completes the non-structural stage set. |
| 7 | `flags.py` | Stage F. |
| 8 | `pipeline.py` | Orchestrator. At this point the engine runs end-to-end **in Parity Mode** — Stages G, A, M, T, F, U — and is fully testable. |
| 9 | **Diff Harness** (`backend/diagnostics/`) | Build now, not later. With Parity Mode runnable, the harness can measure RAW fidelity before any structural work begins. |
| 10 | `legal_phrases.py` | Stage X — first structural stage, only after Parity Mode and the harness are stable. |
| 11 | `structure.py` | Stage S. |
| 12 | `qa_format.py` | Stage Q — last, the most structural. |

**The principle:** reach a measurable, known-good Parity-Mode baseline (step 8)
and a working Diff Harness (step 9) **before** building Stages X, S, and Q. The
structural stages are exactly the parity-skipped stages — deferring them costs
nothing and means every structural edit is measured against a stable baseline
from the moment it is written.

---

*End of specification. This document is the build reference for
`backend/corrections/`. Pair it with the Legal Standards Reference (for the "why"
behind each Standard ID), the UFM Transcript Templates (for the separate DOCX
build stage), and the Transcript Diff Harness spec (for Parity-Mode comparison).
Repo location: `docs/architecture/transcript_engine/`.*
