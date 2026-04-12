"""Tests for the umwelt compile and run CLI subcommands."""

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
# compile subcommand
# ---------------------------------------------------------------------------


def test_compile_auth_fix_exits_0():
    result = _run("compile", "--target", "nsjail", str(FIXTURES / "auth-fix.umw"))
    assert result.returncode == 0, result.stderr


def test_compile_auth_fix_outputs_textproto():
    result = _run("compile", "--target", "nsjail", str(FIXTURES / "auth-fix.umw"))
    assert result.returncode == 0, result.stderr
    assert 'name: "umwelt-sandbox"' in result.stdout
    assert 'hostname: "umwelt"' in result.stdout


def test_compile_auth_fix_has_network_deny():
    result = _run("compile", "--target", "nsjail", str(FIXTURES / "auth-fix.umw"))
    assert result.returncode == 0, result.stderr
    assert "clone_newnet: true" in result.stdout


def test_compile_auth_fix_has_memory_limit():
    result = _run("compile", "--target", "nsjail", str(FIXTURES / "auth-fix.umw"))
    assert result.returncode == 0, result.stderr
    assert "rlimit_as: 512" in result.stdout


def test_compile_auth_fix_has_time_limit():
    result = _run("compile", "--target", "nsjail", str(FIXTURES / "auth-fix.umw"))
    assert result.returncode == 0, result.stderr
    # 5m = 300s
    assert "time_limit: 300" in result.stdout


def test_compile_minimal_exits_0():
    result = _run("compile", "--target", "nsjail", str(FIXTURES / "minimal.umw"))
    assert result.returncode == 0, result.stderr
    assert 'name: "umwelt-sandbox"' in result.stdout


def test_compile_nonexistent_target_exits_1():
    result = _run("compile", "--target", "nonexistent", str(FIXTURES / "minimal.umw"))
    assert result.returncode == 1
    assert "nonexistent" in result.stderr


def test_compile_missing_file_exits_2():
    result = _run("compile", "--target", "nsjail", "does_not_exist.umw")
    assert result.returncode == 2
    assert "error" in result.stderr.lower()


def test_compile_help_exits_0():
    result = _run("compile", "--help")
    assert result.returncode == 0
    assert "--target" in result.stdout


# ---------------------------------------------------------------------------
# check subcommand now reports nsjail compiler
# ---------------------------------------------------------------------------


def test_check_reports_nsjail_compiler():
    result = _run("check", str(FIXTURES / "auth-fix.umw"))
    assert result.returncode == 0, result.stderr
    assert "nsjail" in result.stdout
    assert "os" in result.stdout


def test_check_reports_1_compiler_registered():
    result = _run("check", str(FIXTURES / "auth-fix.umw"))
    assert result.returncode == 0, result.stderr
    assert "1 registered" in result.stdout or "Compilers: 1" in result.stdout


# ---------------------------------------------------------------------------
# run subcommand help (doesn't need nsjail installed)
# ---------------------------------------------------------------------------


def test_run_help_exits_0():
    result = _run("run", "--help")
    assert result.returncode == 0
    assert "--target" in result.stdout
