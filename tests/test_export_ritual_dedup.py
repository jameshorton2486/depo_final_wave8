"""Integration tests across render_stage_s -> export_render for all three
export paths (preview, snapshot export document, certified package body).

These tests are the safeguard that was missing when the opening-ritual
duplication reached main: nothing exercised the full structural-render ->
export path, so the duplicate EXAMINATION header and the unconditional
"(... duly sworn)" line went undetected.

Invariant for every path after the ritual-dedup pass:
  * exactly one EXAMINATION header,
  * exactly one BY-line with a single trailing colon (no "BY ...::"),
  * no "sworn" line anywhere (the witness-sworn line is deferred to the
    gated witness-sworn pass).
"""
from __future__ import annotations

from backend.api.transcripts import _build_export_document_from_snapshot
from backend.api.packaging import _build_paginated_and_index_inputs_from_snapshot_state


# --- shared inputs ---------------------------------------------------------

def _snapshot_state():
    return {
        "working_utterances": [
            {"utterance_id": "u1", "utterance_index": 0, "speaker_index": 1,
             "speaker_label": "Speaker 1", "start_time": 0.0, "end_time": 1.0,
             "text": "Please state your full name for the record."},
            {"utterance_id": "u2", "utterance_index": 1, "speaker_index": 2,
             "speaker_label": "Speaker 2", "start_time": 1.0, "end_time": 2.0,
             "text": "David Shaw."},
        ],
        "speaker_mapping": [
            {"participant_id": "p1", "name": "Coleman", "role": "examining_attorney",
             "honorific": "MR", "speaker_indices": "[1]", "name_source": None},
            {"participant_id": "p2", "name": "David Shaw", "role": "witness",
             "honorific": "MR", "speaker_indices": "[2]", "name_source": None},
        ],
        # Front-matter metadata: present so the test proves the export no
        # longer turns these into a duplicate ritual / sworn line.
        "export_metadata": {
            "caption": "SMITH vs. JONES",
            "cause_number": "2024-CV-1",
            "witness_name": "David Shaw",
            "proceedings_date": "May 19, 2026",
            "examining_attorney_label": "MR. COLEMAN",
        },
        "regex_rule_state": [],
        "lexicon_state": {},
        "exhibits": [],
    }


# --- text extractors -------------------------------------------------------

def _export_doc_texts(doc) -> list[str]:
    return [ln.text for p in doc.pages for ln in p.lines]


def _paginated_texts(paginated) -> list[str]:
    out: list[str] = []
    for page in paginated.pages:
        for slot in page.slots:
            if not slot.is_empty:
                out.append(slot.physical_line.text)
    return out


def _all_text_fields(obj) -> list[str]:
    """Collect every 'text' string from a nested JSON structure."""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "text" and isinstance(v, str):
                out.append(v)
            else:
                out.extend(_all_text_fields(v))
    elif isinstance(obj, list):
        for x in obj:
            out.extend(_all_text_fields(x))
    return out


# --- shared invariant ------------------------------------------------------

def _assert_single_clean_ritual(texts: list[str]) -> None:
    stripped = [t.strip() for t in texts]
    exam = [t for t in stripped if t == "EXAMINATION"]
    assert len(exam) == 1, f"expected exactly one EXAMINATION header, got {exam}"
    by = [t for t in stripped
          if t.startswith("BY ") and t.endswith(":") and not t.endswith("::")]
    assert len(by) == 1, f"expected exactly one clean BY-line, got {by}"
    assert not any("::" in t for t in stripped), \
        f"malformed double-colon present: {[t for t in stripped if '::' in t]}"
    assert not any("sworn" in t.lower() for t in stripped), \
        f"sworn line present: {[t for t in stripped if 'sworn' in t.lower()]}"


# --- the three paths -------------------------------------------------------

def test_snapshot_export_document_single_clean_ritual():
    # Path that passes front matter (witness + examining_attorney_label).
    doc, _ = _build_export_document_from_snapshot(_snapshot_state())
    _assert_single_clean_ritual(_export_doc_texts(doc))


def test_certified_package_body_single_clean_ritual():
    # Path that passes NO front matter -- relies entirely on the stage_s
    # ritual rendered in the body. Pre-dedup this rendered as malformed
    # colloquy ("BY MR. COLEMAN::"); now it is a clean header.
    paginated, _ = _build_paginated_and_index_inputs_from_snapshot_state(_snapshot_state())
    _assert_single_clean_ritual(_paginated_texts(paginated))


def test_export_preview_endpoint_single_clean_ritual(client, sample_job_with_content):
    # Live preview path through the real endpoint and builders.
    res = client.get(f"/api/transcripts/jobs/{sample_job_with_content}/export-preview")
    assert res.status_code == 200
    texts = _all_text_fields(res.json())
    _assert_single_clean_ritual(texts)
