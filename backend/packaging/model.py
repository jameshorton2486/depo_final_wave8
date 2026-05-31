"""Packaging model — Wave 20.

The data vocabulary of the Transcript Packaging Engine. Wave 20 assembles
a *Certified Transcript Package* — the testimony body wrapped with
administrative pages, indices, a manifest, and a reporter's certificate.

The DOCX is merely the container the package is written into; the
*package* is the legally meaningful unit. These dataclasses model that
package, never a file.

See docs/wave20_packaging.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- engine identity ------------------------------------------------
PACKAGING_ENGINE_VERSION = "wave20.1"
DEFAULT_TEMPLATE_VERSION = "texas_ufm.v1"
DEFAULT_GEOMETRY_PROFILE = "texas_ufm"

# --- Package State (review item 1) ----------------------------------
# The lifecycle state of a Certified Transcript Package.
PACKAGE_STATES: tuple[str, ...] = (
    "DRAFT",        # assembled, not yet finalized
    "REVIEW",       # under reporter review
    "CERTIFIED",    # finalized, immutable, certificate attached
    "EXPORTED",     # a certified package written to a file
    "AMENDED",      # superseded by an amended package version
    "SUPERSEDED",   # replaced by a newer package version
    "SEALED",       # sealed by court order
)

# Legal one-directional transitions. A certified package is immutable:
# it may only move to EXPORTED / SEALED, or be marked AMENDED/SUPERSEDED
# when a *new* package version replaces it (never mutated in place).
PACKAGE_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"REVIEW", "CERTIFIED"}),
    "REVIEW": frozenset({"DRAFT", "CERTIFIED"}),
    "CERTIFIED": frozenset({"EXPORTED", "SEALED", "AMENDED", "SUPERSEDED"}),
    "EXPORTED": frozenset({"SEALED", "AMENDED", "SUPERSEDED"}),
    "AMENDED": frozenset(),
    "SUPERSEDED": frozenset(),
    "SEALED": frozenset(),
}

# A certified package's content is frozen in these states.
IMMUTABLE_STATES: frozenset[str] = frozenset(
    {"CERTIFIED", "EXPORTED", "AMENDED", "SUPERSEDED", "SEALED"})


def can_transition(from_state: str, to_state: str) -> bool:
    """True when a package may legally move from `from_state` to `to_state`."""
    return to_state in PACKAGE_STATE_TRANSITIONS.get(from_state, frozenset())


# --- administrative page kinds --------------------------------------
ADMIN_PAGE_KINDS: tuple[str, ...] = (
    "caption",
    "appearances",
    "chronological_index",
    "witness_index",
    "exhibit_index",
    "corrections_signature",
    "certificate",
)

# --- index kinds ----------------------------------------------------
INDEX_KINDS: tuple[str, ...] = ("chronological", "witness", "exhibit")


@dataclass
class AdministrativePage:
    """One administrative page — template-driven semantic content.

    `lines` is the page's text content. Physical geometry (the format
    box, line numbering, page numbers) is applied later by the Wave 19
    Geometry Layer — administrative pages share that geometry system.
    """

    kind: str
    title: str
    lines: list[str] = field(default_factory=list)
    template_version: str = DEFAULT_TEMPLATE_VERSION

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "title": self.title,
            "lines": list(self.lines),
            "template_version": self.template_version,
        }


@dataclass
class Exhibit:
    """An exhibit identity record (review item 7 — exhibit identity model).

    Wave 20 builds the exhibit *index*. `exhibit_files` is the seam a
    later wave's exhibit-document packaging attaches to; it is empty here.
    """

    exhibit_number: str
    exhibit_title: str = ""
    owner_snapshot_id: str = ""
    owner_anchor_utterance_id: str = ""
    reference_render_line_id: str = ""
    reference: str = ""                       # resolved "Page N, Line M"
    exhibit_files: list[str] = field(default_factory=list)

    def refresh_reference(self, resolver) -> None:
        """Re-derive the visible citation from stable exhibit ownership."""
        render_line_id, page, line = resolver.resolve_exhibit(
            self.owner_snapshot_id,
            self.owner_anchor_utterance_id,
            fallback_render_line_id=self.reference_render_line_id,
        )
        if render_line_id:
            self.reference_render_line_id = render_line_id
        if page is None:
            self.reference = ""
        elif line is None:
            self.reference = f"Page {page}"
        else:
            self.reference = f"Page {page}, Line {line}"

    def to_dict(self) -> dict:
        return {
            "exhibit_number": self.exhibit_number,
            "exhibit_title": self.exhibit_title,
            "owner_snapshot_id": self.owner_snapshot_id,
            "owner_anchor_utterance_id": self.owner_anchor_utterance_id,
            "reference_render_line_id": self.reference_render_line_id,
            "reference": self.reference,
            "exhibit_files": list(self.exhibit_files),
        }


@dataclass
class IndexEntry:
    """One referenceable entry in an index — a stable legal reference."""

    label: str
    owner_snapshot_id: str = ""
    owner_render_line_id: str = ""
    page: int | None = None
    line: int | None = None
    detail: str = ""

    def refresh_reference(self, resolver) -> None:
        """Re-derive page/line from stable transcript ownership."""
        page, line = resolver.resolve_index_entry(
            self.owner_snapshot_id,
            self.owner_render_line_id,
            fallback_page=self.page,
            fallback_line=self.line,
        )
        self.page = page
        self.line = line

    @property
    def reference(self) -> str:
        """A stable 'Page N, Line M' citation, or '' when unresolved."""
        if self.page is None:
            return ""
        if self.line is None:
            return f"Page {self.page}"
        return f"Page {self.page}, Line {self.line}"

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "owner_snapshot_id": self.owner_snapshot_id,
            "owner_render_line_id": self.owner_render_line_id,
            "page": self.page,
            "line": self.line,
            "detail": self.detail,
            "reference": self.reference,
        }


@dataclass
class TranscriptIndex:
    """One index — chronological, alphabetical witness, or exhibit."""

    kind: str
    entries: list[IndexEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "entries": [e.to_dict() for e in self.entries],
            "count": len(self.entries),
        }


@dataclass
class PackageIdentity:
    """Stable identity of a Certified Transcript Package (review item 2).

    Every field is derived deterministically from the inputs, so
    re-assembling the same locked snapshot yields the same identity —
    the basis of Package Reproducibility.
    """

    package_id: str
    transcript_snapshot_id: str
    state_hash: str
    package_version: int = 1
    certification_id: str = ""
    export_id: str = ""

    def to_dict(self) -> dict:
        return {
            "package_id": self.package_id,
            "transcript_snapshot_id": self.transcript_snapshot_id,
            "state_hash": self.state_hash,
            "package_version": self.package_version,
            "certification_id": self.certification_id,
            "export_id": self.export_id,
        }


@dataclass
class PackageManifest:
    """The Package Manifest — a self-describing record of what produced
    the package. The manifest_hash (computed in manifest.py) is the
    Package Integrity anchor.
    """

    identity: PackageIdentity
    certification_state: str = "DRAFT"
    package_timestamp: str = ""               # excluded from manifest_hash
    included_exhibits: list[str] = field(default_factory=list)
    generated_indices: list[str] = field(default_factory=list)
    template_versions: dict[str, str] = field(default_factory=dict)
    geometry_profile: str = DEFAULT_GEOMETRY_PROFILE
    packaging_engine_version: str = PACKAGING_ENGINE_VERSION
    manifest_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "identity": self.identity.to_dict(),
            "certification_state": self.certification_state,
            "package_timestamp": self.package_timestamp,
            "included_exhibits": list(self.included_exhibits),
            "generated_indices": list(self.generated_indices),
            "template_versions": dict(self.template_versions),
            "geometry_profile": self.geometry_profile,
            "packaging_engine_version": self.packaging_engine_version,
            "manifest_hash": self.manifest_hash,
        }


@dataclass
class GenerationReport:
    """Package Generation Report (review item 15) — an operational
    summary of what assembly produced and what still needs attention.
    """

    body_pages: int = 0
    administrative_pages: int = 0
    exhibits_indexed: int = 0
    witnesses_indexed: int = 0
    unresolved_flags: int = 0
    warnings: list[str] = field(default_factory=list)
    ai_review_summary: dict = field(default_factory=dict)
    certification_status: str = "DRAFT"
    validation_passed: bool = False

    @property
    def total_pages(self) -> int:
        return self.body_pages + self.administrative_pages

    def to_dict(self) -> dict:
        return {
            "body_pages": self.body_pages,
            "administrative_pages": self.administrative_pages,
            "total_pages": self.total_pages,
            "exhibits_indexed": self.exhibits_indexed,
            "witnesses_indexed": self.witnesses_indexed,
            "unresolved_flags": self.unresolved_flags,
            "warnings": list(self.warnings),
            "ai_review_summary": dict(self.ai_review_summary),
            "certification_status": self.certification_status,
            "validation_passed": self.validation_passed,
        }


class PackageImmutableError(RuntimeError):
    """Raised on an attempt to mutate a finalized (certified) package."""


@dataclass
class TranscriptPackage:
    """A Certified Transcript Package — the assembled legal artifact.

    `section_order` is the authoritative ordering decided by the
    Packaging Engine's Package Ordering Authority: a list of admin-page
    kinds plus the body marker `BODY_MARKER`.
    """

    BODY_MARKER = "__body__"

    identity: PackageIdentity
    manifest: PackageManifest
    generation_report: GenerationReport
    administrative_pages: dict = field(default_factory=dict)   # kind -> page
    section_order: list[str] = field(default_factory=list)
    body_page_count: int = 0
    indices: dict = field(default_factory=dict)                # kind -> index
    state: str = "DRAFT"

    @property
    def package_id(self) -> str:
        return self.identity.package_id

    def iter_sections(self):
        """Yield ('admin', AdministrativePage) / ('body', page_count) in
        the authoritative package order."""
        for key in self.section_order:
            if key == self.BODY_MARKER:
                yield ("body", self.body_page_count)
            else:
                page = self.administrative_pages.get(key)
                if page is not None:
                    yield ("admin", page)

    def _assert_mutable(self) -> None:
        if self.state in IMMUTABLE_STATES:
            raise PackageImmutableError(
                f"Package {self.package_id} is {self.state} and immutable; "
                f"changes must produce a new package version.")

    def transition(self, to_state: str) -> None:
        """Move the package to a new lifecycle state, enforcing the
        legal transition graph."""
        if not can_transition(self.state, to_state):
            raise PackageImmutableError(
                f"Illegal package transition {self.state} -> {to_state}.")
        self.state = to_state
        self.manifest.certification_state = to_state
        self.generation_report.certification_status = to_state

    def to_dict(self) -> dict:
        return {
            "package_id": self.package_id,
            "state": self.state,
            "identity": self.identity.to_dict(),
            "manifest": self.manifest.to_dict(),
            "generation_report": self.generation_report.to_dict(),
            "section_order": list(self.section_order),
            "body_page_count": self.body_page_count,
            "administrative_pages": {
                k: p.to_dict() for k, p in self.administrative_pages.items()},
            "indices": {k: idx.to_dict() for k, idx in self.indices.items()},
        }
