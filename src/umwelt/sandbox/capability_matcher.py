"""Capability matcher for the capability taxon.

Wraps lists of ToolEntity and KitEntity for selector evaluation by the
core engine.
"""

from __future__ import annotations

from typing import Any

from umwelt.sandbox.entities import KitEntity, ToolEntity


class CapabilityMatcher:
    """MatcherProtocol implementation for the capability taxon."""

    def __init__(
        self,
        tools: list[ToolEntity] | None = None,
        kits: list[KitEntity] | None = None,
    ) -> None:
        self._tools = tools or []
        self._kits = kits or []

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        if type_name == "tool":
            return list(self._tools)
        if type_name == "kit":
            return list(self._kits)
        if type_name == "*":
            result: list[Any] = []
            result.extend(self._tools)
            result.extend(self._kits)
            return result
        return []

    def children(self, parent: Any, child_type: str) -> list[Any]:
        """No parent-child relationships in the capability taxon."""
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        """Return True if any tool in this matcher satisfies the selector.

        Used for cross-taxon context qualifiers like:
            tool[name="Bash"] file[...] { ... }

        The selector is a SimpleSelector whose attribute filters are evaluated
        against each tool via match_simple.
        """
        from umwelt.selector.match import match_simple

        matched = match_simple(selector, self, list(self._tools))
        return len(matched) > 0

    def get_attribute(self, entity: Any, name: str) -> Any:
        return getattr(entity, name, None)

    def get_id(self, entity: Any) -> str | None:
        name = getattr(entity, "name", None)
        if name is not None:
            return str(name)
        return None
