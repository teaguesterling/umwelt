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
