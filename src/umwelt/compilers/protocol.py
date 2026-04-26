"""Compiler protocol and registry.

Core umwelt ships zero concrete compilers. The sandbox consumer (and
third-party consumers) register theirs via `register(name, compiler)`
at import time.
"""

from __future__ import annotations

import warnings
from typing import Any, Literal, Protocol, runtime_checkable

from umwelt.cascade.resolver import ResolvedView
from umwelt.errors import RegistryError

Altitude = Literal["os", "language", "semantic", "conversational"]


@runtime_checkable
class Compiler(Protocol):
    """A compiler translates a ResolvedView to a target's native config.

    Compilers MUST:
      - Be pure (same ResolvedView -> same output).
      - Have no hard runtime dependency on the target tool's Python wrapper.
      - Declare an altitude.
      - Silently drop rules they cannot realize (out-of-altitude context
        qualifiers, unrealized pattern properties, unknown taxa).
    """

    target_name: str
    target_format: str
    altitude: Altitude

    def compile(self, view: ResolvedView, **options: Any) -> str | list[str] | dict[str, Any]:
        ...


_REGISTRY: dict[str, Compiler] = {}


def register(name: str, compiler: Compiler) -> None:
    """Register a compiler under `name`. Duplicate registration warns."""
    if name in _REGISTRY:
        warnings.warn(
            f"compiler {name!r} already registered; replacing",
            stacklevel=2,
        )
    _REGISTRY[name] = compiler


def get(name: str) -> Compiler:
    """Look up a registered compiler by name."""
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise RegistryError(f"no compiler registered for target {name!r}") from exc


def available() -> list[str]:
    """Return the sorted list of registered compiler names."""
    return sorted(_REGISTRY.keys())


def clear_compilers() -> None:
    """Empty the compiler registry. For test isolation."""
    _REGISTRY.clear()


_ALTITUDE_RANK: dict[str, int] = {
    "os": 0,
    "language": 1,
    "semantic": 2,
    "conversational": 3,
}


def _filter_by_altitude(view: ResolvedView, max_altitude: Altitude) -> ResolvedView:
    """Return a ResolvedView containing only properties at or below max_altitude."""
    from umwelt.registry.properties import get_property

    max_rank = _ALTITUDE_RANK[max_altitude]
    filtered = ResolvedView()

    for taxon in view.taxa():
        for entity, props in view.entries(taxon):
            kept: dict[str, str] = {}
            type_name = getattr(entity, "type_name", None)
            for prop_name, prop_value in props.items():
                prop_altitude = None
                if type_name:
                    try:
                        schema = get_property(taxon, type_name, prop_name)
                        prop_altitude = schema.altitude
                    except Exception:
                        pass

                if prop_altitude is None or _ALTITUDE_RANK.get(prop_altitude, 0) <= max_rank:
                    kept[prop_name] = prop_value
            if kept:
                filtered.add(taxon, entity, kept)

    return filtered
