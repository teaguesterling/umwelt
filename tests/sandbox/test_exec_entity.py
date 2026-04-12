"""Tests for executable entity registration and dataclass."""

from __future__ import annotations

import pytest

from umwelt.sandbox.entities import ExecEntity


def test_exec_entity_fields():
    e = ExecEntity(name="bash", path="/bin/bash")
    assert e.name == "bash"
    assert e.path == "/bin/bash"
    assert e.search_path is None


def test_exec_entity_frozen():
    e = ExecEntity(name="python3")
    with pytest.raises(AttributeError):
        e.name = "other"  # type: ignore[misc]


def test_exec_entity_search_path():
    e = ExecEntity(search_path="/bin:/usr/bin")
    assert e.search_path == "/bin:/usr/bin"
    assert e.name is None


def test_exec_entity_all_none_by_default():
    e = ExecEntity()
    assert e.name is None
    assert e.path is None
    assert e.search_path is None


def test_exec_entity_registered_in_vocabulary():
    from umwelt.registry import get_entity, get_property, registry_scope
    from umwelt.sandbox.vocabulary import register_sandbox_vocabulary

    with registry_scope():
        register_sandbox_vocabulary()
        entity = get_entity("world", "exec")
        assert entity.name == "exec"
        assert "name" in entity.attributes
        assert "path" in entity.attributes


def test_exec_path_property_registered():
    from umwelt.registry import get_property, registry_scope
    from umwelt.sandbox.vocabulary import register_sandbox_vocabulary

    with registry_scope():
        register_sandbox_vocabulary()
        prop = get_property("world", "exec", "path")
        assert prop.name == "path"
        assert prop.value_type is str


def test_exec_search_path_property_registered():
    from umwelt.registry import get_property, registry_scope
    from umwelt.sandbox.vocabulary import register_sandbox_vocabulary

    with registry_scope():
        register_sandbox_vocabulary()
        prop = get_property("world", "exec", "search-path")
        assert prop.name == "search-path"
        assert prop.value_type is str


def test_tool_exec_bridge_property_registered():
    from umwelt.registry import get_property, registry_scope
    from umwelt.sandbox.vocabulary import register_sandbox_vocabulary

    with registry_scope():
        register_sandbox_vocabulary()
        prop = get_property("capability", "tool", "exec")
        assert prop.name == "exec"
        assert prop.value_type is str
