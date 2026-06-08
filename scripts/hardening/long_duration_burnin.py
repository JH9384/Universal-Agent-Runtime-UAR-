#!/usr/bin/env python3
"""Long-Duration Burn-In Runner — Track 3 (G.7 instrumented).

Runs continuous operational validation for 24h, 72h, or 168h sessions.
Monitors:
- Memory growth (RSS over time)
- Recommendation throughput and trust scores
- Cache consistency across trust/mission-control/snapshot endpoints
- Metadata key growth and scan latency
- Snapshot accumulation rate and retrieval latency
- Report generation duration (trust, burn-in, evidence pack)
- Knowledge graph growth (node count, edge count, generation time)

Usage:
    python scripts/hardening/long_duration_burnin.py \
        --duration 24h --api-url http://localhost:8000

Durations: 24h, 72h, 168h
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import psutil
import requests

# Tolerance within which trust scores from different endpoints are
# considered consistent (absolute difference).
_CACHE_CONSISTENCY_TOLERANCE = 0.05


@dataclass
class Sample:
    """Single metric sample at a point in time."""

    timestamp: float
    rss_mb: float
    vms_mb: float
    cpu_percent: float
    # Core trust / recommendations
    recommendation_count: int = 0
    recommendation_latency_ms: float = 0.0
    replay_success_count: int = 0
    replay_latency_ms: float = 0.0
    trust_score: Optional[float] = None
    calibration_error: Optional[float] = None
    # 1. Cache consistency
    trust_endpoint_score: Optional[float] = None
    mission_control_trust_score: Optional[float] = None
    cache_consistency_score: Optional[float] = None
    cache_consistency_ok: Optional[bool] = None
    # 2. Metadata growth
    metadata_key_count: Optional[int] = None
    metadata_scan_latency_ms: Optional[float] = None
    # 3. Snapshot accumulation
    snapshot_count: Optional[int] = None
    snapshot_retrieval_latency_ms: Optional[float] = None
    entity_retention_capable: Optional[bool] = None
    entity_retention_snapshot_count: Optional[int] = None
    entity_integrity_status: Optional[str] = None
    entity_integrity_issue_count: Optional[int] = None
    # 4. Report timing
    trust_report_duration_ms: Optional[float] = None
    burnin_report_duration_ms: Optional[float] = None
    # 5. Graph growth
    graph_node_count: Optional[int] = None
    graph_edge_count: Optional[int] = None
    graph_generation_time_ms: Optional[float] = None


@dataclass
class BurnInReport:
    """Aggregated report from a long-duration burn-in session."""

    duration_hours: int
    start_time: str
    end_time: str
    sample_count: int
    samples: List[Dict[str, object]] = field(default_factory=list)
    summary: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


# ---------------------------------------------------------------------------
# System resource probe
# ---------------------------------------------------------------------------

def get_memory_info() -> tuple[float, float, float]:
    """Return (rss_mb, vms_mb, cpu_percent) for the current process."""
    proc = psutil.Process(os.getpid())
    mem = proc.memory_info()
    cpu = proc.cpu_percent(interval=0.1)
    return mem.rss / 1024 / 1024, mem.vms / 1024 / 1024, cpu


# ---------------------------------------------------------------------------
# Individual observation probes (each returns a partial dict)
# ---------------------------------------------------------------------------

def _get(
    session: requests.Session,
    url: str,
    timeout: int = 15,
) -> tuple[Optional[dict], float]:
    """GET url, return (json_or_None, latency_ms)."""
    t0 = time.time()
    try:
        r = session.get(url, timeout=timeout)
        latency = (time.time() - t0) * 1000
        if r.status_code == 200:
            return r.json(), latency
        return None, latency
    except Exception:
        return None, (time.time() - t0) * 1000


def probe_recommendations(
    session: requests.Session, api_url: str
) -> dict:
    data, latency = _get(
        session,
        f"{api_url}/api/uar/recommendations?hours=24&limit=100",
    )
    count = len((data or {}).get("recommendations", [])) if data else 0
    return {
        "recommendation_count": count,
        "recommendation_latency_ms": round(latency, 1),
    }


def probe_runs(session: requests.Session, api_url: str) -> dict:
    data, latency = _get(session, f"{api_url}/api/uar/runs?limit=10")
    runs = (data or {}).get("runs", data) if data else []
    count = len(runs) if isinstance(runs, list) else 0
    return {
        "replay_success_count": count,
        "replay_latency_ms": round(latency, 1),
    }


def probe_cache_consistency(
    session: requests.Session, api_url: str
) -> dict:
    """Sample trust score from three independent endpoints and compare.

    Endpoints sampled:
      /recommendations/trust       — trust engine view
      /mission-control             — aggregated snapshot view

    cache_consistency_score: absolute difference between the two trust
    readings. None if either endpoint is unavailable.
    cache_consistency_ok: True when diff <= _CACHE_CONSISTENCY_TOLERANCE.
    """
    trust_data, _ = _get(
        session, f"{api_url}/api/uar/recommendations/trust"
    )
    mc_data, _ = _get(session, f"{api_url}/api/uar/mission-control")

    trust_score: Optional[float] = None
    mc_trust: Optional[float] = None
    cal_error: Optional[float] = None

    if trust_data:
        types = trust_data.get("recommendation_types", [])
        if types:
            trust_score = types[0].get("trust_score")
        cal_error = trust_data.get("system_calibration_error")

    if mc_data:
        trust_summary = mc_data.get("trust_summary", {})
        mc_trust = trust_summary.get("average_trust_score")

    consistency: Optional[float] = None
    ok: Optional[bool] = None
    if trust_score is not None and mc_trust is not None:
        consistency = round(abs(trust_score - mc_trust), 4)
        ok = consistency <= _CACHE_CONSISTENCY_TOLERANCE

    return {
        "trust_score": trust_score,
        "calibration_error": cal_error,
        "trust_endpoint_score": trust_score,
        "mission_control_trust_score": mc_trust,
        "cache_consistency_score": consistency,
        "cache_consistency_ok": ok,
    }


def probe_metadata_growth(
    session: requests.Session, api_url: str
) -> dict:
    """Measure metadata key count via the admin diagnostics endpoint.

    Falls back to probing /api/uar/incidents list length as a proxy
    if no dedicated diagnostics endpoint is available.
    """
    scan_start = time.time()
    key_count: Optional[int] = None

    # Try the diagnostics metadata endpoint first
    admin_url = f"{api_url}/api/uar/admin/metadata/stats"
    data, _ = _get(session, admin_url)
    if data:
        key_count = data.get("key_count")

    # Fallback: count incidents as a metadata proxy
    if key_count is None:
        inc_data, _ = _get(
            session, f"{api_url}/api/uar/incidents"
        )
        if inc_data is not None and isinstance(inc_data, list):
            key_count = len(inc_data)

    scan_latency = round((time.time() - scan_start) * 1000, 1)
    return {
        "metadata_key_count": key_count,
        "metadata_scan_latency_ms": scan_latency,
    }


def probe_snapshot_accumulation(
    session: requests.Session, api_url: str
) -> dict:
    """Count time-machine snapshots and measure retrieval latency."""
    data, latency = _get(
        session,
        f"{api_url}/api/uar/operator/snapshots?limit=200",
    )
    if data is None:
        data, latency = _get(
            session,
            f"{api_url}/api/uar/snapshots?limit=200",
        )

    count: Optional[int] = None
    if isinstance(data, list):
        count = len(data)
    elif isinstance(data, dict):
        count = len(data.get("snapshots", data.get("items", [])))

    return {
        "snapshot_count": count,
        "snapshot_retrieval_latency_ms": round(latency, 1),
    }


def probe_report_timing(
    session: requests.Session, api_url: str
) -> dict:
    """Measure how long the trust-validation and burn-in reports take."""
    t0 = time.time()
    _get(session, f"{api_url}/api/uar/reports/trust-validation")
    trust_dur = round((time.time() - t0) * 1000, 1)

    t0 = time.time()
    _get(session, f"{api_url}/api/uar/reports/burn-in")
    burnin_dur = round((time.time() - t0) * 1000, 1)

    return {
        "trust_report_duration_ms": trust_dur,
        "burnin_report_duration_ms": burnin_dur,
    }


def probe_entity_pressure(
    session: requests.Session, api_url: str
) -> Dict[str, object]:
    """Read Mission Control entity retention/integrity pressure fields."""
    try:
        start = time.perf_counter()
        resp = session.get(f"{api_url}/api/uar/mission-control", timeout=10)
        latency = (time.perf_counter() - start) * 1000
        if resp.status_code != 200:
            return {
                "entity_retention_capable": None,
                "entity_retention_snapshot_count": None,
                "entity_integrity_status": "unknown",
                "entity_integrity_issue_count": None,
                "entity_pressure_latency_ms": round(latency, 1),
            }

        data = resp.json()
        retention = data.get("entity_retention") or {}
        integrity = data.get("entity_integrity") or {}
        entities = retention.get("entities") or {}
        snapshots = entities.get("snapshots") or {}
        summary = integrity.get("summary") or {}
        issues = integrity.get("issues") or []

        issue_count = summary.get("issue_count")
        if issue_count is None and isinstance(issues, list):
            issue_count = len(issues)

        return {
            "entity_retention_capable": snapshots.get("retention_capable"),
            "entity_retention_snapshot_count": snapshots.get("count"),
            "entity_integrity_status": integrity.get("status", "unknown"),
            "entity_integrity_issue_count": issue_count,
            "entity_pressure_latency_ms": round(latency, 1),
        }
    except Exception as exc:
        return {
            "entity_retention_capable": None,
            "entity_retention_snapshot_count": None,
            "entity_integrity_status": "error",
            "entity_integrity_issue_count": None,
            "entity_pressure_error": str(exc),
        }


def probe_graph_growth(
    session: requests.Session, api_url: str, sample_run_id: str
) -> dict:
    """Measure knowledge-graph size and generation time for a sample run."""
    if not sample_run_id:
        return {
            "graph_node_count": None,
            "graph_edge_count": None,
            "graph_generation_time_ms": None,
        }
    data, latency = _get(
        session, f"{api_url}/api/uar/graph/{sample_run_id}"
    )
    gen_time = round(latency, 1)
    nodes: Optional[int] = None
    edges: Optional[int] = None
    if data:
        nodes = len(data.get("nodes", []))
        edges = len(data.get("edges", []))
    return {
        "graph_node_count": nodes,
        "graph_edge_count": edges,
        "graph_generation_time_ms": gen_time,
    }


# ---------------------------------------------------------------------------
# Main burn-in loop
# ---------------------------------------------------------------------------

def _resolve_sample_run_id(
    session: requests.Session, api_url: str
) -> str:
    """Return the most recent run_id for graph probing, or empty string."""
    try:
        data, _ = _get(session, f"{api_url}/api/uar/runs?limit=1")
        if isinstance(data, list) and data:
            return data[0].get("run_id", data[0].get("id", ""))
        if isinstance(data, dict):
            runs = data.get("runs", [])
            if runs:
                return runs[0].get("run_id", runs[0].get("id", ""))
    except Exception:
        pass
    return ""


def run_burnin(
    duration_hours: int,
    api_url: str,
    api_key: str,
    interval_seconds: int = 300,
    output_file: Optional[str] = None,
) -> BurnInReport:
    """Run a long-duration burn-in session."""
    start_ts = time.time()
    end_ts = start_ts + duration_hours * 3600
    samples: List[Sample] = []

    print(f"Burn-in started: {datetime.now(timezone.utc).isoformat()}")
    print(f"Duration: {duration_hours}h | Interval: {interval_seconds}s")
    print(f"API: {api_url}")
    print(
        "Observing: memory | recommendations | cache-consistency | "
        "metadata-growth | snapshots | report-timing | graph-growth"
    )

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {api_key}"

    # Resolve a sample run_id once at startup for graph probing.
    # Refreshed every 10 samples to catch new runs.
    sample_run_id = _resolve_sample_run_id(session, api_url)
    sample_counter = 0

    while time.time() < end_ts:
        if sample_counter % 10 == 0:
            sample_run_id = _resolve_sample_run_id(session, api_url)

        rss, vms, cpu = get_memory_info()

        rec = probe_recommendations(session, api_url)
        runs = probe_runs(session, api_url)
        cache = probe_cache_consistency(session, api_url)
        meta = probe_metadata_growth(session, api_url)
        snaps = probe_snapshot_accumulation(session, api_url)
        entity_pressure = probe_entity_pressure(session, api_url)
        reports = probe_report_timing(session, api_url)
        graph = probe_graph_growth(session, api_url, sample_run_id)

        sample = Sample(
            timestamp=time.time(),
            rss_mb=round(rss, 1),
            vms_mb=round(vms, 1),
            cpu_percent=round(cpu, 1),
            **rec,
            **runs,
            **cache,
            **meta,
            **snaps,
            **entity_pressure,
            **reports,
            **graph,
        )
        samples.append(sample)
        sample_counter += 1

        elapsed = time.time() - start_ts
        consistency_flag = (
            "✓" if sample.cache_consistency_ok
            else ("✗" if sample.cache_consistency_ok is False else "?")
        )
        print(
            f"[{elapsed/3600:.1f}h/{duration_hours}h] "
            f"RSS:{sample.rss_mb:.0f}MB "
            f"CPU:{sample.cpu_percent:.0f}% "
            f"Rec:{sample.recommendation_count}"
            f"({sample.recommendation_latency_ms:.0f}ms) "
            f"Trust:{sample.trust_score or '—'} "
            f"Cache:{consistency_flag}"
            f"({sample.cache_consistency_score or '?'}) "
            f"MetaKeys:{sample.metadata_key_count or '?'} "
            f"Snaps:{sample.snapshot_count or '?'} "
            f"TrustRpt:{sample.trust_report_duration_ms or '?'}ms "
            f"Graph:{sample.graph_node_count or '?'}N"
            f"/{sample.graph_edge_count or '?'}E"
        )

        sleep_until = time.time() + interval_seconds
        while time.time() < min(sleep_until, end_ts):
            time.sleep(1)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    if samples:
        def _vals(attr: str) -> List[float]:
            return [
                getattr(s, attr)
                for s in samples
                if getattr(s, attr) is not None
            ]

        def _avg(vs: List[float]) -> Optional[float]:
            return round(sum(vs) / len(vs), 3) if vs else None

        def _max(vs: List[float]) -> Optional[float]:
            return round(max(vs), 3) if vs else None

        rss_vals = _vals("rss_mb")
        rec_lat = _vals("recommendation_latency_ms")
        consistency_vals = _vals("cache_consistency_score")
        meta_counts = _vals("metadata_key_count")
        meta_lats = _vals("metadata_scan_latency_ms")
        snap_counts = _vals("snapshot_count")
        snap_lats = _vals("snapshot_retrieval_latency_ms")
        entity_issue_counts = _vals("entity_integrity_issue_count")
        trust_rpt = _vals("trust_report_duration_ms")
        burnin_rpt = _vals("burnin_report_duration_ms")
        node_counts = _vals("graph_node_count")
        edge_counts = _vals("graph_edge_count")
        graph_times = _vals("graph_generation_time_ms")

        cache_violations = sum(
            1 for s in samples
            if s.cache_consistency_ok is False
        )

        summary: Dict[str, object] = {
            # Memory
            "rss_start_mb": rss_vals[0] if rss_vals else None,
            "rss_end_mb": rss_vals[-1] if rss_vals else None,
            "rss_growth_mb": round(
                rss_vals[-1] - rss_vals[0], 1
            ) if len(rss_vals) >= 2 else None,
            "rss_peak_mb": _max(rss_vals),
            "avg_cpu_percent": _avg(_vals("cpu_percent")),
            # Recommendations
            "total_recommendations_seen": sum(
                s.recommendation_count for s in samples
            ),
            "avg_recommendation_latency_ms": _avg(rec_lat),
            "max_recommendation_latency_ms": _max(rec_lat),
            "trust_score_final": samples[-1].trust_score,
            "calibration_error_final": samples[-1].calibration_error,
            # 1. Cache consistency
            "cache_consistency_violations": cache_violations,
            "cache_consistency_violation_rate": round(
                cache_violations / len(samples), 4
            ) if samples else None,
            "avg_cache_consistency_score": _avg(consistency_vals),
            "max_cache_consistency_score": _max(consistency_vals),
            # 2. Metadata growth
            "metadata_key_count_start": (
                int(meta_counts[0]) if meta_counts else None
            ),
            "metadata_key_count_end": (
                int(meta_counts[-1]) if meta_counts else None
            ),
            "metadata_key_growth": (
                int(meta_counts[-1] - meta_counts[0])
                if len(meta_counts) >= 2 else None
            ),
            "avg_metadata_scan_latency_ms": _avg(meta_lats),
            "max_metadata_scan_latency_ms": _max(meta_lats),
            # 3. Snapshot accumulation
            "snapshot_count_start": (
                int(snap_counts[0]) if snap_counts else None
            ),
            "snapshot_count_end": (
                int(snap_counts[-1]) if snap_counts else None
            ),
            "snapshot_growth": (
                int(snap_counts[-1] - snap_counts[0])
                if len(snap_counts) >= 2 else None
            ),
            "expected_snapshots": duration_hours,
            "avg_snapshot_retrieval_latency_ms": _avg(snap_lats),
            "max_snapshot_retrieval_latency_ms": _max(snap_lats),
            # 3b. Entity retention/integrity pressure
            "entity_retention_capable_rate": round(
                sum(1 for s in samples if s.entity_retention_capable is True)
                / len(samples),
                4,
            ) if samples else None,
            "entity_retention_snapshot_count_start": (
                samples[0].entity_retention_snapshot_count
            ),
            "entity_retention_snapshot_count_end": (
                samples[-1].entity_retention_snapshot_count
            ),
            "entity_integrity_status_final": samples[-1].entity_integrity_status,
            "entity_integrity_issue_count_start": (
                samples[0].entity_integrity_issue_count
            ),
            "entity_integrity_issue_count_end": (
                samples[-1].entity_integrity_issue_count
            ),
            "max_entity_integrity_issue_count": _max(entity_issue_counts),
            # 4. Report timing
            "avg_trust_report_duration_ms": _avg(trust_rpt),
            "max_trust_report_duration_ms": _max(trust_rpt),
            "avg_burnin_report_duration_ms": _avg(burnin_rpt),
            "max_burnin_report_duration_ms": _max(burnin_rpt),
            # 5. Graph growth
            "graph_node_count_start": (
                int(node_counts[0]) if node_counts else None
            ),
            "graph_node_count_end": (
                int(node_counts[-1]) if node_counts else None
            ),
            "graph_edge_count_start": (
                int(edge_counts[0]) if edge_counts else None
            ),
            "graph_edge_count_end": (
                int(edge_counts[-1]) if edge_counts else None
            ),
            "avg_graph_generation_time_ms": _avg(graph_times),
            "max_graph_generation_time_ms": _max(graph_times),
        }
    else:
        summary = {}

    report = BurnInReport(
        duration_hours=duration_hours,
        start_time=datetime.fromtimestamp(
            start_ts, tz=timezone.utc
        ).isoformat(),
        end_time=datetime.fromtimestamp(
            time.time(), tz=timezone.utc
        ).isoformat(),
        sample_count=len(samples),
        samples=[asdict(s) for s in samples],
        summary=summary,
    )

    if output_file:
        Path(output_file).write_text(
            json.dumps(report.to_dict(), indent=2) + "\n"
        )
        print(f"Report written to {output_file}")

    print(f"Burn-in complete. Samples: {len(samples)}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Long-duration burn-in runner (24h, 72h, 168h)",
    )
    parser.add_argument(
        "--duration",
        choices=["24h", "72h", "168h"],
        default="24h",
        help="Burn-in duration",
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="UAR API base URL",
    )
    parser.add_argument(
        "--api-key",
        default="dev-key-12345",
        help="API key",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Sampling interval in seconds (default: 300 = 5min)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file (default: auto-generated)",
    )
    args = parser.parse_args()

    duration_hours = int(args.duration[:-1])

    report_dir = Path("reports/burnin")
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = args.output or str(
        report_dir / f"burnin_{args.duration}_{timestamp}.json"
    )

    try:
        run_burnin(
            duration_hours=duration_hours,
            api_url=args.api_url,
            api_key=args.api_key,
            interval_seconds=args.interval,
            output_file=output_file,
        )
    except KeyboardInterrupt:
        print("\nBurn-in interrupted by user.")
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
