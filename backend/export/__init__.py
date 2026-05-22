"""Backend export package — Wave 18.

Real binary document generation. Every writer consumes the SAME
canonical ExportDocument (backend/transcript/export_render.py) that
feeds the Export Preview -- so preview and export never drift.

See docs/wave18_export_menu.md.
"""
from backend.export.export_service import export_document, EXPORT_FORMATS

__all__ = ["export_document", "EXPORT_FORMATS"]
