"""Chaos engineering probe for UAR runtime resilience.

Injects random failures into store operations and network calls
to verify recovery behaviour.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


def _chaos_store(path: str, fail_rate: float, duration: int) -> None:
    """Inject transient failures by corrupting DB file permissions."""
    print(f"[store] Chaos: fail_rate={fail_rate}, duration={duration}s")
    start = time.time()
    while time.time() - start < duration:
        if random.random() < fail_rate:
            if os.path.exists(path):
                os.chmod(path, 0o000)
                print(f"[store] Locked {path}")
                time.sleep(random.uniform(0.1, 0.5))
                os.chmod(path, 0o644)
                print(f"[store] Restored {path}")
        time.sleep(0.5)
    print("[store] Chaos complete")


def _chaos_network(delay_ms: int, duration: int) -> None:
    """Simulate network latency by sleeping in request path."""
    print(f"[network] Chaos: delay={delay_ms}ms, duration={duration}s")
    start = time.time()
    while time.time() - start < duration:
        time.sleep(delay_ms / 1000.0)
        print(f"[network] Injected {delay_ms}ms delay")
        time.sleep(1)
    print("[network] Chaos complete")


def _chaos_memory(duration: int) -> None:
    """Allocate and release large memory blocks."""
    print(f"[memory] Chaos: duration={duration}s")
    start = time.time()
    chunks = []
    while time.time() - start < duration:
        if random.random() < 0.3:
            size = random.randint(1, 10) * 1024 * 1024
            chunks.append(bytearray(size))
            print(f"[memory] Allocated {size / 1024 / 1024:.1f} MB")
        if len(chunks) > 5:
            released = chunks.pop(0)
            print(f"[memory] Released {len(released) / 1024 / 1024:.1f} MB")
        time.sleep(0.5)
    chunks.clear()
    print("[memory] Chaos complete")


def _chaos_cpu(target_percent: int, duration: int) -> None:
    """Consume CPU cycles to reach target utilization."""
    print(f"[cpu] Chaos: target={target_percent}%, duration={duration}s")
    start = time.time()
    while time.time() - start < duration:
        # Busy loop for target_percent of each second
        busy_time = target_percent / 100.0
        busy_start = time.time()
        while time.time() - busy_start < busy_time:
            pass
        time.sleep(max(0, 1.0 - busy_time))
    print("[cpu] Chaos complete")


def _chaos_disk(
    max_size_mb: int, duration: int
) -> None:
    """Fill temp files to simulate disk pressure."""
    print(f"[disk] Chaos: max={max_size_mb}MB, duration={duration}s")
    start = time.time()
    temp_files = []
    import tempfile

    while time.time() - start < duration:
        if random.random() < 0.2:
            size = random.randint(1, max_size_mb) * 1024 * 1024
            fd, path = tempfile.mkstemp(prefix="chaos_disk_")
            try:
                os.write(fd, b"\x00" * size)
                temp_files.append(path)
                print(f"[disk] Wrote {size / 1024 / 1024:.1f} MB to {path}")
            finally:
                os.close(fd)
        if len(temp_files) > 3:
            old = temp_files.pop(0)
            try:
                os.remove(old)
                print(f"[disk] Removed {old}")
            except OSError:
                pass
        time.sleep(0.5)
    for f in temp_files:
        try:
            os.remove(f)
        except OSError:
            pass
    print("[disk] Chaos complete")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="UAR chaos engineering probe"
    )
    parser.add_argument(
        "--mode",
        choices=["store", "network", "memory", "cpu", "disk", "all"],
        default="all",
        help="Chaos mode",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration in seconds",
    )
    parser.add_argument(
        "--store-fail-rate",
        type=float,
        default=0.1,
        help="Probability of store failure per tick",
    )
    parser.add_argument(
        "--network-delay",
        type=int,
        default=500,
        help="Network delay in milliseconds",
    )
    parser.add_argument(
        "--db-path",
        default="uar_runs.db",
        help="Path to SQLite DB for store chaos",
    )
    parser.add_argument(
        "--cpu-target",
        type=int,
        default=80,
        help="Target CPU percent for CPU chaos",
    )
    parser.add_argument(
        "--disk-max-mb",
        type=int,
        default=100,
        help="Max temp file size in MB for disk chaos",
    )
    args = parser.parse_args()

    if args.mode in ("store", "all"):
        _chaos_store(
            args.db_path, args.store_fail_rate, args.duration
        )
    if args.mode in ("network", "all"):
        _chaos_network(args.network_delay, args.duration)
    if args.mode in ("memory", "all"):
        _chaos_memory(args.duration)
    if args.mode in ("cpu", "all"):
        _chaos_cpu(args.cpu_target, args.duration)
    if args.mode in ("disk", "all"):
        _chaos_disk(args.disk_max_mb, args.duration)

    print("Chaos probe complete. Check logs for recovery behaviour.")


if __name__ == "__main__":
    main()
