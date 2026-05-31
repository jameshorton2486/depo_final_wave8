"""Transcript Packaging Engine — Wave 20.

Wave 20 assembles a *Certified Transcript Package* — the testimony body
wrapped with administrative pages, indices, a manifest, and a
reporter's certificate, produced deterministically and reproducibly.

It does NOT alter transcript semantics or pagination: the canonical
renderer decided what the transcript says, Wave 19 decided where every
line sits. Wave 20 wraps that finished body into a legal artifact.

Pipeline:
    Transcript Snapshot (Wave 18.5, locked)
      -> Canonical Renderer
      -> Pagination Engine (Wave 19A)
      -> Geometry Layer (Wave 19B)
      -> Index Generation (Wave 20)
      -> Administrative Page Generators (Wave 20)
      -> Packaging Engine (Wave 20)
      -> Certified Transcript Package

See docs/wave20_packaging.md.
"""
from backend.packaging.indices import (
    ExhibitEvent,
    IndexInputs,
    OwnershipResolver,
    WitnessEvent,
    build_ownership_resolver,
    generate_indices,
)
from backend.packaging.manifest import (
    build_identity,
    build_manifest,
    compute_manifest_hash,
    verify_package_integrity,
)
from backend.packaging.model import (
    PACKAGE_STATES,
    PACKAGING_ENGINE_VERSION,
    AdministrativePage,
    Exhibit,
    GenerationReport,
    IndexEntry,
    PackageIdentity,
    PackageImmutableError,
    PackageManifest,
    TranscriptIndex,
    TranscriptPackage,
    can_transition,
)
from backend.packaging.packager import (
    SECTION_ORDER,
    assemble_package,
    certify_package,
)
from backend.packaging.validation import (
    REQUIRED_METADATA_FIELDS,
    ValidationResult,
    validate_for_certification,
    validate_metadata,
)

__all__ = [
    "PACKAGE_STATES",
    "PACKAGING_ENGINE_VERSION",
    "AdministrativePage",
    "Exhibit",
    "GenerationReport",
    "IndexEntry",
    "PackageIdentity",
    "PackageImmutableError",
    "PackageManifest",
    "TranscriptIndex",
    "TranscriptPackage",
    "can_transition",
    "ExhibitEvent",
    "IndexInputs",
    "OwnershipResolver",
    "WitnessEvent",
    "build_ownership_resolver",
    "generate_indices",
    "build_identity",
    "build_manifest",
    "compute_manifest_hash",
    "verify_package_integrity",
    "SECTION_ORDER",
    "assemble_package",
    "certify_package",
    "REQUIRED_METADATA_FIELDS",
    "ValidationResult",
    "validate_for_certification",
    "validate_metadata",
]
