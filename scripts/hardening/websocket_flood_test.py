#!/usr/bin/env python3
"""Websocket Flood Test — Track 3.

Validates websocket stability under sustained event volume.
Scales: 10x, 50x, 100x baseline event rates.

Monitors:
- Connection success rate
- Message latency (send → ack)
- Reconnect count
- Drop rate
- Memory growth during test

Usage:
    python scripts/hardening/websocket_flood_test.py \
        --api-url ws://localhost:8000 \
        --scale 10x \
        --duration 60

Scales: 10x, 50x, 100x
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import psutil
import websockets


@dataclass
class FloodSample:
    timestamp: float
    connections_open: int
    messages_sent: int
    messages_received: int
    reconnects: int
    latency_ms: float
    rss_mb: float
    cpu_percent: float


@dataclass
class FloodReport:
    scale: str
    duration_seconds: int
    concurrent_connections: int
    start_time: str
    end_time: str
    samples: List[Dict[str, any]] = field(default_factory=list)
    summary: Dict[str, any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, any]:
        return asdict(self)


def get_memory_info() -> tuple[float, float]:
    proc = psutil.Process(os.getpid())
    mem = proc.memory_info()
    cpu = proc.cpu_percent(interval=0.1)
    return mem.rss / 1024 / 1024, cpu


async def _connect_and_echo(
    uri: str,
    api_key: str,
    message_rate: float,
    duration: float,
    results: Dict[str, any],
    conn_id: int,
) -> None:
    """Open one websocket, send messages at given rate, record stats."""
    headers = {"Authorization": f"Bearer {api_key}"}
    sent = 0
    received = 0
    reconnects = 0
    latencies: List[float] = []
    start = time.time()
    deadline = start + duration

    # Initial payload — minimal valid RunRequest
    payload = {
        "goal": {"description": "flood-test", "skills": ["echo"]},
        "user_id": f"flood-{conn_id}",
    }

    while time.time() < deadline:
        try:
            async with websockets.connect(
                uri, extra_headers=headers, open_timeout=5
            ) as ws:
                # Send initial request
                await ws.send(json.dumps(payload))

                # Echo loop
                while time.time() < deadline:
                    t0 = time.time()
                    msg = json.dumps(
                        {
                            "type": "heartbeat",
                            "seq": sent,
                            "ts": t0,
                        }
                    )
                    await ws.send(msg)
                    sent += 1

                    # Wait for any response (or timeout)
                    try:
                        await asyncio.wait_for(ws.recv(), timeout=5.0)
                        received += 1
                        latencies.append((time.time() - t0) * 1000)
                    except asyncio.TimeoutError:
                        pass

                    # Rate limit
                    await asyncio.sleep(1.0 / message_rate)

        except websockets.exceptions.WebSocketException:
            reconnects += 1
            await asyncio.sleep(0.5)
        except Exception:
            reconnects += 1
            await asyncio.sleep(1.0)

    results[conn_id] = {
        "sent": sent,
        "received": received,
        "reconnects": reconnects,
        "latencies": latencies,
    }


async def run_flood(
    api_url: str,
    api_key: str,
    scale: str,
    duration_seconds: int,
    concurrent: int = 5,
) -> FloodReport:
    """Run websocket flood test."""
    scale_map = {"10x": 10.0, "50x": 50.0, "100x": 100.0}
    message_rate = scale_map.get(scale, 10.0)

    # Convert http:// to ws:// if needed
    ws_url = api_url.replace("http://", "ws://").replace("https://", "wss://")
    uri = f"{ws_url}/api/uar/stream/ws"

    start_ts = time.time()
    samples: List[FloodSample] = []
    results: Dict[int, any] = {}

    print(f"Websocket Flood — {scale} @ {message_rate} msg/s per conn")
    print(f"Duration: {duration_seconds}s | Conns: {concurrent}")
    print(f"URI: {uri}")

    # Launch concurrent connections
    tasks = [
        asyncio.create_task(
            _connect_and_echo(
                uri, api_key, message_rate, duration_seconds, results, i
            )
        )
        for i in range(concurrent)
    ]

    # Sampling loop
    sample_deadline = time.time() + duration_seconds
    while time.time() < sample_deadline:
        rss, cpu = get_memory_info()
        total_sent = sum(r.get("sent", 0) for r in results.values())
        total_recv = sum(r.get("received", 0) for r in results.values())
        total_recon = sum(r.get("reconnects", 0) for r in results.values())
        all_lat = [
            lat for r in results.values() for lat in r.get("latencies", [])
        ]
        avg_lat = sum(all_lat) / len(all_lat) if all_lat else 0.0

        sample = FloodSample(
            timestamp=time.time(),
            connections_open=len([t for t in tasks if not t.done()]),
            messages_sent=total_sent,
            messages_received=total_recv,
            reconnects=total_recon,
            latency_ms=round(avg_lat, 1),
            rss_mb=round(rss, 1),
            cpu_percent=round(cpu, 1),
        )
        samples.append(sample)

        elapsed = time.time() - start_ts
        print(
            f"[{elapsed:.0f}s/{duration_seconds}s] "
            f"Sent:{total_sent} Recv:{total_recv} "
            f"Reconn:{total_recon} Lat:{avg_lat:.0f}ms "
            f"RSS:{rss:.0f}MB"
        )

        await asyncio.sleep(5)

    # Wait for all connections to finish
    await asyncio.gather(*tasks, return_exceptions=True)

    # Build summary
    total_sent = sum(r.get("sent", 0) for r in results.values())
    total_recv = sum(r.get("received", 0) for r in results.values())
    total_recon = sum(r.get("reconnects", 0) for r in results.values())
    all_lat = [lat for r in results.values() for lat in r.get("latencies", [])]

    if samples:
        rss_values = [s.rss_mb for s in samples]
        summary = {
            "total_sent": total_sent,
            "total_received": total_recv,
            "total_reconnects": total_recon,
            "drop_rate": round(1 - (total_recv / total_sent), 4)
            if total_sent
            else 0.0,
            "avg_latency_ms": round(sum(all_lat) / len(all_lat), 1)
            if all_lat
            else None,
            "max_latency_ms": round(max(all_lat), 1) if all_lat else None,
            "rss_start_mb": rss_values[0],
            "rss_end_mb": rss_values[-1],
            "rss_growth_mb": round(rss_values[-1] - rss_values[0], 1),
            "rss_peak_mb": max(rss_values),
            "avg_cpu_percent": round(
                sum(s.cpu_percent for s in samples) / len(samples), 1
            ),
        }
    else:
        summary = {}

    return FloodReport(
        scale=scale,
        duration_seconds=duration_seconds,
        concurrent_connections=concurrent,
        start_time=datetime.fromtimestamp(
            start_ts, tz=timezone.utc
        ).isoformat(),
        end_time=datetime.fromtimestamp(
            time.time(), tz=timezone.utc
        ).isoformat(),
        samples=[asdict(s) for s in samples],
        summary=summary,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Websocket flood test (10x/50x/100x)",
    )
    parser.add_argument(
        "--api-url",
        default="ws://127.0.0.1:8000",
        help="UAR API base URL (ws:// or http://)",
    )
    parser.add_argument(
        "--api-key",
        default="dev-key-12345",
        help="API key",
    )
    parser.add_argument(
        "--scale",
        choices=["10x", "50x", "100x"],
        default="10x",
        help="Message rate multiplier",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=5,
        help="Concurrent websocket connections",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file",
    )
    args = parser.parse_args()

    report_dir = Path("reports/burnin")
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = args.output or str(
        report_dir / f"websocket_flood_{args.scale}_{timestamp}.json"
    )

    try:
        report = asyncio.run(
            run_flood(
                api_url=args.api_url,
                api_key=args.api_key,
                scale=args.scale,
                duration_seconds=args.duration,
                concurrent=args.concurrent,
            )
        )
    except KeyboardInterrupt:
        print("\nFlood test interrupted.")
        return 130

    Path(output_file).write_text(json.dumps(report.to_dict(), indent=2) + "\n")
    print(f"Report written to {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
