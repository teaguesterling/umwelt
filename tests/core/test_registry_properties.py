"""Tests for property registration."""

import pytest

from umwelt.errors import RegistryError
from umwelt.registry import (
    AttrSchema,
    get_property,
    list_properties,
    register_entity,
    register_property,
    register_taxon,
    registry_scope,
)


def test_register_exact_property():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(
            taxon="world",
            name="file",
            attributes={"path": AttrSchema(type=str, required=True)},
            description="a file",
        )
        register_property(
            taxon="world",
            entity="file",
            name="editable",
            value_type=bool,
            description="whether the actor may modify this file",
        )
        prop = get_property("world", "file", "editable")
        assert prop.name == "editable"
        assert prop.value_type is bool
        assert prop.comparison == "exact"


def test_register_comparison_property():
    with registry_scope():
        register_taxon(name="capability", description="c")
        register_entity(taxon="capability", name="tool", attributes={}, description="t")
        register_property(
            taxon="capability",
            entity="tool",
            name="max-level",
            value_type=int,
            comparison="<=",
            value_attribute="level",
            value_range=(0, 8),
            description="maximum computation level",
            category="effects_ceiling",
        )
        prop = get_property("capability", "tool", "max-level")
        assert prop.comparison == "<="
        assert prop.value_attribute == "level"
        assert prop.value_range == (0, 8)
        assert prop.category == "effects_ceiling"


def test_register_pattern_property():
    with registry_scope():
        register_taxon(name="capability", description="c")
        register_entity(taxon="capability", name="tool", attributes={}, description="t")
        register_property(
            taxon="capability",
            entity="tool",
            name="allow-pattern",
            value_type=list,
            comparison="pattern-in",
            description="glob patterns that allow the invocation",
        )
        assert get_property("capability", "tool", "allow-pattern").comparison == "pattern-in"


def test_duplicate_property_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        register_property(
            taxon="world",
            entity="file",
            name="editable",
            value_type=bool,
            description="d1",
        )
        with pytest.raises(RegistryError, match="already registered"):
            register_property(
                taxon="world",
                entity="file",
                name="editable",
                value_type=bool,
                description="d2",
            )


def test_register_property_unknown_entity_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        with pytest.raises(RegistryError, match="entity 'file' not registered"):
            register_property(
                taxon="world",
                entity="file",
                name="editable",
                value_type=bool,
                description="d",
            )


def test_list_properties_for_entity():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        register_property(
            taxon="world", entity="file", name="editable", value_type=bool, description="a"
        )
        register_property(
            taxon="world", entity="file", name="visible", value_type=bool, description="b"
        )
        names = {p.name for p in list_properties("world", "file")}
        assert names == {"editable", "visible"}
