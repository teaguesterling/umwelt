"""Matcher for the principal taxon (S5).

Synthesizes PrincipalEntity instances from principal[id=] selectors in a
view — same pattern as UseMatcher. Consumed via context passed from
cascade/resolver.
"""
from __future__ import annotations

from typing import Any

from umwelt.sandbox.entities import PrincipalEntity


class PrincipalMatcher:
    """MatcherProtocol implementation for principal taxon."""

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        if type_name not in ("principal", "*"):
            return []
        return list(self._synthesize_principals(context))

    def _synthesize_principals(self, context: Any) -> list[PrincipalEntity]:
        if context is None:
            return []
        rules = getattr(context, "rules", None)
        if rules is None:
            return []
        seen: set[str | None] = set()
        result: list[PrincipalEntity] = []
        for rule in rules:
            for sel in rule.selectors:
                for part in sel.parts:
                    if part.selector.type_name != "principal":
                        continue
                    ident = part.selector.id_value
                    if ident in seen:
                        continue
                    seen.add(ident)
                    result.append(PrincipalEntity(name=ident))
        return result

    def children(self, parent: Any, child_type: str) -> list[Any]:
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        from umwelt.selector.match import match_simple
        candidates = self._synthesize_principals(context)
        return len(match_simple(selector, self, candidates)) > 0

    def get_attribute(self, entity: Any, name: str) -> Any:
        if not isinstance(entity, PrincipalEntity):
            return None
        if name == "name":
            return entity.name
        return None

    def get_id(self, entity: Any) -> str | None:
        if not isinstance(entity, PrincipalEntity):
            return None
        return entity.name
