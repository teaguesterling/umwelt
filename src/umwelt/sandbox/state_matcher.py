"""State matcher for the state taxon.

Wraps lists of HookEntity, BudgetEntity, and JobEntity for selector
evaluation by the core engine.
"""

from __future__ import annotations

from typing import Any

from umwelt.sandbox.entities import BudgetEntity, HookEntity, JobEntity, ModeEntity


class StateMatcher:
    """MatcherProtocol implementation for the state taxon."""

    def __init__(
        self,
        hooks: list[HookEntity] | None = None,
        budgets: list[BudgetEntity] | None = None,
        jobs: list[JobEntity] | None = None,
        modes: list[ModeEntity] | None = None,
    ) -> None:
        # Default: one after-change hook so there's always a live hook entity.
        self._hooks = hooks if hooks is not None else [HookEntity(event="after-change")]
        self._budgets = budgets or []
        self._jobs = jobs or []
        self._modes = modes or []

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        if type_name == "hook":
            return list(self._hooks)
        if type_name == "budget":
            return list(self._budgets)
        if type_name == "job":
            return list(self._jobs)
        if type_name == "mode":
            return list(self._modes)
        if type_name == "*":
            result: list[Any] = []
            result.extend(self._hooks)
            result.extend(self._budgets)
            result.extend(self._jobs)
            result.extend(self._modes)
            return result
        return []

    def children(self, parent: Any, child_type: str) -> list[Any]:
        """No parent-child relationships in the state taxon."""
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        """Mode selectors are always active in v0.5; other state entities don't qualify.

        v0.5: mode is a compositional class label. Cross-axis rules gated on
        mode fire unconditionally at view-resolve time. Runtime class filtering
        (only fire if the current mode matches) is a v0.6 concern coordinated
        with kibitzer's ChangeToolMode.
        """
        return getattr(selector, "type_name", None) == "mode"

    def get_attribute(self, entity: Any, name: str) -> Any:
        return getattr(entity, name, None)

    def get_id(self, entity: Any) -> str | None:
        if isinstance(entity, ModeEntity):
            return entity.id
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
