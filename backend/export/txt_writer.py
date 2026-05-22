"""Plain text / ASCII export writer — Wave 18.

Writes the canonical ExportDocument as a plain .txt file. This is the
same paginated layout the app has always produced, now written to a
real file on disk instead of streamed as a browser blob.
"""
from __future__ import annotations

from pathlib import Path

from backend.transcript.export_render import ExportDocument

_RULE = "=" * 55


def render_txt(doc: ExportDocument) -> str:
    """Render the export document to a plain-text string."""
    out: list[str] = []
    if doc.caption:
        out.append(doc.caption)
    if doc.cause_number:
        out.append(f"CAUSE NO. {doc.cause_number}")
    if doc.witness:
        out.append(f"CERTIFIED DEPOSITION OF {doc.witness.upper()}")
    out.append("")

    for page in doc.pages:
        out.append(_RULE)
        out.append(f"PAGE {page.page_number}")
        out.append(_RULE)
        for ln in page.lines:
            out.append(f"{str(ln.line_number).rjust(3)} | {ln.text}")
        out.append("")

    return "\n".join(out)


def write_txt(doc: ExportDocument, path: str | Path) -> Path:
    """Write the export document as a .txt file. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_txt(doc), encoding="utf-8")
    return path
