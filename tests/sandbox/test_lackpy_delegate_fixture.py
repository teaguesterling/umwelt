"""Integration tests for the lackpy-delegate example fixture.

Verifies the fixture parses, compiles to all three targets, and that the
lackpy-namespace compiler's output contains the expected structure.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from umwelt.cascade.resolver import ResolvedView
from umwelt.parser import parse
from umwelt.registry import registry_scope
from umwelt.sandbox.compilers.lackpy_namespace import LackpyNamespaceCompiler
from umwelt.sandbox.desugar import register_sandbox_sugar
from umwelt.sandbox.entities import ToolEntity
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary

FIXTURES = Path(__file__).resolve().parents[2] / "src" / "umwelt" / "_fixtures"
FIXTURE = FIXTURES / "lackpy-delegate.umw"


def test_lackpy_delegate_fixture_parses() -> None:
    """The lackpy-delegate fixture parses without errors."""
    with registry_scope():
        register_sandbox_vocabulary()
        register_sandbox_sugar()
        view = parse(FIXTURE)
    assert len(view.rules) >= 5


def test_lackpy_delegate_fixture_has_tool_rules() -> None:
    """The fixture contains tool allow rules."""
    with registry_scope():
        register_sandbox_vocabulary()
        register_sandbox_sugar()
        view = parse(FIXTURE)
    # Find rules with tool selectors
    tool_rules = [
        r for r in view.rules
        if any(
            any(p.selector.type_name == "tool" for p in sel.parts)
            for sel in r.selectors
        )
    ]
    assert len(tool_rules) >= 3  # Read, Grep, Glob, and bare tool


def test_lackpy_namespace_compiler_with_explicit_tools() -> None:
    """Compiler produces expected tool lists when entities are pre-populated."""
    rv = ResolvedView()
    rv.add("capability", ToolEntity(name="Read"), {"allow": "true"})
    rv.add("capability", ToolEntity(name="Grep"), {"allow": "true"})
    rv.add("capability", ToolEntity(name="Glob"), {"allow": "true"})
    rv.add("capability", ToolEntity(name=""), {"max-level": "1"})
    config = LackpyNamespaceCompiler().compile(rv)
    assert set(config["allowed_tools"]) == {"Read", "Grep", "Glob"}
    assert config["max_level"] == 1
    assert config["denied_tools"] == []


def test_cli_compile_lackpy_delegate_nsjail() -> None:
    """The lackpy-delegate fixture compiles to nsjail."""
    result = subprocess.run(
        [sys.executable, "-m", "umwelt.cli", "compile", "--target", "nsjail", str(FIXTURE)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "nsjail" in result.stdout or "umwelt-sandbox" in result.stdout


def test_cli_compile_lackpy_delegate_bwrap() -> None:
    """The lackpy-delegate fixture compiles to bwrap."""
    result = subprocess.run(
        [sys.executable, "-m", "umwelt.cli", "compile", "--target", "bwrap", str(FIXTURE)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # bwrap output is JSON with an argv key
    output = json.loads(result.stdout)
    assert "argv" in output


def test_cli_compile_lackpy_delegate_lackpy_namespace() -> None:
    """The lackpy-delegate fixture compiles to lackpy-namespace."""
    result = subprocess.run(
        [sys.executable, "-m", "umwelt.cli", "compile", "--target", "lackpy-namespace", str(FIXTURE)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert "allowed_tools" in output
    assert "denied_tools" in output
    assert "kits" in output
