"""Pagination Engine — Wave 19A.

The PRIMARY engine of physical transcript production. It decides,
deterministically, what content lands on which page -- the
RenderLine -> PhysicalLine -> PageSlot -> Page mapping.

The Geometry Layer (Wave 19B) decorates this engine's output; the
Export Engine writes it. Neither paginates independently.

See docs/wave19_ufm_layout.md.
"""
from backend.pagination.model import (
    PhysicalLine,
    PageSlot,
    Page,
    PaginatedDocument,
)
from backend.pagination.legal_validation import (
    LegalPageMapValidationResult,
    validate_legal_page_map,
)
from backend.pagination.paginator import paginate

__all__ = [
    "PhysicalLine",
    "PageSlot",
    "Page",
    "PaginatedDocument",
    "LegalPageMapValidationResult",
    "paginate",
    "validate_legal_page_map",
]
