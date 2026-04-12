"""Tests for the nsjail runner module."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.entities import FileEntity, NetworkEntity, ResourceEntity
from umwelt.sandbox.runners.nsjail import NsjailResult, run_in_nsjail


def _simple_view() -> ResolvedView:
    rv = ResolvedView()
    rv.add(
        "world",
        FileEntity(path="src/main.py", abs_path=Path("/workspace/src/main.py"), name="main.py"),
        {"editable": "false"},
    )
    rv.add("world", NetworkEntity(), {"deny": "*"})
    rv.add("world", ResourceEntity(kind="wall-time"), {"limit": "60s"})
    return rv


# ---------------------------------------------------------------------------
# Mock-based tests (no real nsjail required)
# ---------------------------------------------------------------------------


def test_runner_invokes_nsjail_with_config():
    """Verify the runner calls nsjail --config <tmpfile> -- <command>."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "hello\n"
    mock_result.stderr = ""

    with patch("umwelt.sandbox.runners.nsjail.subprocess.run", return_value=mock_result) as mock_run:
        result = run_in_nsjail(_simple_view(), ["echo", "hello"])

    assert result.returncode == 0
    assert result.stdout == "hello\n"

    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "nsjail"
    assert call_args[1] == "--config"
    assert call_args[2].endswith(".cfg")
    assert call_args[3] == "--"
    assert call_args[4:] == ["echo", "hello"]


def test_runner_config_contains_textproto():
    """Verify the temp config file written by the runner contains valid textproto."""
    captured_config_path: list[str] = []

    def capture_and_succeed(args, **kwargs):
        captured_config_path.append(args[2])
        # Read the config before it gets deleted
        import os
        config_content = open(args[2]).read() if os.path.exists(args[2]) else ""
        captured_config_path.append(config_content)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("umwelt.sandbox.runners.nsjail.subprocess.run", side_effect=capture_and_succeed):
        run_in_nsjail(_simple_view(), ["true"])

    config_content = captured_config_path[1]
    assert 'name: "umwelt-sandbox"' in config_content
    assert "clone_newnet: true" in config_content
    assert "time_limit: 60" in config_content


def test_runner_nsjail_not_found_returns_error():
    """If nsjail is not on PATH, runner returns returncode -1."""
    with patch("umwelt.sandbox.runners.nsjail.subprocess.run", side_effect=FileNotFoundError):
        result = run_in_nsjail(_simple_view(), ["echo", "hello"])

    assert result.returncode == -1
    assert "not found" in result.stderr


def test_runner_timeout_returns_error():
    """If nsjail times out, runner returns returncode -2."""
    import subprocess

    with patch(
        "umwelt.sandbox.runners.nsjail.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="nsjail", timeout=5),
    ):
        result = run_in_nsjail(_simple_view(), ["sleep", "100"], timeout=5.0)

    assert result.returncode == -2
    assert "timed out" in result.stderr


def test_runner_temp_file_cleaned_up():
    """The temp config file is deleted after the run."""
    config_path_holder: list[str] = []

    def capture_path(args, **kwargs):
        config_path_holder.append(args[2])
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("umwelt.sandbox.runners.nsjail.subprocess.run", side_effect=capture_path):
        run_in_nsjail(_simple_view(), ["true"])

    import os
    assert config_path_holder, "no config path captured"
    assert not os.path.exists(config_path_holder[0]), "temp config file was not deleted"


def test_result_dataclass_fields():
    """NsjailResult has the expected fields."""
    r = NsjailResult(returncode=0, stdout="out", stderr="err", config_path="/tmp/x.cfg")
    assert r.returncode == 0
    assert r.stdout == "out"
    assert r.stderr == "err"
    assert r.config_path == "/tmp/x.cfg"


def test_runner_respects_workspace_root():
    """workspace_root parameter is forwarded to the compiler."""
    captured: list[str] = []

    def capture_config(args, **kwargs):
        import os
        if os.path.exists(args[2]):
            captured.append(open(args[2]).read())
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    rv = ResolvedView()
    rv.add(
        "world",
        FileEntity(path="main.py", abs_path=Path("/proj/main.py"), name="main.py"),
        {"editable": "false"},
    )

    with patch("umwelt.sandbox.runners.nsjail.subprocess.run", side_effect=capture_config):
        run_in_nsjail(rv, ["python", "main.py"], workspace_root="/proj")

    assert captured
    assert 'dst: "/proj/main.py"' in captured[0]


# ---------------------------------------------------------------------------
# Integration test — only runs if nsjail is installed
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("nsjail") is None, reason="nsjail not installed")
def test_integration_nsjail_echo():
    """Integration: run a real echo command inside nsjail."""
    rv = ResolvedView()
    result = run_in_nsjail(rv, ["echo", "integration-ok"])
    assert result.returncode == 0
    assert "integration-ok" in result.stdout
