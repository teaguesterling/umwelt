"""Tests for the hook dispatcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from umwelt.sandbox.hooks.dispatcher import HookContext, HookDispatcher, HookResult


def make_context(tmp_path: Path, timeout: float = 5.0) -> HookContext:
    return HookContext(project_root=tmp_path, timeout_seconds=timeout)


def test_success_captures_stdout_stderr(tmp_path):
    dispatcher = HookDispatcher()
    results = dispatcher.dispatch(
        [("greet", "echo hello")],
        make_context(tmp_path),
    )
    assert len(results) == 1
    r = results[0]
    assert isinstance(r, HookResult)
    assert r.returncode == 0
    assert "hello" in r.stdout
    assert r.timed_out is False
    assert r.label == "greet"
    assert r.command == "echo hello"


def test_failure_continues_to_next_command(tmp_path):
    dispatcher = HookDispatcher()
    results = dispatcher.dispatch(
        [("fail", "sh -c 'exit 1'"), ("succeed", "echo done")],
        make_context(tmp_path),
    )
    assert len(results) == 2
    assert results[0].returncode == 1
    assert results[0].timed_out is False
    assert results[1].returncode == 0
    assert "done" in results[1].stdout


def test_timeout_sets_timed_out_flag(tmp_path):
    dispatcher = HookDispatcher()
    results = dispatcher.dispatch(
        [("slow", "sleep 10")],
        HookContext(project_root=tmp_path, timeout_seconds=0.1),
    )
    assert len(results) == 1
    r = results[0]
    assert r.timed_out is True
    assert r.returncode == -1


def test_command_not_found(tmp_path):
    dispatcher = HookDispatcher()
    results = dispatcher.dispatch(
        [("missing", "nonexistent_cmd_xyz_umwelt")],
        make_context(tmp_path),
    )
    assert len(results) == 1
    r = results[0]
    assert r.returncode == -1
    assert r.timed_out is False
    assert "nonexistent_cmd_xyz_umwelt" in r.stderr


def test_cwd_is_project_root(tmp_path):
    dispatcher = HookDispatcher()
    results = dispatcher.dispatch(
        [("pwd", "pwd")],
        make_context(tmp_path),
    )
    assert len(results) == 1
    # The output should be the project root (tmp_path)
    # Note: resolve() handles any symlinks in tmp_path
    assert results[0].returncode == 0
    assert Path(results[0].stdout.strip()).resolve() == tmp_path.resolve()


def test_duration_is_positive(tmp_path):
    dispatcher = HookDispatcher()
    results = dispatcher.dispatch(
        [("quick", "echo hi")],
        make_context(tmp_path),
    )
    assert len(results) == 1
    assert results[0].duration_seconds > 0
