"""Tests for the umwelt check subcommand."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "toy.umw"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["UMWELT_PRELOAD_TOY"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "umwelt.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_check_clean_fixture_exits_zero():
    result = _run(["check", str(FIXTURE)])
    assert result.returncode == 0, result.stderr


def test_check_reports_rule_count():
    result = _run(["check", str(FIXTURE)])
    assert "3 rule" in result.stdout or "3 rules" in result.stdout


def test_check_notes_zero_compilers_in_core():
    result = _run(["check", str(FIXTURE)])
    assert "0 compilers" in result.stdout or "no compilers" in result.stdout.lower()


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
