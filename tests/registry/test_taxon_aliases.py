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


def test_list_taxa_includes_aliases():
    with registry_scope():
        register_taxon(name="state", description="")
        register_taxon_alias(alias="coordination", canonical="state")
        from umwelt.registry import list_taxa
        names = {t.name for t in list_taxa()}
        assert "state" in names
