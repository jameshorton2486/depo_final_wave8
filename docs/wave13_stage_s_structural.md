# Wave 13 — Stage S: Structural Rendering Layer

Status: **SPEC + BUILT.**

## 1. What Stage S is

Stage S is the **deterministic structural renderer**. It consumes the
immutable RAW transcript plus the confirmed Wave 9/11 speaker mapping
and produces a structurally compliant WORKING render: Q/A segmentation,
colloquy isolation, objection isolation, off-record suppression, and
procedural parentheticals.

Stage S is **not** a rewriting layer. It never mutates RAW, never
rewrites or paraphrases testimony, never invents *words*. It
re-segments the exact immutable utterances into their compliant
structural roles and emits procedural lines (parentheticals).

## 2. Architecture

    RAW transcript (immutable)
      -> Speaker Mapping (Wave 9 / 11)
      -> Deterministic Correction Engine (G/A/M/T/F/U)
      -> Stage S Structural Renderer            <-- THIS WAVE
      -> [future] AI Review Suggestion Layer
      -> Export Renderer (Wave 12 export_render.py)
      -> DOCX / PDF

Locked architectural decisions:

- **One `RenderLine` with a `line_type` field** — no subclass per kind.
- **No AI inside Stage S** — purely deterministic; AI review is a later,
  separate layer.
- **Off-record is marked, not deleted** — `render_state` tracked, spans
  tagged, never erased. RAW always retains everything.
- **Multi-speaker segmentation is NOT Stage S's job** — it consumes
  accepted mappings; it never infers speaker splits.
- **Stage S does not own UFM geometry.** It emits semantic `RenderLine`s
  carrying `line_type`, `tab_level`, `procedural`. The Wave 12 export
  layer resolves `tab_level` -> twips and `procedural` -> navy blue.

  DEVIATION NOTE: the source spec placed twips + RGBColor inside Stage
  S. They are instead semantic hints resolved downstream, per the
  approved layered architecture. All rules (tab 3 colloquy, tab 4
  parentheticals, navy blue, two-space colon) are preserved.

## 3. The RenderLine model  (`models.py`)

    RenderLine:
      line_id: str
      line_type: str        # Q | A | colloquy | parenthetical | by_line
                            #  | flagged | blank
      speaker_label: str
      text: str
      source_utterance_ids: list[str]   # pointer back to RAW
      tab_level: int        # 0 margin | 1 Q/A designation | 2 Q/A text
                            #  | 3 colloquy | 4 parenthetical
      procedural: bool      # True => generated procedural line
      render_state: str     # ON_RECORD | OFF_RECORD
      audit_note: str

Every line carries `source_utterance_ids` — reversibility is mandatory.

## 4. Off-record state machine  (`off_record.py`, `render_state.py`)

- Triggers evaluated **only within a Videographer-role block**,
  case-insensitive (`block.lower()`):
  - OFF: `"off the record"`
  - ON:  `"back on the record"` OR `"we are back"`
- `"on the record"` alone is NOT a trigger (false-positive risk).
- On transition, extract time with
  `(\d{1,2}:\d{2})\s*(a\.?m\.?|p\.?m\.?|AM|PM)` and emit:
  - OFF -> `(Whereupon, a recess was taken at [time].)`
  - ON  -> `(Whereupon, the proceedings resumed at [time].)`, then
    immediately re-emit the `BY [examiner]:` attribution line.
- OFF-record spans are tagged `render_state=OFF_RECORD`, never deleted.

## 5. Parenthetical registry  (`parentheticals.py`)

Canonical wordings — state transitions, oaths/interpreters, exhibits,
procedural/non-verbal, post-record spellings. Type 4 geometry:
`tab_level=4`, `procedural=True`, block-indent (wrapped lines stay
indented), no blank lines around them.

## 6. Objection isolation  (`objection_handler.py`)

- An objection embedded in a Q or A is isolated to its own colloquy
  block at `tab_level=3`.
- The break is denoted by a spaced double-hyphen `--`. Stage S
  **dynamically emits** the `--` at the segmentation boundary: append
  ` --` to the interrupted line, prepend `-- ` to the resuming line,
  **if not already present in RAW**.
  - RATIONALE: punctuation is not governed by the verbatim mandate
    (which protects spoken *words*). UFM § 2.9 and Morson's Rule 87
    mandate the dash. RAW utterance records are still never mutated —
    the dash is added to the rendered `RenderLine.text` only, and every
    insertion is logged with an `audit_note`.
  - Morson's Rule 91: no comma/colon/semicolon adjacent to the dash.
- The resumed question is a normal `Q.` line, optionally
  `Q. (BY MR. SMITH)` — never an invented "(Continuing)".

## 7. Colloquy formatting  (`colloquy.py`)

Type 3: label at `tab_level=3`, ALL CAPS, colon, exactly two spaces,
text inline on the same line. Wrapped lines return flush left
(hanging indent, handled by the export layer).

## 8. `Q. (BY MR. SMITH)` reminder

Emitted after any colloquy interruption (may also follow a
parenthetical). NOT a new line type or tab — a standard Type 1 `Q.`
line whose text begins with the `(BY MR. SMITH)` inline reminder.

## 9. Renderer  (`renderer.py`, `line_builder.py`, `transitions.py`)

`renderer.py` orchestrates: consume RAW + mapping, walk blocks through
the off-record state machine + objection handler, build `RenderLine`s.
Deterministic and idempotent — re-running yields identical output.

## 10. Audit layer  (`audit.py`)

Every structural transformation is logged: Q/A splits, objection
isolation, off-record suppression spans, dash insertions. Human
reviewers retain ultimate authority.

## 11. Tests  (`tests/`)

`test_stage_s_renderer.py`, `test_off_record.py`,
`test_objection_isolation.py`, `test_parentheticals.py`,
`test_render_idempotency.py`. Tests live in the existing `tests/`
directory (project conftest fixtures live there) — not `backend/tests/`.

## 12. Future scope (NOT Wave 13)

UFM edge cases noted for later waves: Uh-huh/Huh-uh non-verbals,
polite-request period rule, `(phonetic)` -> SCOPIST flag, witness
self-correction dashes, sealed-record indicator pages, rough-draft
format stripping. Real DOCX geometry remains in the export layer.
