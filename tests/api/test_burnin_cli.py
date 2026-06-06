"""Tests for T4 — Separate Testing (burn-in CLI).

Covers:
- CLI command exists and runs BurnInRunner
- JSON output mode
- Exit code 1 on failure
"""

from __future__ import annotations

from typer.testing import CliRunner

from uar.cli.main import app


runner = CliRunner()


def test_burnin_cli_runs_smoke():
    """uar burn-in run --mode=direct executes without error."""
    result = runner.invoke(
        app, ["burn-in", "run", "--mode=direct", "--suite=smoke"]
    )
    # The CLI runs; actual pass/fail depends on scenario outcomes
    assert result.exit_code in (0, 1), (
        f"Unexpected exit code {result.exit_code}; output:\n{result.output}"
    )
    assert "Running burn-in" in result.output


def test_burnin_cli_json_mode():
    """--json outputs raw JSON report."""
    result = runner.invoke(
        app,
        ["burn-in", "run", "--mode=direct", "--suite=smoke", "--json"],
    )
    assert result.exit_code in (0, 1)
    assert "score" in result.output
    assert "passed" in result.output


def test_burnin_cli_invalid_mode():
    """Invalid mode exits with code 1."""
    result = runner.invoke(
        app, ["burn-in", "run", "--mode=invalid"]
    )
    assert result.exit_code == 1
    assert "Invalid mode" in result.output


def test_burnin_cli_invalid_suite():
    """Invalid suite exits with code 1."""
    result = runner.invoke(
        app, ["burn-in", "run", "--suite=unknown"]
    )
    assert result.exit_code == 1
    assert "Unknown suite" in result.output
