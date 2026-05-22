"""RTF export writer — Wave 18.

Writes the canonical ExportDocument as an RTF file -- rich text that
opens in Word and most editors, monospaced so the paginated layout is
preserved. No external dependency; RTF is generated directly.
"""
from __future__ import annotations

from pathlib import Path

from backend.transcript.export_render import ExportDocument

_RTF_HEADER = (
    r"{\rtf1\ansi\deff0"
    r"{\fonttbl{\f0\fmodern Courier New;}}"
    r"\fs20 "
)
_RTF_FOOTER = "}"


def _esc(text: str) -> str:
    """Escape RTF control characters."""
    return (
        (text or "")
        .replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )


def render_rtf(doc: ExportDocument) -> str:
    """Render the export document to an RTF string."""
    parts: list[str] = [_RTF_HEADER]

    def line(text: str) -> None:
        parts.append(_esc(text) + r"\par ")

    if doc.caption:
        line(doc.caption)
    if doc.cause_number:
        line(f"CAUSE NO. {doc.cause_number}")
    if doc.witness:
        line(f"CERTIFIED DEPOSITION OF {doc.witness.upper()}")
    line("")

    for page in doc.pages:
        line("=" * 55)
        line(f"PAGE {page.page_number}")
        line("=" * 55)
        for ln in page.lines:
            line(f"{str(ln.line_number).rjust(3)} | {ln.text}")
        line("")

    parts.append(_RTF_FOOTER)
    return "".join(parts)


def write_rtf(doc: ExportDocument, path: str | Path) -> Path:
    """Write the export document as an .rtf file. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_rtf(doc), encoding="utf-8")
    return path
