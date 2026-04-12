"""Snapshot tests for the nsjail compiler against expected textproto files.

Each test builds a synthetic ResolvedView that represents what the fixture
.umw file WOULD resolve to against a known project tree, then verifies that
the compiler output matches the expected .textproto file exactly.

This catches any accidental formatting regressions in the compiler.
"""

from __future__ import annotations

from pathlib import Path

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.nsjail import NsjailCompiler
from umwelt.sandbox.entities import (
    FileEntity,
    NetworkEntity,
    ResourceEntity,
)

EXPECTED_DIR = Path(__file__).resolve().parents[2] / "src" / "umwelt" / "_fixtures" / "expected" / "nsjail"


def _load_expected(name: str) -> str:
    return (EXPECTED_DIR / name).read_text()


# ---------------------------------------------------------------------------
# minimal.umw snapshot
# ---------------------------------------------------------------------------


def test_snapshot_minimal():
    """minimal.umw: file[path="hello.txt"] { editable: true; }"""
    rv = ResolvedView()
    rv.add(
        "world",
        FileEntity(path="hello.txt", abs_path=Path("/workspace/hello.txt"), name="hello.txt"),
        {"editable": "true"},
    )
    output = NsjailCompiler().compile(rv)
    expected = _load_expected("minimal.textproto")
    assert output == expected, (
        f"Snapshot mismatch for minimal.textproto.\n\nGot:\n{output}\n\nExpected:\n{expected}"
    )


# ---------------------------------------------------------------------------
# auth-fix.umw snapshot
# ---------------------------------------------------------------------------


def test_snapshot_auth_fix():
    """auth-fix.umw: synthetic two-file view with network + memory + wall-time limits."""
    rv = ResolvedView()
    # src/auth/ files → editable (after CSS cascade)
    rv.add(
        "world",
        FileEntity(
            path="src/auth/login.py",
            abs_path=Path("/workspace/src/auth/login.py"),
            name="login.py",
        ),
        {"editable": "true"},
    )
    # src/ other files → readonly
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

    output = NsjailCompiler().compile(rv)
    expected = _load_expected("auth-fix.textproto")
    assert output == expected, (
        f"Snapshot mismatch for auth-fix.textproto.\n\nGot:\n{output}\n\nExpected:\n{expected}"
    )


# ---------------------------------------------------------------------------
# readonly-exploration.umw snapshot
# ---------------------------------------------------------------------------


def test_snapshot_readonly_exploration():
    """readonly-exploration.umw: all files readonly, network denied, 60s wall-time."""
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

    output = NsjailCompiler().compile(rv)
    expected = _load_expected("readonly-exploration.textproto")
    assert output == expected, (
        f"Snapshot mismatch for readonly-exploration.textproto.\n\nGot:\n{output}\n\nExpected:\n{expected}"
    )
