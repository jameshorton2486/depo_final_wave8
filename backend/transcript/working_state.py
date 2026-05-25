"""Authoritative Stage 3 working transcript state.

RAW transcript rows and packets remain immutable. Reporter-reviewed text
is stored as utterance-level overrides and mirrored into the job's
working packet so Stage 3 reloads, snapshots, and export all read the
same authoritative working layer.
"""
from __future__ import annotations

from loguru import logger

from backend.transcript import packet as packet_mod
from backend.transcript import repository as trepo


def get_working_utterances(job_id: str) -> list[dict]:
    """Return the authoritative working utterances for a job."""
    return trepo.get_utterances(job_id, layer="working")


def persist_working_transcript(
    job_id: str,
    updates: list[dict],
    *,
    source: str = "stage3_workspace",
) -> dict:
    """Persist Stage 3 working transcript text and sync the working packet."""
    result = trepo.save_working_utterance_overrides(job_id, updates, source=source)
    packet_path = sync_working_packet(job_id)
    logger.info(
        f"Working transcript persisted for {job_id}: "
        f"{result['saved']} override(s) saved, {result['removed']} cleared, "
        f"{result['override_count']} active override(s)"
    )
    return {**result, "working_packet_path": packet_path}


def replace_working_transcript_from_snapshot(job_id: str, working_utterances: list[dict]) -> dict:
    """Restore a full working transcript state from snapshot data."""
    result = trepo.replace_working_utterance_overrides(
        job_id,
        working_utterances,
        source="snapshot_rollback",
    )
    packet_path = sync_working_packet(job_id)
    logger.info(
        f"Working transcript rollback restored for {job_id}: "
        f"{result['override_count']} active override(s)"
    )
    return {**result, "working_packet_path": packet_path}


def sync_working_packet(job_id: str) -> str | None:
    """Rewrite the job's working packet from the authoritative working layer."""
    job = trepo.get_job(job_id)
    if not job:
        return None
    packet_path = job.get("working_packet_path")
    if not packet_path:
        return None

    pkt = packet_mod.read_packet(packet_path)
    pkt["generated_at"] = packet_mod._utc_now()  # packet timestamp for lineage
    pkt["layer"] = "working"

    working_utterances = get_working_utterances(job_id)
    override_map = trepo.get_working_utterance_map(job_id)

    out_utterances = []
    for utt in working_utterances:
        copied = dict(utt)
        copied.pop("raw_text", None)
        copied.pop("working_text", None)
        copied.pop("is_working_override", None)
        out_utterances.append(copied)
    pkt["utterances"] = out_utterances
    pkt["working_overrides"] = [
        {
            "utterance_id": row["utterance_id"],
            "working_text": row["working_text"],
            "source": row.get("source") or "",
            "updated_at": row.get("updated_at") or "",
        }
        for row in override_map.values()
    ]

    packet_mod.write_packet(pkt, packet_path)
    return str(packet_path)
