from __future__ import annotations

from backend.export.export_validation import validate_export_bundle
from backend.packaging import ExhibitEvent, IndexInputs, WitnessEvent
from backend.packaging.indices import generate_indices
from backend.pagination.paginator import paginate
from backend.stage_s.models import RenderLine
from backend.transcript.export_render import render_export_document


def _render_lines(n: int = 60) -> list[RenderLine]:
    return [
        RenderLine(
            line_id=f"L{i}",
            line_type="qa",
            text=f"This is render line number {i}.",
            tab_level=2,
        )
        for i in range(n)
    ]


def _paginated(n: int = 60):
    return paginate(_render_lines(n))


def _valid_metadata() -> dict:
    return {
        "cause_number": "2024-CI-09912",
        "caption": "Acme Corp. v. Heath Thomas",
        "court": "288th Judicial District Court, Bexar County, Texas",
        "witness_name": "Heath Thomas",
        "reporter_name": "Miah Bardot",
        "reporter_csr_number": "TX-10423",
        "reporter_csr_expiration": "12/31/2027",
        "firm_registration_no": "10698",
        "proceedings_date": "May 21, 2026",
        "location": "1100 NW Loop 410, San Antonio, Texas",
        "examination_disposition": "waived",
        "custodial_attorney": "Ms. Elizabeth R. Flora, Esq.",
        "officer_charges_amount": "450.00",
        "charges_party": "Acme Corp.",
        "certificate_service_date": "June 5, 2026",
        "time_per_party": [{"party": "Plaintiff Counsel", "duration": "1:30"}],
        "counsel_of_record": [{"name": "Mr. Nunez", "role": "Attorney for Acme Corp."}],
        "appearances": [
            {
                "role": "plaintiff",
                "attorney": "Mr. Nunez",
                "firm": "Nunez & Associates",
                "party": "Acme Corp.",
                "sbot_no": "24098765",
            },
        ],
    }


def _index_inputs() -> IndexInputs:
    return IndexInputs(
        witness_events=[
            WitnessEvent(
                witness_name="Heath Thomas",
                examination_type="direct",
                render_line_id="L3",
            ),
            WitnessEvent(
                witness_name="Anna Alvarado",
                examination_type="cross",
                render_line_id="L40",
            ),
        ],
        exhibit_events=[
            ExhibitEvent(
                exhibit_number="2",
                exhibit_title="Contract",
                render_line_id="L20",
            ),
            ExhibitEvent(
                exhibit_number="1",
                exhibit_title="Photograph",
                render_line_id="L10",
            ),
        ],
    )


def _document():
    lines = [{"line_type": "colloquy", "speaker_label": "", "text": rl.text} for rl in _render_lines(10)]
    return render_export_document(
        lines,
        caption="Acme Corp. v. Heath Thomas",
        cause_number="2024-CI-09912",
        witness="Heath Thomas",
        proceedings_date="May 21, 2026",
    )


def test_export_validation_orchestrator_returns_single_pass_result():
    paginated = _paginated()
    indices, _ = generate_indices(_index_inputs(), paginated)
    preview = _document()
    exported = _document()

    result = validate_export_bundle(
        preview_document=preview,
        export_document=exported,
        paginated_document=paginated,
        metadata=_valid_metadata(),
        indices=indices,
    )

    assert result["ok"] is True
    assert result["errors"] == []
    assert result["checks"]["pagination_integrity"]["ok"] is True
    assert result["checks"]["index_resolution"]["ok"] is True
    assert result["checks"]["certification_readiness"]["ok"] is True
    assert result["checks"]["preview_export_consistency"]["ok"] is True


def test_export_validation_orchestrator_catches_broken_pagination():
    paginated = _paginated()
    paginated.pages[0].slots.pop()
    indices, _ = generate_indices(_index_inputs(), _paginated())

    result = validate_export_bundle(
        preview_document=_document(),
        export_document=_document(),
        paginated_document=paginated,
        metadata=_valid_metadata(),
        indices=indices,
    )

    assert result["ok"] is False
    assert any("Pagination integrity failed" in err for err in result["errors"])
    assert result["checks"]["pagination_integrity"]["ok"] is False
