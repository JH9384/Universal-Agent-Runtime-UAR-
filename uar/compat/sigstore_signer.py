"""Sigstore signing and verification for UOR artifacts.

Provides integration with Sigstore's Rekor transparency log and Fulcio
certificate authority for keyless signing of UOR artifacts.

Requires: pip install sigstore

Usage:
    from uar.compat.sigstore_signer import sign_artifact, verify_artifact
    result = sign_artifact(
        artifact_path="third_party/uor/schema.json",
        identity="ci@uor.foundation",
    )
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

# Optional sigstore imports
try:
    from sigstore.oidc import Issuer
    from sigstore.sign import SigningContext
    from sigstore.verify import Verifier, VerificationMaterials
    from sigstore.models import Bundle
    _HAS_SIGSTORE = True
except ImportError:
    _HAS_SIGSTORE = False
    logger.warning("sigstore not installed. Keyless signing unavailable.")


class SigstoreSigningResult:
    """Result of a signing operation."""

    def __init__(
        self,
        success: bool,
        bundle_path: Optional[Path] = None,
        log_index: Optional[int] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.bundle_path = bundle_path
        self.log_index = log_index
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "bundle_path": str(self.bundle_path) if self.bundle_path else None,
            "log_index": self.log_index,
            "error": self.error,
        }


class SigstoreSigner:
    """Sigstore keyless signing for UOR artifacts.

    Supports Python API (when sigstore installed) and CLI fallback.
    """

    def __init__(self, use_cli_fallback: bool = False):
        self.use_cli_fallback = use_cli_fallback or not _HAS_SIGSTORE
        self._issuer: Optional[Any] = None

        if not self.use_cli_fallback and _HAS_SIGSTORE:
            try:
                self._issuer = Issuer.production()
                logger.info("Sigstore initialized with production issuer")
            except Exception:
                logger.exception("Failed to initialize Sigstore")
                self.use_cli_fallback = True

    def sign_file(
        self,
        file_path: Union[str, Path],
        identity: str,
        output_path: Optional[Union[str, Path]] = None,
    ) -> SigstoreSigningResult:
        """Sign a file using Sigstore keyless signing."""
        file_path = Path(file_path)

        if not file_path.exists():
            return SigstoreSigningResult(
                success=False,
                error="File not found"
            )

        if self.use_cli_fallback:
            return self._sign_with_cosign_cli(file_path, identity, output_path)

        return self._sign_with_python_api(file_path, identity, output_path)

    def _sign_with_python_api(
        self,
        file_path: Path,
        identity: str,
        output_path: Optional[Union[str, Path]],
    ) -> SigstoreSigningResult:
        """Sign using sigstore Python API."""
        if not _HAS_SIGSTORE:
            return SigstoreSigningResult(
                success=False,
                error="sigstore package not installed"
            )

        try:
            token = self._get_oidc_token(identity)
            if not token:
                return SigstoreSigningResult(
                    success=False,
                    error="Failed to obtain OIDC token"
                )

            signer = SigningContext.production()
            with open(file_path, "rb") as f:
                input_data = f.read()

            result = signer.sign(
                input_=input_data,
                identity_token=token,
            )

            if output_path:
                bundle_path = Path(output_path)
            else:
                bundle_path = file_path.with_suffix(file_path.suffix + ".sig")

            bundle_path.write_text(result.to_json())

            return SigstoreSigningResult(
                success=True,
                bundle_path=bundle_path,
                log_index=(
                    result.log_entry.log_id if result.log_entry else None
                ),
            )

        except Exception:
            logger.exception("Python API signing failed")
            return SigstoreSigningResult(
                success=False, error="Signing failed"
            )

    def _sign_with_cosign_cli(
        self,
        file_path: Path,
        identity: str,
        output_path: Optional[Union[str, Path]],
    ) -> SigstoreSigningResult:
        """Fallback: sign using cosign CLI."""
        try:
            subprocess.run(
                ["cosign", "version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return SigstoreSigningResult(
                success=False,
                error=(
                    "cosign CLI not found. "
                    "Install: brew install sigstore/tap/cosign"
                )
            )

        if output_path:
            bundle_path = Path(output_path)
        else:
            bundle_path = file_path.with_suffix(file_path.suffix + ".sig")

        try:
            cmd = [
                "cosign", "sign-blob",
                "--yes",
                "--bundle", str(bundle_path),
                "--identity-token", self._get_ci_token() or "",
                str(file_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return SigstoreSigningResult(
                    success=True,
                    bundle_path=bundle_path,
                )
            else:
                return SigstoreSigningResult(
                    success=False,
                    error="cosign failed",
                )

        except Exception:
            logger.exception("cosign execution failed")
            return SigstoreSigningResult(
                success=False,
                error="cosign execution failed"
            )

    def _get_oidc_token(self, identity: str) -> Optional[str]:
        """Get OIDC token for signing identity."""
        import os

        # GitHub Actions
        if "GITHUB_TOKEN" in os.environ:
            try:
                import requests

                req_token = os.environ.get(
                    "ACTIONS_ID_TOKEN_REQUEST_TOKEN", ""
                )
                req_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")

                if req_token and req_url:
                    resp = requests.get(
                        req_url,
                        headers={"Authorization": f"Bearer {req_token}"},
                        params={"audience": "sigstore"},
                    )
                    resp.raise_for_status()
                    return resp.json()["value"]
            except Exception:
                logger.exception("Failed to get GitHub OIDC token")

        logger.warning(
            "No CI OIDC token found. Local signing requires manual token."
        )
        return os.getenv("SIGSTORE_ID_TOKEN")

    def _get_ci_token(self) -> Optional[str]:
        """Get CI token for cosign."""
        import os
        return os.getenv("SIGSTORE_ID_TOKEN")


class SigstoreVerifier:
    """Verify Sigstore signatures on artifacts."""

    def __init__(self):
        self._verifier: Optional[Any] = None

        if _HAS_SIGSTORE:
            try:
                self._verifier = Verifier.production()
            except Exception:
                logger.exception("Failed to initialize Sigstore verifier")

    def verify_bundle(
        self,
        artifact_path: Union[str, Path],
        bundle_path: Union[str, Path],
    ) -> Dict[str, Any]:
        """Verify an artifact against its Sigstore bundle."""
        artifact_path = Path(artifact_path)
        bundle_path = Path(bundle_path)

        if not artifact_path.exists():
            return {"valid": False, "error": "Artifact not found"}
        if not bundle_path.exists():
            return {"valid": False, "error": "Bundle not found"}

        try:
            bundle_data = json.loads(bundle_path.read_text())

            if _HAS_SIGSTORE and self._verifier:
                return self._verify_with_api(artifact_path, bundle_data)
            else:
                return self._verify_with_cli(artifact_path, bundle_path)

        except Exception:
            logger.exception("Verification failed")
            return {"valid": False, "error": "Verification failed"}

    def _verify_with_api(
        self,
        artifact_path: Path,
        bundle_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Verify using sigstore Python API."""
        try:
            bundle = Bundle.from_json(json.dumps(bundle_data))

            with open(artifact_path, "rb") as f:
                artifact_data = f.read()

            materials = VerificationMaterials(
                input_=artifact_data,
                bundle=bundle,
            )

            if self._verifier is None:
                return {"valid": False, "error": "Verifier not initialized"}
            verifier = self._verifier
            policy = verifier.policy.Identity(  # type: ignore[union-attr]
                identity=bundle_data.get("cert", {}).get("subject", ""),
                issuer="https://accounts.google.com",
            )

            result = verifier.verify(
                materials, policy=policy
            )  # type: ignore[union-attr]

            return {
                "valid": result.ok,
                "identity": bundle_data.get("cert", {}).get("subject"),
                "log_index": bundle_data.get("log_entry", {}).get("log_index"),
                "error": None if result.ok else str(result.reason),
            }

        except Exception:
            logger.exception("API verification failed")
            return {"valid": False, "error": "API verification failed"}

    def _verify_with_cli(
        self,
        artifact_path: Path,
        bundle_path: Path,
    ) -> Dict[str, Any]:
        """Verify using cosign CLI."""
        try:
            result = subprocess.run(
                [
                    "cosign", "verify-blob",
                    "--bundle", str(bundle_path),
                    str(artifact_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return {"valid": True, "identity": None, "log_index": None}
            else:
                return {"valid": False, "error": result.stderr}

        except FileNotFoundError:
            return {"valid": False, "error": "cosign CLI not found"}
        except Exception:
            logger.exception("CLI verification failed")
            return {"valid": False, "error": "Verification failed"}


def sign_artifact(
    artifact_path: Union[str, Path],
    identity: str,
    output_path: Optional[Union[str, Path]] = None,
    use_cli: bool = False,
) -> SigstoreSigningResult:
    """Convenience function to sign an artifact."""
    signer = SigstoreSigner(use_cli_fallback=use_cli)
    return signer.sign_file(artifact_path, identity, output_path)


def verify_artifact(
    artifact_path: Union[str, Path],
    bundle_path: Union[str, Path],
) -> Dict[str, Any]:
    """Convenience function to verify an artifact."""
    verifier = SigstoreVerifier()
    return verifier.verify_bundle(artifact_path, bundle_path)
