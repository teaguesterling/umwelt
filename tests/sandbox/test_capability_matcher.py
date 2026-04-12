"""Tests for the capability taxon matcher."""

from __future__ import annotations

import pytest

from umwelt.registry import registry_scope
from umwelt.sandbox.capability_matcher import CapabilityMatcher
from umwelt.sandbox.entities import KitEntity, ToolEntity
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary


@pytest.fixture
def tools():
    return [
        ToolEntity(name="Bash", kit="shell", altitude="os", level=3),
        ToolEntity(name="Read", kit="fs", altitude="semantic", level=1),
        ToolEntity(name="Write", kit="fs", altitude="semantic", level=2),
    ]


@pytest.fixture
def kits():
    return [
        KitEntity(name="shell", version="1.0"),
        KitEntity(name="fs", version="2.0"),
    ]


def test_match_type_tool_returns_all_tools(tools, kits):
    matcher = CapabilityMatcher(tools=tools, kits=kits)
    result = matcher.match_type("tool")
    assert result == tools


def test_match_type_kit_returns_all_kits(tools, kits):
    matcher = CapabilityMatcher(tools=tools, kits=kits)
    result = matcher.match_type("kit")
    assert result == kits


def test_match_type_star_returns_tools_and_kits(tools, kits):
    matcher = CapabilityMatcher(tools=tools, kits=kits)
    result = matcher.match_type("*")
    assert set(result) == set(tools) | set(kits)
    assert len(result) == len(tools) + len(kits)


def test_match_type_unknown_returns_empty(tools, kits):
    matcher = CapabilityMatcher(tools=tools, kits=kits)
    assert matcher.match_type("ghost") == []


def test_get_attribute_name(tools):
    matcher = CapabilityMatcher(tools=tools)
    bash = tools[0]
    assert matcher.get_attribute(bash, "name") == "Bash"


def test_get_attribute_level(tools):
    matcher = CapabilityMatcher(tools=tools)
    bash = tools[0]
    assert matcher.get_attribute(bash, "level") == 3


def test_get_attribute_missing_returns_none(tools):
    matcher = CapabilityMatcher(tools=tools)
    assert matcher.get_attribute(tools[0], "nonexistent") is None


def test_get_id_returns_tool_name(tools):
    matcher = CapabilityMatcher(tools=tools)
    assert matcher.get_id(tools[0]) == "Bash"
    assert matcher.get_id(tools[1]) == "Read"


def test_children_returns_empty(tools, kits):
    matcher = CapabilityMatcher(tools=tools, kits=kits)
    assert matcher.children(tools[0], "kit") == []
    assert matcher.children(kits[0], "tool") == []


def test_condition_met_matching_tool_returns_true(tools):
    """condition_met should return True when a tool matches the selector."""
    with registry_scope():
        register_sandbox_vocabulary()
        # Parse "tool[name="Bash"]" — we need the SimpleSelector for the tool part.
        import tinycss2

        from umwelt.selector.parse import parse_selector_list
        tokens = tinycss2.parse_component_value_list('tool[name="Bash"]')
        selectors = parse_selector_list(tokens)
        assert len(selectors) == 1
        # The selector has one part; get its SimpleSelector
        simple = selectors[0].parts[0].selector

        matcher = CapabilityMatcher(tools=tools)
        assert matcher.condition_met(simple) is True


def test_condition_met_no_matching_tool_returns_false(tools):
    """condition_met should return False when no tool matches."""
    with registry_scope():
        register_sandbox_vocabulary()
        import tinycss2

        from umwelt.selector.parse import parse_selector_list
        tokens = tinycss2.parse_component_value_list('tool[name="Nonexistent"]')
        selectors = parse_selector_list(tokens)
        simple = selectors[0].parts[0].selector

        matcher = CapabilityMatcher(tools=tools)
        assert matcher.condition_met(simple) is False


def test_condition_met_empty_tools_returns_false():
    """condition_met with no tools always returns False."""
    with registry_scope():
        register_sandbox_vocabulary()
        import tinycss2

        from umwelt.selector.parse import parse_selector_list
        tokens = tinycss2.parse_component_value_list('tool[name="Bash"]')
        selectors = parse_selector_list(tokens)
        simple = selectors[0].parts[0].selector

        matcher = CapabilityMatcher(tools=[])
        assert matcher.condition_met(simple) is False
