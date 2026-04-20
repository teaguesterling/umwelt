"""Tests for the shorthand registry."""

from umwelt.registry.taxa import registry_scope
from umwelt.world.shorthands import ShorthandDef, get_shorthand, register_shorthand


def test_register_and_retrieve():
    with registry_scope():
        register_shorthand(key="tools", entity_type="tool", form="list")
        sd = get_shorthand("tools")
        assert sd is not None
        assert sd.entity_type == "tool"
        assert sd.form == "list"


def test_unknown_returns_none():
    with registry_scope():
        assert get_shorthand("nonexistent") is None


def test_map_form_with_attribute_key():
    with registry_scope():
        register_shorthand(key="resources", entity_type="resource", form="map", attribute_key="limit")
        sd = get_shorthand("resources")
        assert sd is not None
        assert sd.attribute_key == "limit"


def test_scope_isolation():
    with registry_scope():
        register_shorthand(key="tools", entity_type="tool", form="list")
    with registry_scope():
        assert get_shorthand("tools") is None


def test_sandbox_vocabulary_registers_shorthands():
    from umwelt.sandbox.vocabulary import register_sandbox_vocabulary

    with registry_scope():
        register_sandbox_vocabulary()
        assert get_shorthand("tools") is not None
        assert get_shorthand("modes") is not None
        assert get_shorthand("principal") is not None
        assert get_shorthand("inferencer") is not None
        assert get_shorthand("resources") is not None
