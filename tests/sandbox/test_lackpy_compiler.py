"""Tests for the lackpy-namespace compiler."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.lackpy_namespace import LackpyNamespaceCompiler
from umwelt.sandbox.entities import KitEntity, ToolEntity


def test_tool_allowed() -> None:
    rv = ResolvedView()
    rv.add("capability", ToolEntity(name="Read"), {"allow": "true"})
    config = LackpyNamespaceCompiler().compile(rv)
    assert "Read" in config["allowed_tools"]


def test_tool_denied() -> None:
    rv = ResolvedView()
    rv.add("capability", ToolEntity(name="Bash"), {"allow": "false"})
    config = LackpyNamespaceCompiler().compile(rv)
    assert "Bash" in config["denied_tools"]


def test_kit_allowed() -> None:
    rv = ResolvedView()
    rv.add("capability", KitEntity(name="python-dev"), {"allow": "true"})
    config = LackpyNamespaceCompiler().compile(rv)
    assert "python-dev" in config["kits"]


def test_empty_view() -> None:
    rv = ResolvedView()
    config = LackpyNamespaceCompiler().compile(rv)
    assert config["allowed_tools"] == []
    assert config["denied_tools"] == []


def test_world_entities_ignored() -> None:
    from umwelt.sandbox.entities import FileEntity

    rv = ResolvedView()
    rv.add(
        "world",
        FileEntity(path="x", abs_path=Path("x"), name="x"),
        {"editable": "true"},
    )
    config = LackpyNamespaceCompiler().compile(rv)
    assert config["allowed_tools"] == []


def test_global_max_level() -> None:
    rv = ResolvedView()
    rv.add("capability", ToolEntity(name=""), {"max-level": "2"})
    config = LackpyNamespaceCompiler().compile(rv)
    assert config["max_level"] == 2


def test_tool_specific_max_level() -> None:
    rv = ResolvedView()
    rv.add("capability", ToolEntity(name="Bash"), {"allow": "true", "max-level": "2"})
    config = LackpyNamespaceCompiler().compile(rv)
    assert config["tool_levels"]["Bash"] == 2


def test_allow_patterns() -> None:
    rv = ResolvedView()
    rv.add(
        "capability",
        ToolEntity(name="Bash"),
        {"allow": "true", "allow-pattern": "git *, pytest *"},
    )
    config = LackpyNamespaceCompiler().compile(rv)
    assert config["allow_patterns"]["Bash"] == ["git *", "pytest *"]


def test_deny_patterns() -> None:
    rv = ResolvedView()
    rv.add(
        "capability",
        ToolEntity(name="Bash"),
        {"allow": "true", "deny-pattern": "rm -rf *, sudo *"},
    )
    config = LackpyNamespaceCompiler().compile(rv)
    assert config["deny_patterns"]["Bash"] == ["rm -rf *", "sudo *"]


def test_multiple_tools() -> None:
    rv = ResolvedView()
    rv.add("capability", ToolEntity(name="Read"), {"allow": "true"})
    rv.add("capability", ToolEntity(name="Edit"), {"allow": "true"})
    rv.add("capability", ToolEntity(name="Bash"), {"allow": "false"})
    rv.add("capability", KitEntity(name="python-dev"), {"allow": "true"})
    config = LackpyNamespaceCompiler().compile(rv)
    assert set(config["allowed_tools"]) == {"Read", "Edit"}
    assert config["denied_tools"] == ["Bash"]
    assert config["kits"] == ["python-dev"]


def test_compiler_attributes() -> None:
    compiler = LackpyNamespaceCompiler()
    assert compiler.target_name == "lackpy-namespace"
    assert compiler.target_format == "dict"
    assert compiler.altitude == "language"


def test_cli_compile_lackpy_namespace(tmp_path: Path) -> None:
    """Verify CLI accepts lackpy-namespace target and emits valid JSON."""
    view = tmp_path / "test.umw"
    view.write_text('tool[name="Read"] { allow: true; } tool[name="Bash"] { allow: false; }')
    result = subprocess.run(
        [sys.executable, "-m", "umwelt.cli", "compile", "--target", "lackpy-namespace", str(view)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # Output must be valid JSON with the expected top-level keys
    parsed = json.loads(result.stdout)
    assert "allowed_tools" in parsed
    assert "denied_tools" in parsed
    assert "kits" in parsed


def test_check_reports_three_compilers(tmp_path: Path) -> None:
    view = tmp_path / "test.umw"
    view.write_text('tool[name="Read"] { allow: true; }')
    result = subprocess.run(
        [sys.executable, "-m", "umwelt.cli", "check", str(view)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "lackpy-namespace" in result.stdout
    assert "nsjail" in result.stdout
    assert "bwrap" in result.stdout
