"""Tests for the mode x tool cross-axis idiom.

Documented in docs/guide/entity-reference.md ("Cross-axis idioms").
Verifies that `mode#<id> tool[name=...] { allow: false; }` composes
cleanly through the v0.5 cascade without needing `use[of=tool#...]`.

Relates to claims A3 (cross-axis soundness) and A5 (tool.visible property
registered with correct semantics).
"""
from __future__ import annotations

import pytest

from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import get_property, register_matcher, registry_scope
from umwelt.sandbox.capability_matcher import CapabilityMatcher
from umwelt.sandbox.entities import ToolEntity
from umwelt.sandbox.state_matcher import StateMatcher
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.world_matcher import WorldMatcher


@pytest.fixture
def vocab_with_tools(tmp_path):
    tools = [
        ToolEntity(name="Read"),
        ToolEntity(name="Grep"),
        ToolEntity(name="Edit"),
        ToolEntity(name="Bash"),
    ]
    with registry_scope():
        register_sandbox_vocabulary()
        register_matcher(taxon="world", matcher=WorldMatcher(base_dir=tmp_path))
        register_matcher(taxon="capability", matcher=CapabilityMatcher(tools=tools))
        register_matcher(taxon="state", matcher=StateMatcher())
        yield tmp_path


def _parse(text, tmp_path):
    p = tmp_path / "test.umw"
    p.write_text(text)
    return parse(p)


def test_tool_visible_property_registered(vocab_with_tools):
    """A5: tool.visible is registered as a bool property."""
    prop = get_property(taxon="capability", entity="tool", name="visible")
    assert prop.value_type is bool


def test_mode_gated_tool_default_deny(vocab_with_tools):
    """A3: mode#<id> tool { allow: false; } denies all tools in that mode."""
    view = _parse('''
        mode#explore tool { allow: false; }
        mode#explore tool[name="Read"] { allow: true; }
    ''', vocab_with_tools)
    rv = resolve(view)
    entries = [(e, p) for e, p in rv.entries("operation") if isinstance(e, ToolEntity)]
    allows = {e.name: p.get("allow") for e, p in entries}
    # Read should be explicitly allowed; others denied by the bare mode rule.
    assert allows.get("Read") == "true"
    # Grep/Edit/Bash should come back as false (mode#explore tool { allow: false; }).
    for name in ("Grep", "Edit", "Bash"):
        assert allows.get(name) == "false", f"expected {name} denied, got {allows.get(name)}"


def test_mode_tool_beats_bare_tool_via_axis_count(vocab_with_tools):
    """A3: mode#X tool#Y (axis_count=2) beats bare tool#Y (axis_count=1)."""
    view = _parse('''
        tool[name="Bash"] { allow: true; }
        mode#explore tool[name="Bash"] { allow: false; }
    ''', vocab_with_tools)
    rv = resolve(view)
    bash = next(
        (p for e, p in rv.entries("operation")
         if isinstance(e, ToolEntity) and e.name == "Bash"),
        None,
    )
    assert bash is not None
    assert bash.get("allow") == "false"


def test_three_axis_principal_mode_tool(vocab_with_tools):
    """A3: principal#X mode#Y tool#Z is axis_count=3 and wins over narrower rules."""
    view = _parse('''
        mode#implement tool[name="Bash"] { allow: false; }
        principal#Teague mode#implement tool[name="Bash"] { allow: true; }
    ''', vocab_with_tools)
    # Note: requires principal matcher; we'll verify via specificity ordering alone.
    specs = [sel.specificity for rule in view.rules for sel in rule.selectors]
    two_axis, three_axis = specs
    assert three_axis[0] == 3
    assert two_axis[0] == 2
    assert three_axis > two_axis
