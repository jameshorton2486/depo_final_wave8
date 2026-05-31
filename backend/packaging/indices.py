"""Index Generation Engine — Wave 20.

Index construction is a real subsystem, not a formatting afterthought.
It runs strictly AFTER pagination is frozen (the Index Dependency
principle): an index entry's page number is only knowable once the
Wave 19 Pagination Engine has placed every line.

The engine consumes *structured* tracking events — never parsed
transcript text — and the frozen PaginatedDocument, and resolves each
event to a stable "Page N, Line M" reference (Cross-Reference
Stability). It produces the chronological, alphabetical-witness, and
exhibit indices the administrative pages consume.

See docs/wave20_packaging.md section 7.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.packaging.model import (
    Exhibit,
    IndexEntry,
    TranscriptIndex,
)


@dataclass
class WitnessEvent:
    """A structured examination-tracking event: a witness begins (or
    resumes) testimony under a given examination type."""

    witness_name: str
    examination_type: str = "direct"     # direct | cross | redirect | recross
    snapshot_id: str = ""
    render_line_id: str = ""
    volume: int = 1


@dataclass
class ExhibitEvent:
    """A structured exhibit-tracking event: an exhibit is marked."""

    exhibit_number: str
    exhibit_title: str = ""
    description: str = ""
    snapshot_id: str = ""
    anchor_utterance_id: str = ""
    render_line_id: str = ""
    volume: int = 1


@dataclass
class IndexInputs:
    """The structured tracking data the Index Generation Engine consumes."""

    witness_events: list[WitnessEvent] = field(default_factory=list)
    exhibit_events: list[ExhibitEvent] = field(default_factory=list)


@dataclass
class OwnershipResolver:
    """Resolve visible citations from stable ownership metadata."""

    page_reference_map: dict[str, tuple[int, int]] = field(default_factory=dict)
    exhibit_anchor_map: dict[tuple[str, str], str] = field(default_factory=dict)

    def resolve_index_entry(
        self,
        snapshot_id: str,
        render_line_id: str,
        *,
        fallback_page: int | None = None,
        fallback_line: int | None = None,
    ) -> tuple[int | None, int | None]:
        if snapshot_id and render_line_id:
            hit = self.page_reference_map.get(render_line_id)
            if hit is not None:
                return hit
        if render_line_id:
            hit = self.page_reference_map.get(render_line_id)
            if hit is not None:
                return hit
        return fallback_page, fallback_line

    def resolve_exhibit(
        self,
        snapshot_id: str,
        anchor_utterance_id: str,
        *,
        fallback_render_line_id: str = "",
    ) -> tuple[str, int | None, int | None]:
        render_line_id = ""
        if snapshot_id and anchor_utterance_id:
            render_line_id = self.exhibit_anchor_map.get(
                (snapshot_id, anchor_utterance_id), "")
        if not render_line_id and anchor_utterance_id:
            render_line_id = self.exhibit_anchor_map.get(("", anchor_utterance_id), "")
        if not render_line_id:
            render_line_id = fallback_render_line_id
        page, line = self.resolve_index_entry(snapshot_id, render_line_id)
        return render_line_id, page, line


def build_page_reference_map(paginated_document) -> dict[str, tuple[int, int]]:
    """Map each RenderLine id to its FIRST (page_number, slot_number).

    Built from the frozen Wave 19 PaginatedDocument. Because pagination
    is deterministic, this map is stable — the foundation of stable
    page/line references for legal citation.
    """
    ref_map: dict[str, tuple[int, int]] = {}
    if paginated_document is None:
        return ref_map
    for page in getattr(paginated_document, "pages", []):
        for slot in page.slots:
            phys = slot.physical_line
            if phys is None:
                continue
            rid = phys.source_render_line_id
            if rid and rid not in ref_map:
                ref_map[rid] = (page.page_number, slot.slot_number)
    return ref_map


def _resolve(ref_map: dict[str, tuple[int, int]],
             render_line_id: str) -> tuple[int | None, int | None]:
    """Resolve a RenderLine id to (page, line), or (None, None)."""
    hit = ref_map.get(render_line_id)
    return hit if hit is not None else (None, None)


def build_ownership_resolver(
    inputs: IndexInputs,
    paginated_document,
) -> OwnershipResolver:
    """Build the ownership resolver for stable reference derivation."""
    page_reference_map = build_page_reference_map(paginated_document)
    exhibit_anchor_map: dict[tuple[str, str], str] = {}
    for ev in inputs.exhibit_events:
        if ev.anchor_utterance_id and ev.render_line_id:
            exhibit_anchor_map[(ev.snapshot_id, ev.anchor_utterance_id)] = ev.render_line_id
            exhibit_anchor_map.setdefault(("", ev.anchor_utterance_id), ev.render_line_id)
    return OwnershipResolver(
        page_reference_map=page_reference_map,
        exhibit_anchor_map=exhibit_anchor_map,
    )


def build_chronological_index(
    inputs: IndexInputs,
    resolver: OwnershipResolver,
) -> TranscriptIndex:
    """The chronological index — every tracked event in transcript order,
    sorted by resolved page/line. Witness examinations and exhibit
    markings interleave exactly as they occur in the testimony.
    """
    rows: list[IndexEntry] = []

    for ev in inputs.witness_events:
        entry = IndexEntry(
            label=ev.witness_name,
            owner_snapshot_id=ev.snapshot_id,
            owner_render_line_id=ev.render_line_id,
            detail=f"{ev.examination_type.title()} Examination")
        entry.refresh_reference(resolver)
        rows.append(entry)

    for ev in inputs.exhibit_events:
        entry = IndexEntry(
            label=f"Exhibit {ev.exhibit_number}",
            owner_snapshot_id=ev.snapshot_id,
            owner_render_line_id=ev.render_line_id,
            detail=ev.exhibit_title or "Marked")
        entry.refresh_reference(resolver)
        rows.append(entry)

    # Chronological order = page then line. Unresolved entries (page is
    # None) sort to the end deterministically.
    rows.sort(key=lambda e: (e.page is None,
                             e.page or 0, e.line or 0, e.label))
    return TranscriptIndex(kind="chronological", entries=rows)


def build_witness_index(
    inputs: IndexInputs,
    resolver: OwnershipResolver,
) -> TranscriptIndex:
    """The alphabetical witness index — one entry per witness examination,
    ordered by witness surname then examination order.
    """
    rows: list[IndexEntry] = []
    for ev in inputs.witness_events:
        entry = IndexEntry(
            label=ev.witness_name,
            owner_snapshot_id=ev.snapshot_id,
            owner_render_line_id=ev.render_line_id,
            detail=f"{ev.examination_type.title()} Examination")
        entry.refresh_reference(resolver)
        rows.append(entry)

    def _surname_key(entry: IndexEntry) -> tuple:
        parts = entry.label.strip().split()
        surname = parts[-1].lower() if parts else entry.label.lower()
        return (surname, entry.page or 0, entry.line or 0)

    rows.sort(key=_surname_key)
    return TranscriptIndex(kind="witness", entries=rows)


def build_exhibit_index(
    inputs: IndexInputs,
    resolver: OwnershipResolver,
) -> tuple[TranscriptIndex, list[Exhibit]]:
    """The exhibit index — exhibits by number, with the page/line each
    was marked. Also returns the Exhibit identity records (the seam a
    later wave's exhibit-document packaging attaches to).
    """
    rows: list[IndexEntry] = []
    exhibits: list[Exhibit] = []

    for ev in inputs.exhibit_events:
        entry = IndexEntry(
            label=f"Exhibit {ev.exhibit_number}",
            owner_snapshot_id=ev.snapshot_id,
            owner_render_line_id=ev.render_line_id,
            detail=ev.description or ev.exhibit_title or "")
        entry.refresh_reference(resolver)
        exhibit = Exhibit(
            exhibit_number=str(ev.exhibit_number),
            exhibit_title=ev.exhibit_title,
            owner_snapshot_id=ev.snapshot_id,
            owner_anchor_utterance_id=ev.anchor_utterance_id,
            reference_render_line_id=ev.render_line_id,
            reference=entry.reference)
        exhibit.refresh_reference(resolver)
        if exhibit.reference_render_line_id:
            entry.owner_render_line_id = exhibit.reference_render_line_id
            entry.refresh_reference(resolver)
        rows.append(entry)
        exhibits.append(exhibit)

    def _exhibit_key(entry: IndexEntry) -> tuple:
        num = entry.label.replace("Exhibit", "").strip()
        # Numeric exhibits sort numerically; lettered ones sort after.
        return (0, int(num)) if num.isdigit() else (1, num)

    paired = sorted(zip(rows, exhibits),
                    key=lambda pr: _exhibit_key(pr[0]))
    rows = [p[0] for p in paired]
    exhibits = [p[1] for p in paired]
    return TranscriptIndex(kind="exhibit", entries=rows), exhibits


def generate_indices(
    inputs: IndexInputs,
    paginated_document,
) -> tuple[dict, list[Exhibit]]:
    """Generate all three indices from structured tracking data and the
    frozen PaginatedDocument.

    Returns (indices_by_kind, exhibits). `indices_by_kind` has keys
    'chronological', 'witness', 'exhibit'.
    """
    resolver = build_ownership_resolver(inputs, paginated_document)
    chronological = build_chronological_index(inputs, resolver)
    witness = build_witness_index(inputs, resolver)
    exhibit_index, exhibits = build_exhibit_index(inputs, resolver)
    return (
        {
            "chronological": chronological,
            "witness": witness,
            "exhibit": exhibit_index,
        },
        exhibits,
    )
