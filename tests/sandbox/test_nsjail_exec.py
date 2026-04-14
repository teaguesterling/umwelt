"""Tests for nsjail PATH emission from executable entities."""

from __future__ import annotations

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.nsjail import NsjailCompiler
from umwelt.sandbox.entities import EnvEntity, ExecEntity


def test_exec_search_path_emits_path_envar():
    rv = ResolvedView()
    rv.add("world", ExecEntity(search_path="/bin:/usr/bin:/usr/local/bin"), {"search-path": "/bin:/usr/bin:/usr/local/bin"})
    output = NsjailCompiler().compile(rv)
    assert 'envar: "PATH=/bin:/usr/bin:/usr/local/bin"' in output


def test_exec_default_search_path():
    """When executable entity exists but search-path is not set, don't emit PATH."""
    rv = ResolvedView()
    rv.add("world", ExecEntity(name="bash", path="/bin/bash"), {"path": "/bin/bash"})
    output = NsjailCompiler().compile(rv)
    # Named executable without search-path doesn't emit PATH - only the bare one does
    assert "PATH=" not in output


def test_exec_with_search_path_property():
    rv = ResolvedView()
    rv.add("world", ExecEntity(), {"search-path": "/usr/bin:/usr/local/bin"})
    output = NsjailCompiler().compile(rv)
    assert 'envar: "PATH=/usr/bin:/usr/local/bin"' in output


def test_named_exec_entity_no_path_envar():
    """A named executable (exec[name='bash']) doesn't emit PATH, only bare one does."""
    rv = ResolvedView()
    rv.add("world", ExecEntity(name="pytest", path="/usr/local/bin/pytest"), {"path": "/usr/local/bin/pytest"})
    output = NsjailCompiler().compile(rv)
    assert "PATH=" not in output


def test_path_envar_combined_with_other_envars():
    """PATH from executable and allowed env vars coexist."""
    rv = ResolvedView()
    rv.add("world", ExecEntity(), {"search-path": "/bin:/usr/bin"})
    rv.add("world", EnvEntity(name="CI"), {"allow": "true"})
    output = NsjailCompiler().compile(rv)
    assert 'envar: "PATH=/bin:/usr/bin"' in output
    assert 'envar: "CI"' in output
