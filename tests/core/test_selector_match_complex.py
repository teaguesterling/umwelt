"""Tests for compound-selector matching with structural and context modes."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import (
    ToyActor,
    ToyActorsMatcher,
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)
from umwelt.parser import parse
from umwelt.registry import get_matcher, registry_scope
from umwelt.selector.match import match_complex


def _things_with_widgets():
    return [
        ToyThing(type_name="thing", id="alpha", color="red"),
        ToyThing(type_name="widget", id="w1", color="red", parent_id="alpha"),
        ToyThing(type_name="widget", id="w2", color="blue", parent_id="alpha"),
        ToyThing(type_name="thing", id="beta", color="blue"),
        ToyThing(type_name="widget", id="w3", color="red", parent_id="beta"),
    ]


def test_structural_descendant_matches_children():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing widget { }")
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    # Every widget has a thing parent, so all three widgets match.
    assert {w.id for w in matched} == {"w1", "w2", "w3"}


def test_structural_with_attribute_on_parent():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color="red"] widget { }')
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    # Only alpha (red) → widgets w1, w2.
    assert {w.id for w in matched} == {"w1", "w2"}


def test_structural_with_attribute_on_child():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing widget[color="red"] { }')
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    # Red widgets: w1, w3.
    assert {w.id for w in matched} == {"w1", "w3"}


def test_context_qualifier_met():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset({"admin"}),
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse('actor[role="admin"] thing { }')
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    # The qualifier is met, so all things match.
    assert {t.id for t in matched} == {"alpha", "beta"}


def test_context_qualifier_unmet():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset(),  # no active actor
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse('actor[role="admin"] thing { }')
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    assert matched == []


def test_three_level_compound():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset({"admin"}),
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse('actor[role="admin"] thing widget { }')
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    # Qualifier met; navigate thing → widget for all things.
    assert {w.id for w in matched} == {"w1", "w2", "w3"}


class _TestRegistryAdapter:
    def get_matcher(self, taxon: str):
        return get_matcher(taxon)


def _registry_adapter():
    return _TestRegistryAdapter()
