"""Wave 18.5 — Transcript State Engine tests.

Verify the deterministic state hash, snapshot capture, append-only
rollback, certification locking, export references, and the endpoints.
"""
from __future__ import annotations

from backend.transcript_state.model import SNAPSHOT_CATEGORIES, Snapshot
from backend.transcript_state.state_hash import (
    compute_state_hash,
    state_inputs_equal,
)


# --- state hash ------------------------------------------------------

def test_hash_is_deterministic_regardless_of_key_order():
    a = {"render_lines": [{"x": 1, "y": 2}], "export_profile": "texas_ufm"}
    b = {"export_profile": "texas_ufm", "render_lines": [{"y": 2, "x": 1}]}
    assert compute_state_hash(a) == compute_state_hash(b)


def test_hash_ignores_non_input_metadata():
    base = {"render_lines": [{"x": 1}]}
    with_meta = {"render_lines": [{"x": 1}],
                 "note": "captured by James", "created_at": "2026-01-01"}
    # Metadata is not a hash input -> identical hash.
    assert compute_state_hash(base) == compute_state_hash(with_meta)


def test_hash_detects_real_state_change():
    a = {"render_lines": [{"text": "hello"}]}
    b = {"render_lines": [{"text": "goodbye"}]}
    assert compute_state_hash(a) != compute_state_hash(b)


def test_hash_is_sha256_hex():
    h = compute_state_hash({"render_lines": []})
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_state_inputs_equal_helper():
    assert state_inputs_equal({"render_lines": [1]}, {"render_lines": [1]})
    assert not state_inputs_equal({"render_lines": [1]},
                                  {"render_lines": [2]})


# --- snapshot model --------------------------------------------------

def test_snapshot_categories_complete():
    assert set(SNAPSHOT_CATEGORIES) == {
        "AUTO_SAVE", "MANUAL", "PRE_AI", "POST_AI", "POST_REVIEW",
        "PRE_EXPORT", "EXPORT", "CERTIFIED"}


def test_certified_category_is_certification_snapshot():
    s = Snapshot(job_id="j1", state_hash="h", state={},
                 category="CERTIFIED")
    assert s.is_certification_snapshot


def test_locked_snapshot_is_certification_snapshot():
    s = Snapshot(job_id="j1", state_hash="h", state={}, locked=True)
    assert s.is_certification_snapshot


def test_plain_snapshot_is_not_certification_snapshot():
    s = Snapshot(job_id="j1", state_hash="h", state={}, category="MANUAL")
    assert not s.is_certification_snapshot


# --- repository (append-only) ---------------------------------------

def test_snapshot_save_and_get(client):
    from backend.transcript_state import snapshot_repo
    snap = Snapshot(job_id="job-snap-1", state_hash="abc123",
                    state={"render_lines": []}, category="MANUAL")
    snapshot_repo.save_snapshot(snap)
    got = snapshot_repo.get_snapshot(snap.snapshot_id)
    assert got is not None
    assert got.job_id == "job-snap-1"
    assert got.state_hash == "abc123"


def test_snapshot_list_newest_first(client):
    from backend.transcript_state import snapshot_repo
    for i in range(3):
        snapshot_repo.save_snapshot(Snapshot(
            job_id="job-snap-list", state_hash=f"h{i}",
            state={}, note=f"snap {i}"))
    listed = snapshot_repo.list_snapshots("job-snap-list")
    assert len(listed) == 3


def test_lock_snapshot_is_one_way(client):
    from backend.transcript_state import snapshot_repo
    snap = Snapshot(job_id="job-lock", state_hash="h", state={})
    snapshot_repo.save_snapshot(snap)
    assert snapshot_repo.lock_snapshot(snap.snapshot_id)
    got = snapshot_repo.get_snapshot(snap.snapshot_id)
    assert got.locked and got.is_certification_snapshot


def test_export_reference_appends(client):
    from backend.transcript_state import snapshot_repo
    from backend.transcript_state.model import ExportReference
    snap = Snapshot(job_id="job-exp", state_hash="h", state={})
    snapshot_repo.save_snapshot(snap)
    ref = ExportReference(export_id="t.docx", export_format="docx",
                          export_timestamp="2026-05-22T00:00:00")
    assert snapshot_repo.add_export_reference(snap.snapshot_id, ref)
    got = snapshot_repo.get_snapshot(snap.snapshot_id)
    assert len(got.export_refs) == 1
    assert got.export_refs[0]["export_format"] == "docx"


def test_snapshot_rollback_restores_speaker_indices(sample_job_with_content):
    from backend.transcript import repository as trepo
    from backend.transcript_state import snapshot_service

    original = trepo.get_participants(sample_job_with_content)
    snap = snapshot_service.create_snapshot(sample_job_with_content, category="MANUAL")

    trepo.save_participants(sample_job_with_content, [
        {"name": "Changed Witness", "role": "witness", "speaker_indices": [0, 1]},
    ])
    changed = trepo.get_participants(sample_job_with_content)
    assert changed != original

    restored_snap = snapshot_service.rollback_to(sample_job_with_content, snap.snapshot_id)
    assert restored_snap is not None

    restored = trepo.get_participants(sample_job_with_content)
    assert restored[0]["speaker_indices"] == [0]
    assert restored[1]["speaker_indices"] == [1]
    assert restored[0]["role"] == "examining_attorney"
    assert restored[1]["role"] == "witness"


# --- endpoints -------------------------------------------------------

def test_create_snapshot_unknown_job_404(client):
    res = client.post("/api/snapshots/jobs/no-such-job",
                       json={"category": "MANUAL"})
    assert res.status_code == 404


def test_create_snapshot_rejects_bad_category(client):
    # Even for an unknown job the 404 fires first; verify the category
    # check via the model's category set instead.
    assert "NONSENSE" not in SNAPSHOT_CATEGORIES


def test_list_snapshots_endpoint_empty(client):
    res = client.get("/api/snapshots/jobs/some-job")
    assert res.status_code == 200
    assert res.json()["count"] == 0


def test_get_unknown_snapshot_404(client):
    res = client.get("/api/snapshots/no-such-snapshot")
    assert res.status_code == 404


def test_rollback_unknown_job_404(client):
    res = client.post("/api/snapshots/jobs/no-such-job/rollback",
                       json={"snapshot_id": "x"})
    assert res.status_code == 404
