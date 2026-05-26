"""Certification-time mutation detection built on top of diagnostics."""
from __future__ import annotations

from pathlib import Path

from backend.diagnostics.diff_harness import compare_layers
from backend.transcript import packet as packet_mod
from backend.transcript import repository as trepo


def _load_raw_utterances(job_id: str) -> list[dict]:
    job = trepo.get_job(job_id) or {}
    raw_packet_path = job.get("raw_packet_path")
    if raw_packet_path and Path(raw_packet_path).exists():
        packet = packet_mod.read_packet(raw_packet_path)
        return [
            {
                "utterance_id": u.get("utterance_id"),
                "utterance_index": u.get("utterance_index"),
                "speaker_index": u.get("speaker_index"),
                "speaker_label": u.get("speaker_label"),
                "start_time": u.get("start_time"),
                "end_time": u.get("end_time"),
                "text": u.get("text") or "",
            }
            for u in packet.get("utterances") or []
        ]
    return trepo.get_utterances(job_id, layer="raw")


def _snapshot_working_utterances(snapshot_state: dict) -> list[dict]:
    out = []
    for item in snapshot_state.get("working_utterances") or []:
        out.append(
            {
                "utterance_id": item.get("utterance_id"),
                "utterance_index": item.get("utterance_index"),
                "speaker_index": item.get("speaker_index"),
                "speaker_label": item.get("speaker_label"),
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
                "text": item.get("text") or item.get("raw_text") or "",
                "raw_text": item.get("raw_text") or "",
                "working_source": item.get("working_source") or "",
                "is_working_override": bool(item.get("is_working_override")),
            }
        )
    return out


def _snapshot_change_log(snapshot_state: dict) -> list[dict]:
    entries = []
    for item in snapshot_state.get("working_utterances") or []:
        source = (item.get("working_source") or "").strip()
        before = item.get("raw_text") or ""
        after = item.get("text") or item.get("raw_text") or ""
        if not source or before == after:
            continue
        entries.append(
            {
                "rule_id": source if ":" in source else f"WORKING:{source}",
                "stage": "working_snapshot",
                "utterance_id": item.get("utterance_id") or "",
                "before": before,
                "after": after,
            }
        )
    return entries


def build_mutation_report(job_id: str, *, snapshot_state: dict, snapshot_id: str = "") -> dict:
    raw = _load_raw_utterances(job_id)
    working = _snapshot_working_utterances(snapshot_state)
    change_log = _snapshot_change_log(snapshot_state)
    diff = compare_layers(
        raw,
        working,
        change_log=change_log,
        left_label="raw",
        right_label="working_snapshot",
        job_id=job_id,
        pipeline_snapshot={"snapshot_id": snapshot_id},
    )

    warnings: list[str] = []
    errors: list[str] = []
    explained_changes = [item for item in diff["per_utterance"] if item.get("explained")]
    unexplained_changes = [item for item in diff["per_utterance"] if not item.get("explained")]

    if explained_changes:
        warnings.append(
            f"{len(explained_changes)} transcript mutation(s) were attributable to logged working-layer sources."
        )
    if diff["metrics"]["net_word_delta"] != 0:
        errors.append(
            f"Net word delta is {diff['metrics']['net_word_delta']} — words changed outside logged corrections."
        )
    for item in unexplained_changes:
        errors.append(
            f"Unexplained {', '.join(item.get('change_types') or ['change'])} at "
            f"{item.get('utterance_id') or '(unmatched)'}."
        )

    return {
        "job_id": job_id,
        "snapshot_id": snapshot_id,
        "blocking": bool(errors),
        "warnings": warnings,
        "errors": errors,
        "diff": diff,
    }
