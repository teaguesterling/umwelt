# tests/policy/test_lint.py
import json
import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.resolution import create_resolution_views
from umwelt.compilers.sql.schema import create_schema
from umwelt.policy.lint import run_lint


@pytest.fixture
def lint_db():
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))

    entities = [
        (1, "capability", "tool", "Read", None, json.dumps({"name": "Read"}), None, 0),
        (2, "capability", "tool", "Bash", json.dumps(["dangerous"]), json.dumps({"name": "Bash"}), None, 0),
        (3, "capability", "tool", "Orphan", None, json.dumps({"name": "Orphan"}), None, 0),
    ]
    con.executemany(
        "INSERT INTO entities (id, taxon, type_name, entity_id, classes, attributes, parent_id, depth) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        entities,
    )
    con.executescript("""
        DELETE FROM entity_closure;
        INSERT INTO entity_closure (ancestor_id, descendant_id, depth)
        SELECT id, id, 0 FROM entities;
    """)
    return con


class TestNarrowWin:
    def test_detects_narrow_win(self, lint_db):
        dialect = SQLiteDialect()
        spec_low = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
        spec_high = '["00000","00000","00000","00001","00000","00001","00000","00000"]'

        candidates = [
            (2, "allow", "true", "exact", spec_low, 0, "a.umw", 1),
            (2, "allow", "false", "exact", spec_high, 1, "a.umw", 3),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        narrow = [w for w in warnings if w.smell == "narrow_win"]
        assert len(narrow) >= 1


class TestShadowedRule:
    def test_detects_shadowed_rule(self, lint_db):
        dialect = SQLiteDialect()
        spec_low = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
        spec_high = '["00000","00000","00000","00001","00000","00001","00000","00000"]'

        candidates = [
            (2, "allow", "true", "exact", spec_low, 0, "a.umw", 5),
            (2, "allow", "false", "exact", spec_high, 1, "a.umw", 10),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        shadowed = [w for w in warnings if w.smell == "shadowed_rule"]
        assert len(shadowed) >= 1


class TestUncoveredEntity:
    def test_detects_uncovered_entity(self, lint_db):
        dialect = SQLiteDialect()
        spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'

        candidates = [
            (1, "allow", "true", "exact", spec, 0, "a.umw", 1),
            (2, "allow", "true", "exact", spec, 0, "a.umw", 1),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        uncovered = [w for w in warnings if w.smell == "uncovered_entity"]
        assert len(uncovered) >= 1
        assert any("Orphan" in w.description for w in uncovered)


class TestSourceOrderDependence:
    def test_detects_source_order_dependence(self, lint_db):
        dialect = SQLiteDialect()
        spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'

        candidates = [
            (2, "allow", "true", "exact", spec, 0, "a.umw", 1),
            (2, "allow", "false", "exact", spec, 1, "a.umw", 5),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        source_order = [w for w in warnings if w.smell == "source_order_dependence"]
        assert len(source_order) >= 1


class TestSpecificityEscalation:
    def test_detects_escalation(self, lint_db):
        dialect = SQLiteDialect()
        spec1 = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
        spec2 = '["00000","00000","00000","00001","00000","00001","00000","00000"]'
        spec3 = '["00000","00000","00001","00001","00000","00001","00000","00000"]'

        candidates = [
            (2, "max-level", "5", "<=", spec1, 0, "a.umw", 1),
            (2, "max-level", "3", "<=", spec2, 1, "a.umw", 3),
            (2, "max-level", "1", "<=", spec3, 2, "a.umw", 5),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        escalation = [w for w in warnings if w.smell == "specificity_escalation"]
        assert len(escalation) >= 1


class TestNoSmells:
    def test_clean_db_no_warnings(self, lint_db):
        dialect = SQLiteDialect()
        spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'

        candidates = [
            (1, "allow", "true", "exact", spec, 0, "a.umw", 1),
            (2, "allow", "true", "exact", spec, 0, "a.umw", 1),
            (3, "allow", "true", "exact", spec, 0, "a.umw", 1),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        serious = [w for w in warnings if w.severity == "warning"]
        assert len(serious) == 0
