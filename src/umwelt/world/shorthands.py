"""Shorthand registry for the umwelt world state layer.

Vocabulary consumers register top-level YAML keys here so the parser can
expand them into entity declarations.  E.g. ``tools: [Read, Edit]`` expands
to two ``tool`` entities when ``tools`` is registered with ``form="list"``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from umwelt.registry.taxa import _current_state


@dataclass(frozen=True)
class ShorthandDef:
    """Definition of a top-level YAML shorthand key."""

    key: str
    entity_type: str
    form: Literal["list", "scalar", "map"]
    attribute_key: str | None = None


def register_shorthand(
    *,
    key: str,
    entity_type: str,
    form: Literal["list", "scalar", "map"],
    attribute_key: str | None = None,
) -> None:
    """Register a shorthand key in the active registry scope."""
    state = _current_state()
    state.shorthands[key] = ShorthandDef(
        key=key,
        entity_type=entity_type,
        form=form,
        attribute_key=attribute_key,
    )


def get_shorthand(key: str) -> ShorthandDef | None:
    """Return the ShorthandDef for *key*, or None if not registered."""
    state = _current_state()
    return state.shorthands.get(key)
