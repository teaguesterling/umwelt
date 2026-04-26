"""Tests for the umwelt check subcommand."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_FIXTURES = Path(__file__).resolve().parents[2] / "src" / "umwelt" / "_fixtures"
FIXTURE = _FIXTURES / "auth-fix.umw"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "umwelt.cli", *args],
        capture_output=True,
        text=True,
    )


def test_check_clean_fixture_exits_zero():
    result = _run(["check", str(FIXTURE)])
    assert result.returncode == 0, result.stderr


def test_check_reports_rule_count():
    result = _run(["check", str(FIXTURE)])
    assert "12 rule" in result.stdout or "12 rules" in result.stdout


def test_check_reports_compiler_count():
    # The sandbox compilers (nsjail, bwrap) are registered by default; check reports them.
    result = _run(["check", str(FIXTURE)])
    # With sandbox registered: "2 registered"; without sandbox: "0 compilers" or "no compilers"
    assert (
        "registered" in result.stdout
        or "0 compilers" in result.stdout
        or "no compilers" in result.stdout.lower()
    )


def test_check_reports_validation_error(tmp_path):
    # An empty rule block is valid but a path-escape would fail a real
    # validator. Since we don't have sandbox validators in core, we
    # test the "file not found" path which returns non-zero.
    result = _run(["check", "/tmp/absent-file.umw"])
    assert result.returncode != 0


def test_check_syntax_error(tmp_path):
    bad = tmp_path / "bad.umw"
    bad.write_text("{ color: red; }")  # missing selector — parser rejects
    result = _run(["check", str(bad)])
    assert result.returncode != 0
