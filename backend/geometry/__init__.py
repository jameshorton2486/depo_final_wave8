"""Geometry Layer — Wave 19B.

Decorates the Pagination Engine's output with UFM physical page
furniture: the format box, line numbers, page numbers, headers,
footers, and the 5-tab system.

Geometry is page furniture -- it never alters transcript content. It
decorates pages whose line placement the Pagination Engine has already
fixed.

All measurements live behind the GeometryProfile abstraction so future
jurisdictions can be added as additional profiles.

See docs/wave19_ufm_layout.md.
"""
from backend.geometry.engine import GeometryDocument, PageGeometry, apply_geometry
from backend.geometry.profile import GeometryProfile, TEXAS_UFM

__all__ = [
    "GeometryProfile", "TEXAS_UFM",
    "apply_geometry", "GeometryDocument", "PageGeometry",
]
