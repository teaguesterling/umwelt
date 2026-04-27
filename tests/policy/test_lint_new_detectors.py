from __future__ import annotations

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
        (3, "capability", "tool", "Deploy", json.dumps(["dangerous", "infrastructure"]), json.dumps({"name": "Deploy"}), None, 0),
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


def _spec(cross=0, id_val=0, cls=0):
    parts = ["00000"] * 8
    parts[0] = f"{cross:05d}"
    parts[3] = f"{id_val:05d}"
    parts[5] = f"{cls:05d}"
    return json.dumps(parts)


class TestCrossAxisDominance:
    def test_detects_cross_axis_over_id(self, lint_db):
        dialect = SQLiteDialect()
        candidates = [
            (3, "allow", "false", "exact", _spec(cross=0, id_val=1), 0, "a.umw", 1),
            (3, "allow", "true", "exact", _spec(cross=1, id_val=0), 1, "a.umw", 5),
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
        hits = [w for w in warnings if w.smell == "cross_axis_dominance"]
        assert len(hits) >= 1
        assert "cross-axis" in hits[0].description.lower()

    def test_no_false_positive_same_axis(self, lint_db):
        dialect = SQLiteDialect()
        candidates = [
            (2, "allow", "false", "exact", _spec(cross=0, id_val=0, cls=1), 0, "a.umw", 1),
            (2, "allow", "true", "exact", _spec(cross=0, id_val=1), 1, "a.umw", 3),
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
        hits = [w for w in warnings if w.smell == "cross_axis_dominance"]
        assert len(hits) == 0


class TestCeilingIneffective:
    def test_detects_ineffective_ceiling(self, lint_db):
        dialect = SQLiteDialect()
        candidates = [
            (2, "max-level", "3", "<=", _spec(cls=1), 0, "a.umw", 1),
            (2, "max-level", "5", "<=", _spec(id_val=1, cls=1), 1, "a.umw", 3),
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
        hits = [w for w in warnings if w.smell == "ceiling_ineffective"]
        assert len(hits) >= 1
        assert "ineffective" in hits[0].description.lower()

    def test_no_false_positive_lowering_ceiling(self, lint_db):
        dialect = SQLiteDialect()
        candidates = [
            (2, "max-level", "5", "<=", _spec(cls=1), 0, "a.umw", 1),
            (2, "max-level", "3", "<=", _spec(id_val=1, cls=1), 1, "a.umw", 3),
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
        hits = [w for w in warnings if w.smell == "ceiling_ineffective"]
        assert len(hits) == 0


class TestSpecificityTie:
    def test_detects_tie(self, lint_db):
        dialect = SQLiteDialect()
        spec = _spec(cls=1)
        candidates = [
            (2, "require", "sandbox", "exact", spec, 0, "a.umw", 1),
            (2, "require", "none", "exact", spec, 0, "b.umw", 1),
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
        hits = [w for w in warnings if w.smell == "specificity_tie"]
        assert len(hits) >= 1
        assert "nondeterministic" in hits[0].description.lower()

    def test_no_false_positive_different_rule_index(self, lint_db):
        dialect = SQLiteDialect()
        spec = _spec(cls=1)
        candidates = [
            (2, "require", "sandbox", "exact", spec, 0, "a.umw", 1),
            (2, "require", "none", "exact", spec, 1, "a.umw", 5),
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
        hits = [w for w in warnings if w.smell == "specificity_tie"]
        assert len(hits) == 0


class TestCrossAxisTie:
    def test_detects_different_axis_competition(self, lint_db):
        dialect = SQLiteDialect()
        spec_a = _spec(cross=1, cls=1)
        spec_b = _spec(cross=1)
        candidates = [
            (3, "allow", "true", "exact", spec_a, 0, "a.umw", 1),
            (3, "allow", "false", "exact", spec_b, 1, "a.umw", 5),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        rowid_base = lint_db.execute("SELECT MAX(rowid) FROM cascade_candidates").fetchone()[0]
        lint_db.execute(
            "INSERT INTO cascade_context_qualifiers (candidate_rowid, taxon, type_name, entity_id) "
            "VALUES (?, 'principal', 'principal', 'ops')",
            (rowid_base - 1,),
        )
        lint_db.execute(
            "INSERT INTO cascade_context_qualifiers (candidate_rowid, taxon, type_name, entity_id) "
            "VALUES (?, 'state', 'mode', 'review')",
            (rowid_base,),
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        hits = [w for w in warnings if w.smell == "cross_axis_tie"]
        assert len(hits) >= 1

    def test_no_false_positive_same_axis(self, lint_db):
        dialect = SQLiteDialect()
        spec_a = _spec(cross=1, cls=1)
        spec_b = _spec(cross=1)
        candidates = [
            (3, "allow", "true", "exact", spec_a, 0, "a.umw", 1),
            (3, "allow", "false", "exact", spec_b, 1, "a.umw", 5),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        rowid_base = lint_db.execute("SELECT MAX(rowid) FROM cascade_candidates").fetchone()[0]
        lint_db.execute(
            "INSERT INTO cascade_context_qualifiers (candidate_rowid, taxon, type_name, entity_id) "
            "VALUES (?, 'state', 'mode', 'deploy')",
            (rowid_base - 1,),
        )
        lint_db.execute(
            "INSERT INTO cascade_context_qualifiers (candidate_rowid, taxon, type_name, entity_id) "
            "VALUES (?, 'state', 'mode', 'review')",
            (rowid_base,),
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        hits = [w for w in warnings if w.smell == "cross_axis_tie"]
        assert len(hits) == 0


class TestCeilingConflict:
    def test_detects_competing_ceilings(self, lint_db):
        dialect = SQLiteDialect()
        spec = _spec(cls=1)
        candidates = [
            (2, "max-level", "3", "<=", spec, 0, "a.umw", 1),
            (2, "max-level", "5", "<=", spec, 1, "a.umw", 3),
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
        hits = [w for w in warnings if w.smell == "ceiling_conflict"]
        assert len(hits) >= 1

    def test_no_false_positive_same_value(self, lint_db):
        dialect = SQLiteDialect()
        spec = _spec(cls=1)
        candidates = [
            (2, "max-level", "3", "<=", spec, 0, "a.umw", 1),
            (2, "max-level", "3", "<=", spec, 1, "a.umw", 3),
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
        hits = [w for w in warnings if w.smell == "ceiling_conflict"]
        assert len(hits) == 0
