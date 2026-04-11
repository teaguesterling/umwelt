"""Integration tests: compound selectors drive cascade correctly."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import (
    ToyActor,
    ToyActorsMatcher,
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)
from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import registry_scope


def _world():
    shapes = ToyShapesMatcher(
        things=[
            ToyThing(type_name="thing", id="alpha", color="red"),
            ToyThing(type_name="thing", id="beta", color="blue"),
        ]
    )
    return shapes


def _get(resolved, taxon, entity_id, prop):
    for e, props in resolved.entries(taxon):
        if e.id == entity_id:
            return props.get(prop)
    return None


def test_context_qualifier_met_applies_rule():
    shapes = _world()
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset({"admin"}),
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse(
            "thing { paint: green; } "
            'actor[role="admin"] thing { paint: admin-only; }'
        )
        resolved = resolve(view)
    # Qualifier met: admin rule wins on specificity (compound adds to it).
    assert _get(resolved, "shapes", "alpha", "paint") == "admin-only"
    assert _get(resolved, "shapes", "beta", "paint") == "admin-only"


def test_context_qualifier_unmet_drops_rule():
    shapes = _world()
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset(),  # no active actor
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse(
            "thing { paint: green; } "
            'actor[role="admin"] thing { paint: admin-only; }'
        )
        resolved = resolve(view)
    # Qualifier unmet: the compound rule drops, the base rule wins.
    assert _get(resolved, "shapes", "alpha", "paint") == "green"
    assert _get(resolved, "shapes", "beta", "paint") == "green"


def test_target_taxon_from_compound_is_rightmost():
    shapes = _world()
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset({"admin"}),
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse('actor[role="admin"] thing { paint: admin-only; }')
        resolved = resolve(view)
    # The rule targets the shapes taxon even though the qualifier
    # references the actors taxon.
    shapes_entries = list(resolved.entries("shapes"))
    actors_entries = list(resolved.entries("actors"))
    assert len(shapes_entries) == 2
    assert actors_entries == []


def test_compound_specificity_beats_simple_specificity():
    shapes = _world()
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset({"admin"}),
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse(
            # specificity (0,1,1): [color] + type
            'thing[color="red"] { paint: bright-red; } '
            # specificity (0,2,2): [role] + type + [role] + type ??? actually
            # (1 attr on actor) + (0 on thing) + (1 actor type) + (1 thing type)
            # = (0, 1, 2)
            'actor[role="admin"] thing { paint: admin-only; }'
        )
        resolved = resolve(view)
    # For alpha (red): both rules match; compound has (0,1,2) vs simple (0,1,1).
    # Compound wins.
    assert _get(resolved, "shapes", "alpha", "paint") == "admin-only"
    # For beta (blue): only the compound rule matches.
    assert _get(resolved, "shapes", "beta", "paint") == "admin-only"
