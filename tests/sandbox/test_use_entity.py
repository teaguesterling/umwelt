"""Tests that use[of=...] registers as a first-class entity.

Verifies claim A5 (property comparison semantics — each `use` permission
property declares its comparison field). See docs/vision/evaluation-framework.md.
"""
from __future__ import annotations

import pytest
from umwelt.registry import get_entity, get_property, register_taxon_alias, registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary


@pytest.fixture
def vocab_scope():
    with registry_scope():
        register_sandbox_vocabulary()
        yield


def test_use_entity_registered(vocab_scope):
    entity = get_entity(taxon="operation", name="use")
    assert entity is not None
    assert "of" in entity.attributes
    assert "of-kind" in entity.attributes
    assert "of-like" in entity.attributes


def test_use_editable_property_registered(vocab_scope):
    """A5: editable is a bool property with exact comparison."""
    prop = get_property(taxon="operation", entity="use", name="editable")
    assert prop.value_type is bool


def test_use_visible_property_registered(vocab_scope):
    """A5: visible is a bool property."""
    prop = get_property(taxon="operation", entity="use", name="visible")
    assert prop.value_type is bool


def test_use_show_property_registered(vocab_scope):
    """A5: show is a str property (enum-like: body/outline/signature)."""
    prop = get_property(taxon="operation", entity="use", name="show")
    assert prop.value_type is str


def test_use_allow_property_registered(vocab_scope):
    """A5: allow is a bool property."""
    prop = get_property(taxon="operation", entity="use", name="allow")
    assert prop.value_type is bool


def test_use_deny_property_registered(vocab_scope):
    """A5: deny is a str property."""
    prop = get_property(taxon="operation", entity="use", name="deny")
    assert prop.value_type is str


def test_use_allow_pattern_uses_pattern_comparison(vocab_scope):
    """A5: allow-pattern has comparison='pattern-in'."""
    prop = get_property(taxon="operation", entity="use", name="allow-pattern")
    assert prop.comparison == "pattern-in"


def test_use_deny_pattern_uses_pattern_comparison(vocab_scope):
    """A5: deny-pattern has comparison='pattern-in'."""
    prop = get_property(taxon="operation", entity="use", name="deny-pattern")
    assert prop.comparison == "pattern-in"


def test_use_findable_under_capability_alias(vocab_scope):
    """I3: use is findable under 'capability' too (operation is an alias)."""
    via_op = get_entity(taxon="operation", name="use")
    via_cap = get_entity(taxon="capability", name="use")
    assert via_op is via_cap
