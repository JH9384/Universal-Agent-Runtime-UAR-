"""Synthetic probing for UAR — blackbox health checks.

T8 — Synthetic Probing: periodically probes UAR endpoints and
notifies PagerDuty (and optionally webhooks) on failure / recovery.

Usage:
    from uar.observability.synthetic_probe import SyntheticProbe
    probe = SyntheticProbe()
    probe.run_all()

Env vars:
    UAR_PROBE_BASE_URL       — Target server (default: http://localhost:8000)
    UAR_PROBE_INTERVAL_SEC   — Poll interval (default: 60)
    UAR_PROBE_TIMEOUT_SEC    — Request timeout (default: 5)
    UAR_PROBE_CONSECUTIVE    — Failures before alert (default: 2)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    """Result of a single probe check."""

    scenario: str
    passed: bool
    latency_ms: float
    status_code: Optional[int] = None
    detail: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ProbeScenario:
    """Configuration for one probe scenario."""

    name: str
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    expected_status: int = 200
    body_contains: Optional[str] = None
    timeout: float = 5.0


class SyntheticProbe:
    """Blackbox synthetic probe for UAR endpoints.

    Maintains per-scenario failure counters; only alerts after
    ``consecutive_failures`` consecutive failures to avoid
    flapping on transient blips.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        consecutive_failures: Optional[int] = None,
        timeout: Optional[float] = None,
        notifier: Optional[Any] = None,
    ) -> None:
        _url = base_url or os.getenv(
            "UAR_PROBE_BASE_URL", "http://localhost:8000"
        )
        self.base_url = _url.rstrip("/")
        self.consecutive = consecutive_failures or int(
            os.getenv("UAR_PROBE_CONSECUTIVE", "2")
        )
        self.timeout = timeout or float(
            os.getenv("UAR_PROBE_TIMEOUT_SEC", "5")
        )
        self._notifier = notifier
        self._failure_counts: Dict[str, int] = {}
        self._alerted: set[str] = set()
        self._scenarios = self._default_scenarios()

    def _default_scenarios(self) -> List[ProbeScenario]:
        """Built-in probe scenarios for core UAR endpoints."""
        return [
            ProbeScenario(
                name="health",
                url=f"{self.base_url}/api/uar/health",
            ),
            ProbeScenario(
                name="metrics",
                url=f"{self.base_url}/metrics",
                body_contains="uar_requests_total",
            ),
            ProbeScenario(
                name="openapi",
                url=f"{self.base_url}/api/openapi.json",
                body_contains="openapi",
            ),
        ]

    def add_scenario(self, scenario: ProbeScenario) -> None:
        """Register an additional probe scenario."""
        self._scenarios.append(scenario)

    def run_all(self) -> List[ProbeResult]:
        """Execute all scenarios and return results.

        Triggers / resolves PagerDuty alerts based on consecutive
        failure counts.
        """
        results: List[ProbeResult] = []
        for sc in self._scenarios:
            result = self._run_one(sc)
            results.append(result)
            self._process_result(result)
        return results

    def _run_one(self, scenario: ProbeScenario) -> ProbeResult:
        t0 = time.time()
        try:
            req = Request(
                scenario.url,
                method=scenario.method,
                headers=scenario.headers,
            )
            with urlopen(req, timeout=scenario.timeout) as resp:
                latency = (time.time() - t0) * 1000
                body = resp.read().decode("utf-8", errors="replace")
                if scenario.body_contains and scenario.body_contains not in body:
                    return ProbeResult(
                        scenario=scenario.name,
                        passed=False,
                        latency_ms=latency,
                        status_code=resp.status,
                        detail=f"Body missing: {scenario.body_contains}",
                    )
                return ProbeResult(
                    scenario=scenario.name,
                    passed=True,
                    latency_ms=latency,
                    status_code=resp.status,
                )
        except URLError as exc:
            latency = (time.time() - t0) * 1000
            return ProbeResult(
                scenario=scenario.name,
                passed=False,
                latency_ms=latency,
                detail=str(exc.reason),
            )
        except Exception as exc:
            latency = (time.time() - t0) * 1000
            return ProbeResult(
                scenario=scenario.name,
                passed=False,
                latency_ms=latency,
                detail=str(exc),
            )

    def _process_result(self, result: ProbeResult) -> None:
        name = result.scenario
        if result.passed:
            self._failure_counts[name] = 0
            if name in self._alerted:
                self._alerted.discard(name)
                self._notify_resolve(result)
            return

        self._failure_counts[name] = self._failure_counts.get(name, 0) + 1
        if (self._failure_counts[name] >= self.consecutive
                and name not in self._alerted):
            self._alerted.add(name)
            self._notify_trigger(result)

    def _notify_trigger(self, result: ProbeResult) -> None:
        summary = f"UAR probe failed: {result.scenario}"
        detail = {
            "latency_ms": round(result.latency_ms, 1),
            "status_code": result.status_code,
            "detail": result.detail,
            "url": self._scenario_url(result.scenario),
        }
        logger.error("%s — %s", summary, detail)
        if self._notifier is not None:
            try:
                self._notifier.trigger(summary, result.scenario, detail)
            except Exception:
                logger.exception("Notifier trigger failed")

    def _notify_resolve(self, result: ProbeResult) -> None:
        summary = f"UAR probe recovered: {result.scenario}"
        logger.info(summary)
        if self._notifier is not None:
            try:
                self._notifier.resolve(summary, result.scenario)
            except Exception:
                logger.exception("Notifier resolve failed")

    def _scenario_url(self, scenario_name: str) -> str:
        for sc in self._scenarios:
            if sc.name == scenario_name:
                return sc.url
        return ""

    def run_loop(self, interval: Optional[float] = None) -> None:
        """Run probes in an infinite loop (for daemon / cron usage)."""
        sec = interval or float(os.getenv("UAR_PROBE_INTERVAL_SEC", "60"))
        logger.info("Starting synthetic probe loop (interval=%.0fs)", sec)
        while True:
            self.run_all()
            time.sleep(sec)
