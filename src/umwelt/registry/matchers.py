"""Matcher protocol and registration.

A matcher is the consumer-supplied bridge between a `ComplexSelector`
and the consumer's world. The parser, selector engine, and cascade
resolver are matcher-agnostic — they know how to call these methods
but not what the implementation does. A filesystem matcher walks
real paths; an in-memory test matcher walks a dict.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from umwelt.errors import RegistryError
from umwelt.registry.taxa import _current_state, get_taxon, resolve_taxon


@runtime_checkable
class MatcherProtocol(Protocol):
    """Consumer-supplied access to a world for selector evaluation.

    The protocol is deliberately thin. Each method takes selector-space
    inputs and returns opaque entity handles that only the matcher knows
    how to interpret — the core selector engine treats them as tokens.
    """

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        """Return all entities of this type in the matcher's world.

        For structural lookups where no parent entity is pre-selected,
        this returns every entity of the type.
        """
        ...

    def children(self, parent: Any, child_type: str) -> list[Any]:
        """Return `child_type` entities that are descendants of `parent`.

        Used for within-taxon structural descendant selectors (e.g.,
        `dir[name="src"] file[name$=".py"]` — the matcher walks the
        dir -> file parent-child relationship).
        """
        ...

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        """Return True if a cross-taxon context qualifier is satisfied.

        Called by the selector engine when a compound selector crosses
        taxa (`tool[name="Bash"] file[...]`). The qualifier taxon's
        matcher is consulted with the qualifier selector to determine
        whether the rule's context condition holds.
        """
        ...

    def get_attribute(self, entity: Any, name: str) -> Any:
        """Return the value of an attribute on an entity, or None if absent.

        Used by the selector match engine to evaluate attribute filters.
        """
        ...

    def get_id(self, entity: Any) -> str | None:
        """Return the entity's identity value (used by `#id` selectors).

        Return None when the entity has no natural identity; `#id` selectors
        won't match such entities.
        """
        ...


class CompositeMatcher:
    """Delegates to multiple matchers for the same taxon.

    Auto-created when register_matcher() is called twice for the same taxon.
    Union semantics for match_type/children, OR for condition_met,
    first-non-None for get_id/get_attribute.
    """

    def __init__(self, *delegates: MatcherProtocol):
        self._delegates: list[MatcherProtocol] = list(delegates)

    def add(self, matcher: MatcherProtocol) -> None:
        self._delegates.append(matcher)

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        results: list[Any] = []
        for d in self._delegates:
            results.extend(d.match_type(type_name, context))
        return results

    def children(self, parent: Any, child_type: str) -> list[Any]:
        results: list[Any] = []
        for d in self._delegates:
            results.extend(d.children(parent, child_type))
        return results

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        return any(d.condition_met(selector, context) for d in self._delegates)

    def get_attribute(self, entity: Any, name: str) -> Any:
        for d in self._delegates:
            val = d.get_attribute(entity, name)
            if val is not None:
                return val
        return None

    def get_id(self, entity: Any) -> str | None:
        for d in self._delegates:
            val = d.get_id(entity)
            if val is not None:
                return val
        return None


def register_matcher(*, taxon: str, matcher: MatcherProtocol) -> None:
    """Register a matcher for a taxon. Auto-composes on collision."""
    get_taxon(taxon)  # raises if unknown
    canonical = resolve_taxon(taxon)
    state = _current_state()
    if canonical in state.matchers:
        existing = state.matchers[canonical]
        if isinstance(existing, CompositeMatcher):
            existing.add(matcher)
        else:
            state.matchers[canonical] = CompositeMatcher(existing, matcher)
    else:
        state.matchers[canonical] = matcher


def get_matcher(taxon: str) -> MatcherProtocol:
    """Look up the matcher for a taxon. Resolves taxon aliases."""
    state = _current_state()
    canonical = resolve_taxon(taxon)
    try:
        return state.matchers[canonical]
    except KeyError as exc:
        raise RegistryError(f"no matcher registered for taxon {taxon!r}") from exc
