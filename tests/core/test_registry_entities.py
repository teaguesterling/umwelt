"""Tests for entity registration."""

import pytest

from umwelt.errors import RegistryError
from umwelt.registry import (
    AttrSchema,
    get_entity,
    list_entities,
    register_entity,
    register_taxon,
    registry_scope,
    resolve_entity_type,
)


def test_register_entity_minimal():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(
            taxon="world",
            name="file",
            attributes={"path": AttrSchema(type=str, required=True)},
            description="a file",
        )
        entity = get_entity("world", "file")
        assert entity.name == "file"
        assert entity.taxon == "world"
        assert entity.parent is None
        assert entity.attributes["path"].type is str
        assert entity.attributes["path"].required is True


def test_register_entity_with_parent():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(
            taxon="world",
            name="dir",
            attributes={"path": AttrSchema(type=str, required=True)},
            description="a dir",
        )
        register_entity(
            taxon="world",
            name="file",
            parent="dir",
            attributes={"path": AttrSchema(type=str, required=True)},
            description="a file",
        )
        assert get_entity("world", "file").parent == "dir"


def test_register_entity_with_category():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(
            taxon="world",
            name="file",
            attributes={},
            description="a file",
            category="filesystem",
        )
        assert get_entity("world", "file").category == "filesystem"


def test_duplicate_entity_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        with pytest.raises(RegistryError, match="already registered"):
            register_entity(taxon="world", name="file", attributes={}, description="b")


def test_register_entity_unknown_taxon_raises():
    with registry_scope(), pytest.raises(RegistryError, match="taxon 'ghost' not registered"):
        register_entity(taxon="ghost", name="file", attributes={}, description="a")


def test_get_entity_unknown_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        with pytest.raises(RegistryError, match="entity 'file' not registered"):
            get_entity("world", "file")


def test_resolve_entity_type_unique():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        taxa = resolve_entity_type("file")
        assert taxa == ["world"]


def test_resolve_entity_type_ambiguous():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_taxon(name="audit", description="a")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        register_entity(taxon="audit", name="file", attributes={}, description="b")
        taxa = resolve_entity_type("file")
        assert set(taxa) == {"world", "audit"}


def test_resolve_entity_type_unknown():
    with registry_scope():
        assert resolve_entity_type("ghost") == []


def test_list_entities_for_taxon():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        register_entity(taxon="world", name="dir", attributes={}, description="b")
        entities = list_entities("world")
        assert {e.name for e in entities} == {"file", "dir"}
