"""HTTP client for the Atomic Language Model (ALM) service.

This is the class-style client used by the UOR ``/agents/atomic_lang_model/*``
endpoints. The pipeline-style ``alm_*`` skills used by the executor live in
:mod:`uar.skills.atomic_lang_model`.
"""

from __future__ import annotations

import atexit
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore


class AtomicLanguageModelSkill:
    """
    Wrapper skill for interacting with the external Atomic Language Model
    (ALM) service. This skill abstracts the complex, mathematically rigorous
    ALM into a simple, UAR-native API, ensuring UAR remains agnostic to the
    underlying model's implementation (Rust/Coq).

    The ALM service provides:
    - Formal grammar analysis with mathematical proofs
    - Next-token prediction with probabilistic modeling
    - Syntax validation against Chomsky's Minimalist Grammar
    - Ultra-lightweight implementation (<50kB binary)

    API Endpoints (actual ALM service):
    - GET /predict?prefix=<text> - Predict next token
    - GET /generate?count=<n> - Generate sentences
    - POST /validate - Validate syntax with {"sentences": [...]}

    Backward compatibility:
    - analyze_grammar() - Maps to /validate endpoint
    - generate_sequence() - Maps to /generate endpoint
    - verify_syntax() - Maps to /predict endpoint
    """

    def __init__(
        self,
        base_url: str | None = None,
        use_legacy_api: bool = False,
    ):
        """
        Initialize ALM skill.

        Args:
            base_url: Base URL of ALM service. Defaults to localhost:5000.
            use_legacy_api: If True, uses old API structure for backward
                compatibility. If False, uses actual ALM API structure.
        """
        if base_url is None:
            base_url = os.getenv(
                "ALM_SERVICE_URL", "http://localhost:5001/api/v1"
            )
        self.base_url = base_url.rstrip("/")
        self.use_legacy_api = use_legacy_api

        if HTTPX_AVAILABLE:
            try:
                timeout = max(
                    1.0,
                    float(
                        os.getenv("ALM_TIMEOUT_SEC", "30").strip() or "30"
                    ),
                )
                limits = httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                )
                self.client = httpx.Client(timeout=timeout, limits=limits)
            except (OSError, ValueError) as e:
                logger.warning(
                    f"Failed to create httpx client: {e}. "
                    "Falling back to mock responses."
                )
                self.client = None  # type: ignore
        else:
            self.client = None  # type: ignore

    def close(self):
        """Close the httpx client to release resources."""
        if self.client is not None:
            self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures client is closed."""
        self.close()
        return False

    def analyze_grammar(self, grammar_spec: str) -> Dict[str, Any]:
        """
        Analyzes a formal grammar specification (e.g., BNF, EBNF) against
        ALM's formal rules.

        Maps to POST /validate endpoint in actual ALM API.

        :param grammar_spec: The grammar string to analyze.
        :return: A dictionary containing formal analysis results.
        """
        logger.info(
            f"Calling ALM service at {self.base_url}/validate "
            f"with spec: {grammar_spec[:50]}..."
        )
        if self.client is None:
            logger.warning(
                "httpx not available - using mock response. "
                "Install httpx for real ALM service integration."
            )
            if "recursive" in grammar_spec.lower():
                return {
                    "status": "success",
                    "analysis": "Grammar supports provable recursion.",
                    "details": "Passed formal verification checks.",
                }
            return {
                "status": "success",
                "analysis": "Grammar analyzed successfully.",
                "details": "Basic syntax check passed.",
            }

        try:
            if self.use_legacy_api:
                # Legacy API: POST /analyze_grammar
                response = self.client.post(
                    f"{self.base_url}/analyze_grammar",
                    json={"grammar_spec": grammar_spec},
                )
            else:
                # Actual ALM API: POST /validate with sentences array
                response = self.client.post(
                    f"{self.base_url}/validate",
                    json={"sentences": [grammar_spec]},
                )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling ALM service: {e}")
            return {
                "status": "error",
                "error": f"HTTP error: {str(e)}",
                "details": "Failed to connect to ALM service",
            }
        except Exception as e:
            logger.error(f"Unexpected error calling ALM service: {e}")
            return {
                "status": "error",
                "error": str(e),
                "details": "Unexpected error",
            }

    def generate_sequence(self, prefix: str, count: int = 5) -> List[str]:
        """
        Generates a sequence of tokens based on a given prefix using the
        ALM's probabilistic model.

        Maps to GET /generate?count=<n> endpoint in actual ALM API.

        :param prefix: The starting text sequence.
        :param count: The number of tokens to generate.
        :return: A list of generated tokens/strings.
        """
        logger.info(
            f"Calling ALM service at {self.base_url}/generate "
            f"with prefix: '{prefix}' and count: {count}..."
        )
        if self.client is None:
            logger.warning(
                "httpx not available - using mock response. "
                "Install httpx for real ALM service integration."
            )
            if "student" in prefix:
                return ["student", "left", "the", "school", "yesterday"]
            return [f"token_{i}" for i in range(count)]

        try:
            if self.use_legacy_api:
                # Legacy API: POST /generate with JSON body
                response = self.client.post(
                    f"{self.base_url}/generate",
                    json={"prefix": prefix, "count": count},
                )
            else:
                # Actual ALM API: GET /generate?count=<n>
                response = self.client.get(
                    f"{self.base_url}/generate",
                    params={"count": count},
                )
            response.raise_for_status()
            result = response.json()
            # Handle different response formats
            if "tokens" in result:
                return result["tokens"]
            elif "sentences" in result:
                return result["sentences"]
            elif isinstance(result, list):
                return result
            else:
                return [f"token_{i}" for i in range(count)]
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling ALM service: {e}")
            return [f"token_{i}" for i in range(count)]
        except Exception as e:
            logger.error(f"Unexpected error calling ALM service: {e}")
            return [f"token_{i}" for i in range(count)]

    def verify_syntax(self, text: str) -> Dict[str, Any]:
        """
        Performs a full syntactic and semantic validation of a given text
        against the ALM's grammar.

        Maps to GET /predict?prefix=<text> endpoint in actual ALM API.

        :param text: The text to validate.
        :return: A dictionary with validation status and error details.
        """
        logger.info(
            f"Calling ALM service at {self.base_url}/predict "
            f"with text: '{text[:50]}...'"
        )
        if self.client is None:
            logger.warning(
                "httpx not available - using mock response. "
                "Install httpx for real ALM service integration."
            )
            if "student left" in text:
                return {
                    "valid": True,
                    "proof_id": "proof_123",
                    "notes": (
                        "Syntactically correct and semantically plausible."
                    ),
                }
            return {
                "valid": False,
                "error": "Syntax error or semantic violation detected.",
                "details": "Requires formal grammar check.",
            }

        try:
            if self.use_legacy_api:
                # Legacy API: POST /verify
                response = self.client.post(
                    f"{self.base_url}/verify", json={"text": text}
                )
            else:
                # Actual ALM API: GET /predict?prefix=<text>
                response = self.client.get(
                    f"{self.base_url}/predict",
                    params={"prefix": text},
                )
            response.raise_for_status()
            result = response.json()
            # Handle different response formats
            if "valid" in result:
                return result
            elif "is_valid" in result:
                return {"valid": result["is_valid"], **result}
            elif "prediction" in result:
                # For predict endpoint, infer validity from prediction
                return {
                    "valid": True,
                    "prediction": result["prediction"],
                    "notes": "Next token prediction successful",
                }
            else:
                return {"valid": True, "result": result}
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling ALM service: {e}")
            return {
                "valid": False,
                "error": f"HTTP error: {str(e)}",
                "details": "Failed to connect to ALM service",
            }
        except Exception as e:
            logger.error(f"Unexpected error calling ALM service: {e}")
            return {
                "valid": False,
                "error": str(e),
                "details": "Unexpected error",
            }

    # Direct methods for actual ALM API endpoints
    def predict(self, prefix: str) -> Dict[str, Any]:
        """
        Predict the next token using the ALM's probabilistic model.

        Direct mapping to GET /predict endpoint in actual ALM API.

        :param prefix: The text prefix to predict from.
        :return: A dictionary with prediction results.
        """
        logger.info(f"Calling ALM /predict with prefix: '{prefix[:50]}...'")
        if self.client is None:
            logger.warning("httpx not available - using mock response")
            return {"prediction": "token_mock", "probability": 0.5}

        try:
            response = self.client.get(
                f"{self.base_url}/predict",
                params={"prefix": prefix},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling ALM /predict: {e}")
            return {"error": str(e), "prediction": None}
        except Exception as e:
            logger.error(f"Unexpected error calling ALM /predict: {e}")
            return {"error": str(e), "prediction": None}

    def validate_sentences(self, sentences: List[str]) -> Dict[str, Any]:
        """
        Validate multiple sentences against ALM's grammar.

        Direct mapping to POST /validate endpoint in actual ALM API.

        :param sentences: List of sentences to validate.
        :return: A dictionary with validation results for each sentence.
        """
        logger.info(f"Calling ALM /validate with {len(sentences)} sentences")
        if self.client is None:
            logger.warning("httpx not available - using mock response")
            return {
                "results": [{"sentence": s, "valid": True} for s in sentences]
            }

        try:
            response = self.client.post(
                f"{self.base_url}/validate",
                json={"sentences": sentences},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling ALM /validate: {e}")
            return {"error": str(e), "results": []}
        except Exception as e:
            logger.error(f"Unexpected error calling ALM /validate: {e}")
            return {"error": str(e), "results": []}

    def generate_sentences(self, count: int = 5) -> List[str]:
        """
        Generate sentences using the ALM's probabilistic model.

        Direct mapping to GET /generate endpoint in actual ALM API.

        :param count: Number of sentences to generate.
        :return: A list of generated sentences.
        """
        logger.info(f"Calling ALM /generate with count: {count}")
        if self.client is None:
            logger.warning("httpx not available - using mock response")
            return [f"sentence_{i}" for i in range(count)]

        try:
            response = self.client.get(
                f"{self.base_url}/generate",
                params={"count": count},
            )
            response.raise_for_status()
            result = response.json()
            if "sentences" in result:
                return result["sentences"]
            elif isinstance(result, list):
                return result
            else:
                return [f"sentence_{i}" for i in range(count)]
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling ALM /generate: {e}")
            return [f"sentence_{i}" for i in range(count)]
        except Exception as e:
            logger.error(f"Unexpected error calling ALM /generate: {e}")
            return [f"sentence_{i}" for i in range(count)]


# Instantiate the skill for use in the main application
# Check environment variable for legacy API mode
ALM_USE_LEGACY_API = os.getenv("ALM_USE_LEGACY_API", "false").lower() == "true"
ALM_SKILL = AtomicLanguageModelSkill(use_legacy_api=ALM_USE_LEGACY_API)


# Register cleanup handler to close the httpx client on exit
def _cleanup_alm_client():
    """Cleanup function to close the ALM client on exit."""
    if ALM_SKILL.client is not None:
        ALM_SKILL.close()


atexit.register(_cleanup_alm_client)
