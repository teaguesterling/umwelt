"""Tests for entity population from the matcher registry."""
from __future__ import annotations

import json
import sqlite3
import pytest
from pathlib import Path
from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.schema import create_schema
from umwelt.compilers.sql.populate import populate_entities, entity_to_row


class TestEntityToRow:
    def test_file_entity(self):
        from umwelt.sandbox.entities import FileEntity
        entity = FileEntity(path="src/auth.py", abs_path=Path("/tmp/src/auth.py"), name="auth.py", language="python")
        row = entity_to_row("world", "file", entity)
        assert row["taxon"] == "world"
        assert row["type_name"] == "file"
        assert row["entity_id"] == "src/auth.py"
        attrs = json.loads(row["attributes"])
        assert attrs["path"] == "src/auth.py"
        assert attrs["language"] == "python"

    def test_tool_entity(self):
        from umwelt.sandbox.entities import ToolEntity
        entity = ToolEntity(name="Bash", altitude="os", level=5)
        row = entity_to_row("capability", "tool", entity)
        assert row["entity_id"] == "Bash"
        attrs = json.loads(row["attributes"])
        assert attrs["name"] == "Bash"
        assert attrs["altitude"] == "os"

    def test_mode_entity(self):
        from umwelt.sandbox.entities import ModeEntity
        entity = ModeEntity(name="implement", classes=("implement", "tdd"))
        row = entity_to_row("state", "mode", entity)
        classes = json.loads(row["classes"])
        assert classes == ["implement", "tdd"]

    def test_network_entity(self):
        from umwelt.sandbox.entities import NetworkEntity
        entity = NetworkEntity()
        row = entity_to_row("world", "network", entity)
        assert row["entity_id"] is None


class TestPopulateEntities:
    def test_populates_from_matchers(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("# app")
        (tmp_path / "README.md").write_text("# readme")

        dialect = SQLiteDialect()
        con = sqlite3.connect(":memory:")
        con.executescript(create_schema(dialect))

        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        from umwelt.registry.taxa import _ACTIVE_STATE, RegistryState

        # Use a fresh registry to avoid conflicts with other tests
        token = _ACTIVE_STATE.set(RegistryState())
        try:
            register_sandbox_vocabulary()

            # Register matchers
            from umwelt.registry.matchers import register_matcher
            from umwelt.sandbox.world_matcher import WorldMatcher
            register_matcher(taxon="world", matcher=WorldMatcher(base_dir=tmp_path))

            populate_entities(con, tmp_path)

            count = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            assert count > 0

            # Check a file was populated
            row = con.execute(
                "SELECT json_extract(attributes, '$.path') FROM entities WHERE type_name = 'file' AND entity_id LIKE '%app.py'"
            ).fetchone()
            assert row is not None

            # Check closure table was built
            closure_count = con.execute("SELECT COUNT(*) FROM entity_closure").fetchone()[0]
            assert closure_count > 0
        finally:
            _ACTIVE_STATE.reset(token)

        con.close()
