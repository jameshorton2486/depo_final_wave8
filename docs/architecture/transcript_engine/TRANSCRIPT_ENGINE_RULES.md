# CLAUDE_TRANSCRIPT_RULES.md

**The Transcript Engine Constitution**

This is the short, authoritative list of invariant rules for DEPO-PRO's
transcript-processing system. It governs the deterministic correction engine
(`backend/corrections/`), the diff harness (`backend/diagnostics/`), and any
future AI layer.

It is deliberately brief. The full reasoning lives in the two specs in this
folder. This file exists so the non-negotiables can be read in one minute and
never drift.

**If code conflicts with this file, the code is wrong.**

---

## The Invariants

1. **RAW is immutable.** The Deepgram response and the canonical
   `raw_text` / `raw.json` are never written by any processing stage, ever.
   RAW is evidence. All work happens on the WORKING layer.

2. **The verbatim mandate is absolute.** No stage removes, normalizes, or
   "cleans up" filler words, informal affirmations, stutters, false starts, or
   trailing thoughts. No stage corrects a witness's grammar, syntax, word
   choice, or pronunciation. Testimony is transcribed as spoken.

3. **No semantic rewriting in the deterministic engine.** The correction engine
   only makes changes that reduce to a finite regex pattern or an exact
   dictionary lookup. If a change needs meaning to be understood, the engine
   does not make it.

4. **No AI in the deterministic engine, and no AI in Parity Mode.** The engine
   in this folder contains zero model calls. The future AI layer is a separate,
   downstream, optional, reversible stage — never upstream of the deterministic
   engine, never inside it.

5. **No transcript text is deleted.** Off-record spans are *omitted from the
   WORKING render* and replaced by parentheticals; RAW still holds everything.
   Content ordered stricken stays printed. Post-record content is flagged, not
   deleted. Nothing testimony-bearing is ever destroyed.

6. **No silent corrections.** Every change the engine makes is written to the
   correction log — rule ID, before, after, stage, location. If it is not in
   the log, it did not happen; if it happened and is not in the log, that is a
   defect.

7. **Flag, do not guess.** When the engine detects a probable error it cannot
   fix within rule 3, it inserts a numbered `[SCOPIST: FLAG]` and changes
   nothing. It never best-guesses an entity, a date, a number, or a speaker.

8. **`‹LC:...›` markers are untouchable.** They belong to a separate coexisting
   system. Never strip, split, move, merge, or convert them to flags.

9. **Idempotency.** Running the engine twice equals running it once. Every rule
   checks its target state before firing.

10. **RAW is the truth source — not the Deepgram Playground.** Regression is
    measured APP-vs-RAW. The Playground is a separate ASR run and is advisory
    only; it never gates a build.

11. **The harness measures drift; it does not decide truth.** The diff harness
    reports structural and word-count integrity. It never judges *legal*
    correctness — that is the court reporter's certification.

12. **These specs are source-of-truth.** The documents in
    `docs/architecture/transcript_engine/` are engineering contracts. Code is
    built from them. They are versioned with the code. When in doubt, the spec
    wins.

---

## Forbidden Behaviors (quick reference)

- ❌ Writing to RAW.
- ❌ Removing or normalizing fillers / stutters / affirmations.
- ❌ Correcting witness grammar or pronunciation.
- ❌ A model call anywhere in `backend/corrections/`.
- ❌ Deleting testimony-bearing text.
- ❌ A correction with no correction-log entry.
- ❌ Guessing an unverified entity, date, or speaker instead of flagging.
- ❌ Treating Playground output as a pass/fail oracle.

---

*Authoritative. Part of `docs/architecture/transcript_engine/`. Wave 10.*
