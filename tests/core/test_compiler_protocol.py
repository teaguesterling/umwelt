"""Tests for the Compiler protocol and registry."""

from __future__ import annotations

import pytest

from umwelt.cascade.resolver import ResolvedView
from umwelt.compilers import (
    Compiler,
    available,
    clear_compilers,
)
from umwelt.compilers import (
    get as get_compiler,
)
from umwelt.compilers import (
    register as register_compiler,
)
from umwelt.errors import RegistryError


class _NullCompiler:
    target_name = "null"
    target_format = "str"
    altitude = "semantic"

    def compile(self, view: ResolvedView) -> str:
        return ""


class _EchoCompiler:
    target_name = "echo"
    target_format = "list"
    altitude = "os"

    def compile(self, view: ResolvedView) -> list[str]:
        return [taxon for taxon in view.taxa()]


def test_register_and_get():
    clear_compilers()
    register_compiler("null", _NullCompiler())
    assert get_compiler("null").target_name == "null"


def test_available_lists_registered_names():
    clear_compilers()
    register_compiler("null", _NullCompiler())
    register_compiler("echo", _EchoCompiler())
    assert set(available()) == {"null", "echo"}


def test_unknown_compiler_raises():
    clear_compilers()
    with pytest.raises(RegistryError, match="no compiler registered"):
        get_compiler("ghost")


def test_duplicate_registration_last_wins_with_warning(recwarn):
    clear_compilers()
    register_compiler("null", _NullCompiler())
    register_compiler("null", _NullCompiler())
    # At least one warning emitted.
    assert any("already registered" in str(w.message) for w in recwarn.list)


def test_clear_compilers_empties_registry():
    register_compiler("null", _NullCompiler())
    clear_compilers()
    assert available() == []


def test_protocol_runtime_check():
    assert isinstance(_NullCompiler(), Compiler)
    assert isinstance(_EchoCompiler(), Compiler)


def test_compile_against_resolved_view():
    clear_compilers()
    register_compiler("echo", _EchoCompiler())
    rv = ResolvedView()
    rv.add("world", object(), {"editable": "true"})
    rv.add("capability", object(), {"allow": "true"})
    compiler = get_compiler("echo")
    result = compiler.compile(rv)
    assert set(result) == {"world", "capability"}
