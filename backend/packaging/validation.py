"""Package Validation Pipeline — Wave 20.

Before a package is assembled (and certainly before it is certified),
its inputs are validated. Packaging fails *gracefully* with specific
errors rather than producing a certified package with blank mandatory
fields.

Review items 11 (metadata validation) and 13 (validation pipeline).

The pipeline is data-driven: REQUIRED_METADATA_FIELDS is the single
place the mandatory-field set is defined, so Q20-6 can be answered by
editing one tuple.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# The mandatory metadata for a certifiable Texas-UFM package.
# NEEDS_JAMES_CONFIRMATION (plan Q20-6).
REQUIRED_METADATA_FIELDS: tuple[str, ...] = (
    "cause_number",
    "caption",
    "court",
    "witness_name",
    "reporter_name",
    "reporter_csr_number",
    "proceedings_date",
)

# BLOCKER-3 follow-on / Q20-6 boundary:
# These are the additional certificate data-capture fields already
# surfaced in Stage 5 and rendered by the certificate page. Certification
# should fail cleanly when they are absent rather than producing a
# package that still contains bracketed legal placeholders.
REQUIRED_CERTIFICATE_FIELDS: tuple[str, ...] = (
    "examination_disposition",
    "custodial_attorney",
    "officer_charges_amount",
    "charges_party",
    "certificate_service_date",
    "reporter_csr_expiration",
    "firm_registration_no",
    "time_per_party",
    "counsel_of_record",
    "appearances",
)


@dataclass
class ValidationResult:
    """The outcome of a validation pass — errors block, warnings inform."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing blocks packaging (warnings do not block)."""
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _is_blank(value) -> bool:
    """True when a metadata value is missing or effectively empty."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def validate_metadata(metadata: dict) -> ValidationResult:
    """Validate package metadata against the required-field set.

    A missing or blank required field is an *error* (blocks packaging).
    Appearances are validated as a warning when absent — a deposition
    with no recorded appearances is unusual but not strictly invalid.
    """
    metadata = metadata or {}
    result = ValidationResult()

    for field_name in REQUIRED_METADATA_FIELDS:
        if _is_blank(metadata.get(field_name)):
            result.errors.append(
                f"Required metadata field is missing or blank: "
                f"'{field_name}'.")

    for field_name in REQUIRED_CERTIFICATE_FIELDS:
        if _is_blank(metadata.get(field_name)):
            result.errors.append(
                f"Required certification field is missing or blank: "
                f"'{field_name}'.")

    for idx, appearance in enumerate(metadata.get("appearances") or [], start=1):
        if _is_blank((appearance or {}).get("sbot_no")):
            result.errors.append(
                "Required certification field is missing or blank: "
                f"'appearances[{idx}].sbot_no'."
            )

    if _is_blank(metadata.get("location")):
        result.warnings.append(
            "No deposition location recorded for the caption page.")

    return result


def validate_indices(indices: dict) -> ValidationResult:
    """Validate generated indices — every index entry must resolve to a
    real page reference once pagination is frozen (Cross-Reference
    Stability, review item 6).
    """
    result = ValidationResult()
    for kind, index in (indices or {}).items():
        for entry in getattr(index, "entries", []):
            if entry.page is None:
                result.warnings.append(
                    f"{kind} index entry '{entry.label}' has no page "
                    f"reference — pagination may not be final.")
    return result


def validate_for_certification(
    metadata: dict,
    indices: dict,
    body_page_count: int,
) -> ValidationResult:
    """The full pre-certification validation pass.

    Combines metadata validation, index validation, and a body-presence
    check into one result. A package with no body pages cannot certify.
    """
    result = ValidationResult()

    meta_result = validate_metadata(metadata)
    result.errors.extend(meta_result.errors)
    result.warnings.extend(meta_result.warnings)

    index_result = validate_indices(indices)
    result.errors.extend(index_result.errors)
    result.warnings.extend(index_result.warnings)

    if body_page_count <= 0:
        result.errors.append(
            "Package has no transcript body pages — nothing to certify.")

    return result
