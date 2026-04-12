"""Tests for the umwelt CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "toy.umw"


def _run(args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["UMWELT_PRELOAD_TOY"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "umwelt.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_parse_prints_ast():
    result = _run(["parse", str(FIXTURE)])
    assert result.returncode == 0, result.stderr
    assert "thing" in result.stdout
    assert "paint" in result.stdout


def test_parse_nonexistent_file():
    result = _run(["parse", "/tmp/definitely-not-here.umw"])
    assert result.returncode != 0
    assert "No such file" in result.stderr or "not found" in result.stderr.lower()


def test_inspect_reports_rule_counts():
    result = _run(["inspect", str(FIXTURE)])
    assert result.returncode == 0, result.stderr
    assert "3 rules" in result.stdout or "3 rule" in result.stdout
    assert "shapes" in result.stdout  # taxon name


def test_inspect_lists_property_names():
    result = _run(["inspect", str(FIXTURE)])
    assert result.returncode == 0
    assert "paint" in result.stdout
    assert "max-glow" in result.stdout


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
