> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 18 — Export Engine, Menu & Real File Generation

Status: **BUILT.**

Companion to `docs/roadmap_ufm_production.md`. That document is the
strategic arc (Waves 18-20); this is the detailed plan for Wave 18 only.

## 1. The problem Wave 18 solves

Today's export builds a plain-text string in the browser and triggers a
blob download. Inside the PyWebView desktop shell that download
silently fails -- the success toast fires, but no file is written. And
even when it "works," `.docx`/`.pdf` are just text with a misleading
extension.

Wave 18 replaces this with **backend file generation written to real
disk locations**, in real formats, chosen from a menu.

## 2. The export menu

A panel on the Export screen with two choices: **format** and
**destination**.

### 2.1 Formats

- **ASCII / TXT** -- plain text, the current paginated layout.
- **DOCX** -- a real Word document via `python-docx`.
- **PDF** -- a real PDF via `reportlab`.
- **RTF** -- rich text.

NEEDS_JAMES_CONFIRMATION (Q5): whether "ASCII" is plain .txt or a
specific fixed-width court layout. Spec assumes plain .txt for now.

### 2.2 Destinations

| Format      | Default destination          | Alternative           |
|-------------|------------------------------|-----------------------|
| ASCII / TXT | Windows Downloads folder     | case workspace folder |
| DOCX        | native "Save As" dialog      | case workspace folder |
| PDF         | native "Save As" dialog      | case workspace folder |
| RTF         | native "Save As" dialog      | case workspace folder |

The menu lets the reporter override the destination per export. "Case
workspace folder" means the per-case directory the app already creates.

## 3. How files are generated and delivered

### 3.1 Backend does the writing

A new endpoint -- `POST /api/transcripts/jobs/{job_id}/export` --
accepts `{format, destination}`, renders the document, writes the file
to disk, and returns the absolute path. The backend, not the browser,
writes the file. This is what fixes the PyWebView bug.

### 3.2 The "Save As" dialog

For DOCX/PDF/RTF the default flow uses PyWebView's native file-save
dialog (`window.create_file_dialog(SAVE_DIALOG, ...)`). The reporter
picks folder and name; the backend writes there.

NEEDS_JAMES_CONFIRMATION (Q3 of roadmap): if PyWebView's save dialog is
unavailable in the installed version, the fallback is the fixed
destinations (Downloads / case folder) with no dialog.

### 3.3 Real document generation

- **DOCX** -- `python-docx`. Wave 18 produces a clean, real,
  structurally formatted Word document: correct caption block, Q/A
  paragraphs with hanging indents, colloquy, parentheticals, and a
  page break between transcript pages. **It does NOT yet draw the UFM
  format box / line-number margin geometry, and it does not yet apply
  true UFM pagination -- both are introduced in Wave 19.**
- **PDF** -- `reportlab`. Same content, paginated.
- **RTF** -- generated as RTF markup.
- **TXT/ASCII** -- the current text layout, written to a file.

### 3.4 One canonical renderer

All four formats consume the SAME canonical render output (the
`render.py` -> `export_render.py` pipeline that already feeds the
Export Preview). No per-format re-rendering -- formats differ only in
how the SAME document is *written*, never in what it *says*. This is
the Q6 commitment from the roadmap.

## 4. New dependencies

`python-docx` and `reportlab`, installed into the project venv:

    pip install python-docx reportlab --break-system-packages

This is roadmap blocker Q1. Without these, Wave 18 cannot produce real
documents.

## 5. Modules (planned)

    backend/export/
      __init__.py
      document_model.py   -- the in-memory export document (shared)
      docx_writer.py      -- python-docx generation
      pdf_writer.py       -- reportlab generation
      rtf_writer.py       -- RTF generation
      txt_writer.py       -- plain text / ASCII
      export_service.py   -- orchestration: render -> write -> path
    backend/api/transcripts.py   -- new POST .../export endpoint
    frontend/.../stage_6.js      -- the export menu + Save As flow

## 6. Tests (planned)

`tests/test_wave18_export.py` -- each writer produces a non-empty file
of the right type; the export service writes to the requested
destination; the endpoint 404s on an unknown job; unknown format/
destination is rejected; the canonical render output is identical
across formats (no drift).

## 7. Explicitly out of scope for Wave 18

- Format box, line numbers, page numbers, headers, footers, time
  stamps -> **Wave 19**.
- Caption / appearances / indices / corrections / certificate pages
  -> **Wave 20**.
- Condensed transcript, realtime feed, litigation-support exports
  -> later.
- Export profiles (California, arbitration, rough draft) -> later;
  Wave 18 builds Texas UFM directly (roadmap Q8).

## 8. Acceptance criteria

Wave 18 is done when:
- The Export screen has a working format + destination menu.
- Exporting DOCX produces a real .docx that opens in Word with correct,
  paginated testimony.
- Exporting PDF produces a real, paginated PDF.
- TXT and RTF produce correct files.
- Files are written to the chosen destination and the UI reports the
  real saved path (no more silent failure).
- All four formats render from the one canonical pipeline.
- The full test suite passes, plus the new Wave 18 tests.
