# tests/policy/conftest.py
from __future__ import annotations

import json
import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.resolution import create_resolution_views
from umwelt.compilers.sql.schema import create_schema


@pytest.fixture
def dialect():
    return SQLiteDialect()


@pytest.fixture
def policy_db(dialect):
    """In-memory SQLite with schema, entities, cascade_candidates, and resolution views.

    Entities:
      - tool#Read (id=1)
      - tool#Edit (id=2, classes=["edit"])
      - tool#Bash (id=3, classes=["dangerous", "shell"])
      - mode#implement (id=4)
      - mode#review (id=5)

    Cascade candidates (rules):
      Rule 0: tool { allow: true; max-level: 5; }         specificity (0,0,0,1,0,0,0,0)
      Rule 1: tool.dangerous { max-level: 3; }             specificity (0,0,0,1,0,1,0,0)
      Rule 2: tool#Bash { risk-note: "Prefer structured"; } specificity (0,0,1,1,0,0,0,0)
      Rule 3: mode { allow: true; }                        specificity (0,0,0,1,0,0,0,0)
      Rule 4: tool.dangerous { allow: false; }             specificity (0,0,0,1,0,1,0,0) [same spec as rule 1, higher index]
    """
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))

    entities = [
        (1, "capability", "tool", "Read", None, json.dumps({"name": "Read"}), None, 0),
        (2, "capability", "tool", "Edit", json.dumps(["edit"]), json.dumps({"name": "Edit"}), None, 0),
        (3, "capability", "tool", "Bash", json.dumps(["dangerous", "shell"]), json.dumps({"name": "Bash"}), None, 0),
        (4, "state", "mode", "implement", None, json.dumps({"name": "implement"}), None, 0),
        (5, "state", "mode", "review", None, json.dumps({"name": "review"}), None, 0),
    ]
    con.executemany(
        "INSERT INTO entities (id, taxon, type_name, entity_id, classes, attributes, parent_id, depth) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        entities,
    )

    # Self-closure entries
    con.executescript("""
        DELETE FROM entity_closure;
        INSERT INTO entity_closure (ancestor_id, descendant_id, depth)
        SELECT id, id, 0 FROM entities;
    """)

    spec_tool = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
    spec_tool_class = '["00000","00000","00000","00001","00000","00001","00000","00000"]'
    spec_tool_id = '["00000","00000","00001","00001","00000","00000","00000","00000"]'
    spec_mode = '["00000","00000","00000","00001","00000","00000","00000","00000"]'

    candidates = [
        # Rule 0: tool { allow: true; max-level: 5; }
        (1, "allow", "true", "exact", spec_tool, 0, "policy.umw", 1),
        (2, "allow", "true", "exact", spec_tool, 0, "policy.umw", 1),
        (3, "allow", "true", "exact", spec_tool, 0, "policy.umw", 1),
        (1, "max-level", "5", "<=", spec_tool, 0, "policy.umw", 1),
        (2, "max-level", "5", "<=", spec_tool, 0, "policy.umw", 1),
        (3, "max-level", "5", "<=", spec_tool, 0, "policy.umw", 1),
        # Rule 1: tool.dangerous { max-level: 3; }
        (3, "max-level", "3", "<=", spec_tool_class, 1, "policy.umw", 3),
        # Rule 2: tool#Bash { risk-note: "Prefer structured"; }
        (3, "risk-note", "Prefer structured", "exact", spec_tool_id, 2, "policy.umw", 5),
        # Rule 3: mode { allow: true; }
        (4, "allow", "true", "exact", spec_mode, 3, "policy.umw", 7),
        (5, "allow", "true", "exact", spec_mode, 3, "policy.umw", 7),
        # Rule 4: tool.dangerous { allow: false; } — same specificity as rule 0 for Bash, higher index
        (3, "allow", "false", "exact", spec_tool_class, 4, "policy.umw", 9),
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
