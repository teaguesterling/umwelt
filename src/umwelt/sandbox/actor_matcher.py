"""Actor matcher for the actor taxon.

Minimal v0.1 implementation — no runtime actor state. condition_met always
returns False. Exists so compound selectors with actor qualifiers don't error.
"""

from __future__ import annotations

from typing import Any

from umwelt.sandbox.entities import ExecutorEntity, InferencerEntity


class ActorMatcher:
    """MatcherProtocol implementation for the actor taxon.

    In v0.1 there is no runtime actor state. The matcher holds an optional
    list of inferencers and executors; condition_met always returns False.
    """

    def __init__(
        self,
        inferencers: list[InferencerEntity] | None = None,
        executors: list[ExecutorEntity] | None = None,
    ) -> None:
        self._inferencers: list[InferencerEntity] = inferencers or []
        self._executors: list[ExecutorEntity] = executors or []

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        if type_name == "inferencer":
            return list(self._inferencers)
        if type_name == "executor":
            return list(self._executors)
        if type_name == "*":
            result: list[Any] = []
            result.extend(self._inferencers)
            result.extend(self._executors)
            return result
        return []

    def children(self, parent: Any, child_type: str) -> list[Any]:
        """No parent-child relationships in the actor taxon."""
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        """No runtime actor state in v0.1 — always False."""
        return False

    def get_attribute(self, entity: Any, name: str) -> Any:
        return getattr(entity, name, None)

    def get_id(self, entity: Any) -> str | None:
        model = getattr(entity, "model", None)
        if model is not None:
            return str(model)
        tool_name = getattr(entity, "tool_name", None)
        if tool_name is not None:
            return str(tool_name)
        return None
