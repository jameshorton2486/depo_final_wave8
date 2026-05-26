"""Hardening tests for the transcript diagnostics layer.

The diff engine is what mutation detection depends on, yet the existing
``tests/diagnostics/`` files cover only alignment, metric arithmetic, and a
pair of determinism checks. This suite hardens the parts with real branching
logic and no current coverage:

* ``diff_harness.run_diff`` — the job-not-found guard, the raw→working-only
  layer guard, the raw-layer load fallbacks (packet file vs DB), and
  change-log attribution from working overrides;
* ``diff_harness.write_job_artifacts`` — that all four artifacts are written,
  including to the default ``data/diff/{job_id}/`` root;
* ``report.render_report`` — the ``!`` (unexplained) vs ``~`` (explained)
  marker logic and the metrics block, including an empty diff;
* ``ref_import.normalize_reference_text`` — currently zero coverage.

DB-backed tests build jobs directly through the repository under the
``temp_db`` fixture; the ``report`` and ``ref_import`` tests are pure.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.diagnostics.diff_harness import (
    compare_layers,
    run_diff,
    write_job_artifacts,
)
from backend.diagnostics.ref_import import normalize_reference_text
from backend.diagnostics.report import render_report
from backend.transcript import repository as trepo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UTTERANCES = [
    (0, 0, "Speaker 0", "Please state your name for the record."),
    (1, 1, "Speaker 1", "My name is Dana Reed."),
    (2, 0, "Speaker 0", "And where do you currently reside?"),
]


def _make_job(temp_db) -> str:
    """Create a job with a confirmed raw transcript layer; return its job_id."""
    job = trepo.create_job({"source_filename": "fixture.mp3"})
    job_id = job["job_id"]
    speakers = [
        {"speaker_row_id": "spk-0", "speaker_index": 0, "speaker_label": "Speaker 0",
         "assigned_name": "Mr. Vance", "speaker_role": "examining_attorney", "word_count": 13},
        {"speaker_row_id": "spk-1", "speaker_index": 1, "speaker_label": "Speaker 1",
         "assigned_name": "Dana Reed", "speaker_role": "witness", "word_count": 5},
    ]
    utterances = [
        {"utterance_id": f"utt-{i}", "utterance_index": i, "speaker_index": spk,
         "speaker_label": label, "start_time": float(i * 5), "end_time": float(i * 5 + 4),
         "text": text, "avg_confidence": 0.99}
        for (i, spk, label, text) in _UTTERANCES
    ]
    trepo.save_transcript_content(job_id, speakers, utterances, words=[])
    return job_id


def _diff_with_one_explained_one_unexplained() -> dict:
    """A pure compare_layers diff: utt-1 explained by a rule, utt-2 not."""
    left = [
        {"utterance_id": "utt-1", "speaker_index": 0, "text": "the witness arrived"},
        {"utterance_id": "utt-2", "speaker_index": 1, "text": "at two o'clock"},
    ]
    right = [
        {"utterance_id": "utt-1", "speaker_index": 0, "text": "the witness had arrived"},
        {"utterance_id": "utt-2", "speaker_index": 1, "text": "at three o'clock"},
    ]
    change_log = [
        {"utterance_id": "utt-1", "rule_id": "WORKING:edit",
         "before": "the witness arrived", "after": "the witness had arrived"},
    ]
    return compare_layers(left, right, change_log=change_log, job_id="job-pure")


# ---------------------------------------------------------------------------
# run_diff — guards
# ---------------------------------------------------------------------------

def test_run_diff_raises_for_unknown_job(temp_db):
    """A job_id with no matching record is a hard error, not a silent empty diff."""
    with pytest.raises(ValueError):
        run_diff("no-such-job-id")


def test_run_diff_rejects_unsupported_layer_pair(temp_db):
    """The harness currently supports only raw -> working; anything else raises."""
    job_id = _make_job(temp_db)
    with pytest.raises(ValueError):
        run_diff(job_id, left_layer="working", right_layer="corrected")


# ---------------------------------------------------------------------------
# run_diff — raw-layer load fallback
# ---------------------------------------------------------------------------

def test_run_diff_falls_back_to_db_raw_layer(temp_db):
    """With no raw packet file on the job, run_diff loads raw from the DB layer.

    The job is created via save_transcript_content only — raw_packet_path is
    never set — so the harness must use the DB raw layer rather than failing.
    """
    job_id = _make_job(temp_db)
    diff = run_diff(job_id)
    # All three raw utterances were loaded from the DB.
    assert diff["metrics"]["left_utterance_count"] == 3
    assert diff["left_label"] == "raw"
    assert diff["right_label"] == "working"


def test_run_diff_clean_job_reports_no_changes(temp_db):
    """A job with no working overrides diffs raw against an identical working layer."""
    job_id = _make_job(temp_db)
    diff = run_diff(job_id)
    assert diff["metrics"]["changed_utterances"] == 0
    assert diff["metrics"]["net_word_delta"] == 0
    assert diff["per_utterance"] == []


# ---------------------------------------------------------------------------
# run_diff — change-log attribution from working overrides
# ---------------------------------------------------------------------------

def test_run_diff_attributes_sourced_override_as_explained(temp_db):
    """A working override carrying a source is reported as an explained change."""
    job_id = _make_job(temp_db)
    trepo.save_working_utterance_overrides(
        job_id,
        [{"utterance_id": "utt-2", "working_text": "And where do you reside?"}],
        source="REGEX:TEST-01",
    )
    diff = run_diff(job_id)

    changed = [u for u in diff["per_utterance"] if u["utterance_id"] == "utt-2"]
    assert len(changed) == 1
    assert changed[0]["explained"] is True
    assert changed[0]["rule_ids"]                       # a rule is attributed
    assert diff["metrics"]["unexplained_changes"] == 0


def test_run_diff_is_deterministic_across_runs(temp_db):
    """The same job diffs identically every time — required of a regression tool."""
    job_id = _make_job(temp_db)
    trepo.save_working_utterance_overrides(
        job_id,
        [{"utterance_id": "utt-1", "working_text": "My name is Dana M. Reed."}],
        source="REGEX:TEST-02",
    )
    first = run_diff(job_id)
    second = run_diff(job_id)
    assert first["metrics"] == second["metrics"]
    assert first["per_utterance"] == second["per_utterance"]


# ---------------------------------------------------------------------------
# write_job_artifacts
# ---------------------------------------------------------------------------

def test_write_job_artifacts_writes_all_four_files(temp_db, tmp_path):
    """The harness emits report, metrics, correction-log, and pipeline-snapshot."""
    job_id = _make_job(temp_db)
    out = write_job_artifacts(job_id, output_root=tmp_path / "diff_out")
    paths = out["paths"]
    for key in ("report_path", "metrics_path",
                "correction_log_path", "pipeline_snapshot_path"):
        assert Path(paths[key]).exists(), f"missing artifact: {key}"
    # The metrics artifact is valid JSON matching the diff metrics.
    written = json.loads(Path(paths["metrics_path"]).read_text(encoding="utf-8"))
    assert written == out["diff"]["metrics"]


def test_write_job_artifacts_uses_default_diff_root(temp_db):
    """With no output_root, artifacts land under data_root/diff/{job_id}/.

    The temp_db fixture points settings.data_root at the test tmp dir, so the
    default location resolves there.
    """
    job_id = _make_job(temp_db)
    out = write_job_artifacts(job_id)
    report_path = Path(out["paths"]["report_path"])
    assert report_path.name == "diff_report.txt"
    assert report_path.parent.name == job_id
    assert report_path.parent.parent.name == "diff"


# ---------------------------------------------------------------------------
# report.render_report
# ---------------------------------------------------------------------------

def test_render_report_marks_explained_and_unexplained_distinctly():
    """An unexplained change is marked '!'; an explained one is marked '~'.

    The '!' line is the defect signal the diff report exists to surface, so the
    two markers must never be confused.
    """
    report = render_report(_diff_with_one_explained_one_unexplained())
    assert "~ utt-1" in report          # explained by a logged rule
    assert "! utt-2" in report          # unexplained — the defect signal


def test_render_report_includes_every_metric_key():
    """The metrics block lists all fourteen metric keys for the reader."""
    report = render_report(_diff_with_one_explained_one_unexplained())
    for key in (
        "left_utterance_count", "right_utterance_count",
        "left_word_count", "right_word_count",
        "gross_word_delta", "logged_word_delta", "net_word_delta",
        "changed_utterances", "speaker_reassignments", "timestamp_drifts",
        "insertions", "deletions", "substitutions", "unexplained_changes",
    ):
        assert key in report


def test_render_report_handles_a_clean_diff():
    """A diff with no per-utterance changes still renders header and metrics."""
    clean = compare_layers(
        [{"utterance_id": "utt-1", "speaker_index": 0, "text": "identical"}],
        [{"utterance_id": "utt-1", "speaker_index": 0, "text": "identical"}],
        job_id="job-clean",
    )
    report = render_report(clean)
    assert "DEPO-PRO transcript diff" in report
    assert "Per-utterance diff:" in report
    assert "!" not in report            # nothing unexplained on a clean diff


# ---------------------------------------------------------------------------
# ref_import.normalize_reference_text
# ---------------------------------------------------------------------------

def test_normalize_reference_text_ids_lines_and_skips_blanks():
    """Each non-blank line becomes a canonical REF utterance; blank lines drop out."""
    text = "First line.\n\n   \nSecond line.\nThird line."
    utterances = normalize_reference_text(text)

    assert [u["text"] for u in utterances] == [
        "First line.", "Second line.", "Third line."]
    assert [u["utterance_id"] for u in utterances] == ["ref-0", "ref-1", "ref-2"]
    assert all(u["speaker_label"] == "REFERENCE" for u in utterances)


def test_normalize_reference_text_empty_input_returns_empty_list():
    """Empty or whitespace-only reference text yields no utterances, not an error."""
    assert normalize_reference_text("") == []
    assert normalize_reference_text("   \n  \n") == []
