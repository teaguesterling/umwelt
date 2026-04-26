"""Tests for cross-taxon validator protocol, registration, and dispatch."""
from __future__ import annotations

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.parser import parse
from umwelt.registry import registry_scope
from umwelt.registry.validators import (
    CrossTaxonValidatorProtocol,
    get_cross_taxon_validators,
    register_cross_taxon_validator,
)


class _RecordingCrossValidator:
    def __init__(self):
        self.views_seen: list = []
    def validate(self, view, warnings):
        self.views_seen.append(view)


def test_cross_validator_protocol_is_runtime_checkable():
    assert isinstance(_RecordingCrossValidator(), CrossTaxonValidatorProtocol)

def test_register_and_retrieve_cross_validator():
    with registry_scope():
        v = _RecordingCrossValidator()
        register_cross_taxon_validator(v)
        assert v in get_cross_taxon_validators()

def test_cross_validator_receives_full_view():
    with registry_scope():
        install_toy_taxonomy()
        v = _RecordingCrossValidator()
        register_cross_taxon_validator(v)
        parse("thing { paint: red; } actor { allowed: true; }")
    assert len(v.views_seen) == 1
    assert len(v.views_seen[0].rules) == 2

def test_cross_validator_runs_after_per_taxon():
    with registry_scope():
        install_toy_taxonomy()
        order = []

        class PerTaxon:
            def validate(self, rules, warnings):
                order.append("per-taxon")

        class CrossTaxon:
            def validate(self, view, warnings):
                order.append("cross-taxon")

        from umwelt.registry import register_validator
        register_validator(taxon="shapes", validator=PerTaxon())
        register_cross_taxon_validator(CrossTaxon())
        parse("thing { paint: red; }")

    assert order == ["per-taxon", "cross-taxon"]
