"""Tests for the umwelt CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Use the sandbox fixture now that the CLI auto-loads the sandbox vocabulary.
_FIXTURES = Path(__file__).resolve().parents[2] / "src" / "umwelt" / "_fixtures"
FIXTURE = _FIXTURES / "minimal.umw"
FIXTURE_AUTH = _FIXTURES / "auth-fix.umw"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "umwelt.cli", *args],
        capture_output=True,
        text=True,
    )


def test_parse_prints_ast():
    result = _run(["parse", str(FIXTURE)])
    assert result.returncode == 0, result.stderr
    assert "file" in result.stdout
    assert "editable" in result.stdout


def test_parse_nonexistent_file():
    result = _run(["parse", "/tmp/definitely-not-here.umw"])
    assert result.returncode != 0
    assert "No such file" in result.stderr or "not found" in result.stderr.lower()


def test_inspect_reports_rule_counts():
    result = _run(["inspect", str(FIXTURE)])
    assert result.returncode == 0, result.stderr
    assert "1 rule" in result.stdout


def test_inspect_lists_property_names():
    result = _run(["inspect", str(FIXTURE_AUTH)])
    assert result.returncode == 0, result.stderr
    assert "editable" in result.stdout


def test_parse_syntax_error_exits_nonzero(tmp_path):
    bad = tmp_path / "bad.umw"
    bad.write_text("{ color: red; }")  # missing selector — parser rejects
    result = _run(["parse", str(bad)])
    assert result.returncode != 0


def test_help_works():
    result = _run(["--help"])
    assert result.returncode == 0
    assert "umwelt" in result.stdout
    assert "parse" in result.stdout
    assert "inspect" in result.stdout
