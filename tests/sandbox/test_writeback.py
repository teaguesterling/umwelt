"""Tests for workspace writeback."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from umwelt.sandbox.workspace.errors import ViewViolation
from umwelt.sandbox.workspace.manifest import ManifestEntry, WorkspaceManifest
from umwelt.sandbox.workspace.writeback import Applied, Conflict, NoOp, Rejected, WriteBack


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _entry(
    tmp_path: Path,
    filename: str = "f.py",
    writable: bool = True,
    content: str = "original",
) -> tuple[ManifestEntry, Path, Path]:
    """Create a real file, a virtual file, and a manifest entry."""
    real = tmp_path / "real" / filename
    real.parent.mkdir(parents=True, exist_ok=True)
    real.write_text(content)

    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    virtual = ws / filename
    if writable:
        virtual.write_text(content)
    else:
        virtual.symlink_to(real)

    entry = ManifestEntry(
        real_path=real,
        virtual_path=Path(filename),
        writable=writable,
        content_hash_at_build=_hash(content),
        strategy_name="default",
    )
    return entry, real, ws


def test_writable_unchanged_is_noop(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, NoOp)


def test_writable_changed_real_unchanged_is_applied(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    (ws / "f.py").write_text("modified by delegate")
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, Applied)
    assert result.new_content == b"modified by delegate"


def test_writable_changed_real_changed_is_conflict(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    (ws / "f.py").write_text("delegate edit")
    real.write_text("external edit")
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, Conflict)


def test_writable_unchanged_real_changed_is_conflict(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    real.write_text("external edit")
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, Conflict)


def test_readonly_unchanged_is_noop(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=False)
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, NoOp)


def test_readonly_changed_is_rejected(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=False)
    # Modify the real file (which the symlink points to)
    real.write_text("someone modified this")
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, Rejected)


def test_full_writeback_applies_changes(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    (ws / "f.py").write_text("delegate wrote this")
    manifest = WorkspaceManifest(
        entries=(entry,),
        base_dir=tmp_path / "real",
        workspace_root=ws,
    )
    wb = WriteBack()
    result = wb.apply(manifest)
    assert len(result.applied) == 1
    assert real.read_text() == "delegate wrote this"


def test_strict_mode_raises_on_rejected(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=False)
    real.write_text("modified")
    manifest = WorkspaceManifest(entries=(entry,), base_dir=tmp_path / "real", workspace_root=ws)
    with pytest.raises(ViewViolation):
        WriteBack(strict=True).apply(manifest)


def test_strict_mode_raises_on_conflict(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    (ws / "f.py").write_text("delegate edit")
    real.write_text("external edit")
    manifest = WorkspaceManifest(entries=(entry,), base_dir=tmp_path / "real", workspace_root=ws)
    with pytest.raises(ViewViolation):
        WriteBack(strict=True).apply(manifest)
