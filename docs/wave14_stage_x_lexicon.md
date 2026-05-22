# Wave 14 — Stage X (Lexicon) + Backend Regex Correction Pipeline

Status: **SPEC + BUILT.**

## 1. Scope

Wave 14 is two deterministic pieces:

1. **Stage X — the lexicon/spelling engine.** A merged, priority-ordered
   lexicon applied as whole-word, possessive-aware, deterministic
   substitution.
2. **The backend regex correction pipeline.** Per-case regex rules,
   persisted, ordered, replayable, audited.

The live AI suggestions layer is explicitly **Wave 15** — not this
wave.

## 2. Architecture

    Case
      -> regex correction set (persisted, ordered)
      -> Stage X lexicon (merged, priority-ordered)
      -> render pipeline (render.py / Stage S)
      -> export preview
      -> export

Both pieces run **before** the structural render, so the Export
Preview reflects them. Both are deterministic, audited, reversible,
and never mutate RAW.

## 3. Stage X — lexicon engine

### 3.1 Lexicon source of truth (merged, priority-ordered)

The canonical lexicon is merged at startup from five sources. On a key
collision, the **higher-priority source wins**:

1. `confirmed_spellings` — reporter-verified; highest authority.
2. reporter per-case corrections.
3. `deepgram_keyterms`.
4. intake-generated `keyterms.json`.
5. future shared/global legal dictionaries (not built yet).

Reporter-confirmed corrections always override everything below them.

### 3.2 Substitution scope — whole-word only

Stage X replaces **whole words only**. It never mutates a substring
inside a larger word.

- Safe: `trinaty -> Trinity`, `trinaty's -> Trinity's` (possessive
  preserved).
- Unsafe and forbidden: `ultrinaty -> ultraTrinity`.

Matching is token-aware, punctuation-aware, and possessive-aware: a
match is a full token, optionally followed by `'s`/`'s`, bounded by
non-word characters.

### 3.3 Case handling

Stage X corrects capitalisation **for explicitly confirmed lexicon
entries only**:

- `acoustic neuroma -> Acoustic Neuroma`
- `miah bardot -> Miah Bardot`
- `texas rules of civil procedure -> Texas Rules of Civil Procedure`

Casing is corrected only for confirmed entries — never inferred, never
semantic guesswork.

### 3.4 Verbatim boundary

Stage X applies only explicitly confirmed substitutions / deterministic
dictionary replacements / exact controlled matches. It NEVER invents
spellings, guesses intent, rewrites testimony, or performs semantic
correction. On uncertainty: preserve the original, and (future) flag
for review. Every substitution is audit-logged, reversible, traceable.

### 3.5 Relationship to the existing correction engine

`backend/corrections/metadata.py` already has PRE-07 (confirmed
spellings) and PRE-08 (keyterm casing). Stage X supersedes those with a
single proper lexicon layer: the 5-source merge, priority ordering, and
possessive-aware whole-word matching they lack. PRE-07/PRE-08 remain in
place for the existing pipeline; Stage X is the canonical lexicon entry
point used by the render path.

## 4. Backend regex correction pipeline

### 4.1 Per-case persistence

Regex rules are saved per case in a new table `case_regex_rules`:

    rule_id, case_id, find_pattern, replace_with,
    rule_order, enabled, created_at

Rules are ordered (`rule_order`) and individually `enabled`/disabled.
They persist across sessions and replay deterministically on re-render.

### 4.2 Rules remain visible, editable, disable-able, ordered, logged

The pipeline applies enabled rules in `rule_order`. Every applied
substitution is audit-logged. A malformed regex is skipped with a
logged warning, never crashes the pipeline.

### 4.3 Replay

Re-rendering a case re-applies the persisted regex set then the Stage X
lexicon, deterministically — so the Export Preview stays synchronised
with the saved correction profile.

## 5. Modules

    backend/lexicon/
      __init__.py
      model.py        -- LexiconEntry, Lexicon
      merge.py        -- 5-source priority merge
      stage_x.py      -- whole-word possessive-aware substitution
    backend/corrections/regex_rules.py  -- regex rule application
    backend/db/schema_v5.sql            -- case_regex_rules table
    backend/api/corrections.py          -- CRUD for regex rules

## 6. Tests

`tests/test_stage_x_lexicon.py`, `tests/test_regex_rules.py` —
covering merge priority, whole-word/possessive matching, casing,
no-substring-mutation, regex ordering/enable/disable, persistence,
determinism, and RAW immutability.

## 7. Out of scope (Wave 15)

Live AI suggestions, LLM integration, AI review queue, confidence
scoring, human-review workflows.
