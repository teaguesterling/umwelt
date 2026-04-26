"""Tests for runtime mode filtering via active_mode context.

When active_mode is passed to resolve(), only mode-gated rules whose
mode ID matches active_mode (or unscoped rules) should fire. This
unblocks Kibitzer's per-mode policy queries without pre-resolving all
modes at load time.
"""
from __future__ import annotations

import pytest

from umwelt.cascade.resolver import ResolvedView, resolve
from umwelt.parser import parse
from umwelt.registry import register_matcher, registry_scope
from umwelt.sandbox.capability_matcher import CapabilityMatcher
from umwelt.sandbox.entities import ModeEntity, ToolEntity
from umwelt.sandbox.state_matcher import StateMatcher
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.world_matcher import WorldMatcher


@pytest.fixture
def sandbox_env(tmp_path):
    tools = [
        ToolEntity(name="Read"),
        ToolEntity(name="Edit"),
        ToolEntity(name="Bash"),
    ]
    modes = [
        ModeEntity(id="implement"),
        ModeEntity(id="review"),
        ModeEntity(id="explore"),
    ]
    with registry_scope():
        register_sandbox_vocabulary()
        register_matcher(taxon="world", matcher=WorldMatcher(base_dir=tmp_path))
        register_matcher(taxon="capability", matcher=CapabilityMatcher(tools=tools))
        register_matcher(taxon="state", matcher=StateMatcher(modes=modes))
        yield tmp_path


def _parse(text, tmp_path):
    p = tmp_path / "test.umw"
    p.write_text(text)
    return parse(p)


def _tool_props(rv: ResolvedView, tool_name: str) -> dict[str, str]:
    for e, props in rv.entries("operation"):
        if isinstance(e, ToolEntity) and e.name == tool_name:
            return props
    return {}


class TestActiveModeFallback:
    """Without active_mode, mode-gated rules fire unconditionally (v0.5 compat)."""

    def test_no_active_mode_all_mode_rules_fire(self, sandbox_env):
        view = _parse('''
            tool { allow: true; }
            mode#explore tool { allow: false; }
        ''', sandbox_env)
        rv = resolve(view)
        assert _tool_props(rv, "Read").get("allow") == "false"

    def test_none_eval_context_same_as_no_active_mode(self, sandbox_env):
        view = _parse('''
            tool { allow: true; }
            mode#review tool { max-level: 2; }
        ''', sandbox_env)
        rv = resolve(view, eval_context=None)
        assert _tool_props(rv, "Bash").get("max-level") == "2"


class TestActiveModeFiltering:
    """When active_mode is set, only matching mode qualifiers fire."""

    def test_matching_mode_rule_fires(self, sandbox_env):
        view = _parse('''
            tool { allow: true; max-level: 8; }
            mode#implement tool { max-level: 5; }
        ''', sandbox_env)
        rv = resolve(view, eval_context={"active_mode": "implement"})
        assert _tool_props(rv, "Bash").get("max-level") == "5"

    def test_non_matching_mode_rule_dropped(self, sandbox_env):
        view = _parse('''
            tool { allow: true; max-level: 8; }
            mode#review tool { max-level: 2; }
        ''', sandbox_env)
        rv = resolve(view, eval_context={"active_mode": "implement"})
        assert _tool_props(rv, "Bash").get("max-level") == "8"

    def test_unscoped_rules_always_fire(self, sandbox_env):
        view = _parse('''
            tool { allow: true; }
            mode#review tool { allow: false; }
        ''', sandbox_env)
        rv = resolve(view, eval_context={"active_mode": "implement"})
        assert _tool_props(rv, "Read").get("allow") == "true"

    def test_multiple_mode_rules_only_matching_fires(self, sandbox_env):
        view = _parse('''
            tool { allow: true; max-level: 8; }
            mode#implement tool { max-level: 5; }
            mode#review tool { max-level: 2; }
            mode#explore tool { allow: false; }
        ''', sandbox_env)
        rv = resolve(view, eval_context={"active_mode": "implement"})
        assert _tool_props(rv, "Bash").get("max-level") == "5"
        assert _tool_props(rv, "Bash").get("allow") == "true"

    def test_mode_id_selector_matching(self, sandbox_env):
        """mode#implement matches active_mode='implement' exactly."""
        view = _parse('''
            tool { allow: true; }
            mode#implement tool[name="Bash"] { allow: false; }
        ''', sandbox_env)
        rv = resolve(view, eval_context={"active_mode": "implement"})
        assert _tool_props(rv, "Bash").get("allow") == "false"
        assert _tool_props(rv, "Read").get("allow") == "true"


class TestStateMatcher:
    """Unit tests for StateMatcher.condition_met with active_mode context."""

    def test_condition_met_mode_no_context(self):
        matcher = StateMatcher(modes=[ModeEntity(id="implement")])
        selector = _mock_selector("mode", "implement")
        assert matcher.condition_met(selector) is True

    def test_condition_met_mode_matching_active(self):
        matcher = StateMatcher(modes=[ModeEntity(id="implement")])
        selector = _mock_selector("mode", "implement")
        assert matcher.condition_met(selector, {"active_mode": "implement"}) is True

    def test_condition_met_mode_non_matching_active(self):
        matcher = StateMatcher(modes=[ModeEntity(id="implement")])
        selector = _mock_selector("mode", "review")
        assert matcher.condition_met(selector, {"active_mode": "implement"}) is False

    def test_condition_met_mode_no_id_with_active(self):
        """Bare `mode` selector (no #id) always passes — it means any mode."""
        matcher = StateMatcher(modes=[ModeEntity(id="implement")])
        selector = _mock_selector("mode", None)
        assert matcher.condition_met(selector, {"active_mode": "implement"}) is True

    def test_condition_met_non_mode_always_false(self):
        matcher = StateMatcher()
        selector = _mock_selector("hook", "after-change")
        assert matcher.condition_met(selector) is False


def _mock_selector(type_name: str, id_value: str | None):
    """Create a minimal object that looks like a SimpleSelector for condition_met."""
    class MockSelector:
        pass
    s = MockSelector()
    s.type_name = type_name
    s.id_value = id_value
    return s
