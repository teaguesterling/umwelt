# tests/policy/test_projections.py
import json
import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.resolution import create_resolution_views
from umwelt.compilers.sql.schema import create_schema
from umwelt.policy.projections import create_projection_views, create_compilation_meta


@pytest.fixture
def projection_db():
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))

    prop_types = [
        ("capability", "tool", "allow", "str", "exact", ""),
        ("capability", "tool", "visible", "str", "exact", ""),
        ("capability", "tool", "max-level", "int", "<=", ""),
        ("state", "mode", "writable", "str", "exact", ""),
        ("state", "mode", "strategy", "str", "exact", ""),
    ]
    con.executemany(
        "INSERT INTO property_types (taxon, entity_type, name, value_type, comparison, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        prop_types,
    )

    entities = [
        (1, "capability", "tool", "Read", None, json.dumps({"name": "Read"}), None, 0),
        (2, "capability", "tool", "Bash", json.dumps(["dangerous"]), json.dumps({"name": "Bash"}), None, 0),
        (3, "state", "mode", "implement", None, json.dumps({}), None, 0),
    ]
    con.executemany(
        "INSERT INTO entities (id, taxon, type_name, entity_id, classes, attributes, parent_id, depth) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        entities,
    )

    spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
    candidates = [
        (1, "allow", "true", "exact", spec, 0, "", 0),
        (2, "allow", "true", "exact", spec, 0, "", 0),
        (2, "max-level", "3", "<=", spec, 0, "", 0),
        (3, "writable", "src/", "exact", spec, 0, "", 0),
    ]
    con.executemany(
        "INSERT INTO cascade_candidates "
        "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        candidates,
    )
    con.commit()
    create_resolution_views(con, dialect)
    return con


class TestProjectionViews:
    def test_creates_tools_view(self, projection_db):
        create_projection_views(projection_db)
        rows = projection_db.execute("SELECT * FROM tools").fetchall()
        assert len(rows) == 2

    def test_tools_view_has_pivoted_columns(self, projection_db):
        create_projection_views(projection_db)
        row = projection_db.execute(
            "SELECT name, allow, max_level FROM tools WHERE name = 'Bash'"
        ).fetchone()
        assert row is not None
        assert row[1] == "true"
        assert row[2] == "3"

    def test_creates_modes_view(self, projection_db):
        create_projection_views(projection_db)
        rows = projection_db.execute("SELECT * FROM modes").fetchall()
        assert len(rows) == 1

    def test_modes_view_columns(self, projection_db):
        create_projection_views(projection_db)
        row = projection_db.execute(
            "SELECT name, writable FROM modes WHERE name = 'implement'"
        ).fetchone()
        assert row is not None
        assert row[1] == "src/"

    def test_creates_resolved_entities_view(self, projection_db):
        create_projection_views(projection_db)
        rows = projection_db.execute("SELECT * FROM resolved_entities").fetchall()
        assert len(rows) >= 2

    def test_no_property_types_still_works(self):
        dialect = SQLiteDialect()
        con = sqlite3.connect(":memory:")
        con.executescript(create_schema(dialect))
        create_resolution_views(con, dialect)
        create_projection_views(con)


class TestCompilationMeta:
    def test_creates_meta_table(self, projection_db):
        create_compilation_meta(projection_db, source_world="test.world.yml", source_stylesheet="policy.umw")
        row = projection_db.execute(
            "SELECT value FROM compilation_meta WHERE key = 'source_world'"
        ).fetchone()
        assert row[0] == "test.world.yml"

    def test_meta_has_entity_count(self, projection_db):
        create_compilation_meta(projection_db)
        row = projection_db.execute(
            "SELECT value FROM compilation_meta WHERE key = 'entity_count'"
        ).fetchone()
        assert int(row[0]) == 3

    def test_meta_has_compiled_at(self, projection_db):
        create_compilation_meta(projection_db)
        row = projection_db.execute(
            "SELECT value FROM compilation_meta WHERE key = 'compiled_at'"
        ).fetchone()
        assert row[0]  # non-empty ISO timestamp
