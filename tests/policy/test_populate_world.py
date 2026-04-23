import json
import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.populate import populate_from_world
from umwelt.compilers.sql.schema import create_schema
from umwelt.world.model import DeclaredEntity, Projection, WorldFile


@pytest.fixture
def empty_db():
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))
    yield con
    con.close()


class TestPopulateFromWorld:
    def test_basic_entity_insertion(self, empty_db):
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Read"),),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        row = empty_db.execute(
            "SELECT type_name, entity_id FROM entities WHERE entity_id = 'Read'"
        ).fetchone()
        assert row == ("tool", "Read")

    def test_classes_stored_as_json(self, empty_db):
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Bash", classes=("dangerous", "shell")),),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        row = empty_db.execute(
            "SELECT classes FROM entities WHERE entity_id = 'Bash'"
        ).fetchone()
        assert json.loads(row[0]) == ["dangerous", "shell"]

    def test_attributes_stored_as_json(self, empty_db):
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Read", attributes={"description": "read files"}),),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        row = empty_db.execute(
            "SELECT attributes FROM entities WHERE entity_id = 'Read'"
        ).fetchone()
        assert json.loads(row[0])["description"] == "read files"

    def test_multiple_entities(self, empty_db):
        wf = WorldFile(
            entities=(
                DeclaredEntity(type="tool", id="Read"),
                DeclaredEntity(type="tool", id="Edit"),
                DeclaredEntity(type="mode", id="implement"),
            ),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        count = empty_db.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        assert count == 3

    def test_projection_inserted_as_entity(self, empty_db):
        wf = WorldFile(
            entities=(),
            projections=(Projection(type="dir", id="node_modules", attributes={"path": "node_modules/"}),),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        row = empty_db.execute(
            "SELECT type_name, entity_id FROM entities WHERE entity_id = 'node_modules'"
        ).fetchone()
        assert row == ("dir", "node_modules")

    def test_world_entity_wins_on_collision(self, empty_db):
        # Pre-insert a matcher-discovered entity
        empty_db.execute(
            "INSERT INTO entities (taxon, type_name, entity_id, classes, attributes, depth) "
            "VALUES ('capability', 'tool', 'Bash', NULL, NULL, 0)"
        )
        empty_db.commit()

        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Bash", classes=("dangerous",)),),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)

        rows = empty_db.execute(
            "SELECT classes FROM entities WHERE entity_id = 'Bash'"
        ).fetchall()
        assert len(rows) == 1
        assert json.loads(rows[0][0]) == ["dangerous"]

    def test_closure_table_rebuilt(self, empty_db):
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Read"),),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        closure = empty_db.execute(
            "SELECT COUNT(*) FROM entity_closure"
        ).fetchone()[0]
        assert closure >= 1  # at least self-closure
