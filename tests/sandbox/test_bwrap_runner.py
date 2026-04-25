"""Tests for the bwrap runner module."""

from __future__ import annotations

import shutil
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.entities import MountEntity, ResourceEntity
from umwelt.sandbox.runners.bwrap import BwrapResult, run_in_bwrap


def test_runner_returns_result_on_success():
    rv = ResolvedView()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "hello"
    mock_result.stderr = ""
    with patch("umwelt.sandbox.runners.bwrap.subprocess.run", return_value=mock_result):
        result = run_in_bwrap(rv, ["echo", "hello"])
    assert result.returncode == 0
    assert result.stdout == "hello"


def test_runner_returns_neg1_when_bwrap_not_found():
    rv = ResolvedView()
    with patch("umwelt.sandbox.runners.bwrap.subprocess.run", side_effect=FileNotFoundError):
        result = run_in_bwrap(rv, ["echo"])
    assert result.returncode == -1
    assert "not found" in result.stderr


def test_runner_returns_neg2_on_timeout():
    rv = ResolvedView()
    with patch(
        "umwelt.sandbox.runners.bwrap.subprocess.run",
        side_effect=subprocess.TimeoutExpired("bwrap", 5),
    ):
        result = run_in_bwrap(rv, ["echo"])
    assert result.returncode == -2


def test_runner_assembles_bwrap_argv_wrapper_command():
    """Verify the runner concatenates: bwrap ARGV -- WRAPPER COMMAND."""
    rv = ResolvedView()
    rv.add("world", MountEntity(path="/workspace/src"), {"source": "./src"})
    rv.add("world", ResourceEntity(), {"wall-time": "60s"})

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    with patch("umwelt.sandbox.runners.bwrap.subprocess.run", return_value=mock_result) as mock_run:
        run_in_bwrap(rv, ["python", "script.py"])

    called_argv = mock_run.call_args[0][0]
    assert called_argv[0] == "bwrap"
    assert "--" in called_argv
    separator_idx = called_argv.index("--")
    # After --, the wrapper commands come before the delegate command
    post_separator = called_argv[separator_idx + 1:]
    assert "timeout" in post_separator
    assert "python" in post_separator


def test_result_dataclass_fields():
    """BwrapResult has the expected fields."""
    r = BwrapResult(returncode=0, stdout="out", stderr="err", full_argv=["bwrap", "--clearenv", "--", "echo"])
    assert r.returncode == 0
    assert r.stdout == "out"
    assert r.stderr == "err"
    assert r.full_argv[0] == "bwrap"


def test_runner_full_argv_recorded():
    """full_argv is available on the result for debugging."""
    rv = ResolvedView()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    with patch("umwelt.sandbox.runners.bwrap.subprocess.run", return_value=mock_result):
        result = run_in_bwrap(rv, ["true"])
    assert result.full_argv[0] == "bwrap"
    assert "--" in result.full_argv


@pytest.mark.skipif(shutil.which("bwrap") is None, reason="bwrap not installed")
def test_integration_bwrap_echo():
    """Integration: run a real echo command inside bwrap."""
    rv = ResolvedView()
    result = run_in_bwrap(rv, ["/bin/echo", "integration-ok"])
    assert result.returncode == 0
    assert "integration-ok" in result.stdout
