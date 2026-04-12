"""Convenience runner: compile a view → write temp config → invoke nsjail."""

from __future__ import annotations

import contextlib
import os
import subprocess
import tempfile
from dataclasses import dataclass

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.nsjail import NsjailCompiler


@dataclass
class NsjailResult:
    """Result of a nsjail invocation."""

    returncode: int
    stdout: str
    stderr: str
    config_path: str  # the temp config file path (for debugging)


def run_in_nsjail(
    resolved_view: ResolvedView,
    command: list[str],
    workspace_root: str = "/workspace",
    timeout: float | None = None,
) -> NsjailResult:
    """Compile view to textproto, write a temp config, and invoke nsjail.

    Returns an NsjailResult regardless of whether nsjail is installed.
    If nsjail is not found, returncode is -1 with an appropriate stderr message.
    If nsjail times out, returncode is -2.
    """
    compiler = NsjailCompiler()
    textproto = compiler.compile(resolved_view, workspace_root=workspace_root)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".cfg", prefix="umwelt-nsjail-", delete=False
    ) as f:
        f.write(textproto)
        config_path = f.name

    try:
        result = subprocess.run(
            ["nsjail", "--config", config_path, "--", *command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return NsjailResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            config_path=config_path,
        )
    except FileNotFoundError:
        return NsjailResult(
            returncode=-1,
            stdout="",
            stderr="nsjail binary not found on PATH",
            config_path=config_path,
        )
    except subprocess.TimeoutExpired:
        return NsjailResult(
            returncode=-2,
            stdout="",
            stderr="nsjail timed out",
            config_path=config_path,
        )
    finally:
        with contextlib.suppress(OSError):
            os.unlink(config_path)
