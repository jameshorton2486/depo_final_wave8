"""Raw transcript integrity helpers.

The raw transcript packet is immutable once captured. Its integrity is
anchored by a deterministic SHA-256 over the packet's canonical JSON
representation and stored in a durable sidecar file adjacent to
`raw.json`.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


HASH_ALGORITHM = "sha256"


class RawTranscriptImmutableError(RuntimeError):
    """Raised on an attempt to rewrite the immutable RAW transcript layer."""


class RawTranscriptIntegrityError(RuntimeError):
    """Raised when a raw transcript packet fails integrity verification."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(payload: dict) -> bytes:
    """Stable canonical JSON encoding shared with transcript-state hashing."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")


def compute_packet_hash(payload: dict) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def integrity_sidecar_path(raw_packet_path: str | Path) -> Path:
    raw_packet_path = Path(raw_packet_path)
    return raw_packet_path.with_name(f"{raw_packet_path.stem}.integrity.json")


def write_raw_integrity_sidecar(
    raw_packet_path: str | Path,
    packet_payload: dict,
    *,
    captured_at: str | None = None,
) -> Path:
    sidecar_path = integrity_sidecar_path(raw_packet_path)
    sidecar = {
        "raw_packet_path": str(Path(raw_packet_path)),
        "algorithm": HASH_ALGORITHM,
        "hash": compute_packet_hash(packet_payload),
        "captured_at": captured_at or _utc_now(),
    }
    sidecar_path.write_text(
        json.dumps(sidecar, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return sidecar_path


def ensure_raw_integrity_metadata(raw_packet_path: str | Path) -> dict:
    """Return integrity metadata, backfilling the sidecar if missing."""
    raw_packet_path = Path(raw_packet_path)
    if not raw_packet_path.exists():
        raise RawTranscriptIntegrityError(
            f"Raw transcript packet missing: {raw_packet_path}"
        )
    sidecar_path = integrity_sidecar_path(raw_packet_path)
    if not sidecar_path.exists():
        packet_payload = json.loads(raw_packet_path.read_text(encoding="utf-8"))
        write_raw_integrity_sidecar(raw_packet_path, packet_payload)
    return json.loads(sidecar_path.read_text(encoding="utf-8"))


def write_immutable_raw_packet(packet_payload: dict, destination: str | Path) -> Path:
    """Write the RAW packet exactly once and persist its integrity sidecar."""
    destination = Path(destination)
    if destination.exists():
        raise RawTranscriptImmutableError(
            f"Raw transcript packet already exists and is immutable: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(packet_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_raw_integrity_sidecar(destination, packet_payload)
    return destination


def verify_raw_packet(raw_packet_path: str | Path) -> dict:
    """Re-hash raw.json and compare it to the stored integrity sidecar."""
    raw_packet_path = Path(raw_packet_path)
    if not raw_packet_path.exists():
        raise RawTranscriptIntegrityError(
            f"Raw transcript packet missing: {raw_packet_path}"
        )
    metadata = ensure_raw_integrity_metadata(raw_packet_path)
    if metadata.get("algorithm") != HASH_ALGORITHM:
        raise RawTranscriptIntegrityError(
            f"Unsupported raw transcript integrity algorithm: {metadata.get('algorithm')}"
        )
    packet_payload = json.loads(raw_packet_path.read_text(encoding="utf-8"))
    actual_hash = compute_packet_hash(packet_payload)
    expected_hash = metadata.get("hash") or ""
    if actual_hash != expected_hash:
        raise RawTranscriptIntegrityError(
            "Raw transcript integrity verification failed: stored hash does not "
            "match the current raw packet."
        )
    return {
        **metadata,
        "verified": True,
        "actual_hash": actual_hash,
        "integrity_path": str(integrity_sidecar_path(raw_packet_path)),
    }
