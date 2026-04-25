"""Property registration for the umwelt plugin registry.

Properties are the declaration vocabulary for an entity type. A property
can be a simple assignment (`editable: true`) or carry comparison
semantics encoded in the property name prefix (`max-level: 2` means
"cap the tool's computation level at <= 2").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from umwelt.errors import RegistryError
from umwelt.registry.entities import get_entity
from umwelt.registry.taxa import _current_state, resolve_taxon

Comparison = Literal["exact", "<=", ">=", "in", "overlap", "pattern-in"]
RestrictiveDirection = Literal["false", "true", "min", "max", "subset", "superset"]


@dataclass(frozen=True)
class PropertySchema:
    """Metadata for a registered declaration property."""

    name: str
    taxon: str
    entity: str
    value_type: type
    comparison: Comparison = "exact"
    restrictive_direction: RestrictiveDirection | None = None
    value_attribute: str | None = None
    value_unit: str | None = None
    value_range: tuple[Any, Any] | None = None
    description: str = ""
    category: str | None = None


def register_property(
    *,
    taxon: str,
    entity: str,
    name: str,
    value_type: type,
    description: str,
    comparison: Comparison = "exact",
    restrictive_direction: RestrictiveDirection | None = None,
    value_attribute: str | None = None,
    value_unit: str | None = None,
    value_range: tuple[Any, Any] | None = None,
    category: str | None = None,
) -> None:
    """Register a property on a (taxon, entity) pair."""
    get_entity(taxon, entity)  # raises if unknown
    canonical = resolve_taxon(taxon)
    state = _current_state()
    key = (canonical, entity, name)
    if key in state.properties:
        raise RegistryError(
            f"property {name!r} already registered on {taxon}.{entity}"
        )
    state.properties[key] = PropertySchema(
        name=name,
        taxon=canonical,
        entity=entity,
        value_type=value_type,
        comparison=comparison,
        restrictive_direction=restrictive_direction,
        value_attribute=value_attribute,
        value_unit=value_unit,
        value_range=value_range,
        description=description,
        category=category,
    )


def get_property(taxon: str, entity: str, name: str) -> PropertySchema:
    """Look up a property by (taxon, entity, name). Resolves taxon aliases."""
    state = _current_state()
    canonical = resolve_taxon(taxon)
    try:
        return state.properties[(canonical, entity, name)]
    except KeyError as exc:
        raise RegistryError(
            f"property {name!r} not registered on {taxon}.{entity}"
        ) from exc


def list_properties(taxon: str, entity: str) -> list[PropertySchema]:
    """Return all properties registered on an entity. Resolves taxon aliases."""
    state = _current_state()
    canonical = resolve_taxon(taxon)
    return [
        p
        for (t, e, _n), p in state.properties.items()
        if t == canonical and e == entity
    ]
