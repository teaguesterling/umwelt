"""Tests for generic context qualifier mechanism."""
from __future__ import annotations

import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.schema import EXPECTED_TABLES, create_schema


def test_context_qualifiers_table_exists():
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "cascade_context_qualifiers" in tables


def test_context_qualifiers_in_expected_tables():
    assert "cascade_context_qualifiers" in EXPECTED_TABLES


from umwelt.policy import PolicyEngine


@pytest.fixture
def context_engine(tmp_path):
    world = tmp_path / "w.world.yml"
    world.write_text("""
entities:
  - type: tool
    id: Read
  - type: tool
    id: Bash
    classes: [dangerous]
  - type: mode
    id: review
  - type: mode
    id: implement
  - type: principal
    id: Teague
""")
    style = tmp_path / "p.umw"
    style.write_text("""
tool { allow: true; }
mode#review tool { allow: false; }
mode#review tool[name="Read"] { allow: true; }
mode#implement tool.dangerous { max-level: 3; }
principal#Teague tool { visible: true; }
""")
    return PolicyEngine.from_files(world=world, stylesheet=style)


class TestContextQualifierStorage:
    def test_unscoped_rule_has_no_qualifiers(self, context_engine):
        rows = context_engine.execute("""
            SELECT cc.rowid
            FROM cascade_candidates cc
            WHERE cc.mode_qualifier IS NULL
            AND NOT EXISTS (
                SELECT 1 FROM cascade_context_qualifiers ccq
                WHERE ccq.candidate_rowid = cc.rowid
            )
        """)
        assert len(rows) > 0, "Expected unscoped rules with no context qualifiers"

    def test_mode_gated_rule_has_context_qualifier(self, context_engine):
        rows = context_engine.execute("""
            SELECT ccq.taxon, ccq.type_name, ccq.entity_id
            FROM cascade_context_qualifiers ccq
            JOIN cascade_candidates cc ON ccq.candidate_rowid = cc.rowid
            WHERE ccq.type_name = 'mode' AND ccq.entity_id = 'review'
        """)
        assert len(rows) > 0

    def test_principal_gated_rule_has_context_qualifier(self, context_engine):
        rows = context_engine.execute("""
            SELECT ccq.taxon, ccq.type_name, ccq.entity_id
            FROM cascade_context_qualifiers ccq
            WHERE ccq.type_name = 'principal' AND ccq.entity_id = 'Teague'
        """)
        assert len(rows) > 0

    def test_qualifier_taxon_is_correct(self, context_engine):
        rows = context_engine.execute("""
            SELECT DISTINCT ccq.taxon, ccq.type_name
            FROM cascade_context_qualifiers ccq
            ORDER BY ccq.type_name
        """)
        result = {(r[0], r[1]) for r in rows}
        assert ("state", "mode") in result
        assert ("principal", "principal") in result

    def test_backward_compat_mode_qualifier_still_populated(self, context_engine):
        rows = context_engine.execute(
            "SELECT DISTINCT mode_qualifier FROM cascade_candidates "
            "WHERE mode_qualifier IS NOT NULL ORDER BY mode_qualifier"
        )
        qualifiers = {r[0] for r in rows}
        assert "review" in qualifiers
        assert "implement" in qualifiers


class TestContextFilteredResolve:
    def test_context_mode_review_denies_bash(self, context_engine):
        val = context_engine.resolve(
            type="tool", id="Bash", property="allow",
            context=[("state", "mode", "review")],
        )
        assert val == "false"

    def test_context_mode_review_allows_read(self, context_engine):
        val = context_engine.resolve(
            type="tool", id="Read", property="allow",
            context=[("state", "mode", "review")],
        )
        assert val == "true"

    def test_context_mode_implement_caps_level(self, context_engine):
        val = context_engine.resolve(
            type="tool", id="Bash", property="max-level",
            context=[("state", "mode", "implement")],
        )
        assert val == "3"

    def test_context_none_returns_all(self, context_engine):
        val_no_ctx = context_engine.resolve(type="tool", id="Bash", property="allow")
        val_ctx_none = context_engine.resolve(
            type="tool", id="Bash", property="allow", context=None,
        )
        assert val_no_ctx == val_ctx_none

    def test_context_unscoped_rules_always_apply(self, context_engine):
        val = context_engine.resolve(
            type="tool", id="Read", property="allow",
            context=[("state", "mode", "implement")],
        )
        assert val == "true"

    def test_context_dict_shorthand(self, context_engine):
        val = context_engine.resolve(
            type="tool", id="Bash", property="allow",
            context={"mode": "review"},
        )
        assert val == "false"

    def test_context_multi_qualifier(self, context_engine):
        val = context_engine.resolve(
            type="tool", id="Bash", property="allow",
            context=[("state", "mode", "review"), ("principal", "principal", "Teague")],
        )
        assert val == "false"


class TestContextFilteredResolveAll:
    def test_resolve_all_with_context(self, context_engine):
        tools = context_engine.resolve_all(
            type="tool",
            context=[("state", "mode", "review")],
        )
        bash = next(t for t in tools if t["entity_id"] == "Bash")
        assert bash["properties"]["allow"] == "false"


class TestContextFilteredTrace:
    def test_trace_with_context(self, context_engine):
        result = context_engine.trace(
            type="tool", id="Bash", property="max-level",
            context=[("state", "mode", "implement")],
        )
        assert result.value == "3"


class TestContextFilteredCheck:
    def test_check_with_context(self, context_engine):
        assert context_engine.check(
            type="tool", id="Bash",
            context=[("state", "mode", "review")],
            allow="false",
        )

    def test_require_with_context(self, context_engine):
        context_engine.require(
            type="tool", id="Read",
            context=[("state", "mode", "review")],
            allow="true",
        )
