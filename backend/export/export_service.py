"""Export service — Wave 18 orchestration.

Renders the canonical ExportDocument and writes it to disk in the
requested format and destination. The backend writes the file -- not
the browser -- which is what fixes the PyWebView blob-download failure.

Architectural commitments (Wave 18):
  * Export uses the SAME canonical renderer as the Export Preview.
  * Every export is logged: format, destination, absolute path.
  * Generated documents are reproducible from the same transcript.
"""
from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from backend.export.docx_writer import write_docx
from backend.export.pdf_writer import write_pdf
from backend.export.rtf_writer import write_rtf
from backend.export.txt_writer import write_txt
from backend.transcript.export_render import ExportDocument

# Supported formats -> (writer, extension).
EXPORT_FORMATS: dict = {
    "txt":  (write_txt, ".txt"),
    "ascii": (write_txt, ".txt"),   # ASCII == plain .txt for Wave 18
    "docx": (write_docx, ".docx"),
    "pdf":  (write_pdf, ".pdf"),
    "rtf":  (write_rtf, ".rtf"),
}

# Destination keywords the API accepts.
DEST_DOWNLOADS = "downloads"
DEST_CASE_FOLDER = "case_folder"
DEST_PATH = "path"               # an explicit absolute path (Save As)


def _safe_slug(text: str, fallback: str = "transcript") -> str:
    """Filesystem-safe slug from the case caption."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")
    return (slug or fallback)[:48]


def _downloads_dir() -> Path:
    """The current user's Downloads folder."""
    return Path.home() / "Downloads"


def resolve_destination(
    destination: str,
    explicit_path: str | None,
    case_dir: str | Path | None,
    filename: str,
) -> Path:
    """Resolve a destination keyword + filename into an absolute path."""
    if destination == DEST_PATH:
        if not explicit_path:
            raise ValueError("destination 'path' requires an explicit path")
        target = Path(explicit_path)
        # If a directory was given, append the filename.
        if target.is_dir() or not target.suffix:
            target = target / filename
        return target
    if destination == DEST_CASE_FOLDER:
        if not case_dir:
            raise ValueError(
                "destination 'case_folder' requires a case directory")
        return Path(case_dir) / "exports" / filename
    if destination == DEST_DOWNLOADS:
        return _downloads_dir() / filename
    raise ValueError(f"Unknown destination: {destination}")


def export_document(
    doc: ExportDocument,
    fmt: str,
    destination: str = DEST_DOWNLOADS,
    *,
    explicit_path: str | None = None,
    case_dir: str | Path | None = None,
) -> dict:
    """Render `doc` to `fmt` and write it to `destination`.

    Returns {format, path, pages, lines}. Raises ValueError on an
    unknown format or destination.
    """
    fmt = (fmt or "").lower().strip()
    if fmt not in EXPORT_FORMATS:
        raise ValueError(
            f"Unknown export format '{fmt}'. "
            f"Supported: {', '.join(sorted(EXPORT_FORMATS))}")

    writer, ext = EXPORT_FORMATS[fmt]
    filename = f"{_safe_slug(doc.caption)}_Certified_Transcript{ext}"
    target = resolve_destination(
        destination, explicit_path, case_dir, filename)

    written = writer(doc, target)
    logger.info(
        f"Export complete: format={fmt} destination={destination} "
        f"path={written}")

    return {
        "format": fmt,
        "path": str(written),
        "filename": written.name,
        "pages": doc.total_pages,
        "lines": doc.total_lines,
    }
