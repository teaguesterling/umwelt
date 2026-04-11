"""Tests for the per-taxon validator dispatcher."""

from __future__ import annotations

import pytest

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.ast import ParseWarning
from umwelt.errors import ViewValidationError
from umwelt.parser import parse
from umwelt.registry import (
    register_validator,
    registry_scope,
)


class _RecordingValidator:
    """Validator that records which rules it saw. Raises nothing."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def validate(self, rules, warnings):
        for rule in rules:
            for sel in rule.selectors:
                self.seen.append(sel.parts[-1].selector.type_name or "*")


class _RejectingValidator:
    """Validator that raises ViewValidationError for rule with 'widget' type."""

    def validate(self, rules, warnings):
        for rule in rules:
            for sel in rule.selectors:
                if sel.parts[-1].selector.type_name == "widget":
                    raise ViewValidationError("widgets are not allowed in v0.1 core tests")


class _WarningValidator:
    """Validator that appends a ParseWarning for every thing rule."""

    def validate(self, rules, warnings):
        for rule in rules:
            for sel in rule.selectors:
                if sel.parts[-1].selector.type_name == "thing":
                    warnings.append(
                        ParseWarning(
                            message="thing flagged by validator",
                            span=rule.span,
                        )
                    )


def test_validator_sees_its_taxon_rules():
    with registry_scope():
        install_toy_taxonomy()
        v = _RecordingValidator()
        register_validator(taxon="shapes", validator=v)
        parse("thing { } widget { }")
    assert v.seen == ["thing", "widget"]


def test_validator_does_not_see_other_taxa():
    with registry_scope():
        install_toy_taxonomy()
        v = _RecordingValidator()
        register_validator(taxon="shapes", validator=v)
        parse("actor { }")  # actors taxon
    assert v.seen == []


def test_rejecting_validator_raises():
    with registry_scope():
        install_toy_taxonomy()
        register_validator(taxon="shapes", validator=_RejectingValidator())
        with pytest.raises(ViewValidationError, match="widgets are not allowed"):
            parse("widget { }")


def test_validator_appends_warnings():
    with registry_scope():
        install_toy_taxonomy()
        register_validator(taxon="shapes", validator=_WarningValidator())
        view = parse("thing { }")
    assert any("flagged by validator" in w.message for w in view.warnings)


def test_validate_flag_disables_validators():
    with registry_scope():
        install_toy_taxonomy()
        register_validator(taxon="shapes", validator=_RejectingValidator())
        # With validate=False, the rejecting validator never runs.
        view = parse("widget { }", validate=False)
    assert len(view.rules) == 1


def test_multiple_validators_per_taxon_all_run():
    with registry_scope():
        install_toy_taxonomy()
        a = _RecordingValidator()
        b = _RecordingValidator()
        register_validator(taxon="shapes", validator=a)
        register_validator(taxon="shapes", validator=b)
        parse("thing { }")
    assert a.seen == ["thing"]
    assert b.seen == ["thing"]
