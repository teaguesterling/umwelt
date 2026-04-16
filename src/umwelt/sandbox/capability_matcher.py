"""Capability matcher for the capability taxon.

Wraps lists of ToolEntity, KitEntity, and UseEntity for selector evaluation.
UseEntity instances are synthesized at match time from the view's rules
(via the context= argument to match_type).
"""

from __future__ import annotations

from typing import Any

from umwelt.sandbox.entities import KitEntity, ToolEntity, UseEntity


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
        if type_name == "use":
            return list(self._synthesize_uses(context))
        if type_name == "*":
            result: list[Any] = []
            result.extend(self._tools)
            result.extend(self._kits)
            result.extend(self._synthesize_uses(context))
            return result
        return []

    def _synthesize_uses(self, context: Any) -> list[UseEntity]:
        """Derive UseEntity instances from use[...] selectors in the view.

        context is the View being resolved. If context is None or has no
        rules attribute, yield nothing.
        """
        if context is None:
            return []
        rules = getattr(context, "rules", None)
        if rules is None:
            return []
        seen: set[tuple[str | None, str | None, str | None]] = set()
        result: list[UseEntity] = []
        for rule in rules:
            for sel in rule.selectors:
                for part in sel.parts:
                    if part.selector.type_name != "use":
                        continue
                    of = None
                    of_kind = None
                    of_like = None
                    for attr in part.selector.attributes:
                        if attr.name == "of":
                            of = attr.value
                        elif attr.name == "of-kind":
                            of_kind = attr.value
                        elif attr.name == "of-like":
                            of_like = attr.value
                    key = (of, of_kind, of_like)
                    if key in seen:
                        continue
                    seen.add(key)
                    result.append(UseEntity(of=of, of_kind=of_kind, of_like=of_like))
        return result

    def children(self, parent: Any, child_type: str) -> list[Any]:
        """No parent-child relationships in the capability taxon."""
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        from umwelt.selector.match import match_simple
        matched = match_simple(selector, self, list(self._tools))
        return len(matched) > 0

    def get_attribute(self, entity: Any, name: str) -> Any:
        # UseEntity uses of_kind/of_like internally but of-kind/of-like in selectors.
        if isinstance(entity, UseEntity):
            if name == "of":
                return entity.of
            if name == "of-kind":
                return entity.of_kind
            if name == "of-like":
                return entity.of_like
            return None
        return getattr(entity, name, None)

    def get_id(self, entity: Any) -> str | None:
        if isinstance(entity, UseEntity):
            return None  # UseEntity has no natural #id
        name = getattr(entity, "name", None)
        if name is not None:
            return str(name)
        return None
