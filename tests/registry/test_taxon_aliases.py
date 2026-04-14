"""Tests for taxon aliasing — multiple names pointing to the same TaxonSchema."""
from __future__ import annotations

import pytest
from umwelt.registry import (
    get_taxon,
    register_taxon,
    registry_scope,
)
from umwelt.registry.taxa import register_taxon_alias


def test_alias_resolves_to_same_schema():
    with registry_scope():
        register_taxon(name="state", description="observation layer")
        register_taxon_alias(alias="coordination", canonical="state")
        state = get_taxon("state")
        coordination = get_taxon("coordination")
        assert state is coordination


def test_alias_for_unknown_canonical_raises():
    with registry_scope():
        with pytest.raises(KeyError):
            register_taxon_alias(alias="coordination", canonical="state")


def test_alias_collides_with_existing_taxon_raises():
    with registry_scope():
        register_taxon(name="state", description="")
        register_taxon(name="coordination", description="")
        with pytest.raises(ValueError):
            register_taxon_alias(alias="coordination", canonical="state")


def test_list_taxa_excludes_alias_entries():
    with registry_scope():
        register_taxon(name="state", description="")
        register_taxon_alias(alias="coordination", canonical="state")
        from umwelt.registry import list_taxa
        names = {t.name for t in list_taxa()}
        assert "state" in names
        assert "coordination" not in names


def test_aliasing_an_alias_raises():
    with registry_scope():
        register_taxon(name="state", description="")
        register_taxon_alias(alias="coordination", canonical="state")
        with pytest.raises(ValueError):
            register_taxon_alias(alias="control", canonical="coordination")


def test_properties_resolve_through_alias():
    from umwelt.registry import (
        get_property,
        list_properties,
        register_entity,
        register_property,
    )
    from umwelt.registry.entities import AttrSchema
    with registry_scope():
        register_taxon(name="state", description="")
        register_taxon_alias(alias="coordination", canonical="state")
        register_entity(
            taxon="state",
            name="hook",
            attributes={"event": AttrSchema(type=str, required=True)},
            description="",
        )
        register_property(
            taxon="coordination", entity="hook", name="run",
            value_type=str, description="",
        )
        via_canonical = get_property("state", "hook", "run")
        via_alias = get_property("coordination", "hook", "run")
        assert via_canonical is via_alias
        assert len(list_properties("state", "hook")) == 1
        assert len(list_properties("coordination", "hook")) == 1


def test_matchers_resolve_through_alias():
    from umwelt.registry import get_matcher, register_matcher

    class StubMatcher:
        def match_type(self, type_name, context=None): return []
        def children(self, parent, child_type): return []
        def condition_met(self, selector, context=None): return True
        def get_attribute(self, entity, name): return None
        def get_id(self, entity): return None

    with registry_scope():
        register_taxon(name="state", description="")
        register_taxon_alias(alias="coordination", canonical="state")
        m = StubMatcher()
        register_matcher(taxon="coordination", matcher=m)
        assert get_matcher("state") is m
        assert get_matcher("coordination") is m
