"""Package Manifest & Integrity — Wave 20.

The Package Manifest is a self-describing record of exactly what
produced a package: which snapshot, which engine versions, which
indices and exhibits. Its `manifest_hash` is the Package Integrity
anchor.

Determinism: the manifest_hash is computed over a CANONICAL subset that
*excludes* the timestamp, so re-assembling the same locked snapshot
yields an identical hash — the basis of Package Reproducibility. The
package_id is likewise derived deterministically from the snapshot id,
state hash, and package version.

Review items 2 (package identity), 4 (integrity verification),
8 (certificate binding).
"""
from __future__ import annotations

import hashlib
import json

from backend.packaging.model import (
    PACKAGING_ENGINE_VERSION,
    PackageIdentity,
    PackageManifest,
)


def _canonical(value) -> str:
    """Canonical JSON encoding — sorted keys, stable separators."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, default=str)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_package_id(snapshot_id: str, state_hash: str,
                      package_version: int) -> str:
    """Deterministically derive a package id.

    Re-assembling the same snapshot at the same version yields the same
    id — required for Package Reproducibility. A new package *version*
    (an amendment) deterministically yields a new id.
    """
    seed = f"{snapshot_id}|{state_hash}|v{package_version}"
    return f"pkg-{_sha256(seed)[:16]}"


def derive_certification_id(package_id: str, state_hash: str) -> str:
    """Deterministically derive a certification id for a package."""
    return f"cert-{_sha256(f'{package_id}|{state_hash}')[:16]}"


def build_identity(
    snapshot_id: str,
    state_hash: str,
    package_version: int = 1,
    export_id: str = "",
) -> PackageIdentity:
    """Build the deterministic PackageIdentity for a package."""
    package_id = derive_package_id(snapshot_id, state_hash, package_version)
    return PackageIdentity(
        package_id=package_id,
        transcript_snapshot_id=snapshot_id,
        state_hash=state_hash,
        package_version=package_version,
        certification_id=derive_certification_id(package_id, state_hash),
        export_id=export_id,
    )


def _manifest_hash_subset(manifest: PackageManifest) -> dict:
    """The deterministic subset of the manifest that the hash covers.

    Excludes `package_timestamp` (wall-clock, non-reproducible) and
    `manifest_hash` itself. Everything that defines *what the package
    is* participates; nothing that is merely *when it was made* does.
    """
    return {
        "identity": manifest.identity.to_dict(),
        "certification_state": manifest.certification_state,
        "included_exhibits": sorted(manifest.included_exhibits),
        "generated_indices": sorted(manifest.generated_indices),
        "template_versions": manifest.template_versions,
        "geometry_profile": manifest.geometry_profile,
        "packaging_engine_version": manifest.packaging_engine_version,
    }


def compute_manifest_hash(manifest: PackageManifest) -> str:
    """Compute the deterministic manifest hash (Package Integrity anchor)."""
    return _sha256(_canonical(_manifest_hash_subset(manifest)))


def build_manifest(
    identity: PackageIdentity,
    *,
    certification_state: str = "DRAFT",
    package_timestamp: str = "",
    included_exhibits: list[str] | None = None,
    generated_indices: list[str] | None = None,
    template_versions: dict[str, str] | None = None,
    geometry_profile: str = "texas_ufm",
) -> PackageManifest:
    """Build a PackageManifest and stamp its deterministic hash."""
    manifest = PackageManifest(
        identity=identity,
        certification_state=certification_state,
        package_timestamp=package_timestamp,
        included_exhibits=list(included_exhibits or []),
        generated_indices=list(generated_indices or []),
        template_versions=dict(template_versions or {}),
        geometry_profile=geometry_profile,
        packaging_engine_version=PACKAGING_ENGINE_VERSION,
    )
    manifest.manifest_hash = compute_manifest_hash(manifest)
    return manifest


# --- Package Integrity Verification (review item 4) -----------------

def verify_package_integrity(
    package,
    *,
    expected_snapshot_id: str | None = None,
    expected_state_hash: str | None = None,
) -> dict:
    """Verify a package is internally consistent and correctly bound.

    Checks:
      * the manifest hash recomputes to the stored value;
      * the manifest identity matches the package identity;
      * (optionally) the package is bound to the expected snapshot and
        transcript state hash.

    Returns {ok, checks, failures}. A failed check never raises — the
    caller decides how to surface a tamper/mismatch finding.
    """
    checks: dict[str, bool] = {}
    failures: list[str] = []
    manifest = package.manifest

    recomputed = compute_manifest_hash(manifest)
    checks["manifest_hash_intact"] = (recomputed == manifest.manifest_hash)
    if not checks["manifest_hash_intact"]:
        failures.append("Manifest hash does not match its contents.")

    checks["identity_consistent"] = (
        manifest.identity.package_id == package.identity.package_id)
    if not checks["identity_consistent"]:
        failures.append("Manifest identity does not match package identity.")

    if expected_snapshot_id is not None:
        bound = (package.identity.transcript_snapshot_id
                 == expected_snapshot_id)
        checks["snapshot_bound"] = bound
        if not bound:
            failures.append(
                "Package is not bound to the expected transcript snapshot.")

    if expected_state_hash is not None:
        bound = package.identity.state_hash == expected_state_hash
        checks["state_hash_bound"] = bound
        if not bound:
            failures.append(
                "Package state hash does not match the expected snapshot.")

    return {
        "ok": not failures,
        "checks": checks,
        "failures": failures,
    }
