#!/usr/bin/env python3
"""G.5 Operational Evidence Pack — Master Generator.

Generates a reproducible evidence bundle that answers:
- Is the platform healthy?
- Is the trust model behaving?
- Is the learning freeze intact?
- Is operational intelligence producing signal?

Usage:
    python scripts/hardening/generate_evidence_pack.py
        [--api-url URL] [--api-key KEY]
        [--archive] [--no-archive]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO_ROOT / "reports" / "evidence"
LATEST_DIR = EVIDENCE_DIR / "latest"
ARCHIVE_DIR = EVIDENCE_DIR / "archives"
FREEZE_BASELINE = EVIDENCE_DIR / ".freeze_baseline.json"

FROZEN_FILES = [
    REPO_ROOT / "uar" / "core" / "operational_learning.py",
    REPO_ROOT / "uar" / "core" / "adaptive_confidence.py",
    REPO_ROOT / "uar" / "core" / "trust_engine.py",
    REPO_ROOT / "uar" / "core" / "trust_ranking.py",
]

SCRIPT_DIR = REPO_ROOT / "scripts" / "hardening"
WEB_DIR = REPO_ROOT / "apps" / "web"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _run_subprocess(
    cmd: List[str],
    cwd: Optional[Path] = None,
    timeout: int = 300,
    capture: bool = True,
) -> Dict[str, Any]:
    """Run a subprocess and return structured result."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else str(REPO_ROOT),
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Timed out after {timeout}s",
            "timed_out": True,
        }
    except Exception as exc:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "timed_out": False,
        }


def _write_report(name: str, content: str) -> Path:
    """Write a markdown report to the latest evidence directory."""
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    path = LATEST_DIR / f"{name}.md"
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# 1. Trust Validation
# ---------------------------------------------------------------------------
def run_trust_validation(
    api_url: Optional[str], api_key: Optional[str]
) -> Dict[str, Any]:
    script = SCRIPT_DIR / "trust_validation_report.py"
    output = LATEST_DIR / "trust_validation.md"
    cmd = [sys.executable, str(script), "--output", str(output)]
    if api_url:
        cmd += ["--api-url", api_url]
    if api_key:
        cmd += ["--api-key", api_key]

    result = _run_subprocess(cmd, capture=True)
    ok = result["returncode"] == 0
    if not ok and not output.exists():
        fallback = (
            f"# Trust Validation Report\n\n"
            f"**Generated:** {_now()}\n"
            f"**Status:** DEGRADED (API unavailable)\n\n"
            f"## Error\n\n"
            f"```\n{result['stderr'][-500:]}\n```\n"
        )
        LATEST_DIR.mkdir(parents=True, exist_ok=True)
        output.write_text(fallback)
    return {
        "status": "PASS" if ok else "FAIL",
        "file": str(output.relative_to(REPO_ROOT)),
        "stdout": result["stdout"][-500:] if result["stdout"] else "",
        "stderr": result["stderr"][-500:] if result["stderr"] else "",
    }


# ---------------------------------------------------------------------------
# 2. Burn-In Comparison
# ---------------------------------------------------------------------------
def run_burnin_comparison(
    api_url: Optional[str], api_key: Optional[str]
) -> Dict[str, Any]:
    script = SCRIPT_DIR / "burnin_comparison.py"
    output = LATEST_DIR / "burnin_comparison.md"
    cmd = [sys.executable, str(script), "--output", str(output)]
    if api_url:
        cmd += ["--api-url", api_url]
    if api_key:
        cmd += ["--api-key", api_key]

    result = _run_subprocess(cmd, capture=True)
    ok = result["returncode"] == 0
    if not ok and not output.exists():
        fallback = (
            f"# Burn-In Comparison\n\n"
            f"**Generated:** {_now()}\n"
            f"**Status:** DEGRADED (API unavailable)\n\n"
            f"## Error\n\n"
            f"```\n{result['stderr'][-500:]}\n```\n"
        )
        LATEST_DIR.mkdir(parents=True, exist_ok=True)
        output.write_text(fallback)
    return {
        "status": "PASS" if ok else "FAIL",
        "file": str(output.relative_to(REPO_ROOT)),
        "stdout": result["stdout"][-500:] if result["stdout"] else "",
        "stderr": result["stderr"][-500:] if result["stderr"] else "",
    }


# ---------------------------------------------------------------------------
# 3. Alert Accuracy
# ---------------------------------------------------------------------------
def run_alert_accuracy(hours: int = 168) -> Dict[str, Any]:
    script = SCRIPT_DIR / "alert_accuracy_report.py"
    output = LATEST_DIR / "alert_accuracy.md"
    cmd = [
        sys.executable,
        str(script),
        "--hours",
        str(hours),
        "--output",
        str(output),
    ]

    result = _run_subprocess(cmd, capture=True)
    ok = result["returncode"] == 0
    return {
        "status": "PASS" if ok else "FAIL",
        "file": str(output.relative_to(REPO_ROOT)),
        "stdout": result["stdout"][-500:] if result["stdout"] else "",
        "stderr": result["stderr"][-500:] if result["stderr"] else "",
    }


# ---------------------------------------------------------------------------
# 4. Insight Report (aggregate API endpoints)
# ---------------------------------------------------------------------------
def fetch_insights(
    api_url: Optional[str], api_key: Optional[str]
) -> Dict[str, Any]:
    endpoints = [
        "/api/uar/insights/patterns",
        "/api/uar/insights/evolution",
        "/api/uar/insights/workflows",
        "/api/uar/insights/clusters",
        "/api/uar/insights/operator-intelligence",
    ]

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    base_url = (api_url or "http://localhost:8000").rstrip("/")
    findings: Dict[str, Any] = {}
    errors: List[str] = []

    try:
        import requests
    except ImportError:
        return {
            "status": "SKIP",
            "reason": "requests not installed",
            "findings": {},
        }

    for endpoint in endpoints:
        name = endpoint.split("/")[-1]
        try:
            resp = requests.get(
                f"{base_url}{endpoint}",
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 200:
                findings[name] = resp.json()
            else:
                errors.append(f"{name}: HTTP {resp.status_code}")
                findings[name] = {"error": f"HTTP {resp.status_code}"}
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            findings[name] = {"error": str(exc)}

    # Build markdown report
    lines = [
        "# Insight Report",
        "",
        f"**Generated:** {_now()}",
        f"**API Base:** {base_url}",
        "",
        "## Endpoints",
        "",
    ]
    for name, data in findings.items():
        status = "✅" if "error" not in data else "❌"
        lines.append(f"### {status} {name}")
        lines.append("")
        if "error" not in data:
            lines.append(f"- **Narrative:** {data.get('narrative', 'N/A')}")
            for k, v in data.items():
                if k in (
                    "narrative",
                    "generated_at",
                    "insight_type",
                    "pattern_type",
                ):
                    continue
                if isinstance(v, (list, dict)):
                    v = json.dumps(v, indent=2)[:300] + "..."
                lines.append(f"- **{k}:** {v}")
        else:
            lines.append(f"- **Error:** {data['error']}")
        lines.append("")

    if errors:
        lines.append("## Errors")
        lines.append("")
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    _write_report("insight_report", "\n".join(lines))

    return {
        "status": "PASS" if not errors else "PARTIAL",
        "errors": errors,
        "endpoints_checked": len(endpoints),
    }


# ---------------------------------------------------------------------------
# 5. Freeze Verification
# ---------------------------------------------------------------------------
def verify_freeze() -> Dict[str, Any]:
    current = {}
    for path in FROZEN_FILES:
        if path.exists():
            current[str(path.relative_to(REPO_ROOT))] = _sha256_file(path)
        else:
            current[str(path.relative_to(REPO_ROOT))] = "FILE_NOT_FOUND"

    if FREEZE_BASELINE.exists():
        baseline = json.loads(FREEZE_BASELINE.read_text())
        mismatches = []
        for filepath, current_hash in current.items():
            baseline_hash = baseline.get("files", {}).get(filepath)
            if baseline_hash != current_hash:
                mismatches.append(
                    {
                        "file": filepath,
                        "baseline": baseline_hash,
                        "current": current_hash,
                    }
                )

        status = "PASS" if not mismatches else "FAIL"
        lines = [
            "# Freeze Verification",
            "",
            f"**Generated:** {_now()}",
            f"**Baseline:** {baseline.get('timestamp', 'unknown')}",
            f"**Status:** {status}",
            "",
            "## Files Checked",
            "",
            "| File | Baseline | Current | Status |",
            "|---|---|---|---|",
        ]
        for filepath, current_hash in sorted(current.items()):
            baseline_hash = baseline.get("files", {}).get(filepath, "N/A")
            match = "✅" if baseline_hash == current_hash else "❌"
            lines.append(
                f"| {filepath} | `{baseline_hash[:16]}...` | "
                f"`{current_hash[:16]}...` | {match} |"
            )
        lines.append("")

        if mismatches:
            lines.append("## Mismatches")
            lines.append("")
            for m in mismatches:
                lines.append(f"- **{m['file']}** changed since baseline")
            lines.append("")
    else:
        # Establish baseline
        baseline = {
            "timestamp": _now(),
            "files": current,
        }
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        FREEZE_BASELINE.write_text(json.dumps(baseline, indent=2) + "\n")
        status = "BASELINE_ESTABLISHED"
        lines = [
            "# Freeze Verification",
            "",
            f"**Generated:** {_now()}",
            f"**Status:** {status}",
            "",
            "## Baseline Established",
            "",
            "This is the first freeze verification run. The current hashes "
            "have been saved as the baseline for future comparisons.",
            "",
            "| File | Hash |",
            "|---|---|",
        ]
        for filepath, h in sorted(current.items()):
            lines.append(f"| {filepath} | `{h}` |")
        lines.append("")

    _write_report("freeze_verification", "\n".join(lines))
    return {
        "status": status,
        "mismatches": len(mismatches)
        if FREEZE_BASELINE.exists() and status != "BASELINE_ESTABLISHED"
        else 0,
    }


# ---------------------------------------------------------------------------
# 6. Security Status
# ---------------------------------------------------------------------------
def check_security() -> Dict[str, Any]:
    results: Dict[str, Any] = {"npm": {}, "pip": {}}

    # npm audit
    npm_result = _run_subprocess(
        ["npm", "audit", "--json"],
        cwd=WEB_DIR,
        timeout=60,
    )
    npm_vulns: Dict[str, int] = {
        "critical": 0,
        "high": 0,
        "moderate": 0,
        "low": 0,
        "info": 0,
    }
    npm_ok = False
    if npm_result["returncode"] == 0:
        npm_ok = True
    else:
        try:
            audit_data = json.loads(npm_result["stdout"] or "{}")
            vulns = audit_data.get("vulnerabilities", {})
            for vid, vdata in vulns.items():
                sev = vdata.get("severity", "unknown")
                npm_vulns[sev] = npm_vulns.get(sev, 0) + 1
        except Exception:
            pass

    results["npm"] = {
        "ok": npm_ok,
        "vulnerabilities": npm_vulns,
        "stdout": npm_result["stdout"][-300:] if npm_result["stdout"] else "",
        "stderr": npm_result["stderr"][-300:] if npm_result["stderr"] else "",
    }

    # pip audit (or fallback)
    pip_result = _run_subprocess(
        [sys.executable, "-m", "pip_audit", "--format=json"],
        timeout=120,
    )
    pip_vulns: Dict[str, int] = {
        "critical": 0,
        "high": 0,
        "moderate": 0,
        "low": 0,
    }
    pip_ok = False
    if pip_result["returncode"] == 0:
        pip_ok = True
    else:
        # Try to parse JSON output
        try:
            audit_data = json.loads(pip_result["stdout"] or "{}")
            for entry in audit_data:
                sev = entry.get("vulnerability", {}).get("severity", "unknown")
                pip_vulns[sev] = pip_vulns.get(sev, 0) + 1
        except Exception:
            pass

    stderr_text = pip_result["stderr"] or ""
    results["pip"] = {
        "ok": pip_ok,
        "vulnerabilities": pip_vulns,
        "available": "No module named" not in stderr_text
        and "pip_audit" not in stderr_text,
    }

    # Generate markdown
    lines = [
        "# Security Status",
        "",
        f"**Generated:** {_now()}",
        "",
        "## npm (apps/web)",
        "",
    ]
    if results["npm"]["ok"]:
        lines.append("- **Status:** ✅ No vulnerabilities found")
    else:
        lines.append("- **Status:** ⚠️ Vulnerabilities detected")
        for sev, count in results["npm"]["vulnerabilities"].items():
            if count > 0:
                lines.append(f"  - {sev.capitalize()}: {count}")
    lines.append("")

    lines.append("## Python Dependencies")
    lines.append("")
    if not results["pip"]["available"]:
        lines.append(
            "- **Status:** ⚠️ `pip-audit` not installed — run "
            "`pip install pip-audit`"
        )
    elif results["pip"]["ok"]:
        lines.append("- **Status:** ✅ No vulnerabilities found")
    else:
        lines.append("- **Status:** ⚠️ Vulnerabilities detected")
        for sev, count in results["pip"]["vulnerabilities"].items():
            if count > 0:
                lines.append(f"  - {sev.capitalize()}: {count}")
    lines.append("")

    overall = "PASS"
    if not results["npm"]["ok"]:
        overall = "FAIL"
    if results["pip"]["available"] and not results["pip"]["ok"]:
        overall = "FAIL"

    lines.append(f"## Overall: {overall}")
    lines.append("")

    _write_report("security_status", "\n".join(lines))
    return {
        "status": overall,
        "npm": results["npm"],
        "pip": results["pip"],
    }


# ---------------------------------------------------------------------------
# 7. Test Summary
# ---------------------------------------------------------------------------
def run_tests() -> Dict[str, Any]:
    # Python tests
    pytest_result = _run_subprocess(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/api/",
            "-x",
            "--no-header",
            "-q",
        ],
        timeout=120,
    )
    pytest_passed = 0
    pytest_failed = 0
    pytest_skipped = 0
    if pytest_result["stdout"]:
        import re

        m = re.search(
            r"(\d+) passed.*?,(\d+) failed.*?,(\d+) skipped",
            pytest_result["stdout"],
        )
        if m:
            pytest_passed = int(m.group(1))
            pytest_failed = int(m.group(2))
            pytest_skipped = int(m.group(3))
        else:
            m = re.search(r"(\d+) passed", pytest_result["stdout"])
            if m:
                pytest_passed = int(m.group(1))

    # npm tests
    npm_result = _run_subprocess(
        ["npm", "test", "--", "--run"],
        cwd=WEB_DIR,
        timeout=120,
    )
    npm_ok = npm_result["returncode"] == 0
    pytest_status = (
        "✅ PASS" if pytest_failed == 0 and pytest_passed > 0 else "❌ FAIL"
    )

    lines = [
        "# Test Summary",
        "",
        f"**Generated:** {_now()}",
        "",
        "## Python (pytest)",
        "",
        f"- **Passed:** {pytest_passed}",
        f"- **Failed:** {pytest_failed}",
        f"- **Skipped:** {pytest_skipped}",
        f"- **Status:** {pytest_status}",
        "",
        "## JavaScript (npm test)",
        "",
    ]
    if npm_ok:
        lines.append("- **Status:** ✅ PASS")
    else:
        lines.append("- **Status:** ❌ FAIL or no tests")
    lines.append("")

    overall = (
        "PASS"
        if (pytest_failed == 0 and pytest_passed > 0 and npm_ok)
        else "FAIL"
    )
    lines.append(f"## Overall: {overall}")
    lines.append("")

    _write_report("test_summary", "\n".join(lines))
    return {
        "status": overall,
        "pytest": {
            "passed": pytest_passed,
            "failed": pytest_failed,
            "skipped": pytest_skipped,
        },
        "npm": {"ok": npm_ok},
    }


# ---------------------------------------------------------------------------
# 8. Phase G Summary
# ---------------------------------------------------------------------------
def generate_phase_g_summary(results: Dict[str, Any]) -> str:
    lines = [
        "# Phase G Summary",
        "",
        f"**Generated:** {_now()}",
        "**Evidence Pack:** `reports/evidence/latest/`",
        "",
        "## Completed",
        "",
        "- ✅ G.1 Hygiene",
        "- ✅ G.2 Security",
        "- ✅ G.3 Router Decomposition",
        "- ✅ G.4 Navigation Refactor",
        "- ✅ G.5 Evidence Pack",
        "- ✅ G.6 Freeze Verification",
        "",
        "## Pending",
        "",
        "- ⏳ G.7 Long Burn-In",
        "",
        "## Evidence Pack Results",
        "",
        "| Report | Status | Notes |",
        "|---|---|---|",
    ]
    for key, val in results.items():
        status = val.get("status", "UNKNOWN")
        notes = ""
        if "mismatches" in val:
            notes = (
                f"{val['mismatches']} mismatch(es)"
                if val["mismatches"]
                else "Clean"
            )
        elif "pytest" in val:
            p = val["pytest"]
            notes = f"{p['passed']} passed, {p['failed']} failed"
        elif "npm" in val and "vulnerabilities" in val.get("npm", {}):
            npm_v = val["npm"]["vulnerabilities"]
            crit = npm_v.get("critical", 0)
            high = npm_v.get("high", 0)
            notes = f"npm {crit}C/{high}H"
        elif "errors" in val:
            notes = f"{len(val['errors'])} error(s)"
        lines.append(f"| {key} | {status} | {notes} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*This summary is auto-generated by "
        "`scripts/hardening/generate_evidence_pack.py`."
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 9. Archive
# ---------------------------------------------------------------------------
def archive_evidence_pack() -> Path:
    archive_name = f"evidence_pack_{_timestamp()}"
    dest = ARCHIVE_DIR / archive_name
    if LATEST_DIR.exists():
        shutil.copytree(LATEST_DIR, dest, dirs_exist_ok=True)
    return dest


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="G.5 Operational Evidence Pack Generator",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("UAR_API_URL", "http://localhost:8000"),
        help="UAR API base URL",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("UAR_API_KEY", ""),
        help="UAR API key",
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Skip archiving to reports/evidence/archives/",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        default=[],
        choices=[
            "trust",
            "burnin",
            "alerts",
            "insights",
            "freeze",
            "security",
            "tests",
        ],
        help="Skip specific report sections",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(" G.5 Operational Evidence Pack Generator")
    print("=" * 60)
    print()

    # Setup directories
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    results: Dict[str, Any] = {}

    # 1. Trust Validation
    if "trust" not in args.skip:
        print("[1/7] Trust Validation...")
        results["trust_validation"] = run_trust_validation(
            args.api_url or None, args.api_key or None
        )
        print(f"      → {results['trust_validation']['status']}")

    # 2. Burn-In Comparison
    if "burnin" not in args.skip:
        print("[2/7] Burn-In Comparison...")
        results["burnin_comparison"] = run_burnin_comparison(
            args.api_url or None, args.api_key or None
        )
        print(f"      → {results['burnin_comparison']['status']}")

    # 3. Alert Accuracy
    if "alerts" not in args.skip:
        print("[3/7] Alert Accuracy...")
        results["alert_accuracy"] = run_alert_accuracy()
        print(f"      → {results['alert_accuracy']['status']}")

    # 4. Insights
    if "insights" not in args.skip:
        print("[4/7] Insight Report...")
        results["insight_report"] = fetch_insights(
            args.api_url or None, args.api_key or None
        )
        print(f"      → {results['insight_report']['status']}")

    # 5. Freeze Verification
    if "freeze" not in args.skip:
        print("[5/7] Freeze Verification...")
        results["freeze_verification"] = verify_freeze()
        print(f"      → {results['freeze_verification']['status']}")

    # 6. Security Status
    if "security" not in args.skip:
        print("[6/7] Security Status...")
        results["security_status"] = check_security()
        print(f"      → {results['security_status']['status']}")

    # 7. Test Summary
    if "tests" not in args.skip:
        print("[7/7] Test Summary...")
        results["test_summary"] = run_tests()
        print(f"      → {results['test_summary']['status']}")

    # Phase G Summary
    print()
    print("Writing phase_g_summary.md...")
    summary_md = generate_phase_g_summary(results)
    _write_report("phase_g_summary", summary_md)

    # Archive
    if not args.no_archive:
        print("Archiving evidence pack...")
        archive_path = archive_evidence_pack()
        print(f"  → {archive_path.relative_to(REPO_ROOT)}")

    print()
    print("=" * 60)
    print(" Evidence pack complete.")
    print(f" Latest: {LATEST_DIR.relative_to(REPO_ROOT)}")
    if not args.no_archive:
        print(f" Archive: {archive_path.relative_to(REPO_ROOT)}")
    print("=" * 60)

    # Exit code: 0 if all PASS, 1 otherwise
    all_pass = all(
        r.get("status", "").startswith(("PASS", "BASELINE"))
        for r in results.values()
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
