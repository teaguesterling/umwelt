"""Taxon registration for the umwelt plugin registry."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from umwelt.errors import RegistryError

if TYPE_CHECKING:
    from umwelt.registry.entities import EntitySchema


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
    # Keyed by (taxon_name, entity_name)
    entities: dict[tuple[str, str], EntitySchema] = field(default_factory=dict)


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
        raise RegistryError(f"taxon {name!r} already registered")
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


def list_taxa() -> list[TaxonSchema]:
    """Return all registered taxa in the active scope."""
    return list(_current_state().taxa.values())


@contextmanager
def registry_scope() -> Iterator[RegistryState]:
    """Enter a fresh registry scope. For tests and multi-tenant usage."""
    fresh = RegistryState()
    token = _ACTIVE_STATE.set(fresh)
    try:
        yield fresh
    finally:
        _ACTIVE_STATE.reset(token)
