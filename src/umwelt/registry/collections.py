"""Collection registry for named entity bundles."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from umwelt.registry.taxa import _current_state

if TYPE_CHECKING:
    from umwelt.registry.matchers import MatcherProtocol
    from umwelt.world.model import DeclaredEntity


class _CollectionDef:
    __slots__ = ("name", "loader", "matcher_factory")

    def __init__(self, name, loader, matcher_factory):
        self.name = name
        self.loader = loader
        self.matcher_factory = matcher_factory


def register_collection(
    name: str,
    loader: Callable[[], list[DeclaredEntity]],
    matcher_factory: Callable[[], MatcherProtocol] | None = None,
) -> None:
    state = _current_state()
    state.collections[name] = _CollectionDef(
        name=name, loader=loader, matcher_factory=matcher_factory
    )


def require_collection(name: str) -> None:
    """Activate a named collection. Idempotent."""
    state = _current_state()
    if name in state.required_collections:
        return
    if name not in state.collections:
        raise KeyError(f"unknown collection {name!r}")
    defn = state.collections[name]
    entities = defn.loader()
    state.collection_entities.extend(entities)
    if defn.matcher_factory is not None:
        from umwelt.registry.matchers import register_matcher

        matcher = defn.matcher_factory()
        taxon = _infer_taxon(entities)
        if taxon:
            register_matcher(taxon=taxon, matcher=matcher)
    state.required_collections.add(name)


def get_collection_entities() -> list[DeclaredEntity]:
    state = _current_state()
    return list(state.collection_entities)


def _infer_taxon(entities):
    if not entities:
        return None
    try:
        from umwelt.registry.entities import resolve_entity_type

        taxa = resolve_entity_type(entities[0].type)
        return taxa[0] if taxa else None
    except Exception:
        return None
