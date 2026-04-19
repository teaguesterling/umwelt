"""Tests for cascade resolution views.

Verifies comparison-aware resolution: exact (highest specificity wins),
<= (tightest bound / MIN), pattern-in (set union).
"""
from __future__ import annotations

import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.resolution import create_resolution_views
from umwelt.compilers.sql.schema import create_schema


@pytest.fixture
def db():
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))
    return con


def _insert_candidates(con, rows):
    """Insert cascade candidate rows: (entity_id, prop, value, comparison, specificity, rule_index)."""
    dialect = SQLiteDialect()
    for entity_id, prop, value, comparison, spec, rule_idx in rows:
        spec_str = dialect.format_specificity(spec)
        con.execute(
            "INSERT INTO cascade_candidates (entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, 'test.umw', 1)",
            (entity_id, prop, value, comparison, spec_str, rule_idx),
        )
    con.commit()


def _resolved(con, entity_id: int, prop: str) -> str | None:
    row = con.execute(
        "SELECT property_value FROM resolved_properties WHERE entity_id = ? AND property_name = ?",
        (entity_id, prop),
    ).fetchone()
    return row[0] if row else None


class TestExactResolution:
    def test_higher_specificity_wins(self, db):
        _insert_candidates(db, [
            (1, "editable", "false", "exact", (1, 0, 0, 0, 0, 1, 0, 0), 0),
            (1, "editable", "true",  "exact", (1, 0, 100, 0, 0, 1, 0, 0), 1),
        ])
        create_resolution_views(db, SQLiteDialect())
        assert _resolved(db, 1, "editable") == "true"

    def test_document_order_breaks_ties(self, db):
        _insert_candidates(db, [
            (1, "editable", "false", "exact", (1, 0, 100, 0, 0, 0, 0, 0), 0),
            (1, "editable", "true",  "exact", (1, 0, 100, 0, 0, 0, 0, 0), 1),
        ])
        create_resolution_views(db, SQLiteDialect())
        assert _resolved(db, 1, "editable") == "true"

    def test_independent_entities(self, db):
        _insert_candidates(db, [
            (1, "editable", "true",  "exact", (1, 0, 100, 0, 0, 0, 0, 0), 0),
            (2, "editable", "false", "exact", (1, 0, 0, 0, 0, 0, 0, 0), 0),
        ])
        create_resolution_views(db, SQLiteDialect())
        assert _resolved(db, 1, "editable") == "true"
        assert _resolved(db, 2, "editable") == "false"

    def test_a1_unique_winners(self, db):
        """Every (entity, property) pair has exactly one winner."""
        _insert_candidates(db, [
            (1, "editable", "true",  "exact", (1, 0, 100, 0, 0, 0, 0, 0), 0),
            (1, "editable", "false", "exact", (1, 0, 0, 0, 0, 0, 0, 0), 1),
            (1, "visible",  "true",  "exact", (1, 0, 0, 0, 0, 0, 0, 0), 0),
        ])
        create_resolution_views(db, SQLiteDialect())
        dupes = db.execute("""
            SELECT entity_id, property_name, COUNT(*) AS n
            FROM resolved_properties GROUP BY entity_id, property_name HAVING n > 1
        """).fetchall()
        assert dupes == []


class TestCapResolution:
    def test_tightest_bound_wins(self, db):
        _insert_candidates(db, [
            (1, "max-level", "5", "<=", (1, 0, 0, 0, 0, 1, 0, 0), 0),
            (1, "max-level", "3", "<=", (1, 0, 0, 0, 0, 101, 0, 0), 1),
        ])
        create_resolution_views(db, SQLiteDialect())
        assert _resolved(db, 1, "max-level") == "3"

    def test_cap_independent_of_specificity(self, db):
        """For <=, the minimum value wins regardless of specificity."""
        _insert_candidates(db, [
            (1, "max-level", "2", "<=", (1, 0, 0, 0, 0, 1, 0, 0), 0),
            (1, "max-level", "5", "<=", (1, 0, 0, 0, 0, 10001, 0, 0), 1),
        ])
        create_resolution_views(db, SQLiteDialect())
        assert _resolved(db, 1, "max-level") == "2"


class TestPatternResolution:
    def test_patterns_aggregate(self, db):
        _insert_candidates(db, [
            (1, "allow-pattern", "git *",    "pattern-in", (1, 0, 0, 0, 0, 101, 0, 0), 0),
            (1, "allow-pattern", "pytest *", "pattern-in", (1, 0, 0, 0, 0, 101, 0, 0), 1),
        ])
        create_resolution_views(db, SQLiteDialect())
        result = _resolved(db, 1, "allow-pattern")
        assert result is not None
        assert "git *" in result
        assert "pytest *" in result

    def test_patterns_deduplicate(self, db):
        _insert_candidates(db, [
            (1, "allow-pattern", "git *", "pattern-in", (1, 0, 0, 0, 0, 101, 0, 0), 0),
            (1, "allow-pattern", "git *", "pattern-in", (1, 0, 0, 0, 0, 101, 0, 0), 1),
        ])
        create_resolution_views(db, SQLiteDialect())
        result = _resolved(db, 1, "allow-pattern")
        assert result == "git *"


class TestSpecificityOrdering:
    def test_json_specificity_ordering_is_correct(self, db):
        """Higher axis_count wins over higher within-axis specificity."""
        dialect = SQLiteDialect()
        _insert_candidates(db, [
            (1, "allow", "true",  "exact", (2, 0, 0, 0, 0, 101, 0, 0), 0),
            (1, "allow", "false", "exact", (1, 0, 0, 0, 0, 10001, 0, 0), 1),
        ])
        create_resolution_views(db, dialect)
        assert _resolved(db, 1, "allow") == "true"
