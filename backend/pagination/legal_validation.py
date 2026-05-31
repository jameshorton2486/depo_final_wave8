"""Phase 4A legal page-map validation.

Validation-only comparison between:

1. The live export-render page map.
2. The semantic `backend.pagination` page map.
3. An optional saved reference PDF artifact.

This module does NOT change runtime pagination authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from backend.pagination.model import LINES_PER_PAGE, Page, PageSlot, PhysicalLine, PaginatedDocument
from backend.pagination.paginator import paginate
from backend.stage_s.models import RenderLine
from backend.stage_s.renderer import StageSResult, render_stage_s
from backend.transcript import repository as trepo
from backend.transcript import export_render as export_render_mod


@dataclass
class CategoryDrift:
    total: int = 0
    page_number_drift: int = 0
    page_reference_drift: int = 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "page_number_drift": self.page_number_drift,
            "page_reference_drift": self.page_reference_drift,
        }


@dataclass
class ReferenceArtifactComparison:
    artifact_path: str = ""
    artifact_kind: str = ""
    available: bool = False
    reference_pages: int = 0
    live_page_delta: int | None = None
    semantic_page_delta: int | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "artifact_path": self.artifact_path,
            "artifact_kind": self.artifact_kind,
            "available": self.available,
            "reference_pages": self.reference_pages,
            "live_page_delta": self.live_page_delta,
            "semantic_page_delta": self.semantic_page_delta,
            "notes": list(self.notes),
        }


@dataclass
class LegalPageMapValidationResult:
    job_id: str
    source_filename: str
    logical_lines: int
    live_pages: int
    semantic_pages: int
    live_continuations: int
    semantic_continuations: int
    page_reference_drift: int
    page_number_drift: int
    qa_page_breaks_live: int
    qa_page_breaks_semantic: int
    categories: dict[str, CategoryDrift] = field(default_factory=dict)
    reference_artifact: ReferenceArtifactComparison = field(default_factory=ReferenceArtifactComparison)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "source_filename": self.source_filename,
            "logical_lines": self.logical_lines,
            "live_pages": self.live_pages,
            "semantic_pages": self.semantic_pages,
            "live_continuations": self.live_continuations,
            "semantic_continuations": self.semantic_continuations,
            "page_reference_drift": self.page_reference_drift,
            "page_number_drift": self.page_number_drift,
            "qa_page_breaks_live": self.qa_page_breaks_live,
            "qa_page_breaks_semantic": self.qa_page_breaks_semantic,
            "categories": {k: v.to_dict() for k, v in self.categories.items()},
            "reference_artifact": self.reference_artifact.to_dict(),
            "notes": list(self.notes),
        }


def _stage_s_to_working_lines(stage_s: StageSResult) -> tuple[list[dict], list[RenderLine]]:
    """Apply the live export-preview mapping from Stage S to working lines."""
    working: list[dict] = []
    source_lines: list[RenderLine] = []
    for ln in stage_s.lines:
        if ln.render_state == "OFF_RECORD" and not ln.procedural:
            continue
        if ln.line_type == "parenthetical":
            lt = "colloquy"
        elif ln.line_type in ("by_line", "examination"):
            lt = ln.line_type
        elif ln.line_type in ("Q", "A", "colloquy", "flagged"):
            lt = ln.line_type
        else:
            lt = "colloquy"
        working.append(
            {
                "line_type": lt,
                "speaker_label": ln.speaker_label,
                "text": ln.text,
            }
        )
        source_lines.append(ln)
    return working, source_lines


def _new_page(page_number: int) -> Page:
    return Page(
        page_number=page_number,
        page_id=f"legal-page-{page_number:04d}",
        slots=[PageSlot(slot_number=n) for n in range(1, LINES_PER_PAGE + 1)],
    )


def _authoritative_paginate_stage_s(
    source_lines: list[RenderLine],
    working_lines: list[dict],
    *,
    proceedings_date: str = "",
    body_width: int = 64,
) -> tuple[PaginatedDocument, dict[str, tuple[int, int]]]:
    """Paginate using export_render semantics while preserving Stage S ownership."""
    segments: list[tuple[str, str, str]] = []
    if proceedings_date:
        segments.append((f"PROCEEDINGS, {proceedings_date.upper()}", "proceedings", "__proceedings__"))
        segments.append(("", "blank", "__proceedings__"))

    for ln, wl in zip(source_lines, working_lines):
        for text, kind in export_render_mod._body_lines_for(wl, body_width):  # noqa: SLF001
            segments.append((text, kind, ln.line_id))
        segments.append(("", "blank", ln.line_id))

    pages: list[Page] = []
    current = _new_page(1)
    pages.append(current)
    next_slot = 0
    first_refs: dict[str, tuple[int, int]] = {}

    for idx, (text, kind, line_id) in enumerate(segments):
        if next_slot >= LINES_PER_PAGE:
            current = _new_page(len(pages) + 1)
            pages.append(current)
            next_slot = 0
        current.slots[next_slot].physical_line = PhysicalLine(
            text=text,
            tab_level=0,
            line_type=kind,
            source_render_line_id=f"{line_id}#{idx}",
        )
        if line_id not in first_refs and line_id != "__proceedings__":
            first_refs[line_id] = (current.page_number, next_slot + 1)
        next_slot += 1

    return PaginatedDocument(pages=pages, continuations=[]), first_refs


def _semantic_paginate_stage_s(
    source_lines: list[RenderLine],
) -> tuple[PaginatedDocument, dict[str, tuple[int, int]]]:
    """Paginate directly from Stage S logical lines."""
    semantic_lines: list[RenderLine] = []
    for ln in source_lines:
        text = ln.text
        if ln.line_type == "Q":
            text = f"Q.  {text}"
        elif ln.line_type == "A":
            text = f"A.  {text}"
        elif ln.line_type == "flagged":
            label = (ln.speaker_label or "UNIDENTIFIED SPEAKER").strip().rstrip(":")
            text = f"{label}: {text}"
        semantic_lines.append(ln)
        semantic_lines[-1] = RenderLine(
            line_id=ln.line_id,
            line_type=ln.line_type,
            text=text,
            speaker_label=ln.speaker_label,
            source_utterance_ids=list(ln.source_utterance_ids),
            tab_level=ln.tab_level,
            procedural=ln.procedural,
            render_state=ln.render_state,
            audit_note=ln.audit_note,
        )
        semantic_lines.append(
            RenderLine(
                line_id=f"{ln.line_id}__blank",
                line_type="blank",
                text="",
                procedural=True,
            )
        )
    candidate = paginate(semantic_lines, wrap_width=54)
    first_refs: dict[str, tuple[int, int]] = {}
    for page in candidate.pages:
        for slot in page.slots:
            phys = slot.physical_line
            if phys is None:
                continue
            line_id = phys.source_render_line_id
            if line_id and line_id not in first_refs:
                first_refs[line_id] = (page.page_number, slot.slot_number)
    return candidate, first_refs


def _is_objection(line: RenderLine) -> bool:
    return "objection" in (line.text or "").lower()


def _is_exhibit_discussion(line: RenderLine) -> bool:
    return "exhibit" in (line.text or "").lower()


def _is_long_answer(line: RenderLine) -> bool:
    return line.line_type == "A" and len((line.text or "").split()) > 40


def _build_categories(source_lines: list[RenderLine]) -> dict[str, set[str]]:
    categories: dict[str, set[str]] = {
        "long_answers": set(),
        "colloquy": set(),
        "objections": set(),
        "exhibit_discussions": set(),
        "parentheticals": set(),
    }
    for ln in source_lines:
        if _is_long_answer(ln):
            categories["long_answers"].add(ln.line_id)
        if ln.line_type == "colloquy":
            categories["colloquy"].add(ln.line_id)
        if _is_objection(ln):
            categories["objections"].add(ln.line_id)
        if _is_exhibit_discussion(ln):
            categories["exhibit_discussions"].add(ln.line_id)
        if ln.line_type == "parenthetical":
            categories["parentheticals"].add(ln.line_id)
    return categories


def _qa_page_breaks(
    source_lines: list[RenderLine],
    first_refs: dict[str, tuple[int, int]],
    last_refs: dict[str, tuple[int, int]],
) -> int:
    count = 0
    for idx in range(len(source_lines) - 1):
        cur = source_lines[idx]
        nxt = source_lines[idx + 1]
        if cur.line_type != "Q" or nxt.line_type != "A":
            continue
        cur_last = last_refs.get(cur.line_id)
        nxt_first = first_refs.get(nxt.line_id)
        if cur_last is None or nxt_first is None:
            continue
        if cur_last[0] != nxt_first[0] and cur_last[1] == LINES_PER_PAGE and nxt_first[1] == 1:
            count += 1
    return count


def _last_ref_map(
    doc: PaginatedDocument,
    *,
    source_id_normalizer,
) -> dict[str, tuple[int, int]]:
    refs: dict[str, tuple[int, int]] = {}
    for page in doc.pages:
        for slot in page.slots:
            phys = slot.physical_line
            if phys is None:
                continue
            line_id = source_id_normalizer(phys.source_render_line_id or "")
            if line_id:
                refs[line_id] = (page.page_number, slot.slot_number)
    return refs


def _strip_pdf_line_number(line: str) -> str:
    return re.sub(r"^\s*\d+\s*", "", line or "").strip()


def _load_pdf_reference_pages(pdf_path: Path) -> list[str]:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            cleaned = "\n".join(
                _strip_pdf_line_number(part)
                for part in text.splitlines()
                if _strip_pdf_line_number(part)
            )
            pages.append(cleaned)
    return pages


def _compare_reference_artifact(
    pdf_path: str | None,
    *,
    live_pages: int,
    semantic_pages: int,
) -> ReferenceArtifactComparison:
    if not pdf_path:
        return ReferenceArtifactComparison(
            notes=["No reference artifact supplied for automated scoring."],
        )

    path = Path(pdf_path)
    result = ReferenceArtifactComparison(
        artifact_path=str(path),
        artifact_kind=path.suffix.lower().lstrip("."),
        available=path.exists(),
    )
    if not path.exists():
        result.notes.append("Reference artifact path does not exist.")
        return result
    if path.suffix.lower() != ".pdf":
        result.notes.append("Only PDF reference artifacts are automatically scored in Phase 4A.")
        return result

    pages = _load_pdf_reference_pages(path)
    result.reference_pages = len(pages)
    result.live_page_delta = live_pages - len(pages)
    result.semantic_page_delta = semantic_pages - len(pages)
    result.notes.append(
        "Page-count deltas are informative only unless the artifact is confirmed to represent the same transcript job."
    )
    return result


def validate_legal_page_map(
    *,
    job_id: str,
    reference_pdf_path: str | None = None,
) -> LegalPageMapValidationResult:
    """Compare live and semantic page maps for a real persisted transcript job."""
    job = trepo.get_job(job_id)
    if not job:
        raise ValueError(f"Transcript job {job_id} not found")

    utterances = trepo.get_utterances(job_id, layer="working")
    participants = trepo.get_participants(job_id)
    if not participants:
        raise ValueError(f"Transcript job {job_id} has no participant mapping")

    stage_s = render_stage_s(utterances, participants)
    working_lines, source_lines = _stage_s_to_working_lines(stage_s)
    live_doc, live_refs = _authoritative_paginate_stage_s(source_lines, working_lines)
    semantic_doc, semantic_refs = _semantic_paginate_stage_s(source_lines)
    live_last_refs = _last_ref_map(
        live_doc,
        source_id_normalizer=lambda value: value.split("#", 1)[0],
    )
    semantic_last_refs = _last_ref_map(
        semantic_doc,
        source_id_normalizer=lambda value: "" if value.endswith("__blank") else value,
    )

    categories = _build_categories(source_lines)
    category_summary: dict[str, CategoryDrift] = {}
    page_ref_drift = 0
    page_num_drift = 0
    for name, line_ids in categories.items():
        summary = CategoryDrift(total=len(line_ids))
        for line_id in line_ids:
            live_ref = live_refs.get(line_id)
            semantic_ref = semantic_refs.get(line_id)
            if live_ref != semantic_ref:
                summary.page_reference_drift += 1
            if live_ref is not None and semantic_ref is not None and live_ref[0] != semantic_ref[0]:
                summary.page_number_drift += 1
        category_summary[name] = summary

    for line in source_lines:
        live_ref = live_refs.get(line.line_id)
        semantic_ref = semantic_refs.get(line.line_id)
        if live_ref != semantic_ref:
            page_ref_drift += 1
        if live_ref is not None and semantic_ref is not None and live_ref[0] != semantic_ref[0]:
            page_num_drift += 1

    reference_artifact = _compare_reference_artifact(
        reference_pdf_path,
        live_pages=live_doc.total_pages,
        semantic_pages=semantic_doc.total_pages,
    )
    notes = []
    if not reference_pdf_path:
        notes.append(
            "Local Phase 4A run compares both engines on real persisted jobs, but no independent certified PDF was supplied for the same transcript."
        )

    return LegalPageMapValidationResult(
        job_id=job_id,
        source_filename=job.get("source_filename") or "",
        logical_lines=len(source_lines),
        live_pages=live_doc.total_pages,
        semantic_pages=semantic_doc.total_pages,
        live_continuations=len(live_doc.continuations),
        semantic_continuations=len(semantic_doc.continuations),
        page_reference_drift=page_ref_drift,
        page_number_drift=page_num_drift,
        qa_page_breaks_live=_qa_page_breaks(source_lines, live_refs, live_last_refs),
        qa_page_breaks_semantic=_qa_page_breaks(source_lines, semantic_refs, semantic_last_refs),
        categories=category_summary,
        reference_artifact=reference_artifact,
        notes=notes,
    )
