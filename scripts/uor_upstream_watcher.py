#!/usr/bin/env python3
"""UOR Upstream Release Watcher - Monitor and auto-refresh pinned artifacts.

This script polls the UOR-Foundation GitHub releases API for new versions
and can optionally auto-refresh the pinned artifacts when a new release
is detected.

Usage:
    python scripts/uor_upstream_watcher.py [--interval SECONDS] [--auto-refresh]
    python scripts/uor_upstream_watcher.py check [--tag v0.5.2]
    python scripts/uor_upstream_watcher.py refresh [--tag v0.5.3] [--sign]

Environment:
    UOR_WATCH_INTERVAL: Polling interval in seconds (default: 3600)
    UOR_AUTO_REFRESH: Enable auto-refresh on new releases (default: false)
    GITHUB_TOKEN: GitHub API token for higher rate limits (optional)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.request import Request, urlopen

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
UOR_DIR = ROOT / "third_party" / "uor"
VERSION_PATH = UOR_DIR / "VERSION"
DIGESTS_PATH = UOR_DIR / " "
CACHE_DIR = UOR_DIR / "cache"

UPSTREAM_REPO = "UOR-Foundation/UOR-Framework"
GITHUB_API_URL = f"https://api.github.com/repos/{UPSTREAM_REPO}/releases"


def get_github_token() -> Optional[str]:
    """Get GitHub token from environment."""
    return os.getenv("GITHUB_TOKEN")


def make_api_request(url: str) -> Dict[str, Any]:
    """Make authenticated API request if token available."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "UAR-Upstream-Watcher/1.0"
    }
    token = get_github_token()
    if token:
        headers["Authorization"] = f"token {token}"

    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"API request failed: {e}")
        raise


def get_latest_release() -> Optional[Dict[str, Any]]:
    """Get the latest UOR-Framework release from GitHub."""
    try:
        data = make_api_request(GITHUB_API_URL + "/latest")
        return {
            "tag": data.get("tag_name"),
            "published": data.get("published_at"),
            "url": data.get("html_url"),
            "assets": [
                {
                    "name": a.get("name"),
                    "url": a.get("browser_download_url"),
                    "size": a.get("size"),
                }
                for a in data.get("assets", [])
            ],
        }
    except Exception as e:
        logger.error(f"Failed to fetch latest release: {e}")
        return None


def get_local_version() -> Optional[str]:
    """Get the currently pinned UOR version."""
    if not VERSION_PATH.exists():
        return None
    return VERSION_PATH.read_text().strip()


def check_for_update() -> Optional[Dict[str, Any]]:
    """Check if an update is available.

    Returns None if no update, or dict with update info if available.
    """
    local = get_local_version()
    latest = get_latest_release()

    if not latest:
        logger.error("Could not determine latest upstream version")
        return None

    upstream_tag = latest["tag"]

    if not local:
        logger.warning("No local version recorded - treating as fresh install")
        return {
            "action": "install",
            "from": None,
            "to": upstream_tag,
            "release": latest,
        }

    if local == upstream_tag:
        logger.info(f"Up to date: {local}")
        return None

    logger.info(f"Update available: {local} -> {upstream_tag}")
    return {
        "action": "update",
        "from": local,
        "to": upstream_tag,
        "release": latest,
    }


def refresh_artifacts(tag: str, sign: bool = False) -> bool:
    """Refresh pinned artifacts to a new version.

    Args:
        tag: The release tag to fetch
        sign: Whether to generate signed manifest (future feature)

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Refreshing artifacts to {tag}")

    # Call the fetch script
    fetch_script = ROOT / "scripts" / "fetch_uor_artifacts.py"
    if not fetch_script.exists():
        logger.error(f"Fetch script not found: {fetch_script}")
        return False

    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(fetch_script), "--tag", tag],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(result.stdout)
        if sign:
            logger.info("Signing requested but not yet implemented")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Artifact refresh failed: {e}")
        logger.error(f"stderr: {e.stderr}")
        return False


def run_validation(tag: str) -> bool:
    """Run validation against the refreshed artifacts."""
    logger.info(f"Running validation for {tag}")

    validate_script = ROOT / "scripts" / "validate_uor_alignment.py"
    if not validate_script.exists():
        logger.error(f"Validation script not found: {validate_script}")
        return False

    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(validate_script), "--tag", tag],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Validation failed: {e}")
        logger.error(f"stderr: {e.stderr}")
        return False


def cmd_check(args: argparse.Namespace) -> int:
    """Check command - single check for updates."""
    if args.tag:
        # Check specific tag
        logger.info(f"Checking specific tag: {args.tag}")
        local = get_local_version()
        if local == args.tag:
            print(f"Local version matches: {args.tag}")
            return 0
        else:
            print(f"Mismatch: local={local}, requested={args.tag}")
            return 1

    update = check_for_update()
    if update:
        print(json.dumps(update, indent=2))
        return 0 if args.json else 1  # Exit 1 means "update available"
    else:
        print("No update available")
        return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    """Refresh command - manually refresh to a specific version."""
    tag = args.tag
    if not tag:
        # Get latest
        latest = get_latest_release()
        if not latest:
            logger.error("Could not determine latest version")
            return 1
        tag = latest["tag"]

    logger.info(f"Refreshing to {tag}")

    if not refresh_artifacts(tag, sign=args.sign):
        return 1

    if args.validate:
        if not run_validation(tag):
            return 1

    print(f"Successfully refreshed to {tag}")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Watch command - continuous monitoring loop."""
    interval = args.interval or int(os.getenv("UOR_WATCH_INTERVAL", "3600"))
    auto_refresh = args.auto_refresh or os.getenv(
        "UOR_AUTO_REFRESH", ""
    ).lower() in ("true", "1", "yes")

    logger.info(f"Starting watcher (interval={interval}s, auto_refresh={auto_refresh})")

    while True:
        try:
            update = check_for_update()
            if update:
                logger.info(f"Update detected: {update['from']} -> {update['to']}")

                if auto_refresh:
                    logger.info("Auto-refresh enabled - refreshing artifacts")
                    if refresh_artifacts(update["to"]):
                        run_validation(update["to"])
                    else:
                        logger.error("Auto-refresh failed - manual intervention needed")
                else:
                    logger.info("Auto-refresh disabled - manual refresh required")

            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Watcher stopped")
            return 0
        except Exception as e:
            logger.error(f"Watcher error: {e}")
            time.sleep(60)  # Short sleep on error


def main() -> int:
    parser = argparse.ArgumentParser(
        description="UOR Upstream Release Watcher"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Check command
    check_parser = subparsers.add_parser(
        "check", help="Check for available updates"
    )
    check_parser.add_argument(
        "--tag", help="Check specific tag instead of latest"
    )
    check_parser.add_argument(
        "--json", action="store_true", help="Output JSON format"
    )
    check_parser.set_defaults(func=cmd_check)

    # Refresh command
    refresh_parser = subparsers.add_parser(
        "refresh", help="Refresh artifacts to a version"
    )
    refresh_parser.add_argument(
        "--tag", help="Tag to refresh to (default: latest)"
    )
    refresh_parser.add_argument(
        "--sign", action="store_true",
        help="Generate signed manifest (placeholder)"
    )
    refresh_parser.add_argument(
        "--validate", action="store_true", default=True,
        help="Run validation after refresh (default: true)"
    )
    refresh_parser.set_defaults(func=cmd_refresh)

    # Watch command
    watch_parser = subparsers.add_parser(
        "watch", help="Continuously monitor for updates"
    )
    watch_parser.add_argument(
        "--interval", type=int,
        help="Polling interval in seconds (default: 3600)"
    )
    watch_parser.add_argument(
        "--auto-refresh", action="store_true",
        help="Automatically refresh on new releases"
    )
    watch_parser.set_defaults(func=cmd_watch)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
