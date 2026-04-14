"""Entity registration for the umwelt plugin registry."""

from __future__ import annotations

from dataclasses import dataclass

from umwelt.errors import RegistryError
from umwelt.registry.taxa import _current_state, get_taxon


@dataclass(frozen=True)
class AttrSchema:
    """Schema for one entity attribute."""

    type: type
    required: bool = False
    unit: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class EntitySchema:
    """Metadata for a registered entity type."""

    name: str
    taxon: str
    parent: str | None
    attributes: dict[str, AttrSchema]
    description: str
    category: str | None = None


def register_entity(
    *,
    taxon: str,
    name: str,
    attributes: dict[str, AttrSchema],
    description: str,
    parent: str | None = None,
    category: str | None = None,
) -> None:
    """Register an entity type under a taxon."""
    # Verify the taxon exists first (raises RegistryError if not).
    get_taxon(taxon)
    state = _current_state()
    key = (taxon, name)
    if key in state.entities:
        raise RegistryError(
            f"entity {name!r} already registered in taxon {taxon!r}"
        )
    state.entities[key] = EntitySchema(
        name=name,
        taxon=taxon,
        parent=parent,
        attributes=dict(attributes),
        description=description,
        category=category,
    )


def _resolve_taxon(taxon: str) -> str:
    """Resolve a taxon name through aliases to its canonical name."""
    state = _current_state()
    return state.taxon_aliases.get(taxon, taxon)


def get_entity(taxon: str, name: str) -> EntitySchema:
    """Look up a registered entity by (taxon, name).

    If `taxon` is an alias, the lookup is transparently resolved to the
    canonical taxon name.
    """
    state = _current_state()
    canonical = _resolve_taxon(taxon)
    try:
        return state.entities[(canonical, name)]
    except KeyError as exc:
        raise RegistryError(
            f"entity {name!r} not registered in taxon {taxon!r}"
        ) from exc


def list_entities(taxon: str) -> list[EntitySchema]:
    """Return all entities registered under a taxon.

    If `taxon` is an alias, entities are listed from the canonical taxon.
    """
    state = _current_state()
    canonical = _resolve_taxon(taxon)
    return [e for (t, _n), e in state.entities.items() if t == canonical]


def resolve_entity_type(name: str) -> list[str]:
    """Return the list of taxa that have an entity named `name`.

    - Empty list: the type is unknown.
    - Single entry: unambiguous, caller uses it directly.
    - Multiple entries: ambiguous, caller must disambiguate via
      explicit `taxon|type` prefix or `@taxon { ... }` scoping.
    """
    state = _current_state()
    return [t for (t, n) in state.entities if n == name]
