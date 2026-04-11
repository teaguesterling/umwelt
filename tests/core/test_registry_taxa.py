"""Tests for taxon registration."""

import pytest

from umwelt.errors import RegistryError
from umwelt.registry import (
    get_taxon,
    list_taxa,
    register_taxon,
    registry_scope,
)


def test_register_and_lookup():
    with registry_scope():
        register_taxon(name="world", description="the actor's world")
        taxon = get_taxon("world")
        assert taxon.name == "world"
        assert taxon.description == "the actor's world"


def test_register_with_ma_concept():
    with registry_scope():
        register_taxon(
            name="world",
            description="the actor's world",
            ma_concept="world_coupling_axis",
        )
        taxon = get_taxon("world")
        assert taxon.ma_concept == "world_coupling_axis"


def test_duplicate_raises():
    with registry_scope():
        register_taxon(name="world", description="first")
        with pytest.raises(RegistryError, match="already registered"):
            register_taxon(name="world", description="second")


def test_unknown_raises():
    with registry_scope(), pytest.raises(RegistryError, match="not registered"):
        get_taxon("ghost")


def test_list_taxa():
    with registry_scope():
        register_taxon(name="world", description="a")
        register_taxon(name="capability", description="b")
        names = {t.name for t in list_taxa()}
        assert names == {"world", "capability"}


def test_scope_isolation():
    with registry_scope():
        register_taxon(name="world", description="inside")
        assert get_taxon("world").description == "inside"
    # Outside the scope, the taxon is gone
    with pytest.raises(RegistryError):
        get_taxon("world")


def test_nested_scopes():
    with registry_scope():
        register_taxon(name="outer", description="o")
        with registry_scope():
            register_taxon(name="inner", description="i")
            assert get_taxon("inner").name == "inner"
            with pytest.raises(RegistryError):
                get_taxon("outer")
        # Inner scope done; outer is back
        assert get_taxon("outer").name == "outer"
        with pytest.raises(RegistryError):
            get_taxon("inner")
