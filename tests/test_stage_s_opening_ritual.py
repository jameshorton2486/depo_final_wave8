"""Stage 3 opening-ritual + QA-01 trigger gate tests.

New tests for the opening-ritual build pass (EXAMINATION header, BY-line,
inline re-attribution). Kept in a dedicated file so the pass adds tests
without editing the existing stage_s renderer test suite.
"""
from __future__ import annotations

from backend.stage_s import models
from backend.stage_s.line_builder import examination_header_line


# --- Phase 1: LINE_EXAMINATION constant -----------------------------------

def test_line_examination_constant_exists():
    assert hasattr(models, "LINE_EXAMINATION")
    assert models.LINE_EXAMINATION == "examination"


# --- Phase 2: examination_header_line factory ------------------------------

def test_examination_header_line_shape():
    ln = examination_header_line("s-0001")
    assert ln.line_type == models.LINE_EXAMINATION
    assert ln.text == "EXAMINATION"
    assert ln.procedural is True
    assert ln.source_utterance_ids == []
    assert ln.line_id == "s-0001"
