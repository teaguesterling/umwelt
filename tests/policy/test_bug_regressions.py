"""Regression tests for PolicyEngine bugs found during pressure testing.

Bug #1: Fixed constraint class selectors silently match nothing
Bug #2: extend() resets rule_index to 0
Bug #3: extend() new entities don't see pre-compiled rules
"""
from __future__ import annotations

import pytest

from umwelt.policy import PolicyEngine


# ---------------------------------------------------------------------------
# Bug #1: Fixed constraint class selectors
# ---------------------------------------------------------------------------

class TestFixedConstraintClassSelectors:
    """_match_fixed_selector should support type.class selectors, not just
    type#id and bare type."""

    @pytest.fixture
    def engine_with_class_fixed(self, tmp_path):
        world = tmp_path / "test.world.yml"
        world.write_text("""\
entities:
  - type: dir
    id: secrets
    classes: [sensitive]
  - type: dir
    id: config
    classes: [sensitive]
  - type: dir
    id: src
    classes: [source]
fixed:
  "dir.sensitive":
    editable: "false"
    visible: "false"
""")
        style = tmp_path / "test.umw"
        style.write_text("""\
dir { visible: true; editable: true; }
""")
        return PolicyEngine.from_files(world=world, stylesheet=style)

    def test_class_selector_matches_sensitive_dirs(self, engine_with_class_fixed):
        """dir.sensitive fixed constraint should clamp editable to false."""
        val = engine_with_class_fixed.resolve(type="dir", id="secrets", property="editable")
        assert val == "false", "Fixed constraint with class selector should override cascade"

    def test_class_selector_matches_all_sensitive(self, engine_with_class_fixed):
        """Both dirs with .sensitive class should be clamped."""
        val = engine_with_class_fixed.resolve(type="dir", id="config", property="editable")
        assert val == "false", "All entities matching the class should be clamped"

    def test_class_selector_doesnt_affect_non_matching(self, engine_with_class_fixed):
        """dir#src (class=source, not sensitive) should NOT be clamped."""
        val = engine_with_class_fixed.resolve(type="dir", id="src", property="editable")
        assert val == "true", "Non-matching entities should keep cascade value"

    def test_unsupported_selector_warns(self, tmp_path):
        """Selectors that can't be matched should produce a warning, not silence."""
        world = tmp_path / "test.world.yml"
        world.write_text("""\
entities:
  - type: tool
    id: Bash
fixed:
  "tool[name='Bash']":
    allow: "false"
""")
        style = tmp_path / "test.umw"
        style.write_text("tool { allow: true; }\n")
        with pytest.warns(UserWarning, match="fixed constraint selector"):
            PolicyEngine.from_files(world=world, stylesheet=style)


# ---------------------------------------------------------------------------
# Bug #2: extend() rule_index continuity
# ---------------------------------------------------------------------------

class TestExtendRuleIndexContinuity:
    """extend() should continue rule_index from the base engine's max,
    so same-specificity rules follow 'later wins' across boundaries."""

    @pytest.fixture
    def base_engine(self):
        engine = PolicyEngine()
        engine.add_entities([
            {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
        ])
        engine.add_stylesheet("tool.dangerous { require: sandbox; }")
        return engine

    def test_extend_class_rule_overrides_base(self, base_engine):
        """Same-specificity class rule in extension should win over base."""
        extended = base_engine.extend(
            stylesheet="tool.dangerous { require: none; }",
        )
        val = extended.resolve(type="tool", id="Bash", property="require")
        assert val == "none", (
            "Extension rule at same specificity should win via higher rule_index"
        )

    def test_rule_index_increases_across_extend(self, base_engine):
        """The extension's rule_index should be higher than the base's max."""
        extended = base_engine.extend(
            stylesheet="tool.dangerous { require: none; }",
        )
        rows = extended.execute(
            "SELECT rule_index, property_value FROM cascade_candidates "
            "WHERE property_name = 'require' ORDER BY rule_index"
        )
        assert len(rows) == 2
        base_idx, ext_idx = rows[0][0], rows[1][0]
        assert ext_idx > base_idx, (
            f"Extension rule_index ({ext_idx}) should be > base ({base_idx})"
        )


# ---------------------------------------------------------------------------
# Bug #3: extend() new entities see pre-compiled rules
# ---------------------------------------------------------------------------

class TestExtendNewEntityVisibility:
    """New entities added via extend() should be matched by existing
    compiled rules from the base engine."""

    @pytest.fixture
    def base_engine(self):
        engine = PolicyEngine()
        engine.add_entities([
            {"type": "tool", "id": "Read", "classes": ["safe"]},
        ])
        engine.add_stylesheet("""\
tool { visible: true; allow: false; }
tool.safe { allow: true; max-level: 5; }
""")
        return engine

    def test_new_entity_inherits_type_rule(self, base_engine):
        """New tool added via extend should get tool { visible: true }."""
        extended = base_engine.extend(
            entities=[{"type": "tool", "id": "Edit", "classes": ["safe"]}],
        )
        val = extended.resolve(type="tool", id="Edit", property="visible")
        assert val == "true", "New entity should match base type rule"

    def test_new_entity_inherits_class_rule(self, base_engine):
        """New .safe tool should get tool.safe { allow: true }."""
        extended = base_engine.extend(
            entities=[{"type": "tool", "id": "Edit", "classes": ["safe"]}],
        )
        val = extended.resolve(type="tool", id="Edit", property="allow")
        assert val == "true", "New entity should match base class rule"

    def test_new_entity_inherits_max_level(self, base_engine):
        """New .safe tool should get max-level: 5 from base class rule."""
        extended = base_engine.extend(
            entities=[{"type": "tool", "id": "Edit", "classes": ["safe"]}],
        )
        val = extended.resolve(type="tool", id="Edit", property="max-level")
        assert val == "5", "New entity should inherit base max-level"

    def test_existing_entity_still_resolves(self, base_engine):
        """Adding new entity shouldn't break existing entity resolution."""
        extended = base_engine.extend(
            entities=[{"type": "tool", "id": "Edit", "classes": ["safe"]}],
        )
        val = extended.resolve(type="tool", id="Read", property="allow")
        assert val == "true", "Existing entity should still resolve correctly"

    def test_extend_entities_only_no_stylesheet(self, base_engine):
        """extend(entities=...) with no stylesheet should still apply base rules."""
        extended = base_engine.extend(
            entities=[{"type": "tool", "id": "Bash", "classes": ["dangerous"]}],
        )
        val = extended.resolve(type="tool", id="Bash", property="visible")
        assert val == "true", "Entity-only extend should see base type rule"
        val2 = extended.resolve(type="tool", id="Bash", property="allow")
        assert val2 == "false", "Entity-only extend should see base allow: false"
