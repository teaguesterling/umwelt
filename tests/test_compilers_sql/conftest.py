"""Shared fixtures for SQL compiler tests."""
from __future__ import annotations

import json
import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.schema import create_schema


@pytest.fixture
def dialect():
    return SQLiteDialect()


@pytest.fixture
def db(dialect):
    """In-memory SQLite with the policy schema."""
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))
    yield con
    con.close()


@pytest.fixture
def populated_db(db):
    """DB with a representative set of entities across all taxa."""
    entities = [
        # world: files
        (1,  "world", "file", "src/auth.py",       None, json.dumps({"path": "src/auth.py", "name": "auth.py", "language": "python"}), None, 0),
        (2,  "world", "file", "src/util.py",        None, json.dumps({"path": "src/util.py", "name": "util.py", "language": "python"}), None, 0),
        (3,  "world", "file", "tests/test_auth.py", None, json.dumps({"path": "tests/test_auth.py", "name": "test_auth.py", "language": "python"}), None, 0),
        (4,  "world", "file", "README.md",          None, json.dumps({"path": "README.md", "name": "README.md", "language": "markdown"}), None, 0),
        (5,  "world", "file", "src/main.pyc",       None, json.dumps({"path": "src/main.pyc", "name": "main.pyc"}), None, 0),
        # world: dirs
        (10, "world", "dir",  "src",                None, json.dumps({"path": "src", "name": "src"}), None, 0),
        (11, "world", "dir",  "tests",              None, json.dumps({"path": "tests", "name": "tests"}), None, 0),
        # world: resources
        (20, "world", "resource", "memory",         None, json.dumps({"kind": "memory"}), None, 0),
        (21, "world", "resource", "wall-time",      None, json.dumps({"kind": "wall-time"}), None, 0),
        # world: network
        (25, "world", "network", None,               None, json.dumps({}), None, 0),
        # world: exec
        (30, "world", "exec", "bash",               None, json.dumps({"name": "bash", "path": "/bin/bash"}), None, 0),
        # capability: tools
        (40, "capability", "tool", "Read",           None, json.dumps({"name": "Read", "altitude": "os", "level": "2"}), None, 0),
        (41, "capability", "tool", "Edit",           None, json.dumps({"name": "Edit", "altitude": "os", "level": "3"}), None, 0),
        (42, "capability", "tool", "Bash",           None, json.dumps({"name": "Bash", "altitude": "os", "level": "5"}), None, 0),
        (43, "capability", "tool", "Grep",           None, json.dumps({"name": "Grep", "altitude": "os", "level": "1"}), None, 0),
        (44, "capability", "tool", "Agent",          None, json.dumps({"name": "Agent", "altitude": "semantic", "level": "7"}), None, 0),
        (45, "capability", "tool", "Glob",           None, json.dumps({"name": "Glob", "altitude": "os", "level": "1"}), None, 0),
        (46, "capability", "tool", "Write",          None, json.dumps({"name": "Write", "altitude": "os", "level": "3"}), None, 0),
        # state: modes (entity_id = mode name; classes retained for class-selector tests)
        (50, "state", "mode", "implement",     json.dumps(["implement"]),          json.dumps({"writable": "src/, lib/", "strategy": ""}), None, 0),
        (51, "state", "mode", "test",          json.dumps(["test"]),               json.dumps({"writable": "tests/", "strategy": "Write tests for expected behavior, not current behavior."}), None, 0),
        (52, "state", "mode", "explore",       json.dumps(["explore"]),            json.dumps({"writable": "", "strategy": "Map the territory before making changes."}), None, 0),
        (53, "state", "mode", "implement-tdd", json.dumps(["implement", "tdd"]),   json.dumps({"writable": "src/, tests/", "strategy": ""}), None, 0),
        (54, "state", "mode", "review",        json.dumps(["review"]),             json.dumps({"writable": "", "strategy": "Read everything, then verify with tests."}), None, 0),
        # principal
        (60, "principal", "principal", "Teague", None, json.dumps({"name": "Teague"}), None, 0),
        # audit
        (70, "audit", "observation", "coach",   None, json.dumps({"name": "coach"}), None, 0),
    ]
    db.executemany(
        "INSERT INTO entities (id, taxon, type_name, entity_id, classes, attributes, parent_id, depth) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        entities,
    )
    # Hierarchy: src/ contains files 1, 2, 5; tests/ contains file 3
    db.execute("UPDATE entities SET parent_id = 10 WHERE id IN (1, 2, 5)")
    db.execute("UPDATE entities SET parent_id = 11 WHERE id = 3")
    # Rebuild closure table
    db.executescript("""
        DELETE FROM entity_closure;
        INSERT INTO entity_closure
        WITH RECURSIVE closure(ancestor_id, descendant_id, depth) AS (
            SELECT id, id, 0 FROM entities
            UNION ALL
            SELECT c.ancestor_id, e.id, c.depth + 1
            FROM closure c
            JOIN entities e ON e.parent_id = c.descendant_id
        )
        SELECT DISTINCT * FROM closure;
    """)
    db.commit()
    return db


def parse_selector(css_text: str):
    """Parse a CSS selector string via umwelt's parser."""
    import contextlib

    from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
    with contextlib.suppress(Exception):
        register_sandbox_vocabulary()
    from umwelt.parser import parse
    view = parse(css_text + " { _test: true; }", validate=False)
    assert view.rules, f"no rules parsed from: {css_text}"
    return view.rules[0].selectors[0]


def parse_view(css_text: str):
    """Parse a full .umw view string."""
    import contextlib

    from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
    with contextlib.suppress(Exception):
        register_sandbox_vocabulary()
    from umwelt.parser import parse
    return parse(css_text, validate=False)


def query_ids(con, sql: str) -> set[int]:
    """Execute a compiled selector SQL and return matched entity IDs."""
    result = con.execute(f"SELECT e.id FROM entities e WHERE {sql}").fetchall()
    return {row[0] for row in result}
