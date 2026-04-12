"""Tests for mount-entity-driven topology in the nsjail compiler."""
from pathlib import Path

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.nsjail import NsjailCompiler
from umwelt.sandbox.entities import MountEntity


def test_bind_mount_from_entity():
    """mount[path="/workspace/src"] { source: "./src"; } produces a bind mount stanza."""
    rv = ResolvedView()
    rv.add("world", MountEntity(path="/workspace/src"), {"source": "./src", "readonly": "false"})
    output = NsjailCompiler().compile(rv, include_system_mounts=False)
    assert 'src: "./src"' in output
    assert 'dst: "/workspace/src"' in output
    assert "is_bind: true" in output
    assert "rw: true" in output


def test_readonly_mount():
    """mount[path="/workspace/tests"] { source: "./tests"; readonly: true; }"""
    rv = ResolvedView()
    rv.add("world", MountEntity(path="/workspace/tests"), {"source": "./tests", "readonly": "true"})
    output = NsjailCompiler().compile(rv, include_system_mounts=False)
    assert "rw: false" in output


def test_tmpfs_mount_from_entity():
    """mount[path="/tmp"] { type: "tmpfs"; size: "64MB"; }"""
    rv = ResolvedView()
    rv.add("world", MountEntity(path="/tmp", type="tmpfs"), {"type": "tmpfs", "size": "64MB"})
    output = NsjailCompiler().compile(rv, include_system_mounts=False)
    assert 'dst: "/tmp"' in output
    assert 'fstype: "tmpfs"' in output
    assert 'options: "size=64M"' in output
    assert "is_bind: false" in output


def test_mount_entities_coexist_with_file_entities():
    """Mount entities and file entities both produce mount stanzas."""
    from umwelt.sandbox.entities import FileEntity
    rv = ResolvedView()
    rv.add("world", MountEntity(path="/workspace/lib"), {"source": "./lib", "readonly": "true"})
    rv.add("world", FileEntity(path="src/main.py", abs_path=Path("/project/src/main.py"), name="main.py"), {"editable": "true"})
    output = NsjailCompiler().compile(rv, include_system_mounts=False)
    assert output.count("mount {") == 2
