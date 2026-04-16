"""Tests that VSM taxa are registered as aliases of legacy taxa.

Verifies claims G1 (VSM fidelity — VSM taxa names resolve correctly) and
I3 (alias transparency — entity lookups work through aliases).
See docs/vision/evaluation-framework.md.
"""
from __future__ import annotations

import pytest

from umwelt.registry import (
    get_entity,
    get_property,
    get_taxon,
    registry_scope,
)
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary


@pytest.fixture
def vocab_scope():
    """Fresh registry scope with sandbox vocabulary registered."""
    with registry_scope():
        register_sandbox_vocabulary()
        yield


def test_operation_aliases_capability(vocab_scope):
    """G1: operation is the S1 alias for capability."""
    assert get_taxon("operation") is get_taxon("capability")


def test_coordination_aliases_state(vocab_scope):
    """G1: coordination is the S2 alias for state (v0.5 virtual split)."""
    assert get_taxon("coordination") is get_taxon("state")


def test_control_aliases_state(vocab_scope):
    """G1: control is the S3 alias for state (v0.5 virtual split)."""
    assert get_taxon("control") is get_taxon("state")


def test_intelligence_aliases_actor(vocab_scope):
    """G1: intelligence is the S4 alias for actor."""
    assert get_taxon("intelligence") is get_taxon("actor")


def test_tool_entity_findable_under_operation(vocab_scope):
    """I3: entity lookup via the alias returns the same schema as via canonical."""
    tool_via_capability = get_entity(taxon="capability", name="tool")
    tool_via_operation = get_entity(taxon="operation", name="tool")
    assert tool_via_capability is tool_via_operation


def test_hook_entity_findable_under_coordination(vocab_scope):
    """I3: hook is findable under the coordination alias."""
    hook_via_state = get_entity(taxon="state", name="hook")
    hook_via_coordination = get_entity(taxon="coordination", name="hook")
    assert hook_via_state is hook_via_coordination


def test_inferencer_findable_under_intelligence(vocab_scope):
    """I3: inferencer is findable under the intelligence alias."""
    inf_via_actor = get_entity(taxon="actor", name="inferencer")
    inf_via_intelligence = get_entity(taxon="intelligence", name="inferencer")
    assert inf_via_actor is inf_via_intelligence


def test_property_registered_under_alias_resolves_canonically(vocab_scope):
    """I3: a property registered via an alias can be retrieved via canonical."""
    # hook.run is registered under taxon="state" in the sandbox vocabulary.
    prop_via_state = get_property(taxon="state", entity="hook", name="run")
    prop_via_coordination = get_property(taxon="coordination", entity="hook", name="run")
    assert prop_via_state is prop_via_coordination
