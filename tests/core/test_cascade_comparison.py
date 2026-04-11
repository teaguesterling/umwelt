"""Integration tests: comparison-prefix properties flow through parse → cascade."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import (
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)
from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import get_property, registry_scope


def _get(resolved, taxon, entity_id, prop):
    for e, props in resolved.entries(taxon):
        if e.id == entity_id:
            return props.get(prop)
    return None


def test_max_property_parsed_and_cascaded():
    shapes = ToyShapesMatcher(
        things=[ToyThing(type_name="thing", id="alpha", color="red")]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing { max-glow: 100; }")
        resolved = resolve(view)
    assert _get(resolved, "shapes", "alpha", "max-glow") == "100"


def test_comparison_metadata_is_queryable():
    with registry_scope():
        install_toy_taxonomy()
        prop = get_property("shapes", "thing", "max-glow")
        assert prop.comparison == "<="
        assert prop.value_attribute == "glow_level"


def test_max_cascades_by_specificity_not_by_value():
    # The cascade picks the winning rule by specificity, not by "tightest
    # value". A later low-specificity max-glow: 50 does not override an
    # earlier high-specificity max-glow: 200.
    shapes = ToyShapesMatcher(
        things=[ToyThing(type_name="thing", id="alpha", color="red")]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            'thing[color="red"] { max-glow: 200; } '
            "thing { max-glow: 50; }"
        )
        resolved = resolve(view)
    # The attribute-selector rule is more specific; it wins regardless of value.
    assert _get(resolved, "shapes", "alpha", "max-glow") == "200"


def test_exact_and_max_properties_cascade_independently():
    shapes = ToyShapesMatcher(
        things=[ToyThing(type_name="thing", id="alpha", color="red")]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            "thing { paint: green; max-glow: 100; } "
            "thing#alpha { paint: crimson; }"
        )
        resolved = resolve(view)
    # paint won by the id rule; max-glow stays from the base rule.
    assert _get(resolved, "shapes", "alpha", "paint") == "crimson"
    assert _get(resolved, "shapes", "alpha", "max-glow") == "100"
