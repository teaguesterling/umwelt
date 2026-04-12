"""Tests for workspace manifest dataclasses."""

from __future__ import annotations

from pathlib import Path

from umwelt.sandbox.workspace.manifest import ManifestEntry, WorkspaceManifest


def test_manifest_entry_construction():
    entry = ManifestEntry(
        real_path=Path("/project/src/main.py"),
        virtual_path=Path("src/main.py"),
        writable=True,
        content_hash_at_build="abc123",
        strategy_name="default",
    )
    assert entry.writable is True
    assert entry.content_hash_at_build == "abc123"


def test_manifest_entry_readonly():
    entry = ManifestEntry(
        real_path=Path("/project/src/main.py"),
        virtual_path=Path("src/main.py"),
        writable=False,
        content_hash_at_build="def456",
        strategy_name="default",
    )
    assert entry.writable is False
    assert entry.content_hash_at_build == "def456"


def test_workspace_manifest_entries():
    entries = (
        ManifestEntry(Path("/a"), Path("a"), True, "h1", "default"),
        ManifestEntry(Path("/b"), Path("b"), False, "h2", "default"),
    )
    manifest = WorkspaceManifest(
        entries=entries,
        base_dir=Path("/project"),
        workspace_root=Path("/tmp/ws"),
    )
    assert len(manifest.entries) == 2
    assert manifest.base_dir == Path("/project")
    assert manifest.workspace_root == Path("/tmp/ws")
