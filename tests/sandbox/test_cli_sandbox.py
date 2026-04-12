"""CLI tests with the sandbox vocabulary registered.

The CLI auto-loads the sandbox vocabulary at startup via
_load_default_vocabulary(), so these subprocess tests work without any
special environment variables.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "src" / "umwelt" / "_fixtures"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "umwelt.cli", *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# parse command
# ---------------------------------------------------------------------------


def test_parse_minimal():
    result = _run("parse", str(FIXTURES / "minimal.umw"))
    assert result.returncode == 0, result.stderr
    assert "file" in result.stdout
    assert "editable" in result.stdout


def test_parse_auth_fix():
    result = _run("parse", str(FIXTURES / "auth-fix.umw"))
    assert result.returncode == 0, result.stderr
    assert "hook" in result.stdout or "run" in result.stdout


def test_parse_actor_conditioned():
    result = _run("parse", str(FIXTURES / "actor-conditioned.umw"))
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# inspect command
# ---------------------------------------------------------------------------


def test_inspect_minimal():
    result = _run("inspect", str(FIXTURES / "minimal.umw"))
    assert result.returncode == 0, result.stderr
    assert "1 rule" in result.stdout


def test_inspect_auth_fix():
    result = _run("inspect", str(FIXTURES / "auth-fix.umw"))
    assert result.returncode == 0, result.stderr
    assert "rule" in result.stdout
    assert "editable" in result.stdout


# ---------------------------------------------------------------------------
# check command
# ---------------------------------------------------------------------------


def test_check_minimal():
    result = _run("check", str(FIXTURES / "minimal.umw"))
    assert result.returncode == 0, result.stderr


def test_check_auth_fix():
    result = _run("check", str(FIXTURES / "auth-fix.umw"))
    assert result.returncode == 0, result.stderr
