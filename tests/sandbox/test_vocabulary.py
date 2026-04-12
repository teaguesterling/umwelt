"""Tests for sandbox vocabulary registration."""

from __future__ import annotations

import sys

from umwelt.registry import (
    get_entity,
    get_property,
    get_taxon,
    registry_scope,
)


def _register_sandbox() -> None:
    """Register sandbox vocabulary in the current registry scope.

    On first call (before any sandbox module is cached), imports umwelt.sandbox
    so that __init__.py fires into the active scope. On subsequent calls (module
    already cached), calls register_sandbox_vocabulary() directly.
    """
    if "umwelt.sandbox" not in sys.modules:
        import umwelt.sandbox  # noqa: F401  # fires __init__ into current scope
    else:
        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        register_sandbox_vocabulary()


def test_world_taxon_registered():
    with registry_scope():
        _register_sandbox()
        taxon = get_taxon("world")
        assert taxon.name == "world"
        assert taxon.ma_concept == "world_coupling_axis"


def test_capability_taxon_registered():
    with registry_scope():
        _register_sandbox()
        taxon = get_taxon("capability")
        assert taxon.name == "capability"


def test_state_taxon_registered():
    with registry_scope():
        _register_sandbox()
        taxon = get_taxon("state")
        assert taxon.name == "state"


def test_world_file_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "file")
        assert entity.name == "file"
        assert entity.parent == "dir"
        assert "path" in entity.attributes
        assert entity.attributes["path"].required is True


def test_world_dir_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "dir")
        assert entity.parent is None
        assert "path" in entity.attributes


def test_world_resource_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "resource")
        assert "kind" in entity.attributes


def test_world_network_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "network")
        assert entity.name == "network"


def test_world_env_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "env")
        assert "name" in entity.attributes


def test_capability_tool_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("capability", "tool")
        assert "name" in entity.attributes
        assert "level" in entity.attributes


def test_capability_kit_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("capability", "kit")
        assert entity.name == "kit"


def test_state_hook_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("state", "hook")
        assert "event" in entity.attributes


def test_file_editable_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "file", "editable")
        assert prop.value_type is bool
        assert prop.comparison == "exact"


def test_tool_max_level_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("capability", "tool", "max-level")
        assert prop.comparison == "<="
        assert prop.value_attribute == "level"


def test_tool_allow_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("capability", "tool", "allow")
        assert prop.value_type is bool


def test_tool_allow_pattern_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("capability", "tool", "allow-pattern")
        assert prop.comparison == "pattern-in"


def test_hook_run_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("state", "hook", "run")
        assert prop.name == "run"


def test_resource_limit_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "resource", "limit")
        assert prop.name == "limit"


def test_network_deny_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "network", "deny")
        assert prop.name == "deny"


def test_env_allow_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "env", "allow")
        assert prop.name == "allow"
