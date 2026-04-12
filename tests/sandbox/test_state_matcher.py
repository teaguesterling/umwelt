"""Tests for the state taxon matcher."""

from __future__ import annotations

from umwelt.sandbox.entities import BudgetEntity, HookEntity, JobEntity
from umwelt.sandbox.state_matcher import StateMatcher


def test_match_type_hook_returns_default_after_change():
    """Default StateMatcher has one after-change hook."""
    matcher = StateMatcher()
    hooks = matcher.match_type("hook")
    assert len(hooks) == 1
    assert hooks[0].event == "after-change"


def test_match_type_hook_returns_custom_hooks():
    hooks = [HookEntity(event="before-call"), HookEntity(event="on-failure")]
    matcher = StateMatcher(hooks=hooks)
    result = matcher.match_type("hook")
    assert result == hooks


def test_match_type_budget_returns_budgets():
    budgets = [BudgetEntity(kind="memory"), BudgetEntity(kind="cpu-time")]
    matcher = StateMatcher(budgets=budgets)
    result = matcher.match_type("budget")
    assert result == budgets


def test_match_type_job_returns_jobs():
    jobs = [JobEntity(id="job-1", state="running"), JobEntity(id="job-2")]
    matcher = StateMatcher(jobs=jobs)
    result = matcher.match_type("job")
    assert result == jobs


def test_match_type_star_returns_all():
    hooks = [HookEntity(event="after-change")]
    budgets = [BudgetEntity(kind="memory")]
    jobs = [JobEntity(id="job-1")]
    matcher = StateMatcher(hooks=hooks, budgets=budgets, jobs=jobs)
    result = matcher.match_type("*")
    assert set(result) == set(hooks) | set(budgets) | set(jobs)
    assert len(result) == 3


def test_match_type_unknown_returns_empty():
    matcher = StateMatcher()
    assert matcher.match_type("ghost") == []


def test_get_attribute_hook_event():
    hook = HookEntity(event="before-call", phase="pre")
    matcher = StateMatcher(hooks=[hook])
    assert matcher.get_attribute(hook, "event") == "before-call"
    assert matcher.get_attribute(hook, "phase") == "pre"


def test_get_attribute_missing_returns_none():
    hook = HookEntity(event="after-change")
    matcher = StateMatcher(hooks=[hook])
    assert matcher.get_attribute(hook, "nonexistent") is None


def test_get_id_hook_returns_event_name():
    hook = HookEntity(event="on-timeout")
    matcher = StateMatcher(hooks=[hook])
    assert matcher.get_id(hook) == "on-timeout"


def test_get_id_budget_returns_kind():
    budget = BudgetEntity(kind="wall-time")
    matcher = StateMatcher(budgets=[budget])
    assert matcher.get_id(budget) == "wall-time"


def test_get_id_job_returns_id():
    job = JobEntity(id="run-42", state="complete")
    matcher = StateMatcher(jobs=[job])
    assert matcher.get_id(job) == "run-42"


def test_children_returns_empty():
    hook = HookEntity(event="after-change")
    matcher = StateMatcher(hooks=[hook])
    assert matcher.children(hook, "budget") == []


def test_condition_met_returns_false():
    """State entities are never used as cross-taxon context qualifiers."""
    matcher = StateMatcher()
    # Pass a dummy selector — result should always be False.
    assert matcher.condition_met(object()) is False


def test_explicit_empty_hooks_overrides_default():
    """Passing hooks=[] should suppress the default after-change hook."""
    matcher = StateMatcher(hooks=[])
    assert matcher.match_type("hook") == []
