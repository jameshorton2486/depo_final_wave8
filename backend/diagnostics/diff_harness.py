"""Transcript diff harness orchestrator."""
from __future__ import annotations

import json
from pathlib import Path

from backend.config import settings
from backend.diagnostics.align import align_utterances
from backend.diagnostics.metrics import build_change_log_index, summarize_metrics
from backend.diagnostics.report import write_artifacts
from backend.transcript import packet as packet_mod
from backend.transcript import repository as trepo


def _load_raw_layer(job_id: str, job: dict) -> list[dict]:
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


def _load_working_layer(job_id: str, job: dict) -> list[dict]:
    working = trepo.get_utterances(job_id, layer="working")
    if working:
        return working
    working_packet_path = job.get("working_packet_path")
    if working_packet_path and Path(working_packet_path).exists():
        packet = packet_mod.read_packet(working_packet_path)
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
    return []


def _working_change_log(job_id: str) -> list[dict]:
    raw_map = {
        item["utterance_id"]: item
        for item in trepo.get_utterances(job_id, layer="raw")
    }
    log = []
    for override in trepo.get_working_utterance_overrides(job_id):
        utterance_id = override.get("utterance_id") or ""
        source = (override.get("source") or "").strip()
        before = (raw_map.get(utterance_id) or {}).get("text") or ""
        after = override.get("working_text") or ""
        if not source:
            continue
        log.append(
            {
                "rule_id": source if ":" in source else f"WORKING:{source}",
                "stage": "working",
                "utterance_id": utterance_id,
                "before": before,
                "after": after,
            }
        )
    return log


def _pipeline_snapshot(job: dict) -> dict:
    return {
        "job_id": job.get("job_id"),
        "transcription_source": job.get("transcription_source"),
        "engine": job.get("engine"),
        "raw_packet_path": job.get("raw_packet_path") or "",
        "working_packet_path": job.get("working_packet_path") or "",
    }


def compare_layers(
    left: list[dict],
    right: list[dict],
    *,
    change_log: list[dict] | None = None,
    left_label: str = "raw",
    right_label: str = "working",
    job_id: str = "",
    timestamp_tolerance: float = 0.05,
    pipeline_snapshot: dict | None = None,
) -> dict:
    change_log = change_log or []
    change_log_index = build_change_log_index(change_log)
    per_utterance: list[dict] = []

    for left_item, right_item in align_utterances(left, right):
        utterance_id = (
            (right_item or {}).get("utterance_id")
            or (left_item or {}).get("utterance_id")
            or ""
        )
        left_text = (left_item or {}).get("text") or ""
        right_text = (right_item or {}).get("text") or ""
        change_types: list[str] = []

        if left_item is None:
            change_types.append("insertion")
        elif right_item is None:
            change_types.append("deletion")
        elif left_text != right_text:
            change_types.append("substitution")

        if left_item and right_item:
            if left_item.get("speaker_index") != right_item.get("speaker_index"):
                change_types.append("speaker_reassignment")
            start_drift = abs(float((left_item.get("start_time") or 0.0)) - float((right_item.get("start_time") or 0.0)))
            end_drift = abs(float((left_item.get("end_time") or 0.0)) - float((right_item.get("end_time") or 0.0)))
            if start_drift > timestamp_tolerance or end_drift > timestamp_tolerance:
                change_types.append("timestamp_drift")

        if not change_types:
            continue

        rules = [entry.get("rule_id") or "" for entry in change_log_index.get(utterance_id, []) if entry.get("rule_id")]
        per_utterance.append(
            {
                "utterance_id": utterance_id,
                "left_text": left_text,
                "right_text": right_text,
                "left_speaker_index": (left_item or {}).get("speaker_index"),
                "right_speaker_index": (right_item or {}).get("speaker_index"),
                "change_types": change_types,
                "rule_ids": rules,
                "explained": bool(rules),
            }
        )

    metrics = summarize_metrics(left, right, change_log, per_utterance)
    return {
        "job_id": job_id,
        "left_label": left_label,
        "right_label": right_label,
        "metrics": metrics,
        "per_utterance": per_utterance,
        "change_log": change_log,
        "pipeline_snapshot": pipeline_snapshot or {},
    }


def run_diff(job_id: str, *, left_layer: str = "raw", right_layer: str = "working") -> dict:
    job = trepo.get_job(job_id)
    if job is None:
        raise ValueError(f"Transcript job {job_id} not found")
    if left_layer != "raw" or right_layer != "working":
        raise ValueError("This initial harness implementation currently supports raw -> working only.")
    left = _load_raw_layer(job_id, job)
    right = _load_working_layer(job_id, job)
    change_log = _working_change_log(job_id)
    return compare_layers(
        left,
        right,
        change_log=change_log,
        left_label=left_layer,
        right_label=right_layer,
        job_id=job_id,
        pipeline_snapshot=_pipeline_snapshot(job),
    )


def write_job_artifacts(job_id: str, *, output_root: str | Path | None = None) -> dict:
    diff = run_diff(job_id)
    root = Path(output_root) if output_root else (settings.data_root / "diff" / job_id)
    paths = write_artifacts(diff, root)
    return {"diff": diff, "paths": paths}
