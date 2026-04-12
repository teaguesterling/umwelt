"""Hook dispatcher: run lifecycle hook commands via subprocess.

Executes (label, command) pairs sequentially. Continues on failure.
Records returncode, stdout, stderr, duration, and timeout status.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class HookContext:
    project_root: Path
    env: Mapping[str, str] | None = None
    timeout_seconds: float = 60.0


@dataclass(frozen=True)
class HookResult:
    label: str
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool


class HookDispatcher:
    def dispatch(
        self,
        commands: list[tuple[str, str]],
        context: HookContext,
    ) -> list[HookResult]:
        """Run hook commands sequentially. Continue on failure.

        Args:
            commands: List of (label, command) pairs to execute.
            context: Execution context with project_root, env, and timeout.

        Returns:
            List of HookResult, one per command.
        """
        results: list[HookResult] = []
        for label, command in commands:
            result = self._run_one(label, command, context)
            results.append(result)
        return results

    def _run_one(
        self, label: str, command: str, context: HookContext
    ) -> HookResult:
        argv = shlex.split(command)
        env = dict(context.env) if context.env is not None else dict(os.environ)
        start = time.monotonic()
        try:
            proc = subprocess.run(
                argv,
                cwd=context.project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=context.timeout_seconds,
            )
            duration = time.monotonic() - start
            return HookResult(
                label=label,
                command=command,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_seconds=duration,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            return HookResult(
                label=label,
                command=command,
                returncode=-1,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
                timed_out=True,
            )
        except FileNotFoundError:
            duration = time.monotonic() - start
            cmd_name = argv[0] if argv else command
            return HookResult(
                label=label,
                command=command,
                returncode=-1,
                stdout="",
                stderr=f"command not found: {cmd_name}",
                duration_seconds=duration,
                timed_out=False,
            )
