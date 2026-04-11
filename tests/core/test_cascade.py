"""Tests for the cascade resolver."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import (
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)
from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import registry_scope


def _things():
    return [
        ToyThing(type_name="thing", id="alpha", color="red"),
        ToyThing(type_name="thing", id="beta", color="blue"),
    ]


def _get(resolved, taxon, entity_id, prop):
    for e, props in resolved.entries(taxon):
        if e.id == entity_id:
            return props.get(prop)
    return None


def test_single_rule_sets_property():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing { paint: green; }")
        resolved = resolve(view)
    assert _get(resolved, "shapes", "alpha", "paint") == "green"
    assert _get(resolved, "shapes", "beta", "paint") == "green"


def test_specificity_wins():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            "thing { paint: green; } "
            'thing[color="red"] { paint: crimson; }'
        )
        resolved = resolve(view)
    # alpha is red; the more specific rule wins.
    assert _get(resolved, "shapes", "alpha", "paint") == "crimson"
    # beta is blue; only the first rule applies.
    assert _get(resolved, "shapes", "beta", "paint") == "green"


def test_document_order_breaks_specificity_ties():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            'thing[color="red"] { paint: crimson; } '
            'thing[color="red"] { paint: scarlet; }'
        )
        resolved = resolve(view)
    # Both rules have equal specificity; later wins.
    assert _get(resolved, "shapes", "alpha", "paint") == "scarlet"


def test_property_level_cascade():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            "thing { paint: green; max-glow: 100; } "
            'thing#alpha { paint: crimson; }'
        )
        resolved = resolve(view)
    # alpha wins paint from the id rule; max-glow still from the base rule.
    assert _get(resolved, "shapes", "alpha", "paint") == "crimson"
    assert _get(resolved, "shapes", "alpha", "max-glow") == "100"
    # beta gets both from the base rule.
    assert _get(resolved, "shapes", "beta", "paint") == "green"
    assert _get(resolved, "shapes", "beta", "max-glow") == "100"


def test_per_taxon_scoping():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing { paint: green; } actor { allowed: true; }")
        resolved = resolve(view)
    # shapes cascade has thing rules.
    assert _get(resolved, "shapes", "alpha", "paint") == "green"
    # actors cascade is independent; no shapes rule can affect it.
    assert list(resolved.entries("actors")) == []  # no matched actors in the toy world


def test_union_selector_distributes():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            'thing[color="red"], thing[color="blue"] { paint: bright; }'
        )
        resolved = resolve(view)
    assert _get(resolved, "shapes", "alpha", "paint") == "bright"
    assert _get(resolved, "shapes", "beta", "paint") == "bright"
