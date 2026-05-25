#!/usr/bin/env python3
"""Download and verify UOR-Framework release artifacts.

Usage:
    python scripts/fetch_uor_artifacts.py --tag v0.5.2

Artifacts and digests are managed in ``third_party/uor``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
UOR_DIR = ROOT / "third_party" / "uor"
DIGESTS_PATH = UOR_DIR / "DIGESTS.json"
VERSION_PATH = UOR_DIR / "VERSION"
CACHE_DIR = UOR_DIR / "cache"
BASE_URL = "https://github.com/UOR-Foundation/UOR-Framework/releases/download"


def load_digests(tag: str) -> dict[str, str]:
    if not DIGESTS_PATH.exists():
        raise SystemExit(f"Missing digests file: {DIGESTS_PATH}")
    data = json.loads(DIGESTS_PATH.read_text())
    if tag not in data:
        raise SystemExit(f"No digests recorded for tag {tag}")
    return data[tag]


def ensure_tag_matches_version(tag: str) -> None:
    if not VERSION_PATH.exists():
        return
    recorded = VERSION_PATH.read_text().strip()
    if recorded and recorded != tag:
        raise SystemExit(
            "Requested tag {tag} does not match recorded version {rec}".format(
                tag=tag,
                rec=recorded,
            )
        )


def download(url: str) -> bytes:
    with urlopen(url) as response:  # nosec: trusted GitHub HTTPS endpoint
        return response.read()


def sha256(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def fetch(tag: str) -> None:
    ensure_tag_matches_version(tag)
    digests = load_digests(tag)
    target_dir = CACHE_DIR / tag
    target_dir.mkdir(parents=True, exist_ok=True)

    for name, expected_digest in digests.items():
        url = f"{BASE_URL}/{tag}/{name}"
        dest = target_dir / name
        print(f"Downloading {url} -> {dest}")
        data = download(url)
        actual = sha256(data)
        if actual != expected_digest:
            raise SystemExit(
                (
                    "Digest mismatch for {name}: expected {expected} "
                    "got {actual}"
                ).format(
                    name=name,
                    expected=expected_digest,
                    actual=actual,
                )
            )
        dest.write_bytes(data)
        print(f"✔ Saved {dest} ({len(data):,} bytes)")

    print(f"All artifacts fetched for {tag} into {target_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tag",
        default=(VERSION_PATH.read_text().strip()),
    )
    args = parser.parse_args(argv)

    if not args.tag:
        parser.error(
            "Tag must be provided via --tag or third_party/uor/VERSION"
        )

    fetch(args.tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
