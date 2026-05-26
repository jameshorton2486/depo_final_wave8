"""Edge-case hardening tests for ``backend/transcript/mutation_detection.py``.

The existing ``tests/test_mutation_detection.py`` proves the two headline cases
through the API: a silent word deletion blocks certification, and a logged
working-layer correction does not. This suite hardens ``build_mutation_report``
directly, at the unit level, against the cases that file does not reach:

* a clean snapshot with no working changes — not blocking, no noise;
* every individual mutation *type* the gate must catch — substitution,
  whole-utterance deletion, and an unlogged speaker reassignment;
* the boundary between an explained change (warning only) and an unexplained
  one (blocking);
* the ``net_word_delta`` rule — words lost outside the logged corrections;
* determinism — the same inputs always produce an identical report.

These tests build jobs directly via the repository under the ``temp_db``
fixture, so they exercise the real raw-layer load path without depending on the
FastAPI ``client`` fixture.
"""
from __future__ import annotations

import pytest

from backend.transcript import repository as trepo
from backend.transcript.mutation_detection import build_mutation_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXCHANGE = [
    (0, 0, "Speaker 0", "Please state your name for the record."),
    (1, 1, "Speaker 1", "My name is Dana Reed."),
    (2, 0, "Speaker 0", "And where do you currently reside?"),
    (3, 1, "Speaker 1", "I live in San Antonio, Texas."),
]


def _make_job(temp_db) -> str:
    """Create a job with a confirmed raw transcript layer; return its job_id."""
    job = trepo.create_job({"source_filename": "depo_session.mp3"})
    job_id = job["job_id"]
    speakers = [
        {"speaker_row_id": "spk-0", "speaker_index": 0, "speaker_label": "Speaker 0",
         "assigned_name": "Mr. Vance", "speaker_role": "examining_attorney", "word_count": 14},
        {"speaker_row_id": "spk-1", "speaker_index": 1, "speaker_label": "Speaker 1",
         "assigned_name": "Dana Reed", "speaker_role": "witness", "word_count": 11},
    ]
    utterances = [
        {"utterance_id": f"utt-{i}", "utterance_index": i, "speaker_index": spk,
         "speaker_label": label, "start_time": float(i * 5), "end_time": float(i * 5 + 4),
         "text": text, "avg_confidence": 0.99}
        for (i, spk, label, text) in _EXCHANGE
    ]
    trepo.save_transcript_content(job_id, speakers, utterances, words=[])
    return job_id


def _mirror_working(job_id: str) -> list[dict]:
    """Build a working-layer snapshot that exactly mirrors the raw layer.

    Each test then mutates one entry of the returned list to model a specific
    kind of change before handing it to ``build_mutation_report``.
    """
    working = []
    for u in trepo.get_utterances(job_id, layer="raw"):
        text = u.get("text") or ""
        working.append({
            "utterance_id": u.get("utterance_id"),
            "utterance_index": u.get("utterance_index"),
            "speaker_index": u.get("speaker_index"),
            "speaker_label": u.get("speaker_label"),
            "start_time": u.get("start_time"),
            "end_time": u.get("end_time"),
            "text": text,
            "raw_text": text,
            "working_source": "",
            "is_working_override": False,
        })
    return working


def _report(job_id: str, working: list[dict], snapshot_id: str = "snap-1") -> dict:
    return build_mutation_report(
        job_id,
        snapshot_state={"working_utterances": working},
        snapshot_id=snapshot_id,
    )


# ---------------------------------------------------------------------------
# Clean baseline
# ---------------------------------------------------------------------------

def test_unchanged_working_layer_does_not_block(temp_db):
    """A working layer identical to raw produces a clean, non-blocking report."""
    job_id = _make_job(temp_db)
    report = _report(job_id, _mirror_working(job_id))

    assert report["blocking"] is False
    assert report["errors"] == []
    assert report["warnings"] == []
    assert report["diff"]["metrics"]["net_word_delta"] == 0
    assert report["diff"]["metrics"]["changed_utterances"] == 0


# ---------------------------------------------------------------------------
# Explained vs unexplained — the core boundary
# ---------------------------------------------------------------------------

def test_logged_edit_warns_but_does_not_block(temp_db):
    """An edit attributed to a working-layer source is a warning, not a block.

    The change carries a ``working_source``, so it is *explained*; the word
    count it changes is fully accounted for by the logged correction, so
    ``net_word_delta`` stays 0.
    """
    job_id = _make_job(temp_db)
    working = _mirror_working(job_id)
    working[2]["text"] = "And where do you reside?"          # dropped "currently"
    working[2]["working_source"] = "WORKSPACE:manual_edit"
    working[2]["is_working_override"] = True

    report = _report(job_id, working)

    assert report["blocking"] is False
    assert report["errors"] == []
    assert len(report["warnings"]) == 1
    assert report["diff"]["metrics"]["net_word_delta"] == 0


def test_unexplained_substitution_blocks_certification(temp_db):
    """An edit with no working-layer source is unexplained and blocks certifying."""
    job_id = _make_job(temp_db)
    working = _mirror_working(job_id)
    working[3]["text"] = "I live in Austin, Texas."          # changed, no source
    # working_source deliberately left blank

    report = _report(job_id, working)

    assert report["blocking"] is True
    assert any("Unexplained" in err for err in report["errors"])


# ---------------------------------------------------------------------------
# Mutation types the gate must catch
# ---------------------------------------------------------------------------

def test_silent_word_deletion_drives_net_word_delta_nonzero(temp_db):
    """A dropped word with no logged correction trips the net-word-delta rule."""
    job_id = _make_job(temp_db)
    working = _mirror_working(job_id)
    working[1]["text"] = "My name Dana Reed."                # dropped "is"

    report = _report(job_id, working)

    assert report["blocking"] is True
    assert report["diff"]["metrics"]["net_word_delta"] == -1
    assert any("Net word delta" in err for err in report["errors"])


def test_whole_utterance_deletion_is_detected(temp_db):
    """Dropping an entire utterance from the working layer is caught as a deletion."""
    job_id = _make_job(temp_db)
    working = [u for u in _mirror_working(job_id) if u["utterance_id"] != "utt-2"]

    report = _report(job_id, working)

    assert report["blocking"] is True
    assert report["diff"]["metrics"]["deletions"] == 1


def test_unlogged_speaker_reassignment_blocks_certification(temp_db):
    """Reassigning a speaker with no logged source is an unexplained mutation.

    Misattributed testimony is one of the most consequential transcript
    defects, so an unlogged speaker change must block certification even when
    no word of text changed.
    """
    job_id = _make_job(temp_db)
    working = _mirror_working(job_id)
    working[3]["speaker_index"] = 0                          # witness line -> attorney
    # text unchanged, working_source blank

    report = _report(job_id, working)

    assert report["blocking"] is True
    assert report["diff"]["metrics"]["speaker_reassignments"] == 1
    assert any("speaker_reassignment" in err for err in report["errors"])


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_mutation_report_is_deterministic(temp_db):
    """The same job and snapshot state always produce an identical report.

    Determinism is what makes the gate trustworthy as a certification blocker:
    a transcript cannot pass on one run and fail on the next.
    """
    job_id = _make_job(temp_db)
    working = _mirror_working(job_id)
    working[1]["text"] = "My name Dana Reed."                # an unexplained change

    first = _report(job_id, working)
    second = _report(job_id, working)

    assert first == second
