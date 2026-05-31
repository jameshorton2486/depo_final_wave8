## Cert-pipeline — "finish what exists" (NOT the template expansion)

Two finish lines, don't conflate them:
- FINISH WHAT EXISTS: the current certificate assembles + certifies cleanly. Nearly done (below).
- EXPAND: CNA/interpreter cert pages + the template work. Deferred — that's product expansion, not finishing.

Concrete checklist for "finish what exists", in order:

1. ONE confirmation run (no code). A single clean-case certify run likely closes FOUR open items at once:
   - `#2 time_per_party` — static round-trip is correct end-to-end; almost certainly identity contamination, not a code bug. Confirm via clean-case reproduction (prompt is written). Do NOT run a parser/validator fix.
   - `#4 end-time "12:00 AM"` — suspected same contamination; confirm on the clean case.
   - `#7 duplicate saved-case entries` — look-and-confirm; likely non-issue.
   - `#8 geometry tabs (5 vs 3)` — look-and-confirm; likely a superset, not a violation.

2. ONE small real fix: certificate clause `(c)`. CONFIRMED missing in `build_certificate_page`
   (`backend/packaging/admin_pages.py`). The "changes/corrections by the witness, if any, are
   attached" clause is absent. Single-clause insert near the examination/signature clause.
   Exact wording: lift from UFM or an OCR'd reference (the reference depo PDFs are scanned —
   no text layer — so wording verification needs OCR). Low risk, own small pass.

3. ONE integrity pass: `#1 drift guard`. The important one. Fresh-head, audit-first session — NOT end-of-night.

Items `#5` (federal/state caption branch) and `#6` (CNA/interpreter pages) belong to the EXPAND line, not finishing.

time_per_party + templates context (from this session):
- `time_per_party (#2)`: NOT a code bug per static trace; confirm-then-close as contamination.
- Templates (the day's original goal): deferred behind cert-pipeline stability + Phase C inventory. Not abandoned, correctly ordered.
