"""Integration tests: pattern-valued declarations round-trip through cascade."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import (
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)
from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import (
    register_property,
    registry_scope,
)


def _install_pattern_property():
    """Register shapes/thing + an allow-pattern pattern property."""
    install_toy_taxonomy()
    register_property(
        taxon="shapes",
        entity="thing",
        name="allow-pattern",
        value_type=list,
        comparison="pattern-in",
        description="glob patterns allowed for this thing",
    )


def _get(resolved, taxon, entity_id, prop):
    for e, props in resolved.entries(taxon):
        if e.id == entity_id:
            return props.get(prop)
    return None


def test_single_pattern_value():
    shapes = ToyShapesMatcher(
        things=[ToyThing(type_name="thing", id="alpha", color="red")]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        register_property(
            taxon="shapes",
            entity="thing",
            name="allow-pattern",
            value_type=list,
            comparison="pattern-in",
            description="glob allowlist",
        )
        view = parse('thing { allow-pattern: "git *"; }')
        resolved = resolve(view)
    assert _get(resolved, "shapes", "alpha", "allow-pattern") == "git *"


def test_multiple_pattern_values_comma_separated():
    shapes = ToyShapesMatcher(
        things=[ToyThing(type_name="thing", id="alpha", color="red")]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        register_property(
            taxon="shapes",
            entity="thing",
            name="allow-pattern",
            value_type=list,
            comparison="pattern-in",
            description="glob allowlist",
        )
        view = parse(
            'thing { allow-pattern: "git *", "pytest *", "ruff *"; }'
        )
        decls = view.rules[0].declarations
        assert decls[0].values == ("git *", "pytest *", "ruff *")
        resolved = resolve(view)
        # The cascade resolver joins multi-value properties with ", " by default.
        assert _get(resolved, "shapes", "alpha", "allow-pattern") == "git *, pytest *, ruff *"


def test_pattern_cascades_with_specificity():
    shapes = ToyShapesMatcher(
        things=[
            ToyThing(type_name="thing", id="alpha", color="red"),
            ToyThing(type_name="thing", id="beta", color="blue"),
        ]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        register_property(
            taxon="shapes",
            entity="thing",
            name="allow-pattern",
            value_type=list,
            comparison="pattern-in",
            description="glob allowlist",
        )
        view = parse(
            'thing { allow-pattern: "*"; } '
            'thing[color="red"] { allow-pattern: "git *", "pytest *"; }'
        )
        resolved = resolve(view)
    # alpha (red) gets the more specific rule.
    assert _get(resolved, "shapes", "alpha", "allow-pattern") == "git *, pytest *"
    # beta gets the base rule.
    assert _get(resolved, "shapes", "beta", "allow-pattern") == "*"
