"""Matcher for the audit taxon (S3*).

Synthesizes ObservationEntity and ManifestEntity instances from parsed
rules. Same pattern as PrincipalMatcher and UseMatcher.
"""
from __future__ import annotations

from typing import Any

from umwelt.sandbox.entities import ManifestEntity, ObservationEntity


class AuditMatcher:
    """MatcherProtocol implementation for the audit taxon."""

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        if type_name == "observation":
            return list(self._synthesize(context, "observation", ObservationEntity))
        if type_name == "manifest":
            return list(self._synthesize(context, "manifest", ManifestEntity))
        if type_name == "*":
            return (
                list(self._synthesize(context, "observation", ObservationEntity))
                + list(self._synthesize(context, "manifest", ManifestEntity))
            )
        return []

    def _synthesize(self, context: Any, type_name: str, cls) -> list[Any]:
        if context is None:
            return []
        rules = getattr(context, "rules", None)
        if rules is None:
            return []
        seen: set[str | None] = set()
        out: list[Any] = []
        for rule in rules:
            for sel in rule.selectors:
                for part in sel.parts:
                    if part.selector.type_name != type_name:
                        continue
                    ident = part.selector.id_value
                    if ident in seen:
                        continue
                    seen.add(ident)
                    out.append(cls(name=ident))
        return out

    def children(self, parent: Any, child_type: str) -> list[Any]:
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        # Audit entries don't gate other-taxon rules in v0.5.
        return True

    def get_attribute(self, entity: Any, name: str) -> Any:
        if isinstance(entity, (ObservationEntity, ManifestEntity)) and name == "name":
            return entity.name
        return None

    def get_id(self, entity: Any) -> str | None:
        if isinstance(entity, (ObservationEntity, ManifestEntity)):
            return entity.name
        return None
