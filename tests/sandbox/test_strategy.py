"""Tests for the materialization strategy."""

from __future__ import annotations

import hashlib

from umwelt.sandbox.workspace.strategy import (
    SymlinkReadonlyCopyWritable,
    get_strategy,
    register_strategy,
)


def test_materialize_readonly_creates_symlink(tmp_path):
    real = tmp_path / "real.py"
    real.write_text("content")
    ws = tmp_path / "ws"
    ws.mkdir()
    virtual = ws / "real.py"
    strategy = SymlinkReadonlyCopyWritable()
    entry = strategy.materialize(real, virtual, writable=False)
    assert virtual.is_symlink()
    assert virtual.resolve() == real.resolve()
    assert entry.writable is False
    assert entry.content_hash_at_build == hashlib.sha256(b"content").hexdigest()


def test_materialize_writable_creates_copy(tmp_path):
    real = tmp_path / "real.py"
    real.write_text("content")
    ws = tmp_path / "ws"
    ws.mkdir()
    virtual = ws / "real.py"
    strategy = SymlinkReadonlyCopyWritable()
    entry = strategy.materialize(real, virtual, writable=True)
    assert not virtual.is_symlink()
    assert virtual.read_text() == "content"
    assert entry.writable is True
    assert entry.content_hash_at_build == hashlib.sha256(b"content").hexdigest()


def test_materialize_creates_parent_dirs(tmp_path):
    real = tmp_path / "real.py"
    real.write_text("x")
    ws = tmp_path / "ws"
    virtual = ws / "deep" / "path" / "real.py"
    strategy = SymlinkReadonlyCopyWritable()
    strategy.materialize(real, virtual, writable=True)
    assert virtual.exists()


def test_hash_captured_for_both_modes(tmp_path):
    real = tmp_path / "f.py"
    real.write_text("hello")
    ws = tmp_path / "ws"
    ws.mkdir()

    strategy = SymlinkReadonlyCopyWritable()
    entry_ro = strategy.materialize(real, ws / "ro.py", writable=False)
    entry_rw = strategy.materialize(real, ws / "rw.py", writable=True)
    expected_hash = hashlib.sha256(b"hello").hexdigest()
    assert entry_ro.content_hash_at_build == expected_hash
    assert entry_rw.content_hash_at_build == expected_hash


def test_register_and_get_default():
    strategy = get_strategy("default")
    assert isinstance(strategy, SymlinkReadonlyCopyWritable)


def test_register_custom_strategy():
    class Custom:
        name = "custom"

        def materialize(self, real, virtual, writable):
            pass

        def reconcile(self, entry, workspace_root):
            pass

    register_strategy(Custom())
    assert get_strategy("custom").name == "custom"
