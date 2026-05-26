# BLOCKERS.md — Decisions and Dependencies Needing James

_Updated 2026-05-22. **All five blockers are now RESOLVED.** BLOCKER-3
has a data-capture follow-on noted below._

---

## BLOCKER-1 · Geometry — Text-area width vs. UFM minimum

**STATUS: RESOLVED (2026-05-22).**

Per James's directive (Texas UFM mandates a text area no less than
6.5"): `backend/geometry/profile.py` `margin_right_twips` changed from
1440 (1.0") to **1080 (0.75")**. With the 1.25" left margin the text
area is now exactly **9360 twips = 6.5"**. Added a `meets_text_area_minimum`
property and a test assertion. The earlier 6.25" compliance failure is
corrected.

---

## BLOCKER-2 · Pagination flow rules — orphan/widow + Q/A tether

**STATUS: RESOLVED (2026-05-22).**

Per James's directive (UFM mandates exactly 25 lines per page and
prohibits blank body lines): standard orphan/widow control is
**disabled** in `backend/pagination/flow_rules.py` —
`MIN_LINES_TO_START = 1`, `KEEP_TOGETHER_TYPES` is empty, so colloquy,
long answers, and multi-line parentheticals flow continuously across
page breaks.

The one UFM keep-together rule — the **Q/A tether** — is implemented:
`requires_qa_tether()` plus a look-ahead in `paginator.py`. A "Q." line
followed by its "A." is pushed to a fresh page rather than stranded at
the foot of a page with its answer beginning the next page. A long
answer still wraps across pages; only the Q./start-of-A. boundary is
protected. Covered by `test_qa_tether_keeps_question_with_its_answer`.

---

## BLOCKER-3 · Admin-page template wording

**STATUS: RESOLVED — with a data-capture follow-on.**

`backend/packaging/admin_pages.py` now carries the exact Texas
statutory wording (Tex. R. Civ. P. 203.2 / 203.3, UFM Figures 3, 4, 8)
for the caption, appearances, and certificate pages.

**Follow-on (partially resolved):** the statutory text references many
per-deposition fields the pipeline does not yet capture — time used
per party, the officer's charges, custodial attorney, SBOT numbers,
firm registration, CSR expiration, examination waived/retained. Where
a field has no value the generator renders a [BRACKETED] placeholder.
A package with placeholders is correctly held at DRAFT. Fully
populating the certificate requires a data-capture path (intake fields
or a pre-export form) — a real follow-on task, separate from wording.

**Wave 21 update (2026-05-25):** the data-capture path now exists and
certification validation blocks when the enumerated follow-on fields are
missing. The remaining open decision is **Q20-6**: whether this
required-field set is the final James-approved legal set or whether it
should be broadened further. That is now a policy/authority question,
not a missing implementation path.

---

## BLOCKER-4 · Certification end-to-end test with real content

**STATUS: RESOLVED (2026-05-22).**

Added the `sample_job_with_content` fixture (`tests/conftest.py`) and
`test_packaging_certify_full_workflow` — exercises
snapshot -> lock -> assemble -> certify end-to-end with a real-content
job and asserts a CERTIFIED package.

---

## BLOCKER-5 · Export API — geometry not applied to live exports

**STATUS: RESOLVED (2026-05-22).**

`backend/api/transcripts.py` now calls `render_export_with_layout()`
and passes the PaginatedDocument into
`export_service.export_document(paginated_document=...)`. Live DOCX/PDF
exports now receive the Geometry Layer (UFM margins, format box, line
numbers).

---

_All five blockers resolved. Remaining open work: the BLOCKER-3
data-capture path for the bracketed certificate/caption fields._
