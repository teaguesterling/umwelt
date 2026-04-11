"""A toy taxonomy for v0.1-core tests.

Provides an in-memory world that covers the surface area the parser,
selector engine, and cascade resolver need to exercise: multi-taxon
registration, parent-child relationships, exact and prefix matching,
cross-taxon context qualifiers. No filesystem, no subprocess.

Usage:

    with registry_scope():
        install_toy_taxonomy()
        ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from umwelt.registry import (
    AttrSchema,
    register_entity,
    register_matcher,
    register_property,
    register_taxon,
)


@dataclass(frozen=True)
class ToyThing:
    """An entity in the `shapes` toy taxon."""

    type_name: str  # "thing" or "widget"
    id: str
    color: str
    parent_id: str | None = None


@dataclass(frozen=True)
class ToyActor:
    """An entity in the `actors` toy taxon (for cross-taxon tests)."""

    type_name: str  # "actor"
    id: str
    role: str


@dataclass
class ToyShapesMatcher:
    """In-memory matcher for the toy `shapes` taxon."""

    things: list[ToyThing] = field(default_factory=list)

    def match_type(self, type_name: str, context: Any = None) -> list[ToyThing]:
        return [t for t in self.things if t.type_name == type_name]

    def children(self, parent: ToyThing, child_type: str) -> list[ToyThing]:
        return [
            t for t in self.things if t.type_name == child_type and t.parent_id == parent.id
        ]

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        # Shapes aren't used as context qualifiers in v0.1-core tests.
        return False


@dataclass
class ToyActorsMatcher:
    """In-memory matcher for the toy `actors` taxon.

    Supports context-qualifier evaluation: a compound selector like
    `actor[role="admin"] thing[...]` asks this matcher whether any
    actor with role=admin is in the current context. Context is a
    frozenset of actor ids that are "active" for a given evaluation.
    """

    actors: list[ToyActor] = field(default_factory=list)
    active_ids: frozenset[str] = field(default_factory=frozenset)

    def match_type(self, type_name: str, context: Any = None) -> list[ToyActor]:
        return [a for a in self.actors if a.type_name == type_name]

    def children(self, parent: Any, child_type: str) -> list[Any]:
        return []  # actors have no children in the toy world

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        # For the v0.1-core tests, the selector is a SimpleSelector with
        # type_name="actor" and an attribute filter on "role". We walk
        # our active_ids set and check whether any matching actor is in
        # it. The selector engine passes the simple selector it's trying
        # to qualify with.
        from umwelt.ast import SimpleSelector

        if not isinstance(selector, SimpleSelector):
            return False
        if selector.type_name != "actor":
            return False
        wanted_roles: set[str] = set()
        for attr in selector.attributes:
            if attr.name == "role" and attr.op == "=" and attr.value is not None:
                wanted_roles.add(attr.value)
        for actor in self.actors:
            if actor.id in self.active_ids and (
                not wanted_roles or actor.role in wanted_roles
            ):
                return True
        return False


def install_toy_taxonomy(
    shapes_matcher: ToyShapesMatcher | None = None,
    actors_matcher: ToyActorsMatcher | None = None,
) -> tuple[ToyShapesMatcher, ToyActorsMatcher]:
    """Register the toy `shapes` and `actors` taxa in the active registry scope.

    Returns the installed matchers so tests can mutate their state.
    """
    # --- shapes taxon ---
    register_taxon(name="shapes", description="toy shapes taxon for core tests")
    register_entity(
        taxon="shapes",
        name="thing",
        attributes={
            "id": AttrSchema(type=str, required=True),
            "color": AttrSchema(type=str),
        },
        description="a toy thing",
    )
    register_entity(
        taxon="shapes",
        name="widget",
        parent="thing",
        attributes={
            "id": AttrSchema(type=str, required=True),
            "color": AttrSchema(type=str),
        },
        description="a toy widget; descendant of a thing",
    )
    register_property(
        taxon="shapes",
        entity="thing",
        name="paint",
        value_type=str,
        description="override the thing's paint color",
    )
    register_property(
        taxon="shapes",
        entity="thing",
        name="max-glow",
        value_type=int,
        comparison="<=",
        value_attribute="glow_level",
        description="cap on glow intensity",
    )
    register_property(
        taxon="shapes",
        entity="widget",
        name="paint",
        value_type=str,
        description="override the widget's paint color",
    )

    # --- actors taxon (for cross-taxon tests) ---
    register_taxon(name="actors", description="toy actors taxon for cross-taxon tests")
    register_entity(
        taxon="actors",
        name="actor",
        attributes={
            "id": AttrSchema(type=str, required=True),
            "role": AttrSchema(type=str),
        },
        description="a toy actor",
    )
    register_property(
        taxon="actors",
        entity="actor",
        name="allowed",
        value_type=bool,
        description="whether the actor is allowed to act",
    )

    shapes = shapes_matcher or ToyShapesMatcher()
    actors = actors_matcher or ToyActorsMatcher()
    register_matcher(taxon="shapes", matcher=shapes)
    register_matcher(taxon="actors", matcher=actors)
    return shapes, actors


def install_doubled_taxonomy() -> None:
    """Register two taxa that both define a `thing` entity.

    For tests that need to exercise ambiguity and disambiguation.
    """
    register_taxon(name="shapes", description="shapes toy taxon")
    register_entity(
        taxon="shapes",
        name="thing",
        attributes={"id": AttrSchema(type=str, required=True)},
        description="a shapes.thing",
    )
    register_property(
        taxon="shapes",
        entity="thing",
        name="paint",
        value_type=str,
        description="paint color",
    )

    register_taxon(name="shadows", description="shadows toy taxon")
    register_entity(
        taxon="shadows",
        name="thing",
        attributes={"id": AttrSchema(type=str, required=True)},
        description="a shadows.thing",
    )
    register_property(
        taxon="shadows",
        entity="thing",
        name="opacity",
        value_type=float,
        description="opacity 0-1",
    )
