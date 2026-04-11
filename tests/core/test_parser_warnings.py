"""Tests for parser warnings (soft errors that don't abort parsing)."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.parser import parse
from umwelt.registry import registry_scope


def test_duplicate_declaration_key_warns():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red; paint: blue; }")
    # The rule still has two declarations (cascade resolves).
    assert len(view.rules[0].declarations) == 2
    # And the parser attached a warning.
    assert any(
        "duplicate" in w.message.lower() and "paint" in w.message
        for w in view.warnings
    )


def test_no_warning_on_single_declaration():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red; }")
    assert view.warnings == ()


def test_unknown_top_level_at_rule_no_warning():
    # Unknown at-rules are preserved, not warned — they're forward-compat
    # hooks, not errors.
    with registry_scope():
        install_toy_taxonomy()
        view = parse("@future { whatever: 1; }")
    assert len(view.unknown_at_rules) == 1
    assert view.warnings == ()
