"""Tests for simple-selector predicate matching."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import (
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)
from umwelt.parser import parse
from umwelt.registry import registry_scope
from umwelt.selector.match import match_simple


def _things():
    return [
        ToyThing(type_name="thing", id="alpha", color="red"),
        ToyThing(type_name="thing", id="beta", color="blue"),
        ToyThing(type_name="thing", id="gamma", color="red"),
    ]


def test_match_bare_type_returns_all():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing { }")
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert len(matched) == 3


def test_match_id_filters_by_name():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing#beta { }")
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert len(matched) == 1
    assert matched[0].id == "beta"


def test_match_attribute_equals():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color="red"] { }')
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert {t.id for t in matched} == {"alpha", "gamma"}


def test_match_attribute_prefix():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color^="r"] { }')
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert {t.id for t in matched} == {"alpha", "gamma"}


def test_match_attribute_suffix():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color$="ue"] { }')
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert {t.id for t in matched} == {"beta"}


def test_match_attribute_substring():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color*="lu"] { }')
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert {t.id for t in matched} == {"beta"}


def test_match_multiple_attributes_are_anded():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color="red"][id^="al"] { }')
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert {t.id for t in matched} == {"alpha"}


def test_match_attribute_absent_excludes():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing[missing] { }")
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert matched == []


def test_match_universal_returns_all_candidates():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("* { }")
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert len(matched) == 3
