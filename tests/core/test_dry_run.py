"""Tests for the umwelt dry-run subcommand."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "toy.umw"


def _run(args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["UMWELT_PRELOAD_TOY"] = "1"
    env["UMWELT_PRELOAD_TOY_THINGS"] = "alpha:red,beta:blue"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "umwelt.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_dry_run_reports_resolved_properties():
    result = _run(["dry-run", str(FIXTURE)])
    assert result.returncode == 0, result.stderr
    # The fixture sets paint=crimson for alpha and paint=navy for beta
    # (thing[color="blue"]). The dry-run should surface this.
    assert "alpha" in result.stdout
    assert "crimson" in result.stdout
    assert "navy" in result.stdout


def test_dry_run_reports_shared_max_glow():
    result = _run(["dry-run", str(FIXTURE)])
    assert result.returncode == 0
    assert "max-glow" in result.stdout
    assert "100" in result.stdout


def test_dry_run_no_matches_reports_empty(tmp_path):
    empty = tmp_path / "empty.umw"
    empty.write_text("thing#never { paint: void; }")
    result = _run(["dry-run", str(empty)])
    assert result.returncode == 0
    assert "(no matches)" in result.stdout or "0 entities" in result.stdout
