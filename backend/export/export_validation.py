"""Thin export-validation orchestrator for transcript export.

This module does not replace the renderer, paginator, or packaging
validators. It centralizes their invocation into one structured,
auditable pass/fail result.
"""
from __future__ import annotations

from backend.packaging.validation import (
    ValidationResult,
    validate_for_certification,
    validate_indices,
)
from backend.pagination.paginator import paginated_to_render_check


def _doc_payload(doc) -> dict:
    if hasattr(doc, "to_dict"):
        return doc.to_dict()
    return dict(doc or {})


def validate_export_bundle(
    *,
    preview_document,
    export_document,
    paginated_document,
    metadata: dict | None = None,
    indices: dict | None = None,
) -> dict:
    """Run the existing export/certification validators as one gate."""
    result = ValidationResult()
    checks: dict[str, dict] = {}

    try:
        pagination = paginated_to_render_check(paginated_document)
        checks["pagination_integrity"] = {"ok": True, **pagination}
    except AssertionError as exc:
        msg = f"Pagination integrity failed: {exc or 'page slot count mismatch.'}"
        result.errors.append(msg)
        checks["pagination_integrity"] = {"ok": False, "detail": msg}

    index_result = validate_indices(indices or {})
    result.errors.extend(index_result.errors)
    result.warnings.extend(index_result.warnings)
    checks["index_resolution"] = index_result.to_dict()

    body_page_count = getattr(paginated_document, "total_pages", 0) or 0
    certification_result = validate_for_certification(
        metadata or {},
        indices or {},
        body_page_count,
    )
    result.errors.extend(certification_result.errors)
    result.warnings.extend(certification_result.warnings)
    checks["certification_readiness"] = certification_result.to_dict()

    preview_payload = _doc_payload(preview_document)
    export_payload = _doc_payload(export_document)
    preview_matches_export = preview_payload == export_payload
    if not preview_matches_export:
        result.errors.append(
            "Preview/export consistency failed: preview and export documents diverged."
        )
    checks["preview_export_consistency"] = {
        "ok": preview_matches_export,
        "preview_pages": len(preview_payload.get("pages") or []),
        "export_pages": len(export_payload.get("pages") or []),
    }

    return {
        "ok": result.ok,
        "errors": result.errors,
        "warnings": result.warnings,
        "checks": checks,
    }
