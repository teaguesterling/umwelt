"""Tests for mode-filtered PolicyEngine queries.

When mode is passed to resolve()/resolve_all(), only rules gated by
that mode (or unscoped rules) should contribute to resolution.
"""
from __future__ import annotations

import pytest

from umwelt.errors import PolicyDenied
from umwelt.policy import PolicyEngine


@pytest.fixture
def mode_engine(tmp_path):
    world = tmp_path / "w.world.yml"
    world.write_text("""
entities:
  - type: tool
    id: Read
  - type: tool
    id: Edit
  - type: tool
    id: Bash
    classes: [dangerous]
  - type: mode
    id: implement
  - type: mode
    id: review
  - type: mode
    id: explore
""")
    style = tmp_path / "p.umw"
    style.write_text("""
tool { allow: true; max-level: 8; }
tool.dangerous { max-level: 5; }
mode#implement tool.dangerous { max-level: 3; }
mode#review tool { allow: false; }
mode#review tool[name="Read"] { allow: true; }
mode#explore tool { allow: false; }
mode#explore tool[name="Read"] { allow: true; }
mode#explore tool[name="Grep"] { allow: true; }
""")
    return PolicyEngine.from_files(world=world, stylesheet=style)


class TestModeFilteredResolve:
    def test_no_mode_includes_all_rules(self, mode_engine):
        """Without mode filter, all mode-gated rules compete in cascade."""
        val = mode_engine.resolve(type="tool", id="Bash", property="allow")
        assert val is not None

    def test_matching_mode_fires(self, mode_engine):
        val = mode_engine.resolve(type="tool", id="Bash", property="max-level", mode="implement")
        assert val == "3"

    def test_non_matching_mode_dropped(self, mode_engine):
        val = mode_engine.resolve(type="tool", id="Bash", property="max-level", mode="review")
        assert val == "5"

    def test_unscoped_rules_always_apply(self, mode_engine):
        val = mode_engine.resolve(type="tool", id="Read", property="allow", mode="implement")
        assert val == "true"

    def test_review_mode_denies_most_tools(self, mode_engine):
        val = mode_engine.resolve(type="tool", id="Bash", property="allow", mode="review")
        assert val == "false"

    def test_review_mode_allows_read(self, mode_engine):
        val = mode_engine.resolve(type="tool", id="Read", property="allow", mode="review")
        assert val == "true"

    def test_explore_mode_denies_edit(self, mode_engine):
        val = mode_engine.resolve(type="tool", id="Edit", property="allow", mode="explore")
        assert val == "false"

    def test_implement_mode_no_allow_override(self, mode_engine):
        """implement mode has no allow override — unscoped 'allow: true' wins."""
        val = mode_engine.resolve(type="tool", id="Edit", property="allow", mode="implement")
        assert val == "true"


class TestModeFilteredResolveAll:
    def test_resolve_all_with_mode(self, mode_engine):
        tools = mode_engine.resolve_all(type="tool", mode="review")
        assert len(tools) >= 3
        bash = next(t for t in tools if t["entity_id"] == "Bash")
        assert bash["properties"]["allow"] == "false"

    def test_resolve_all_read_allowed_in_review(self, mode_engine):
        tools = mode_engine.resolve_all(type="tool", mode="review")
        read = next(t for t in tools if t["entity_id"] == "Read")
        assert read["properties"]["allow"] == "true"


class TestModeFilteredCheck:
    def test_check_with_mode(self, mode_engine):
        assert mode_engine.check(type="tool", id="Bash", mode="review", allow="false")

    def test_check_mode_allowed(self, mode_engine):
        assert mode_engine.check(type="tool", id="Read", mode="review", allow="true")


class TestModeFilteredRequire:
    def test_require_with_mode_passes(self, mode_engine):
        mode_engine.require(type="tool", id="Read", mode="review", allow="true")

    def test_require_with_mode_raises(self, mode_engine):
        with pytest.raises(PolicyDenied):
            mode_engine.require(type="tool", id="Bash", mode="review", allow="true")


class TestModeFilteredTrace:
    def test_trace_with_mode(self, mode_engine):
        result = mode_engine.trace(type="tool", id="Bash", property="max-level", mode="implement")
        assert result.value == "3"

    def test_trace_without_mode_shows_all_candidates(self, mode_engine):
        result = mode_engine.trace(type="tool", id="Bash", property="max-level")
        assert len(result.candidates) >= 2


class TestBackwardCompat:
    def test_existing_tests_unaffected(self, mode_engine):
        """All existing resolve patterns work without mode parameter."""
        assert mode_engine.resolve(type="tool", id="Read", property="max-level") is not None
        assert mode_engine.resolve(type="tool", id="Bash") is not None
        tools = mode_engine.resolve_all(type="tool")
        assert len(tools) >= 3


class TestModeQualifierStorage:
    """Verify mode_qualifier is stored in cascade_candidates."""

    def test_mode_qualifier_column_exists(self, mode_engine):
        rows = mode_engine.execute(
            "SELECT mode_qualifier FROM cascade_candidates LIMIT 1"
        )
        assert rows is not None

    def test_unscoped_rule_has_null_qualifier(self, mode_engine):
        rows = mode_engine.execute(
            "SELECT DISTINCT mode_qualifier FROM cascade_candidates "
            "WHERE mode_qualifier IS NULL"
        )
        assert len(rows) >= 1

    def test_mode_gated_rule_has_qualifier(self, mode_engine):
        rows = mode_engine.execute(
            "SELECT DISTINCT mode_qualifier FROM cascade_candidates "
            "WHERE mode_qualifier IS NOT NULL "
            "ORDER BY mode_qualifier"
        )
        qualifiers = {r[0] for r in rows}
        assert "implement" in qualifiers
        assert "review" in qualifiers
        assert "explore" in qualifiers
