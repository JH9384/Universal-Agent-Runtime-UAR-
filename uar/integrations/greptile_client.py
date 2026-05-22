"""Greptile AI-powered code search integration.

Enables natural-language queries against the codebase for agent
comprehension and developer assistance.

Install: pip install greptile
Docs: https://docs.greptile.com
"""

import os
from typing import Any, Optional

from .base import BaseIntegration
from uar.core.circuit_breaker_decorator import with_circuit_breaker

logger = __import__("logging").getLogger(__name__)


class GreptileClient(BaseIntegration):
    """Client for Greptile code search / understanding API.

    Usage:
        client = GreptileClient()
        results = await client.query(
            "Where is the Service Layer defined?"
        )
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("GREPTILE_API_KEY", "")
        self.base_url = os.getenv(
            "GREPTILE_API_URL", "https://api.greptile.com/v1"
        )
        self.repo = os.getenv("GREPTILE_REPO", "")
        self._client: Optional[Any] = None

    def _lazy_client(self) -> Any:
        if self._client is None:
            try:
                import httpx

                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
            except ImportError as exc:
                raise ImportError(
                    "httpx not installed. Run: pip install httpx"
                ) from exc
        return self._client

    @with_circuit_breaker(
        "greptile", failure_threshold=5, recovery_timeout=60.0
    )
    async def query(
        self,
        question: str,
        repo: Optional[str] = None,
        branch: str = "main",
    ) -> dict[str, Any]:
        """Ask a natural-language question about the codebase.

        Args:
            question: Natural language query.
            repo: Repository identifier (defaults to GREPTILE_REPO).
            branch: Git branch to search.

        Returns:
            Response dict with ``answer`` and ``references`` keys.
        """
        if not self.api_key:
            logger.warning("GREPTILE_API_KEY not set; returning mock")
            return {"answer": "Greptile not configured", "references": []}

        client = self._lazy_client()
        target_repo = repo or self.repo
        if not target_repo:
            raise ValueError(
                "Repo required. Set GREPTILE_REPO or pass repo=."
            )

        resp = await client.post(
            "/query",
            json={
                "query": question,
                "repositories": [
                    {"repository": target_repo, "branch": branch}
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()

    @with_circuit_breaker(
        "greptile", failure_threshold=3, recovery_timeout=60.0
    )
    async def index_repo(
        self, repo: Optional[str] = None, branch: str = "main"
    ) -> dict[str, Any]:
        """Trigger indexing of a repository."""
        if not self.api_key:
            logger.warning("GREPTILE_API_KEY not set; skipping index")
            return {"status": "skipped"}

        client = self._lazy_client()
        target_repo = repo or self.repo
        if not target_repo:
            raise ValueError("Repo required")

        resp = await client.post(
            "/index",
            json={
                "repository": target_repo,
                "branch": branch,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
