# tests/policy/test_fixed_constraints.py
"""Tests for fixed constraints — post-cascade clamping."""
from __future__ import annotations

import json
import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.resolution import create_resolution_views
from umwelt.compilers.sql.schema import EXPECTED_TABLES, create_schema
from umwelt.compilers.sql.populate import populate_from_world
from umwelt.policy.queries import resolve_entity
from umwelt.world.model import DeclaredEntity, WorldFile


@pytest.fixture
def dialect():
    return SQLiteDialect()


@pytest.fixture
def db(dialect):
    """In-memory SQLite with schema created."""
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))
    yield con
    con.close()


class TestFixedConstraintsSchema:
    def test_fixed_constraints_in_expected_tables(self):
        assert "fixed_constraints" in EXPECTED_TABLES

    def test_fixed_constraints_table_created(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fixed_constraints'"
        ).fetchall()
        assert len(tables) == 1


class TestEffectivePropertiesView:
    def test_effective_properties_view_exists(self, db, dialect):
        """effective_properties view is created after resolution views."""
        # Insert an entity and cascade candidate so views have something to work with
        db.execute(
            "INSERT INTO entities (id, taxon, type_name, entity_id, depth) "
            "VALUES (1, 'cap', 'tool', 'Read', 0)"
        )
        db.execute(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (1, 'allow', 'true', 'exact', "
            "'[\"00000\",\"00000\",\"00000\",\"00001\",\"00000\",\"00000\",\"00000\",\"00000\"]', 0, 'p.umw', 1)"
        )
        db.commit()
        create_resolution_views(db, dialect)

        views = db.execute(
            "SELECT name FROM sqlite_master WHERE type='view' AND name='effective_properties'"
        ).fetchall()
        assert len(views) == 1

    def test_fixed_overrides_cascade(self, db, dialect):
        """When a fixed constraint exists, effective_properties returns the fixed value."""
        db.execute(
            "INSERT INTO entities (id, taxon, type_name, entity_id, depth) "
            "VALUES (1, 'cap', 'tool', 'Bash', 0)"
        )
        db.execute(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (1, 'allow', 'true', 'exact', "
            "'[\"00000\",\"00000\",\"00000\",\"00001\",\"00000\",\"00000\",\"00000\",\"00000\"]', 0, 'p.umw', 1)"
        )
        db.execute(
            "INSERT INTO fixed_constraints (entity_id, property_name, property_value, selector) "
            "VALUES (1, 'allow', 'false', 'tool#Bash')"
        )
        db.commit()
        create_resolution_views(db, dialect)

        row = db.execute(
            "SELECT effective_value, source FROM effective_properties "
            "WHERE entity_id = 1 AND property_name = 'allow'"
        ).fetchone()
        assert row is not None
        assert row[0] == "false"
        assert row[1] == "fixed"

    def test_passthrough_without_fixed(self, db, dialect):
        """Without a fixed constraint, effective_properties returns cascade value with source='cascade'."""
        db.execute(
            "INSERT INTO entities (id, taxon, type_name, entity_id, depth) "
            "VALUES (1, 'cap', 'tool', 'Read', 0)"
        )
        db.execute(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (1, 'allow', 'true', 'exact', "
            "'[\"00000\",\"00000\",\"00000\",\"00001\",\"00000\",\"00000\",\"00000\",\"00000\"]', 0, 'p.umw', 1)"
        )
        db.commit()
        create_resolution_views(db, dialect)

        row = db.execute(
            "SELECT effective_value, source FROM effective_properties "
            "WHERE entity_id = 1 AND property_name = 'allow'"
        ).fetchone()
        assert row is not None
        assert row[0] == "true"
        assert row[1] == "cascade"


class TestPopulateFixedConstraints:
    def test_fixed_raw_populates_table(self, db, dialect):
        """populate_from_world processes fixed_raw into the fixed_constraints table."""
        # Insert entity first
        db.execute(
            "INSERT INTO entities (id, taxon, type_name, entity_id, depth) "
            "VALUES (1, 'cap', 'tool', 'Bash', 0)"
        )
        db.commit()

        wf = WorldFile(
            entities=(),
            projections=(),
            warnings=(),
            fixed_raw={"tool#Bash": {"allow": "false", "max-level": "2"}},
        )
        populate_from_world(db, wf)

        rows = db.execute(
            "SELECT property_name, property_value, selector FROM fixed_constraints ORDER BY property_name"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0] == ("allow", "false", "tool#Bash")
        assert rows[1] == ("max-level", "2", "tool#Bash")

    def test_fixed_raw_type_selector(self, db, dialect):
        """Fixed constraint with type-only selector matches all entities of that type."""
        db.execute(
            "INSERT INTO entities (id, taxon, type_name, entity_id, depth) "
            "VALUES (1, 'cap', 'tool', 'Read', 0)"
        )
        db.execute(
            "INSERT INTO entities (id, taxon, type_name, entity_id, depth) "
            "VALUES (2, 'cap', 'tool', 'Edit', 0)"
        )
        db.commit()

        wf = WorldFile(
            entities=(),
            projections=(),
            warnings=(),
            fixed_raw={"tool": {"max-level": "10"}},
        )
        populate_from_world(db, wf)

        rows = db.execute("SELECT entity_id FROM fixed_constraints ORDER BY entity_id").fetchall()
        assert len(rows) == 2
        assert rows[0][0] == 1
        assert rows[1][0] == 2


class TestResolveEntityUsesEffective:
    def test_resolve_returns_fixed_value(self, db, dialect):
        """End-to-end: entity + cascade rule + fixed constraint -> resolve returns fixed value."""
        db.execute(
            "INSERT INTO entities (id, taxon, type_name, entity_id, depth) "
            "VALUES (1, 'cap', 'tool', 'Bash', 0)"
        )
        db.execute(
            "INSERT INTO entity_closure (ancestor_id, descendant_id, depth) VALUES (1, 1, 0)"
        )
        spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
        db.execute(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (1, 'allow', 'true', 'exact', ?, 0, 'p.umw', 1)",
            (spec,),
        )
        db.execute(
            "INSERT INTO fixed_constraints (entity_id, property_name, property_value, selector) "
            "VALUES (1, 'allow', 'false', 'tool#Bash')"
        )
        db.commit()
        create_resolution_views(db, dialect)

        val = resolve_entity(db, type="tool", id="Bash", property="allow")
        assert val == "false"

    def test_resolve_passthrough_without_fixed(self, db, dialect):
        """Without fixed constraint, resolve_entity returns cascade value."""
        db.execute(
            "INSERT INTO entities (id, taxon, type_name, entity_id, depth) "
            "VALUES (1, 'cap', 'tool', 'Read', 0)"
        )
        db.execute(
            "INSERT INTO entity_closure (ancestor_id, descendant_id, depth) VALUES (1, 1, 0)"
        )
        spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
        db.execute(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (1, 'allow', 'true', 'exact', ?, 0, 'p.umw', 1)",
            (spec,),
        )
        db.commit()
        create_resolution_views(db, dialect)

        val = resolve_entity(db, type="tool", id="Read", property="allow")
        assert val == "true"
