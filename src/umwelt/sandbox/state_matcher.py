"""State matcher for the state taxon.

Wraps lists of HookEntity, BudgetEntity, and JobEntity for selector
evaluation by the core engine.
"""

from __future__ import annotations

from typing import Any

from umwelt.sandbox.entities import BudgetEntity, HookEntity, JobEntity


class StateMatcher:
    """MatcherProtocol implementation for the state taxon."""

    def __init__(
        self,
        hooks: list[HookEntity] | None = None,
        budgets: list[BudgetEntity] | None = None,
        jobs: list[JobEntity] | None = None,
    ) -> None:
        # Default: one after-change hook so there's always a live hook entity.
        self._hooks = hooks if hooks is not None else [HookEntity(event="after-change")]
        self._budgets = budgets or []
        self._jobs = jobs or []

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        if type_name == "hook":
            return list(self._hooks)
        if type_name == "budget":
            return list(self._budgets)
        if type_name == "job":
            return list(self._jobs)
        if type_name == "*":
            result: list[Any] = []
            result.extend(self._hooks)
            result.extend(self._budgets)
            result.extend(self._jobs)
            return result
        return []

    def children(self, parent: Any, child_type: str) -> list[Any]:
        """No parent-child relationships in the state taxon."""
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        """State entities are not used as cross-taxon context qualifiers."""
        return False

    def get_attribute(self, entity: Any, name: str) -> Any:
        return getattr(entity, name, None)

    def get_id(self, entity: Any) -> str | None:
        # HookEntity → event name
        event = getattr(entity, "event", None)
        if event is not None:
            return str(event)
        # BudgetEntity → kind
        kind = getattr(entity, "kind", None)
        if kind is not None:
            return str(kind)
        # JobEntity → id
        job_id = getattr(entity, "id", None)
        if job_id is not None:
            return str(job_id)
        return None
