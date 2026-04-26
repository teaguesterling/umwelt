"""Taxon registration for the umwelt plugin registry."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from umwelt.errors import RegistryError

if TYPE_CHECKING:
    from umwelt.registry.entities import EntitySchema
    from umwelt.registry.matchers import MatcherProtocol
    from umwelt.registry.properties import PropertySchema
    from umwelt.registry.validators import ValidatorProtocol


@dataclass(frozen=True)
class TaxonSchema:
    """Metadata for a registered taxon."""

    name: str
    description: str
    ma_concept: str | None = None


@dataclass
class RegistryState:
    """The full contents of a registry scope.

    Other registry submodules (entities, properties, matchers, validators,
    compilers) attach their own dicts here as fields.
    """

    taxa: dict[str, TaxonSchema] = field(default_factory=dict)
    # Maps alias taxon name → canonical taxon name.
    taxon_aliases: dict[str, str] = field(default_factory=dict)
    # Keyed by (taxon_name, entity_name)
    entities: dict[tuple[str, str], EntitySchema] = field(default_factory=dict)
    # Keyed by (taxon_name, entity_name, property_name)
    properties: dict[tuple[str, str, str], PropertySchema] = field(default_factory=dict)
    matchers: dict[str, MatcherProtocol] = field(default_factory=dict)
    # Multiple validators per taxon allowed; they all run in registration order.
    validators: dict[str, list[ValidatorProtocol]] = field(default_factory=dict)
    # Cross-taxon validators run after per-taxon validators, receiving the full View.
    cross_validators: list[Any] = field(default_factory=list)
    # Keyed by shorthand key (e.g. "tools"). Values are ShorthandDef instances;
    # typed as Any to avoid a circular import with umwelt.world.shorthands.
    shorthands: dict[str, Any] = field(default_factory=dict)
    collections: dict[str, Any] = field(default_factory=dict)
    collection_entities: list[Any] = field(default_factory=list)
    required_collections: set[str] = field(default_factory=set)


_GLOBAL_STATE = RegistryState()
_ACTIVE_STATE: ContextVar[RegistryState] = ContextVar("umwelt_registry_state", default=_GLOBAL_STATE)


def _current_state() -> RegistryState:
    return _ACTIVE_STATE.get()


def register_taxon(
    *,
    name: str,
    description: str,
    ma_concept: str | None = None,
) -> None:
    """Register a taxon with the active registry scope."""
    state = _current_state()
    if name in state.taxa:
        existing = state.taxa[name]
        if existing.description == description:
            return  # idempotent
        raise RegistryError(
            f"taxon {name!r} already registered with conflicting description"
        )
    state.taxa[name] = TaxonSchema(
        name=name,
        description=description,
        ma_concept=ma_concept,
    )


def get_taxon(name: str) -> TaxonSchema:
    """Look up a registered taxon by name."""
    state = _current_state()
    try:
        return state.taxa[name]
    except KeyError as exc:
        raise RegistryError(f"taxon {name!r} not registered") from exc


def register_taxon_alias(alias: str, canonical: str) -> None:
    """Register `alias` as another name for an existing `canonical` taxon.

    After registration, get_taxon(alias) returns the same TaxonSchema as
    get_taxon(canonical). Both names may be used interchangeably in
    register_entity(taxon=...) and view.entries(...) calls.

    Entity lookups via the alias are resolved transparently: get_entity(alias,
    name) returns the same result as get_entity(canonical, name).

    Raises:
        KeyError: if `canonical` has not been registered.
        ValueError: if `alias` is already a registered taxon or alias.
    """
    state = _current_state()
    if canonical not in state.taxa:
        raise KeyError(f"canonical taxon '{canonical}' not registered")
    if canonical in state.taxon_aliases:
        raise ValueError(
            f"'{canonical}' is itself an alias; alias the canonical directly"
        )
    if alias in state.taxa:
        raise ValueError(f"taxon '{alias}' already exists (cannot alias)")
    state.taxa[alias] = state.taxa[canonical]
    state.taxon_aliases[alias] = canonical


def resolve_taxon(name: str) -> str:
    """Resolve a taxon name through aliases to its canonical name.

    Public helper used by all registry submodules (entities, properties,
    matchers, validators) to ensure lookups under an alias route to the
    canonical key.
    """
    state = _current_state()
    return state.taxon_aliases.get(name, name)


def list_taxa() -> list[TaxonSchema]:
    """Return all registered taxa in the active scope, excluding alias entries."""
    state = _current_state()
    return [
        schema
        for name, schema in state.taxa.items()
        if name not in state.taxon_aliases
    ]


@contextmanager
def registry_scope() -> Iterator[RegistryState]:
    """Enter a fresh registry scope. For tests and multi-tenant usage."""
    fresh = RegistryState()
    token = _ACTIVE_STATE.set(fresh)
    try:
        yield fresh
    finally:
        _ACTIVE_STATE.reset(token)
