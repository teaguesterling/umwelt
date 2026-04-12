"""Integration tests: sandbox consumer → core pipeline (parse → resolve).

These tests connect the sandbox consumer all the way through the core
pipeline: register sandbox vocabulary + world matcher, parse a real view,
run resolve(), and verify resolved property values match expectations.
"""

from __future__ import annotations

from pathlib import Path

from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import register_matcher, registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.world_matcher import WorldMatcher


def _make_tree(tmp_path: Path) -> Path:
    """Create a small project tree for matcher tests."""
    (tmp_path / "src" / "auth").mkdir(parents=True)
    (tmp_path / "src" / "common").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "auth" / "login.py").write_text("# login")
    (tmp_path / "src" / "auth" / "oauth.py").write_text("# oauth")
    (tmp_path / "src" / "common" / "util.py").write_text("# util")
    (tmp_path / "tests" / "test_login.py").write_text("# test")
    (tmp_path / "README.md").write_text("# readme")
    return tmp_path


def _setup_world(tmp_path: Path):
    """Register sandbox vocabulary + world matcher in the active scope."""
    register_sandbox_vocabulary()
    matcher = WorldMatcher(base_dir=tmp_path)
    register_matcher(taxon="world", matcher=matcher)
    return matcher


def test_editable_true_for_auth_files(tmp_path):
    """file[path^="src/auth/"] { editable: true; } sets editable on auth files."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup_world(tree)
        view = parse('file[path^="src/auth/"] { editable: true; }', validate=False)
        resolved = resolve(view)
        entities = list(resolved.entries("world"))
        auth_paths = {"src/auth/login.py", "src/auth/oauth.py"}
        matched_paths = {
            e.path for e, props in entities if props.get("editable") == "true"
        }
        assert auth_paths.issubset(matched_paths)
        # Files outside src/auth/ should not have editable: true
        non_auth = {
            e.path for e, props in entities
            if not e.path.startswith("src/auth/") and props.get("editable") == "true"
        }
        assert len(non_auth) == 0


def test_cascade_last_wins(tmp_path):
    """file { editable: false; } overridden by file[path^="src/auth/"] { editable: true; }."""
    tree = _make_tree(tmp_path)
    view_text = (
        'file { editable: false; }\n'
        'file[path^="src/auth/"] { editable: true; }'
    )
    with registry_scope():
        _setup_world(tree)
        view = parse(view_text, validate=False)
        resolved = resolve(view)
        entities = dict(
            (e.path, props)
            for e, props in resolved.entries("world")
            if hasattr(e, "path")
        )
        assert entities.get("src/auth/login.py", {}).get("editable") == "true"
        assert entities.get("src/auth/oauth.py", {}).get("editable") == "true"
        assert entities.get("README.md", {}).get("editable") == "false"
        assert entities.get("src/common/util.py", {}).get("editable") == "false"


def test_all_files_matched_by_universal_rule(tmp_path):
    """file { editable: false; } sets editable on all files."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup_world(tree)
        view = parse("file { editable: false; }", validate=False)
        resolved = resolve(view)
        entities = list(resolved.entries("world"))
        # All file entities should have editable: false
        file_props = [(e.path, props) for e, props in entities if hasattr(e, "path")]
        assert len(file_props) == 5  # 5 files in the tree
        for path, props in file_props:
            assert props.get("editable") == "false", f"{path!r} should be editable: false"


def test_glob_selector_with_resolve(tmp_path):
    """file:glob("src/**/*.py") { editable: true; } matches only .py files under src/."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup_world(tree)
        view = parse('file:glob("src/**/*.py") { editable: true; }', validate=False)
        resolved = resolve(view)
        entities = dict(
            (e.path, props)
            for e, props in resolved.entries("world")
            if hasattr(e, "path")
        )
        assert entities.get("src/auth/login.py", {}).get("editable") == "true"
        assert entities.get("src/auth/oauth.py", {}).get("editable") == "true"
        assert entities.get("src/common/util.py", {}).get("editable") == "true"
        # README.md and test_login.py are not under src/ or not .py under src/**
        assert entities.get("README.md", {}).get("editable") is None
