"""Lifecycle hardening: the durable deletion-log JSONL sidecar."""
from __future__ import annotations


def test_list_empty_when_no_file(temp_db):
    from backend.transcript import deletion_log
    assert deletion_log.list_deletion_events() == []


def test_append_creates_file_and_writes_one_record(temp_db):
    from backend.transcript import deletion_log
    ev = deletion_log.append_deletion_event(
        {"job_id": "j1", "case_id": "c1", "source_filename": "a.mp3",
         "word_count": 10, "utterance_count": 3})
    assert ev["event_id"] and ev["job_id"] == "j1"
    assert ev["metrics"]["word_count"] == 10
    events = deletion_log.list_deletion_events()
    assert len(events) == 1
    assert events[0]["job_id"] == "j1"
    assert events[0]["created_at"]


def test_multiple_appends_preserve_order_newest_first(temp_db):
    from backend.transcript import deletion_log
    for i in range(3):
        deletion_log.append_deletion_event({"job_id": f"j{i}"})
    events = deletion_log.list_deletion_events()
    assert [e["job_id"] for e in events] == ["j2", "j1", "j0"]


def test_force_reason_and_package_ids_recorded(temp_db):
    from backend.transcript import deletion_log
    ev = deletion_log.append_deletion_event(
        {"job_id": "j1"}, force=True, reason="operator override",
        package_ids=["pkg-a", "pkg-b"])
    assert ev["force"] is True
    assert ev["reason"] == "operator override"
    assert ev["package_ids"] == ["pkg-a", "pkg-b"]
