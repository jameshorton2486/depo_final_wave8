# UFM Rules Reference — verified against the 2010 manual

> Answers grounded in the official *Uniform Format Manual for Texas Reporters' Records*
> (2010) text and the Shaw/Filpi reference depositions. Where the manual says "no required
> format," that is stated rather than a layout invented. Figure *contents* I have not seen
> (the figure plates are a separate part of the manual) are flagged.

## 1. Consolidated freelance index (the "Figure 11" index)
- **Rule:** 3.24 governs the Freelance/deposition index. **3.24(b): there is no required
  format.** Placement is flexible — after the administrative pages or at the end (3.24).
- **Content elements that must be indexed if they occur (3.24(a)):** appearances;
  stipulations; examinations; reporter's certification page; signature/correction page(s);
  exhibits (numbered, description, page referenced or marked); certified questions;
  requested information.
- **Actual layout (from Shaw, a real Myler deposition):** a single page, `PAGE` column on
  the right; Appearances → witness name → "Examination by [Attorney] … [page]" (one line
  per examination) → Signature and Changes → Reporter's Certificate; then an `EXHIBITS`
  section with `NO. / DESCRIPTION / PAGE`. Stipulations, certified questions, and requested
  information appear only if they occurred — Shaw had none, so they're absent.
- **Caveat:** any prescribed "center INDEX / center EXHIBITS / fixed column" template is
  convention, not a 3.24 mandate. Model the Shaw artifact; don't hard-enforce a layout.

## 2. 3.23 vs 3.24 — the index fork
- **3.23 (Official / trial):** each volume must contain three separate indexes —
  chronological (3.23(a), witnesses in order + all events), alphabetical (3.23(b), Figure 23),
  exhibit (3.23(c)) — immediately after the administrative pages. Columnar format required;
  single-spaced within a witness's exams, double-spaced between topic changes (3.23(e)).
- **3.24 (Freelance / deposition):** all major portions must be indexed, but no required
  format (3.24(b)); content per 3.24(a); placement flexible.
- **Engine gate:** `Record_Type == "Official"` (or multi-volume) → three-index + master-index
  rules. `Record_Type == "Freelance"` → consolidated single index.

## 3. Alphabetical witness index (3.23(b), 3.23(e))
- Alphabetical listing of witnesses (Figure 23). Columnar format. Single-spaced within a
  witness's direct/cross/redirect/recross; double-spaced between topic changes. When the
  chronological index ends, the alphabetical index begins on the same page if space allows,
  then the exhibit index likewise. Sort by surname.

## 4. Exhibit index formatting
- **Official (3.23(c)):** complete description + the page where each exhibit was *offered and
  received into evidence*. Columnar (3.23(e)).
- **Freelance (3.24(a)(6)):** exhibit number + description + page *referenced or marked*. No
  offered/admitted columns.
- **Offered but not admitted:** trial record shows it as offered, not received (3.23(c); log
  3.2(e) tracks offered/admitted/excluded). Deposition index doesn't carry the distinction.
- Omit the exhibit index entirely when no exhibits exist.

## 5. Master index for multiple volumes (3.23(d); 6.1, 6.3)
- Required only when an Official record exceeds one volume. Lives in its **own separate
  volume, labeled "Volume 1"** (also definition 1.1(o); 6.2(c)).
- Compiles all individual chronological, alphabetical, and exhibit indexes.
- **A `VOL.` column on every entry** is mandatory. A volume-summary listing (e.g.
  "Volume Two — Jury Selection") is **explicitly rejected for filing** (3.23(d) example).
- Figures 24 and 26. Volumes ≤ 300 pages (6.3); Arabic numerals only (6.1).
- (There is **no Section 17** in the manual; multi-volume is entirely 3.23(d) + 6.x.)

## 6. Parentheticals (3.16) and speaker identification (3.22)
- **Parentheticals:** the reporter's own words in parentheses recording an action/event; as
  short as possible; **no blank lines before or after** (3.16). Recommended notations include
  (The witness was sworn), (Interpreter sworn), (Exhibit ^ marked), (Discussion off the
  record), (Recess from ^ to ^), (Indicating), (No verbal response). Criminal trials add
  presence/jury parentheticals (3.16(b)).
- **Speaker ID (3.22):** all speakers in **capital letters**; **last name only** unless two
  attorneys share gender and surname (then first + last). Standard identifications: THE COURT
  (judge), THE WITNESS (witness in colloquy), THE REPORTER, THE INTERPRETER, MR./MRS./MS./
  MISS [last name] (attorney), THE PLAINTIFF, THE DEFENDANT, JUROR/VENIREPERSON, THE BAILIFF,
  THE CLERK, etc. By-line per Figure 21. Third tab setting for speaker labels, followed by a
  colon + two spaces (2.11).

## 7. Interpreter (3.11, 3.12)
- **Suggested oath (3.11):** "Do you solemnly swear or affirm that the interpretation you
  will give in this deposition will be from English to [language] and from [language] to
  English to the best of your ability?" Sign-language variant substitutes American Sign
  Language/Signed English.
- Witness-sworn-through-interpreter setup: Figure 16. Testimony in Q&A; answers assumed
  interpreted unless "(In English)" precedes a portion the witness answered in English (3.12);
  attorney speaking directly in the witness's language → parenthetical (Figure 22).
- The manual body defines interpreter *setup/oaths*, not a distinct interpreter *certificate*
  page — confirm before building one.

## 8. "Uh-huh" / "Huh-uh" (3.9)
- "Uh-huh" = affirmative; "Huh-uh" = negative; transcribe as spoken. Silent nod/shake with no
  verbal response → reporter may indicate the witness is responding affirmatively/negatively.

## 9. Stipulations & volume numbers in the consolidated index
- **Stipulations:** listed as an indexable element (3.24(a)(2)); the manual prescribes no
  specific in-index format (3.24(b)).
- **Volume numbers:** a single-volume deposition's consolidated index needs no `VOL.` column.
  The `VOL.` column is a master-index (multi-volume, 3.23(d)) requirement only.
