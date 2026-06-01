"""Burn-In Runner — executes smoke scenarios and produces a BurnInReport.

Supports two modes:
  direct — calls store/registry/replay in-process (unit-testable, no server)
  http   — fires real HTTP calls against a running UAR server

Trust Spine Phase: T3
Issue: #62
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from uar.testing.burnin.contracts import BurnInEvidence, BurnInReport
from uar.testing.burnin.scenarios import (
    SMOKE_SCENARIOS_DIRECT,
    SMOKE_SCENARIOS_HTTP,
)

_SMOKE_PASS_THRESHOLD = 80


def _average_score(evidence: List[BurnInEvidence]) -> int:
    if not evidence:
        return 0
    return int(round(sum(e.score for e in evidence) / len(evidence)))


class BurnInRunner:
    """Execute burn-in scenarios and return a BurnInReport.

    Args:
        mode: "direct" or "http"
        store: RunStore instance (required for direct mode)
        registry: SkillRegistry instance (required for direct mode)
        base_url: UAR server base URL (required for http mode)
        http_client: httpx.Client instance (http mode; created if None)
    """

    def __init__(
        self,
        mode: str = "direct",
        store: Optional[Any] = None,
        registry: Optional[Any] = None,
        base_url: str = "http://localhost:8000",
        http_client: Optional[Any] = None,
    ) -> None:
        if mode not in ("direct", "http"):
            raise ValueError(
                f"Invalid mode {mode!r}. Must be 'direct' or 'http'."
            )
        self.mode = mode
        self._store = store
        self._registry = registry
        self._base_url = base_url
        self._http_client = http_client

    def _build_direct_ctx(self) -> Dict[str, Any]:
        return {
            "store": self._store,
            "registry": self._registry,
        }

    def _build_http_ctx(self) -> Dict[str, Any]:
        return {
            "base_url": self._base_url,
            "client": self._http_client,
        }

    def run_smoke(self) -> BurnInReport:
        """Execute all smoke scenarios and return a BurnInReport."""
        errors: List[str] = []
        evidence: List[BurnInEvidence] = []

        if self.mode == "direct":
            if self._store is None or self._registry is None:
                return BurnInReport(
                    level="smoke",
                    score=0,
                    passed=False,
                    errors=[
                        "direct mode requires store and registry"
                    ],
                    timestamp=time.time(),
                )
            ctx = self._build_direct_ctx()
            scenarios = SMOKE_SCENARIOS_DIRECT
        else:
            if self._http_client is None:
                try:
                    import httpx
                    self._http_client = httpx.Client()
                except ImportError:
                    return BurnInReport(
                        level="smoke",
                        score=0,
                        passed=False,
                        errors=["httpx is required for http mode"],
                        timestamp=time.time(),
                    )
            ctx = self._build_http_ctx()
            scenarios = SMOKE_SCENARIOS_HTTP

        for scenario_fn in scenarios:
            try:
                result = scenario_fn(ctx)
                evidence.append(result)
                if not result.passed:
                    errors.append(
                        f"{result.scenario}: {result.detail}"
                    )
                ctx[f"_last_{result.scenario}_evidence"] = result
            except Exception as exc:
                errors.append(
                    f"Scenario {scenario_fn.__name__} raised: {exc}"
                )
                evidence.append(BurnInEvidence(
                    scenario=getattr(
                        scenario_fn, "__name__", "unknown"
                    ),
                    passed=False,
                    detail=f"Unexpected error: {exc}",
                    score=0,
                ))

        score = _average_score(evidence)
        passed = score >= _SMOKE_PASS_THRESHOLD and not any(
            not e.passed for e in evidence
        )
        return BurnInReport(
            level="smoke",
            score=score,
            passed=passed,
            evidence=evidence,
            errors=errors,
            timestamp=time.time(),
        )


__all__ = ["BurnInRunner"]
