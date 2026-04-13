"""Convenience runner: compile a view -> build argv -> invoke bwrap."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.bwrap import BwrapCompiler


@dataclass
class BwrapResult:
    """Result of a bwrap invocation."""

    returncode: int
    stdout: str
    stderr: str
    full_argv: list[str]  # the complete command line (for debugging)


def run_in_bwrap(
    resolved_view: ResolvedView,
    command: list[str],
    workspace_root: str = "/workspace",
    timeout: float | None = None,
) -> BwrapResult:
    """Compile view to bwrap argv and invoke bwrap.

    Assembles: bwrap ARGV -- WRAPPER COMMAND

    Returns a BwrapResult regardless of whether bwrap is installed.
    If bwrap is not found, returncode is -1 with an appropriate stderr message.
    If bwrap times out, returncode is -2.
    """
    compiler = BwrapCompiler()
    compilation = compiler.compile_full(resolved_view, workspace_root=workspace_root)

    full_argv = ["bwrap", *compilation.argv, "--", *compilation.wrapper, *command]

    try:
        result = subprocess.run(
            full_argv,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return BwrapResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            full_argv=full_argv,
        )
    except FileNotFoundError:
        return BwrapResult(
            returncode=-1,
            stdout="",
            stderr="bwrap binary not found on PATH",
            full_argv=full_argv,
        )
    except subprocess.TimeoutExpired:
        return BwrapResult(
            returncode=-2,
            stdout="",
            stderr="bwrap timed out",
            full_argv=full_argv,
        )
