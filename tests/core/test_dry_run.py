"""Tests for the umwelt dry-run subcommand."""

from __future__ import annotations

from pathlib import Path

from umwelt.dry_run import format_dry_run
from umwelt.parser import parse
from umwelt.registry import register_matcher, registry_scope
from umwelt.sandbox.capability_matcher import CapabilityMatcher
from umwelt.sandbox.entities import ToolEntity
from umwelt.sandbox.state_matcher import StateMatcher
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.world_matcher import WorldMatcher

_FIXTURES = Path(__file__).resolve().parents[2] / "src" / "umwelt" / "_fixtures"


def _setup(tmp_path: Path) -> None:
    (tmp_path / "src" / "auth").mkdir(parents=True)
    (tmp_path / "src" / "auth" / "login.py").write_text("# login")
    register_sandbox_vocabulary()
    register_matcher(taxon="world", matcher=WorldMatcher(base_dir=tmp_path))
    register_matcher(taxon="capability", matcher=CapabilityMatcher(tools=[
        ToolEntity(name="Read"), ToolEntity(name="Edit"), ToolEntity(name="Bash"),
    ]))
    register_matcher(taxon="state", matcher=StateMatcher())


def test_dry_run_reports_resolved_properties(tmp_path):
    with registry_scope():
        _setup(tmp_path)
        view = parse(_FIXTURES / "auth-fix.umw")
        output = format_dry_run(view)
    assert "editable" in output
    assert "allow" in output


def test_dry_run_reports_file_entities(tmp_path):
    with registry_scope():
        _setup(tmp_path)
        view = parse('file[path^="src/auth/"] { editable: true; }', validate=False)
        output = format_dry_run(view)
    assert "login.py" in output
    assert "editable" in output
    assert "true" in output


def test_dry_run_no_matches_reports_empty(tmp_path):
    with registry_scope():
        _setup(tmp_path)
        view = parse('file[name="nonexistent.go"] { editable: true; }', validate=False)
        output = format_dry_run(view)
    # No files matched — dry-run reports no content for world taxon
    assert "login.py" not in output
