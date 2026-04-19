"""Tests for SQL schema DDL generation."""
from __future__ import annotations

import sqlite3
import pytest
from umwelt.compilers.sql.schema import create_schema, EXPECTED_TABLES
from umwelt.compilers.sql.dialects import SQLiteDialect


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    yield con
    con.close()


class TestSchemaCreation:
    def test_ddl_executes_without_error(self, db):
        dialect = SQLiteDialect()
        ddl = create_schema(dialect)
        db.executescript(ddl)

    def test_all_tables_exist(self, db):
        dialect = SQLiteDialect()
        db.executescript(create_schema(dialect))
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cursor}
        for expected in EXPECTED_TABLES:
            assert expected in tables, f"missing table: {expected}"

    def test_entities_table_columns(self, db):
        dialect = SQLiteDialect()
        db.executescript(create_schema(dialect))
        cursor = db.execute("PRAGMA table_info(entities)")
        columns = {row[1] for row in cursor}
        assert {"id", "taxon", "type_name", "entity_id", "classes", "attributes", "parent_id", "depth"} <= columns

    def test_cascade_candidates_columns(self, db):
        dialect = SQLiteDialect()
        db.executescript(create_schema(dialect))
        cursor = db.execute("PRAGMA table_info(cascade_candidates)")
        columns = {row[1] for row in cursor}
        assert {"entity_id", "property_name", "property_value", "comparison",
                "specificity", "rule_index", "source_file", "source_line"} <= columns

    def test_entity_closure_columns(self, db):
        dialect = SQLiteDialect()
        db.executescript(create_schema(dialect))
        cursor = db.execute("PRAGMA table_info(entity_closure)")
        columns = {row[1] for row in cursor}
        assert {"ancestor_id", "descendant_id", "depth"} <= columns

    def test_insert_entity_with_json(self, db):
        """Verify JSON columns accept and return valid data."""
        import json
        dialect = SQLiteDialect()
        db.executescript(create_schema(dialect))
        db.execute(
            "INSERT INTO entities (taxon, type_name, entity_id, classes, attributes, depth) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("world", "file", "src/auth.py",
             json.dumps(["python"]),
             json.dumps({"path": "src/auth.py", "language": "python"}),
             0),
        )
        row = db.execute("SELECT json_extract(attributes, '$.path') FROM entities WHERE entity_id = 'src/auth.py'").fetchone()
        assert row[0] == "src/auth.py"
