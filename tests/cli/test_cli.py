import subprocess
import sys


def test_cli_runs():
    result = subprocess.run(
        [sys.executable, "-m", "uar.cli.run", "run", "--goal", "test"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Run status" in result.stdout
