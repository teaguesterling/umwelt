"""Tests for the principal taxon (S5).

Verifies claim G1 (VSM fidelity — principal is the S5 identity axis).
See docs/vision/evaluation-framework.md.
"""
from __future__ import annotations

import pytest
from umwelt.parser import parse
from umwelt.cascade.resolver import resolve
from umwelt.registry import registry_scope, register_matcher, get_taxon, get_entity
from umwelt.sandbox.capability_matcher import CapabilityMatcher
from umwelt.sandbox.entities import PrincipalEntity, UseEntity
from umwelt.sandbox.principal_matcher import PrincipalMatcher
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.world_matcher import WorldMatcher


@pytest.fixture
def vocab_with_matchers(tmp_path):
    with registry_scope():
        register_sandbox_vocabulary()
        register_matcher(taxon="world", matcher=WorldMatcher(base_dir=tmp_path))
        register_matcher(taxon="capability", matcher=CapabilityMatcher())
        register_matcher(taxon="principal", matcher=PrincipalMatcher())
        yield tmp_path


def _parse(text, tmp_path):
    p = tmp_path / "test.umw"
    p.write_text(text)
    return parse(p)


def test_principal_taxon_registered(vocab_with_matchers):
    """G1: principal is registered as a standalone S5 taxon."""
    assert get_taxon("principal") is not None
    assert get_entity(taxon="principal", name="principal") is not None


def test_principal_id_selector_matches(vocab_with_matchers):
    """G1: principal#id parses and the ID flows into a PrincipalEntity."""
    view = _parse('principal#Teague { intent: "code review"; grade: 2; }', vocab_with_matchers)
    rv = resolve(view)
    principals = list(rv.entries("principal"))
    matching = [(e, p) for e, p in principals if isinstance(e, PrincipalEntity)]
    assert matching
    entity, props = matching[0]
    assert entity.name == "Teague"
    assert props.get("intent") == '"code review"' or props.get("intent") == "code review"
    assert props.get("grade") == "2"


def test_multiple_principals(vocab_with_matchers):
    """G1: distinct #ids produce distinct PrincipalEntity instances."""
    view = _parse('''
        principal#Alice { intent: "review"; }
        principal#Bob { intent: "implement"; }
    ''', vocab_with_matchers)
    rv = resolve(view)
    principals = [(e, p) for e, p in rv.entries("principal") if isinstance(e, PrincipalEntity)]
    names = {e.name for e, _ in principals}
    assert names == {"Alice", "Bob"}


def test_principal_cross_axis_qualifier(vocab_with_matchers):
    """G1: principal#X use[of=Y] { ... } composes across the principal and operation axes."""
    view = _parse('''
        principal#Teague use[of="file#/src/x.py"] { editable: true; }
    ''', vocab_with_matchers)
    rv = resolve(view)
    # Just confirm no error and the view resolves.
    uses = [(e, p) for e, p in rv.entries("operation") if isinstance(e, UseEntity)]
    # The use rule should resolve (principal qualifier is satisfied because Teague exists).
    assert any(p.get("editable") == "true" for _, p in uses)


def test_principal_taxon_not_an_alias(vocab_with_matchers):
    """G1: principal is a real standalone taxon, not an alias of an existing one."""
    from umwelt.registry import resolve_taxon
    assert resolve_taxon("principal") == "principal"
