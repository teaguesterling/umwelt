"""Tests for declaration parsing inside rule blocks."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.parser import parse
from umwelt.registry import registry_scope


def _sole_declarations(view):
    assert len(view.rules) == 1
    return view.rules[0].declarations


def test_single_declaration():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red; }")
    decls = _sole_declarations(view)
    assert len(decls) == 1
    assert decls[0].property_name == "paint"
    assert decls[0].values == ("red",)


def test_multi_value_declaration_via_commas():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red, green, blue; }")
    decls = _sole_declarations(view)
    assert len(decls) == 1
    assert decls[0].property_name == "paint"
    assert decls[0].values == ("red", "green", "blue")


def test_repeated_declaration_multi_value():
    # `run: "a"; run: "b"` is a multi-value form; the parser produces two
    # Declaration entries and the cascade resolver (Task 22) consolidates.
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing { paint: red; paint: blue; }')
    decls = _sole_declarations(view)
    assert len(decls) == 2
    assert decls[0].values == ("red",)
    assert decls[1].values == ("blue",)


def test_string_value():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing { paint: "crimson red"; }')
    decls = _sole_declarations(view)
    assert decls[0].values == ("crimson red",)


def test_numeric_value_with_unit():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { max-glow: 512; }")
    decls = _sole_declarations(view)
    assert decls[0].property_name == "max-glow"
    assert decls[0].values == ("512",)


def test_numeric_value_with_unit_suffix():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { max-glow: 512MB; }")
    decls = _sole_declarations(view)
    assert decls[0].values == ("512MB",)


def test_declaration_without_trailing_semicolon():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red }")
    decls = _sole_declarations(view)
    assert len(decls) == 1
    assert decls[0].values == ("red",)


def test_multiple_properties():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red; max-glow: 5; }")
    decls = _sole_declarations(view)
    assert len(decls) == 2
    assert decls[0].property_name == "paint"
    assert decls[1].property_name == "max-glow"
