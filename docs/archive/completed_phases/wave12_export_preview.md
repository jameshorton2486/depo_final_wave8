> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 12 — Canonical Export Preview

Status: **BUILT.**

Wave 12 turns the Export screen from a static mockup into a true
"what will actually export" preview, rendered by the same canonical
pipeline that produces the export file.

## The problem this fixed

Before Wave 12 the Export screen showed **hardcoded HTML** — a fake
"SARAH JENKINS vs. NEXUS PHARMA INC." transcript that never changed
regardless of the real case. The export download also had the caption
hardcoded. The preview and the actual transcript had no connection.

## Architecture

    RAW (immutable)
      -> participant mapping
      -> render.py          (WORKING lines)
      -> correction engine  (deterministic stages)
      -> export_render.py   (paginated formatted layout)   <-- NEW
      -> Export preview  AND  export download

`export_render.py` is the single export-layout authority. The preview
and the download both render from it, so they cannot diverge.

## What was built

### Backend

- `backend/transcript/export_render.py` — **NEW.** The canonical
  export-layout renderer. Produces an `ExportDocument`: pages of
  numbered lines (25 lines/page), caption header, PROCEEDINGS /
  EXAMINATION BY blocks, Q/A hanging indents, colloquy speaker labels,
  flagged-line handling. Deterministic; word-wrap never drops a word.
- `backend/api/transcripts.py` —
  - `GET .../jobs/{job_id}/export-preview` — authoritative preview for a
    saved job (RAW -> mapping -> render -> export_render).
  - `POST .../export-preview/fallback` — preview for a transient unsaved
    transcript, marked `is_approximate=True`.

### Frontend

- `frontend/assets/js/api.js` — `getExportPreview()`,
  `getExportPreviewFallback()`.
- `frontend/screens/stage_6_export.html` — the hardcoded mock preview
  and the hardcoded "SARAH JENKINS" caption are **deleted**. Replaced by
  a live preview pane and a **"Refresh Preview"** button.
- `frontend/assets/js/screens/stage_6.js` — rewritten. Renders the
  canonical `ExportDocument`; the export download builds from the same
  document so the file equals the preview. Auto-refreshes when the
  Export screen opens.

### Tests

- `tests/test_wave12_export_preview.py` — 14 tests: pagination, line
  numbering, Q/A prefixes, colloquy labels, flagged lines, no-word-loss,
  determinism, caption/header block, and both endpoints.
- Full suite: **232 passing.**

## Saved vs. unsaved transcripts

A saved job uses the authoritative `export-preview` endpoint. A
transient unsaved transcript uses the fallback endpoint and the preview
is clearly labelled "Approximate — transcript not yet saved". The
long-term authority is always the job-based backend render.

## Known limits (deferred — by plan)

The preview faithfully reflects everything in the pipeline *today*:
speaker mapping, Q/A typing, and the G/A/M/T/F/U correction stages. It
does NOT yet show:

- **Objection isolation, parentheticals, off-record** — correction
  engine Stage S. **Wave 13.**
- **Backend regex corrections, the real AI suggestions layer, spelling
  (Stage X)** — **Wave 14.**

Each lands in the same pipeline before `export_render.py`, so the
Export preview will reflect them automatically as they ship.

Real binary DOCX/PDF generation (true double-spacing, Texas UFM
margins) remains a follow-up; the current export is structured text
that matches the preview exactly.
