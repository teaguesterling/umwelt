"""Tests for the world taxon filesystem matcher."""

from __future__ import annotations

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


def test_match_type_file_returns_all(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")
    names = {f.name for f in files}
    assert "login.py" in names
    assert "oauth.py" in names
    assert "README.md" in names
    assert len(files) == 6


def test_match_type_dir_returns_all(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    dirs = matcher.match_type("dir")
    names = {d.name for d in dirs}
    assert "src" in names
    assert "auth" in names
    assert "tests" in names


def test_get_attribute_path(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")
    login = next(f for f in files if f.name == "login.py")
    assert matcher.get_attribute(login, "path") == "src/auth/login.py"


def test_get_attribute_name(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")
    login = next(f for f in files if f.name == "login.py")
    assert matcher.get_attribute(login, "name") == "login.py"


def test_get_id_is_name(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")
    login = next(f for f in files if f.name == "login.py")
    assert matcher.get_id(login) == "login.py"


def test_match_type_star_returns_all_entities(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    all_entities = matcher.match_type("*")
    # Should include both files and dirs
    assert len(all_entities) > 6  # at least 6 files + some dirs


def test_match_type_unknown_returns_empty(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    assert matcher.match_type("ghost") == []


def test_resource_entities(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    resources = matcher.match_type("resource")
    kinds = {matcher.get_attribute(r, "kind") for r in resources}
    assert "memory" in kinds
    assert "wall-time" in kinds


def test_network_entity(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    networks = matcher.match_type("network")
    assert len(networks) == 1  # the singleton network entity


def test_env_entities(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree, env_vars=["CI", "PATH"])
    envs = matcher.match_type("env")
    names = {matcher.get_attribute(e, "name") for e in envs}
    assert "CI" in names
    assert "PATH" in names
