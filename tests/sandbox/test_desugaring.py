"""Tests for at-rule sugar desugaring (Tasks 13 and 14)."""

from __future__ import annotations

import pytest

from umwelt.ast import RuleBlock
from umwelt.parser import clear_sugar, parse
from umwelt.registry import registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary


# ---------------------------------------------------------------------------
# Fixture: a registry scope with sandbox vocab + sugar registered
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def sandbox_sugar_scope():
    """All tests in this module run inside a fresh registry scope with sandbox vocab."""
    with registry_scope():
        register_sandbox_vocabulary()
        yield
    # clear_sugar after the scope exits so global state is clean
    # (registry_scope handles registry cleanup; sugar registry is module-level)
    clear_sugar()


# ---------------------------------------------------------------------------
# Task 13: @source, @tools, @after-change
# ---------------------------------------------------------------------------

def test_source_plain_path_desugars_to_prefix_file_rule():
    view = parse('@source("src/auth") { * { editable: true; } }', validate=False)
    assert len(view.rules) == 1
    assert len(view.unknown_at_rules) == 0
    rule = view.rules[0]
    assert isinstance(rule, RuleBlock)
    # Selector should be file with path^= prefix
    sel = rule.selectors[0]
    assert sel.target_taxon == "world"
    parts = sel.parts
    assert len(parts) == 1
    simple = parts[0].selector
    assert simple.type_name == "file"
    assert len(simple.attributes) == 1
    attr = simple.attributes[0]
    assert attr.name == "path"
    assert attr.op == "^="
    assert "src/auth" in attr.value
    # Declarations
    assert len(rule.declarations) == 1
    assert rule.declarations[0].property_name == "editable"
    assert "true" in rule.declarations[0].values


def test_source_glob_path_desugars_to_glob_pseudo_class():
    view = parse('@source("src/**/*.py") { * { editable: false; } }', validate=False)
    assert len(view.rules) == 1
    assert len(view.unknown_at_rules) == 0
    rule = view.rules[0]
    sel = rule.selectors[0]
    simple = sel.parts[0].selector
    assert simple.type_name == "file"
    # Should use :glob() pseudo-class, not attribute
    assert len(simple.pseudo_classes) == 1
    pc = simple.pseudo_classes[0]
    assert pc.name == "glob"
    assert "src/**/*.py" in pc.argument
    # Declarations
    assert rule.declarations[0].property_name == "editable"


def test_tools_allow_deny_desugars_to_individual_tool_rules():
    view = parse("@tools { allow: Read, Edit; deny: Bash; }", validate=False)
    # Should produce 3 rules: Read allow, Edit allow, Bash deny
    assert len(view.rules) == 3
    assert len(view.unknown_at_rules) == 0

    rule_map = {}
    for r in view.rules:
        sel = r.selectors[0]
        simple = sel.parts[0].selector
        name_attr = next((a for a in simple.attributes if a.name == "name"), None)
        if name_attr:
            rule_map[name_attr.value] = r.declarations[0].values[0]

    assert rule_map.get("Read") == "true"
    assert rule_map.get("Edit") == "true"
    assert rule_map.get("Bash") == "false"


def test_tools_kit_desugars_to_kit_rule():
    view = parse("@tools { kit: python-dev; }", validate=False)
    assert len(view.rules) == 1
    rule = view.rules[0]
    sel = rule.selectors[0]
    simple = sel.parts[0].selector
    assert simple.type_name == "kit"
    name_attr = next((a for a in simple.attributes if a.name == "name"), None)
    assert name_attr is not None
    assert name_attr.value == "python-dev"
    assert rule.declarations[0].property_name == "allow"
    assert rule.declarations[0].values[0] == "true"


def test_after_change_desugars_to_hook_rule_with_run_decls():
    view = parse("@after-change { test: pytest; lint: ruff; }", validate=False)
    assert len(view.rules) == 1
    rule = view.rules[0]
    sel = rule.selectors[0]
    simple = sel.parts[0].selector
    assert simple.type_name == "hook"
    event_attr = next((a for a in simple.attributes if a.name == "event"), None)
    assert event_attr is not None
    assert event_attr.value == "after-change"
    # Both declarations should be "run"
    assert len(rule.declarations) == 2
    assert all(d.property_name == "run" for d in rule.declarations)
    run_vals = [d.values[0] for d in rule.declarations]
    assert any("pytest" in v for v in run_vals)
    assert any("ruff" in v for v in run_vals)


def test_mixed_sugar_and_entity_selector_rules_parse_correctly():
    """A view with both at-rule sugar and entity-selector rules should parse."""
    source = """
    @tools { allow: Read; }
    file[path^="src/"] { editable: true; }
    @after-change { test: pytest; }
    """
    view = parse(source, validate=False)
    # Should produce 3 rules: tool[name="Read"], file[path^=...], hook[event="after-change"]
    assert len(view.rules) == 3
    assert len(view.unknown_at_rules) == 0


def test_sugar_produces_entity_selector_form_no_at_rule_nodes():
    """After desugaring, no known at-rule names appear in unknown_at_rules."""
    source = """
    @source("src/**/*.py") { * { editable: true; } }
    @tools { deny: Bash; }
    @after-change { deploy: make deploy; }
    """
    view = parse(source, validate=False)
    # All at-rules were consumed; none should be in unknown_at_rules
    assert len(view.unknown_at_rules) == 0
    # All desugared rules are in entity-selector form
    assert len(view.rules) == 3
    for rule in view.rules:
        assert isinstance(rule, RuleBlock)
        # Each rule has at least one selector
        assert len(rule.selectors) > 0


# ---------------------------------------------------------------------------
# Task 14: @network, @budget, @env
# ---------------------------------------------------------------------------

def test_network_deny_desugars_to_network_rule():
    view = parse("@network { deny: *; }", validate=False)
    assert len(view.rules) == 1
    rule = view.rules[0]
    sel = rule.selectors[0]
    simple = sel.parts[0].selector
    assert simple.type_name == "network"
    assert len(rule.declarations) == 1
    assert rule.declarations[0].property_name == "deny"
    assert "*" in rule.declarations[0].values[0]


def test_budget_multiple_dimensions_desugar_to_resource_rules():
    view = parse("@budget { memory: 512MB; wall-time: 60s; }", validate=False)
    assert len(view.rules) == 2
    assert len(view.unknown_at_rules) == 0

    rule_map = {}
    for r in view.rules:
        sel = r.selectors[0]
        simple = sel.parts[0].selector
        assert simple.type_name == "resource"
        kind_attr = next((a for a in simple.attributes if a.name == "kind"), None)
        assert kind_attr is not None
        rule_map[kind_attr.value] = r.declarations[0].values[0]

    assert "memory" in rule_map
    assert "512MB" in rule_map["memory"]
    assert "wall-time" in rule_map
    assert "60s" in rule_map["wall-time"]


def test_env_allow_deny_desugars_with_specificity():
    view = parse("@env { allow: CI, PYTHONPATH; deny: *; }", validate=False)
    # CI, PYTHONPATH → 2 rules; deny: * → 1 broad rule
    assert len(view.rules) == 3
    assert len(view.unknown_at_rules) == 0

    named_rules = []
    broad_rules = []
    for r in view.rules:
        sel = r.selectors[0]
        simple = sel.parts[0].selector
        assert simple.type_name == "env"
        name_attr = next((a for a in simple.attributes if a.name == "name"), None)
        if name_attr:
            named_rules.append((name_attr.value, r.declarations[0].values[0]))
        else:
            broad_rules.append(r)

    assert len(named_rules) == 2
    assert ("CI", "true") in named_rules
    assert ("PYTHONPATH", "true") in named_rules
    # The broad deny rule uses bare `env` selector
    assert len(broad_rules) == 1
    assert broad_rules[0].declarations[0].property_name == "allow"
    assert broad_rules[0].declarations[0].values[0] == "false"
    # Named rules have higher specificity (have attribute selector)
    named_spec = view.rules[0].selectors[0].specificity
    broad_spec = broad_rules[0].selectors[0].specificity
    assert named_spec > broad_spec
