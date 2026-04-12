"""Tests for WorkspaceBuilder (Tasks 9 and 10).

Task 9 covers single-file rules (tests 1-5).
Task 10 covers globs, cascade, path traversal, and empty match (tests 6-13).

Each test uses a fresh registry_scope() with the sandbox vocabulary and a
WorldMatcher registered for the world taxon, matching the integration-test
pattern established in test_world_matcher_integration.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from umwelt.parser import parse
from umwelt.registry import register_matcher, registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.workspace.builder import WorkspaceBuilder
from umwelt.sandbox.workspace.errors import WorkspaceError
from umwelt.sandbox.world_matcher import WorldMatcher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tree(tmp_path: Path) -> Path:
    """Create a small project tree for builder tests."""
    (tmp_path / "src" / "auth").mkdir(parents=True)
    (tmp_path / "src" / "common").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "auth" / "login.py").write_text("# login")
    (tmp_path / "src" / "auth" / "oauth.py").write_text("# oauth")
    (tmp_path / "src" / "common" / "util.py").write_text("# util")
    (tmp_path / "src" / "common" / "types.py").write_text("# types")
    (tmp_path / "tests" / "test_login.py").write_text("# test")
    (tmp_path / "README.md").write_text("# readme")
    return tmp_path


def _setup(tmp_path: Path) -> tuple[Path, WorldMatcher]:
    """Register vocabulary + WorldMatcher in the active scope."""
    register_sandbox_vocabulary()
    matcher = WorldMatcher(base_dir=tmp_path)
    register_matcher(taxon="world", matcher=matcher)
    return tmp_path, matcher


# ---------------------------------------------------------------------------
# Task 9: Single-file, single-rule tests
# ---------------------------------------------------------------------------


def test_build_single_rule_manifest_entry(tmp_path):
    """Build with one file rule; manifest has exactly 1 entry with correct flag."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup(tree)
        view = parse('file[name="README.md"] { editable: false; }', validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            assert len(ws.manifest.entries) == 1
            entry = ws.manifest.entries[0]
            assert entry.writable is False
            assert entry.real_path.name == "README.md"


def test_build_editable_true_creates_copy(tmp_path):
    """editable: true → the virtual file is a copy, not a symlink."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup(tree)
        view = parse('file[name="README.md"] { editable: true; }', validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            assert len(ws.manifest.entries) == 1
            virtual = ws.manifest.entries[0].virtual_path
            assert virtual.exists()
            assert not virtual.is_symlink()
            assert virtual.read_text() == "# readme"


def test_build_editable_false_creates_symlink(tmp_path):
    """editable: false → the virtual file is a symlink."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup(tree)
        view = parse('file[name="README.md"] { editable: false; }', validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            assert len(ws.manifest.entries) == 1
            virtual = ws.manifest.entries[0].virtual_path
            assert virtual.is_symlink()


def test_context_manager_cleans_up(tmp_path):
    """Workspace context manager removes the temp directory on exit."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup(tree)
        view = parse('file[name="README.md"] { editable: false; }', validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            ws_root = ws.root
            assert ws_root.exists()
        assert not ws_root.exists()


def test_unmatched_file_not_in_manifest(tmp_path):
    """Files not matched by any rule are absent from the manifest."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup(tree)
        # Only README.md matched; all other files should not be in manifest.
        view = parse('file[name="README.md"] { editable: false; }', validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            names = {e.real_path.name for e in ws.manifest.entries}
            assert names == {"README.md"}


# ---------------------------------------------------------------------------
# Task 10: Globs, cascade, path traversal, empty match
# ---------------------------------------------------------------------------


def test_glob_selector_matches_multiple_files(tmp_path):
    """file:glob(...) materializes all matching files."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup(tree)
        view = parse('file:glob("src/**/*.py") { editable: false; }', validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            names = {e.real_path.name for e in ws.manifest.entries}
            assert names == {"login.py", "oauth.py", "util.py", "types.py"}


def test_glob_match_writable_false_all_symlinks(tmp_path):
    """Glob-matched files with editable: false all become symlinks."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup(tree)
        view = parse('file:glob("src/**/*.py") { editable: false; }', validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            for entry in ws.manifest.entries:
                assert entry.virtual_path.is_symlink(), f"{entry.virtual_path} should be a symlink"


def test_cascade_later_rule_wins(tmp_path):
    """file { editable: false; } overridden by specific rule for auth files."""
    tree = _make_tree(tmp_path)
    view_text = (
        'file { editable: false; }\n'
        'file[path^="src/auth/"] { editable: true; }'
    )
    with registry_scope():
        _setup(tree)
        view = parse(view_text, validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            by_name = {e.real_path.name: e for e in ws.manifest.entries}
            # Auth files should be writable (editable: true overrides)
            assert by_name["login.py"].writable is True
            assert by_name["oauth.py"].writable is True
            # Other files should be read-only
            assert by_name["README.md"].writable is False
            assert by_name["util.py"].writable is False


def test_cascade_multiple_rules_all_files_matched(tmp_path):
    """Two rules together produce manifest entries for all files."""
    tree = _make_tree(tmp_path)
    view_text = (
        'file { editable: false; }\n'
        'file[path^="src/auth/"] { editable: true; }'
    )
    with registry_scope():
        _setup(tree)
        view = parse(view_text, validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            assert len(ws.manifest.entries) == 6  # all 6 files in tree


def test_path_traversal_raises_workspace_error(tmp_path):
    """Resolved path outside base_dir raises WorkspaceError."""
    # We create a file outside the base_dir and a symlink inside that points to it.
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("secret")

    base = tmp_path / "base"
    base.mkdir()
    # Place a symlink inside base that escapes to outside/secret.txt
    (base / "escape.txt").symlink_to(secret)

    with registry_scope():
        register_sandbox_vocabulary()
        matcher = WorldMatcher(base_dir=base)
        register_matcher(taxon="world", matcher=matcher)
        view = parse('file[name="escape.txt"] { editable: false; }', validate=False)
        builder = WorkspaceBuilder()
        with pytest.raises(WorkspaceError, match="outside base_dir"):
            builder.build(view, base)


def test_empty_match_produces_empty_manifest_with_warning(tmp_path):
    """A rule matching no files yields an empty manifest and a warning."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup(tree)
        # No file has this name.
        view = parse('file[name="nonexistent.go"] { editable: true; }', validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            assert len(ws.manifest.entries) == 0
            assert len(ws.warnings) == 1
            assert "empty" in ws.warnings[0].lower()


def test_workspace_root_mirrors_relative_paths(tmp_path):
    """Virtual paths under workspace root mirror the relative path under base_dir."""
    tree = _make_tree(tmp_path)
    with registry_scope():
        _setup(tree)
        view = parse('file[name="login.py"] { editable: false; }', validate=False)
        with WorkspaceBuilder().build(view, tree) as ws:
            entry = ws.manifest.entries[0]
            # virtual_path should be ws.root / "src/auth/login.py"
            expected_rel = Path("src/auth/login.py")
            assert entry.virtual_path == ws.root / expected_rel
