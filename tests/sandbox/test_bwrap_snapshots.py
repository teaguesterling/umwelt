"""Snapshot tests for the bwrap compiler against expected argv files.

Each test builds a synthetic ResolvedView, compiles to bwrap argv, and
compares against an expected file (one flag per line).

The expected files live in src/umwelt/_fixtures/expected/bwrap/.
"""

from __future__ import annotations

from pathlib import Path

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.bwrap import BwrapCompiler
from umwelt.sandbox.entities import FileEntity, NetworkEntity, ResourceEntity

EXPECTED_DIR = (
    Path(__file__).resolve().parents[2]
    / "src" / "umwelt" / "_fixtures" / "expected" / "bwrap"
)


def _load_argv(name: str) -> list[str]:
    """Load expected argv from a one-flag-per-line file."""
    return (EXPECTED_DIR / name).read_text().splitlines()


def _load_wrapper(name: str) -> list[str]:
    """Load expected wrapper from a one-item-per-line file."""
    return (EXPECTED_DIR / name).read_text().splitlines()


# ---------------------------------------------------------------------------
# minimal snapshot
# ---------------------------------------------------------------------------


def test_snapshot_minimal():
    """minimal: file[path="hello.txt"] { editable: true; }"""
    rv = ResolvedView()
    rv.add(
        "world",
        FileEntity(path="hello.txt", abs_path=Path("/workspace/hello.txt"), name="hello.txt"),
        {"editable": "true"},
    )
    result = BwrapCompiler().compile_full(rv)
    expected_argv = _load_argv("minimal.argv")
    assert result.argv == expected_argv, (
        f"Snapshot mismatch for minimal.argv.\n\nGot:\n{result.argv}\n\nExpected:\n{expected_argv}"
    )


# ---------------------------------------------------------------------------
# auth-fix snapshot
# ---------------------------------------------------------------------------


def test_snapshot_auth_fix():
    """auth-fix: two files + network deny + memory + wall-time limits."""
    rv = ResolvedView()
    rv.add(
        "world",
        FileEntity(
            path="src/auth/login.py",
            abs_path=Path("/workspace/src/auth/login.py"),
            name="login.py",
        ),
        {"editable": "true"},
    )
    rv.add(
        "world",
        FileEntity(
            path="src/common/util.py",
            abs_path=Path("/workspace/src/common/util.py"),
            name="util.py",
        ),
        {"editable": "false"},
    )
    rv.add("world", NetworkEntity(), {"deny": "*"})
    rv.add("world", ResourceEntity(kind="memory"), {"limit": "512MB"})
    rv.add("world", ResourceEntity(kind="wall-time"), {"limit": "5m"})

    result = BwrapCompiler().compile_full(rv)
    expected_argv = _load_argv("auth-fix.argv")
    expected_wrapper = _load_wrapper("auth-fix.wrapper")
    assert result.argv == expected_argv, (
        f"Snapshot mismatch for auth-fix.argv.\n\nGot:\n{result.argv}\n\nExpected:\n{expected_argv}"
    )
    assert result.wrapper == expected_wrapper, (
        f"Snapshot mismatch for auth-fix.wrapper.\n\nGot:\n{result.wrapper}\n\nExpected:\n{expected_wrapper}"
    )


# ---------------------------------------------------------------------------
# readonly-exploration snapshot
# ---------------------------------------------------------------------------


def test_snapshot_readonly_exploration():
    """readonly-exploration: all files readonly, network denied, 60s wall-time."""
    rv = ResolvedView()
    rv.add(
        "world",
        FileEntity(
            path="src/auth/login.py",
            abs_path=Path("/workspace/src/auth/login.py"),
            name="login.py",
        ),
        {"editable": "false"},
    )
    rv.add("world", NetworkEntity(), {"deny": "*"})
    rv.add("world", ResourceEntity(kind="wall-time"), {"limit": "60s"})

    result = BwrapCompiler().compile_full(rv)
    expected_argv = _load_argv("readonly-exploration.argv")
    expected_wrapper = _load_wrapper("readonly-exploration.wrapper")
    assert result.argv == expected_argv, (
        f"Snapshot mismatch for readonly-exploration.argv.\n\nGot:\n{result.argv}\n\nExpected:\n{expected_argv}"
    )
    assert result.wrapper == expected_wrapper, (
        f"Snapshot mismatch for readonly-exploration.wrapper.\n\nGot:\n{result.wrapper}\n\nExpected:\n{expected_wrapper}"
    )
