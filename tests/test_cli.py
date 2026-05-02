import subprocess


def test_cli_runs():
    result = subprocess.run(
        ["python", "-m", "uar.cli.run", "--goal", "test"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Run status" in result.stdout
