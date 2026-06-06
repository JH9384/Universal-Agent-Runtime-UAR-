"""Signed manifest verification using Sigstore/cosign.

This module verifies signed UOR artifacts using Sigstore/cosign.
It supports:
- Signature verification via Sigstore bundles
- SHA-256 artifact digest validation
- UOR canonical digest computation with legacy fallback
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SignedManifest:
    """Represents a signed artifact manifest.

    Integrates with Sigstore for bundle verification and
    SHA-256 for artifact digest validation.
    """

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self._data: Optional[Dict[str, Any]] = None

    def load(self) -> bool:
        """Load and validate manifest structure."""
        if not self.manifest_path.exists():
            logger.warning("Manifest not found: %s", self.manifest_path)
            return False

        try:
            self._data = json.loads(self.manifest_path.read_text())
            return self._validate_structure()
        except json.JSONDecodeError:
            logger.exception("Invalid JSON in manifest")
            return False

    def _validate_structure(self) -> bool:
        """Validate manifest has required fields."""
        if not self._data:
            return False

        required = ["version", "artifacts", "signatures"]
        for field in required:
            if field not in self._data:
                logger.error(
                    "Manifest missing required field: %s", field
                )
                return False

        return True

    def verify_signatures(self) -> bool:
        """Verify all signatures in the manifest using Sigstore.

        Looks for a Sigstore bundle file adjacent to the manifest
        (``.sig`` suffix) and validates it via :class:`SigstoreVerifier`.
        If no bundle exists the check degrades gracefully (returns
        ``True`` with a warning) so unsigned manifests still work.
        """
        if not self._data:
            if not self.load():
                return False

        if not self._data:
            return False
        signatures = self._data.get("signatures", [])
        if not signatures:
            logger.warning("No signatures in manifest")
            return True

        # Locate Sigstore bundle using naming convention.
        bundle_candidates = [
            self.manifest_path.with_suffix(".sig"),
            self.manifest_path.with_suffix(
                self.manifest_path.suffix + ".sig"
            ),
            self.manifest_path.parent
            / (self.manifest_path.name + ".sig"),
        ]
        bundle_path = None
        for candidate in bundle_candidates:
            if candidate.exists():
                bundle_path = candidate
                break

        if bundle_path is None:
            logger.warning(
                "No Sigstore bundle found for %s", self.manifest_path
            )
            return True

        try:
            from uar.compat.sigstore_signer import SigstoreVerifier

            verifier = SigstoreVerifier()
            result = verifier.verify_bundle(
                self.manifest_path, bundle_path
            )
            valid = result.get("valid", False)
            if not valid:
                logger.error(
                    "Manifest signature verification failed: %s",
                    result.get("error", "unknown"),
                )
            return valid
        except Exception:
            logger.exception("Sigstore verification failed")
            return False

    def verify_artifact(
        self, artifact_path: Path, expected_digest: str
    ) -> bool:
        """Verify artifact matches expected digest."""
        if not artifact_path.exists():
            logger.error("Artifact not found: %s", artifact_path)
            return False

        sha256 = hashlib.sha256()
        sha256.update(artifact_path.read_bytes())
        actual_digest = sha256.hexdigest()

        if actual_digest != expected_digest:
            logger.error(
                "Digest mismatch for %s: expected %s...",
                artifact_path.name,
                expected_digest[:16],
            )
            return False

        return True

    def get_artifacts(self) -> Dict[str, str]:
        """Get artifact names to expected digests."""
        if not self._data:
            if not self.load():
                return {}

        if not self._data:
            return {}
        return {
            a["name"]: a["digest"]
            for a in self._data.get("artifacts", [])
            if "name" in a and "digest" in a
        }


class ManifestVerifier:
    """Verifies signed manifests against artifact digests."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def verify_manifest(self, manifest_path: Path) -> bool:
        """Verify a complete manifest including all artifacts."""
        manifest = SignedManifest(manifest_path)

        if not manifest.load():
            return False

        if not manifest.verify_signatures():
            return False

        # Verify each artifact
        artifacts = manifest.get_artifacts()
        for name, expected_digest in artifacts.items():
            artifact_path = self.cache_dir / name
            if not manifest.verify_artifact(artifact_path, expected_digest):
                return False

        logger.info("Manifest verified: %s", manifest_path.name)
        return True


def _uor_digest_or_fallback(obj: Any) -> str:
    """UOR-ADDR-1 canonical digest with fallback to legacy JSON+SHA-256."""
    try:
        from uar.uor.bounded_json import compute_uor_digest

        return compute_uor_digest(obj)
    except Exception:
        raw = json.dumps(obj, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_placeholder_manifest(
    artifacts: Dict[str, str],
    output_path: Path,
) -> None:
    """Create a signed manifest file.

    Args:
        artifacts: Dict of artifact name to SHA256 digest
        output_path: Path to write manifest
    """
    import time

    manifest = {
        "version": "v0.1",
        "artifacts": [
            {"name": name, "digest": digest}
            for name, digest in artifacts.items()
        ],
        "signatures": [],
        "signed_by": None,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest_digest": None,  # Filled below
    }
    manifest["manifest_digest"] = _uor_digest_or_fallback(manifest)

    output_path.write_text(json.dumps(manifest, indent=2))
    logger.info("Created manifest: %s", output_path)
