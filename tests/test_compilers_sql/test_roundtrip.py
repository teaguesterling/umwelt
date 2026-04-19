"""Round-trip tests: parse .umw → compile → SQLite → resolve → verify.

Port of ducklog's test_roundtrip.py adapted for SQLite.
"""
from __future__ import annotations

import pytest
from tests.test_compilers_sql.conftest import parse_view
from umwelt.compilers.sql.compiler import compile_view
from umwelt.compilers.sql.dialects import SQLiteDialect


DIALECT = SQLiteDialect()


@pytest.fixture
def world(populated_db):
    return populated_db


def _resolve(world, umw_text: str):
    view = parse_view(umw_text)
    compile_view(world, view, DIALECT, source_file="test.umw")
    return _Resolved(world)


class _Resolved:
    def __init__(self, con):
        self.con = con

    def property(self, entity_id: str, prop_name: str) -> str | None:
        row = self.con.execute(
            "SELECT rp.property_value FROM resolved_properties rp "
            "JOIN entities e ON rp.entity_id = e.id "
            "WHERE e.entity_id = ? AND rp.property_name = ?",
            (entity_id, prop_name),
        ).fetchone()
        return row[0] if row else None

    def property_by_id(self, entity_db_id: int, prop_name: str) -> str | None:
        row = self.con.execute(
            "SELECT property_value FROM resolved_properties "
            "WHERE entity_id = ? AND property_name = ?",
            (entity_db_id, prop_name),
        ).fetchone()
        return row[0] if row else None

    def all_props(self, entity_id: str) -> dict[str, str]:
        rows = self.con.execute(
            "SELECT rp.property_name, rp.property_value FROM resolved_properties rp "
            "JOIN entities e ON rp.entity_id = e.id WHERE e.entity_id = ?",
            (entity_id,),
        ).fetchall()
        return dict(rows)

    def assert_a1(self):
        dupes = self.con.execute(
            "SELECT entity_id, property_name, COUNT(*) AS n "
            "FROM resolved_properties GROUP BY entity_id, property_name HAVING n > 1"
        ).fetchall()
        assert dupes == [], f"A1 violated: duplicate winners {dupes}"


class TestFilePermissions:
    def test_prefix_match_sets_editable(self, world):
        rv = _resolve(world, '''
            file[path^="src/"] { editable: true; }
            file { editable: false; }
        ''')
        assert rv.property("src/auth.py", "editable") == "true"
        assert rv.property("tests/test_auth.py", "editable") == "false"
        assert rv.property("README.md", "editable") == "false"
        rv.assert_a1()

    def test_suffix_match_hides_pyc(self, world):
        rv = _resolve(world, '''
            file { visible: true; }
            file[path$=".pyc"] { visible: false; }
        ''')
        assert rv.property("src/auth.py", "visible") == "true"
        assert rv.property("src/main.pyc", "visible") == "false"
        rv.assert_a1()

    def test_specificity_ordering(self, world):
        rv = _resolve(world, '''
            file { editable: false; }
            file[path^="src/"] { editable: true; }
        ''')
        assert rv.property("src/auth.py", "editable") == "true"
        rv.assert_a1()

    def test_document_order_breaks_ties(self, world):
        rv = _resolve(world, '''
            file[path^="src/"] { editable: false; }
            file[path^="src/"] { editable: true; }
        ''')
        assert rv.property("src/auth.py", "editable") == "true"
        rv.assert_a1()


class TestToolPermissions:
    def test_tool_allow_deny(self, world):
        rv = _resolve(world, '''
            tool { allow: true; }
            tool[name="Bash"] { allow: false; }
        ''')
        assert rv.property("Read", "allow") == "true"
        assert rv.property("Bash", "allow") == "false"
        rv.assert_a1()

    def test_max_level_tightest_wins(self, world):
        rv = _resolve(world, '''
            tool { max-level: 5; }
            tool[name="Bash"] { max-level: 3; }
        ''')
        assert rv.property("Bash", "max-level") == "3"
        assert rv.property("Read", "max-level") == "5"
        rv.assert_a1()

    def test_allow_pattern_aggregates(self, world):
        rv = _resolve(world, '''
            tool[name="Bash"] { allow-pattern: "git *"; }
            tool[name="Bash"] { allow-pattern: "pytest *"; }
        ''')
        patterns = rv.property("Bash", "allow-pattern")
        assert patterns is not None
        assert "git *" in patterns
        assert "pytest *" in patterns
        rv.assert_a1()


class TestModeGatedTools:
    def test_mode_gates_tool(self, world):
        rv = _resolve(world, '''
            tool { allow: true; }
            mode.explore tool { allow: false; }
        ''')
        assert rv.property("Read", "allow") == "false"
        assert rv.property("Bash", "allow") == "false"
        rv.assert_a1()

    def test_mode_specific_tool_override(self, world):
        rv = _resolve(world, '''
            mode.explore tool { allow: false; }
            mode.explore tool[name="Read"] { allow: true; }
        ''')
        assert rv.property("Read", "allow") == "true"
        assert rv.property("Bash", "allow") == "false"
        rv.assert_a1()

    def test_nonexistent_mode_gates_nothing(self, world):
        rv = _resolve(world, '''
            tool { allow: true; }
            mode.deploy tool { allow: false; }
        ''')
        assert rv.property("Read", "allow") == "true"
        rv.assert_a1()


class TestCrossAxis:
    def test_three_axis_beats_two_axis(self, world):
        rv = _resolve(world, '''
            mode.implement tool[name="Bash"] { allow: false; }
            principal#Teague mode.implement tool[name="Bash"] { allow: true; }
        ''')
        assert rv.property("Bash", "allow") == "true"
        rv.assert_a1()

    def test_two_axis_beats_one_axis(self, world):
        rv = _resolve(world, '''
            tool[name="Bash"] { allow: true; }
            mode.implement tool[name="Bash"] { allow: false; }
        ''')
        assert rv.property("Bash", "allow") == "false"
        rv.assert_a1()


class TestStructuralDescendants:
    def test_dir_file_descendant(self, world):
        rv = _resolve(world, '''
            file { editable: false; }
            dir[name="src"] file { editable: true; }
        ''')
        assert rv.property("src/auth.py", "editable") == "true"
        assert rv.property("tests/test_auth.py", "editable") == "false"
        rv.assert_a1()


class TestFullPolicy:
    def test_realistic_policy(self, world):
        rv = _resolve(world, '''
            file { editable: false; visible: true; }
            file[path^="src/"] { editable: true; }
            file[path$=".pyc"] { visible: false; }

            tool { allow: true; max-level: 3; }
            tool[name="Bash"] { max-level: 2; }
            tool[name="Agent"] { allow: false; }

            tool[name="Bash"] { allow-pattern: "git *"; }
            tool[name="Bash"] { allow-pattern: "pytest *"; }

            network { deny: "*"; }
            resource[kind="memory"] { limit: 512MB; }
        ''')
        assert rv.property("src/auth.py", "editable") == "true"
        assert rv.property("README.md", "editable") == "false"
        assert rv.property("src/main.pyc", "visible") == "false"
        assert rv.property("Read", "allow") == "true"
        assert rv.property("Agent", "allow") == "false"
        assert rv.property("Bash", "max-level") == "2"

        patterns = rv.property("Bash", "allow-pattern")
        assert "git *" in patterns
        assert "pytest *" in patterns

        assert rv.property_by_id(25, "deny") == "*"
        assert rv.property("memory", "limit") == "512MB"
        rv.assert_a1()
