"""Tests for world matcher glob and descendant-combinator support."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from umwelt.sandbox.world_matcher import WorldMatcher


def _make_tree(tmp_path: Path) -> Path:
    """Create a small project tree for matcher tests."""
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


def test_glob_matches_python_files_under_src(tmp_path):
    """file:glob("src/**/*.py") should match only .py files under src/."""
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")
    # Simulate glob pseudo-class: fnmatch against relative path
    glob_pattern = "src/**/*.py"
    matched = [f for f in files if fnmatch.fnmatch(f.path, glob_pattern)]
    paths = {f.path for f in matched}
    assert "src/auth/login.py" in paths
    assert "src/auth/oauth.py" in paths
    assert "src/common/util.py" in paths
    assert "src/common/types.py" in paths
    assert "tests/test_login.py" not in paths
    assert "README.md" not in paths


def test_glob_matches_via_selector_engine(tmp_path):
    """Integration: :glob() pseudo-class is evaluated by the selector engine."""
    from umwelt.ast import PseudoClass, SimpleSelector, SourceSpan
    from umwelt.selector.match import match_simple

    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")

    span = SourceSpan(line=1, col=1)
    simple = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(),
        pseudo_classes=(PseudoClass(name="glob", argument="src/**/*.py"),),
        span=span,
    )
    matched = match_simple(simple, matcher, files)
    paths = {matcher.get_attribute(f, "path") for f in matched}
    assert "src/auth/login.py" in paths
    assert "src/auth/oauth.py" in paths
    assert "README.md" not in paths
    assert "tests/test_login.py" not in paths


def test_children_returns_descendants_not_just_direct(tmp_path):
    """dir → file descendant combinator: files under src/auth/ are descendants of src/."""
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    dirs = matcher.match_type("dir")
    src_dir = next(d for d in dirs if d.name == "src")
    children = matcher.children(src_dir, "file")
    paths = {f.path for f in children}
    # Files under src/auth/ and src/common/ are descendants of src/
    assert "src/auth/login.py" in paths
    assert "src/auth/oauth.py" in paths
    assert "src/common/util.py" in paths
    assert "src/common/types.py" in paths
    # Files outside src/ are not descendants
    assert "tests/test_login.py" not in paths
    assert "README.md" not in paths


def test_children_auth_subdir(tmp_path):
    """Files under src/auth/ are descendants of auth dir only."""
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    dirs = matcher.match_type("dir")
    auth_dir = next(d for d in dirs if d.name == "auth")
    children = matcher.children(auth_dir, "file")
    paths = {f.path for f in children}
    assert "src/auth/login.py" in paths
    assert "src/auth/oauth.py" in paths
    assert "src/common/util.py" not in paths


def test_children_dir_descendant_subdirs(tmp_path):
    """dir → dir descendant: subdirs under src/ are returned."""
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    dirs = matcher.match_type("dir")
    src_dir = next(d for d in dirs if d.name == "src")
    child_dirs = matcher.children(src_dir, "dir")
    names = {d.name for d in child_dirs}
    assert "auth" in names
    assert "common" in names
    assert "tests" not in names


def test_path_traversal_protection(tmp_path):
    """Paths that escape base_dir should not appear in match results."""
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")
    # All returned paths must be within base_dir
    for f in files:
        assert not f.path.startswith("..")
        assert f.abs_path.is_relative_to(tree)
