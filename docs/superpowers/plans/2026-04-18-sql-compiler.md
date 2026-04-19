# SQL Policy Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `umwelt.compilers.sql` — a SQLite-backed policy compiler that translates `.umw` views into SQL, replacing the separate `ducklog` package.

**Architecture:** The SQL compiler walks umwelt's AST (`ComplexSelector` → `SimpleSelector`) and emits SQL WHERE clauses via PyPika Criterion objects. Entities are populated from the existing Matcher registry. Cascade resolution happens via SQLite views (window functions, aggregation). A dialect abstraction layer enables SQLite (default) and DuckDB output.

**Tech Stack:** Python 3.10+, PyPika (optional dep), sqlite3 (stdlib), umwelt AST/registry/parser

**Spec:** `docs/superpowers/specs/2026-04-18-sql-compiler-design.md`

---

## File Structure

```
src/umwelt/compilers/sql/
    __init__.py       # Public API: compile_to_sql(), compile_to_db()
    dialects.py       # Dialect ABC + SQLiteDialect + DuckDBDialect
    schema.py         # DDL generation per dialect
    compiler.py       # AST → SQL WHERE clauses via dialect helpers
    resolution.py     # Cascade resolution view DDL per dialect
    populate.py       # Matcher registry → entity INSERTs

tests/test_compilers_sql/
    __init__.py
    conftest.py       # SQLite in-memory fixtures, entity population helpers
    test_schema.py    # DDL executes, tables exist
    test_compiler.py  # Selector → SQL → entity matching (8 levels)
    test_resolution.py # Cascade resolution: exact, cap, pattern, specificity
    test_roundtrip.py  # Full .umw → SQLite → resolved properties
```

Modified files:
- `pyproject.toml` — add `[sql]`, `[duckdb]`, `[sqldb]` optional deps
- `src/umwelt/cli.py` — replace `_cmd_compile_duckdb` with new SQL compile path

---

### Task 1: Add PyPika Optional Dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add optional dependency groups to pyproject.toml**

In `pyproject.toml`, add the `sql`, `duckdb`, and `sqldb` optional dependency groups after the existing `dev` group:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8",
  "ruff>=0.5",
  "mypy>=1.10",
]
sql = [
  "pypika>=0.48",
]
duckdb = [
  "umwelt[sql]",
  "duckdb>=1.0",
]
sqldb = [
  "umwelt[sql]",
  "sqlalchemy>=2.0",
]
```

- [ ] **Step 2: Install the sql extras locally**

Run: `pip install -e ".[sql,dev]"`
Expected: PyPika installs successfully

- [ ] **Step 3: Verify PyPika imports**

Run: `python -c "from pypika import Query, Table, Field, Criterion; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Add mypy override for pypika**

In `pyproject.toml`, add a mypy override section for pypika (it has no type stubs):

```toml
[[tool.mypy.overrides]]
module = ["pypika", "pypika.*"]
ignore_missing_imports = true
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add sql/duckdb/sqldb optional dependency groups"
```

---

### Task 2: Dialect Abstraction Layer

**Files:**
- Create: `src/umwelt/compilers/sql/__init__.py`
- Create: `src/umwelt/compilers/sql/dialects.py`
- Test: `tests/test_compilers_sql/__init__.py`
- Test: `tests/test_compilers_sql/test_dialects.py`

- [ ] **Step 1: Create package init files**

Create `src/umwelt/compilers/sql/__init__.py`:

```python
"""SQL policy compiler — translates .umw views to SQL databases."""
```

Create `tests/test_compilers_sql/__init__.py` (empty file).

- [ ] **Step 2: Write failing tests for dialect expressions**

Create `tests/test_compilers_sql/test_dialects.py`:

```python
"""Tests for SQL dialect abstraction layer."""
from __future__ import annotations

import pytest
from umwelt.compilers.sql.dialects import SQLiteDialect, DuckDBDialect


class TestSQLiteDialect:
    def setup_method(self):
        self.d = SQLiteDialect()

    def test_json_attr(self):
        result = self.d.json_attr("e", "path")
        assert result == "json_extract(e.attributes, '$.path')"

    def test_list_contains(self):
        result = self.d.list_contains("e", "classes", "implement")
        assert "json_each" in result
        assert "implement" in result

    def test_format_specificity(self):
        spec = (2, 0, 10100, 0, 0, 100, 0, 0)
        result = self.d.format_specificity(spec)
        assert result == '["00002","00000","10100","00000","00000","00100","00000","00000"]'

    def test_specificity_ordering(self):
        """Higher specificity sorts after lower when compared as strings."""
        high = self.d.format_specificity((2, 0, 10100, 0, 0, 100, 0, 0))
        low = self.d.format_specificity((1, 0, 0, 0, 0, 100, 0, 0))
        assert high > low

    def test_array_literal(self):
        result = self.d.array_literal(["implement", "tdd"])
        assert result == '["implement","tdd"]'

    def test_map_literal(self):
        result = self.d.map_literal({"path": "src/auth.py", "language": "python"})
        assert '"path":"src/auth.py"' in result
        assert '"language":"python"' in result


class TestDuckDBDialect:
    def setup_method(self):
        self.d = DuckDBDialect()

    def test_json_attr(self):
        result = self.d.json_attr("e", "path")
        assert result == "e.attributes['path']"

    def test_list_contains(self):
        result = self.d.list_contains("e", "classes", "implement")
        assert result == "list_contains(e.classes, 'implement')"

    def test_format_specificity(self):
        spec = (2, 0, 10100, 0, 0, 100, 0, 0)
        result = self.d.format_specificity(spec)
        assert result == "[2,0,10100,0,0,100,0,0]::INTEGER[]"

    def test_array_literal(self):
        result = self.d.array_literal(["implement", "tdd"])
        assert result == "['implement','tdd']"

    def test_map_literal(self):
        result = self.d.map_literal({"path": "src/auth.py"})
        assert result == "MAP{'path':'src/auth.py'}"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_compilers_sql/test_dialects.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'umwelt.compilers.sql.dialects'`

- [ ] **Step 4: Implement dialect classes**

Create `src/umwelt/compilers/sql/dialects.py`:

```python
"""SQL dialect abstraction for the policy compiler.

Each dialect provides expression helpers that abstract database-specific
syntax: JSON access, array operations, specificity encoding, and literal
formatting. The compiler builds SQL using these helpers rather than
hardcoding any dialect's syntax.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod


class Dialect(ABC):
    """Base class for SQL dialect-specific expression helpers."""

    name: str

    @abstractmethod
    def json_attr(self, alias: str, key: str) -> str:
        """Access a key from a JSON/MAP attributes column."""
        ...

    @abstractmethod
    def list_contains(self, alias: str, column: str, value: str) -> str:
        """Check if a JSON array / list column contains a value."""
        ...

    @abstractmethod
    def format_specificity(self, spec: tuple[int, ...]) -> str:
        """Format a specificity tuple as a storable/sortable literal."""
        ...

    @abstractmethod
    def array_literal(self, values: list[str]) -> str:
        """Format a list of strings as an array literal."""
        ...

    @abstractmethod
    def map_literal(self, mapping: dict[str, str]) -> str:
        """Format a dict as a MAP/JSON literal."""
        ...

    @abstractmethod
    def distinct_first(
        self, columns: str, partition_by: str, order_by: str
    ) -> tuple[str, str]:
        """Return (select_wrapper, where_filter) for picking the first row per partition.

        For DuckDB: DISTINCT ON. For SQLite: ROW_NUMBER window function.
        Returns a tuple of (extra_column_expr, filter_clause).
        """
        ...


class SQLiteDialect(Dialect):
    name = "sqlite"

    def json_attr(self, alias: str, key: str) -> str:
        safe_key = key.replace("'", "''")
        return f"json_extract({alias}.attributes, '$.{safe_key}')"

    def list_contains(self, alias: str, column: str, value: str) -> str:
        safe_val = value.replace("'", "''")
        return (
            f"EXISTS(SELECT 1 FROM json_each({alias}.{column}) "
            f"WHERE value = '{safe_val}')"
        )

    def format_specificity(self, spec: tuple[int, ...]) -> str:
        padded = [f"{v:05d}" for v in spec]
        return json.dumps(padded)

    def array_literal(self, values: list[str]) -> str:
        return json.dumps(values)

    def map_literal(self, mapping: dict[str, str]) -> str:
        return json.dumps(mapping, separators=(",", ":"))

    def distinct_first(
        self, columns: str, partition_by: str, order_by: str
    ) -> tuple[str, str]:
        return (
            f"ROW_NUMBER() OVER (PARTITION BY {partition_by} ORDER BY {order_by}) AS _rn",
            "_rn = 1",
        )


class DuckDBDialect(Dialect):
    name = "duckdb"

    def json_attr(self, alias: str, key: str) -> str:
        safe_key = key.replace("'", "''")
        return f"{alias}.attributes['{safe_key}']"

    def list_contains(self, alias: str, column: str, value: str) -> str:
        safe_val = value.replace("'", "''")
        return f"list_contains({alias}.{column}, '{safe_val}')"

    def format_specificity(self, spec: tuple[int, ...]) -> str:
        return f"[{','.join(str(s) for s in spec)}]::INTEGER[]"

    def array_literal(self, values: list[str]) -> str:
        inner = ",".join(f"'{v}'" for v in values)
        return f"[{inner}]"

    def map_literal(self, mapping: dict[str, str]) -> str:
        pairs = ",".join(f"'{k}':'{v}'" for k, v in mapping.items())
        return f"MAP{{{pairs}}}"

    def distinct_first(
        self, columns: str, partition_by: str, order_by: str
    ) -> tuple[str, str]:
        return ("", "")  # DuckDB uses DISTINCT ON directly


_DIALECTS: dict[str, type[Dialect]] = {
    "sqlite": SQLiteDialect,
    "duckdb": DuckDBDialect,
}


def get_dialect(name: str) -> Dialect:
    """Look up a dialect by name."""
    cls = _DIALECTS.get(name)
    if cls is None:
        available = ", ".join(sorted(_DIALECTS))
        raise ValueError(f"unknown SQL dialect {name!r}; available: {available}")
    return cls()


def register_dialect(name: str, cls: type[Dialect]) -> None:
    """Register a custom dialect."""
    _DIALECTS[name] = cls
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_compilers_sql/test_dialects.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/compilers/sql/__init__.py src/umwelt/compilers/sql/dialects.py \
       tests/test_compilers_sql/__init__.py tests/test_compilers_sql/test_dialects.py
git commit -m "feat(sql): dialect abstraction layer — SQLite + DuckDB"
```

---

### Task 3: Schema DDL Generation

**Files:**
- Create: `src/umwelt/compilers/sql/schema.py`
- Test: `tests/test_compilers_sql/test_schema.py`

- [ ] **Step 1: Write failing tests for schema creation**

Create `tests/test_compilers_sql/test_schema.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compilers_sql/test_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'umwelt.compilers.sql.schema'`

- [ ] **Step 3: Implement schema generation**

Create `src/umwelt/compilers/sql/schema.py`:

```python
"""DDL generation for the policy database schema.

Generates CREATE TABLE/INDEX statements for the policy database.
The schema structure is dialect-agnostic; only column type names
and literal syntax differ between dialects.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from umwelt.compilers.sql.dialects import Dialect

EXPECTED_TABLES = [
    "taxa",
    "entity_types",
    "property_types",
    "entities",
    "entity_closure",
    "cascade_candidates",
]


def create_schema(dialect: Dialect) -> str:
    """Generate the full DDL for the policy database."""
    is_sqlite = dialect.name == "sqlite"
    text_type = "TEXT" if is_sqlite else "VARCHAR"
    int_type = "INTEGER"
    autoincrement = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "INTEGER PRIMARY KEY DEFAULT nextval('entity_seq')"

    sections = []

    # -- Vocabulary tables
    sections.append(f"""
CREATE TABLE IF NOT EXISTS taxa (
    name            {text_type} PRIMARY KEY,
    canonical       {text_type},
    vsm_system      {text_type},
    description     {text_type}
);

CREATE TABLE IF NOT EXISTS entity_types (
    name            {text_type} NOT NULL,
    taxon           {text_type} NOT NULL REFERENCES taxa(name),
    parent_type     {text_type},
    category        {text_type},
    description     {text_type},
    PRIMARY KEY (taxon, name)
);

CREATE TABLE IF NOT EXISTS property_types (
    name            {text_type} NOT NULL,
    taxon           {text_type} NOT NULL,
    entity_type     {text_type} NOT NULL,
    value_type      {text_type} NOT NULL,
    comparison      {text_type} DEFAULT 'exact',
    description     {text_type},
    PRIMARY KEY (taxon, entity_type, name),
    FOREIGN KEY (taxon, entity_type) REFERENCES entity_types(taxon, name)
);""")

    # -- Entity tables
    sections.append(f"""
CREATE TABLE IF NOT EXISTS entities (
    id              {autoincrement},
    taxon           {text_type} NOT NULL,
    type_name       {text_type} NOT NULL,
    entity_id       {text_type},
    classes         {text_type},
    attributes      {text_type},
    parent_id       {int_type} REFERENCES entities(id),
    depth           {int_type} DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_entities_taxon ON entities(taxon);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type_name);
CREATE INDEX IF NOT EXISTS idx_entities_id ON entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_entities_parent ON entities(parent_id);""")

    # -- Closure table
    sections.append(f"""
CREATE TABLE IF NOT EXISTS entity_closure (
    ancestor_id     {int_type} NOT NULL REFERENCES entities(id),
    descendant_id   {int_type} NOT NULL REFERENCES entities(id),
    depth           {int_type} NOT NULL,
    PRIMARY KEY (ancestor_id, descendant_id)
);

CREATE INDEX IF NOT EXISTS idx_closure_ancestor ON entity_closure(ancestor_id);
CREATE INDEX IF NOT EXISTS idx_closure_descendant ON entity_closure(descendant_id);""")

    # -- Cascade candidates (materialized, not a view)
    sections.append(f"""
CREATE TABLE IF NOT EXISTS cascade_candidates (
    entity_id       {int_type} NOT NULL REFERENCES entities(id),
    property_name   {text_type} NOT NULL,
    property_value  {text_type} NOT NULL,
    comparison      {text_type} NOT NULL DEFAULT 'exact',
    specificity     {text_type} NOT NULL,
    rule_index      {int_type} NOT NULL,
    source_file     {text_type},
    source_line     {int_type}
);

CREATE INDEX IF NOT EXISTS idx_candidates_entity_prop ON cascade_candidates(entity_id, property_name);
CREATE INDEX IF NOT EXISTS idx_candidates_comparison ON cascade_candidates(comparison);""")

    return "\n".join(sections)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compilers_sql/test_schema.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/compilers/sql/schema.py tests/test_compilers_sql/test_schema.py
git commit -m "feat(sql): schema DDL generation for policy database"
```

---

### Task 4: Selector-to-SQL Compiler (Levels 1–4)

**Files:**
- Create: `src/umwelt/compilers/sql/compiler.py`
- Create: `tests/test_compilers_sql/conftest.py`
- Test: `tests/test_compilers_sql/test_compiler.py`

The compiler is built in two tasks. This task covers type, ID, attribute, and class selectors (atoms). Task 5 adds compound selectors (molecules).

- [ ] **Step 1: Create test fixtures**

Create `tests/test_compilers_sql/conftest.py`:

```python
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
        # state: modes
        (50, "state", "mode", None, json.dumps(["implement"]),      json.dumps({"writable": "src/, lib/", "strategy": ""}), None, 0),
        (51, "state", "mode", None, json.dumps(["test"]),           json.dumps({"writable": "tests/", "strategy": "Write tests for expected behavior, not current behavior."}), None, 0),
        (52, "state", "mode", None, json.dumps(["explore"]),        json.dumps({"writable": "", "strategy": "Map the territory before making changes."}), None, 0),
        (53, "state", "mode", None, json.dumps(["implement", "tdd"]), json.dumps({"writable": "src/, tests/", "strategy": ""}), None, 0),
        (54, "state", "mode", None, json.dumps(["review"]),         json.dumps({"writable": "", "strategy": "Read everything, then verify with tests."}), None, 0),
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
    from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
    try:
        register_sandbox_vocabulary()
    except Exception:
        pass
    from umwelt.parser import parse
    view = parse(css_text + " { _test: true; }", validate=False)
    assert view.rules, f"no rules parsed from: {css_text}"
    return view.rules[0].selectors[0]


def parse_view(css_text: str):
    """Parse a full .umw view string."""
    from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
    try:
        register_sandbox_vocabulary()
    except Exception:
        pass
    from umwelt.parser import parse
    return parse(css_text, validate=False)


def query_ids(con, sql: str) -> set[int]:
    """Execute a compiled selector SQL and return matched entity IDs."""
    result = con.execute(f"SELECT e.id FROM entities e WHERE {sql}").fetchall()
    return {row[0] for row in result}
```

- [ ] **Step 2: Write failing tests for levels 1–4**

Create `tests/test_compilers_sql/test_compiler.py`:

```python
"""Selector-to-SQL compiler tests.

Organized from atoms to molecules:
  Level 1: Type selectors (file, tool, mode)
  Level 2: ID selectors (file#README.md, tool#Bash)
  Level 3: Attribute selectors ([path="..."], [path^="..."])
  Level 4: Class selectors (mode.implement, mode.implement.tdd)
  Levels 5-8: see below (compound, structural, pseudo)
"""
from __future__ import annotations

from tests.test_compilers_sql.conftest import parse_selector, query_ids
from umwelt.compilers.sql.compiler import compile_selector
from umwelt.compilers.sql.dialects import SQLiteDialect


DIALECT = SQLiteDialect()


# ============================================================================
# Level 1: Bare type selectors
# ============================================================================

class TestTypeSelectors:
    def test_bare_file_matches_all_files(self, populated_db):
        sql = compile_selector(parse_selector("file"), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2, 3, 4, 5}

    def test_bare_tool_matches_all_tools(self, populated_db):
        sql = compile_selector(parse_selector("tool"), DIALECT)
        assert query_ids(populated_db, sql) == {40, 41, 42, 43, 44, 45, 46}

    def test_bare_mode_matches_all_modes(self, populated_db):
        sql = compile_selector(parse_selector("mode"), DIALECT)
        assert query_ids(populated_db, sql) == {50, 51, 52, 53, 54}

    def test_bare_resource_matches_all_resources(self, populated_db):
        sql = compile_selector(parse_selector("resource"), DIALECT)
        assert query_ids(populated_db, sql) == {20, 21}

    def test_type_selector_excludes_other_types(self, populated_db):
        sql = compile_selector(parse_selector("tool"), DIALECT)
        ids = query_ids(populated_db, sql)
        assert all(40 <= i <= 46 for i in ids)


# ============================================================================
# Level 2: ID selectors
# ============================================================================

class TestIDSelectors:
    def test_file_with_id(self, populated_db):
        sql = compile_selector(parse_selector("file#README.md"), DIALECT)
        assert query_ids(populated_db, sql) == {4}

    def test_tool_with_id(self, populated_db):
        sql = compile_selector(parse_selector("tool#Bash"), DIALECT)
        assert query_ids(populated_db, sql) == {42}

    def test_principal_with_id(self, populated_db):
        sql = compile_selector(parse_selector("principal#Teague"), DIALECT)
        assert query_ids(populated_db, sql) == {60}

    def test_nonexistent_id_matches_nothing(self, populated_db):
        sql = compile_selector(parse_selector("tool#NonExistent"), DIALECT)
        assert query_ids(populated_db, sql) == set()


# ============================================================================
# Level 3: Attribute selectors
# ============================================================================

class TestAttributeSelectors:
    def test_exact_match(self, populated_db):
        sql = compile_selector(parse_selector('file[path="src/auth.py"]'), DIALECT)
        assert query_ids(populated_db, sql) == {1}

    def test_prefix_match(self, populated_db):
        sql = compile_selector(parse_selector('file[path^="src/"]'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2, 5}

    def test_suffix_match(self, populated_db):
        sql = compile_selector(parse_selector('file[path$=".py"]'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2, 3}

    def test_contains_match(self, populated_db):
        sql = compile_selector(parse_selector('file[path*="auth"]'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 3}

    def test_multiple_attributes_conjoin(self, populated_db):
        sql = compile_selector(parse_selector('file[path^="src/"][language="python"]'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2}

    def test_attribute_on_tool(self, populated_db):
        sql = compile_selector(parse_selector('tool[altitude="os"]'), DIALECT)
        assert query_ids(populated_db, sql) == {40, 41, 42, 43, 45, 46}

    def test_resource_kind_attribute(self, populated_db):
        sql = compile_selector(parse_selector('resource[kind="memory"]'), DIALECT)
        assert query_ids(populated_db, sql) == {20}


# ============================================================================
# Level 4: Class selectors
# ============================================================================

class TestClassSelectors:
    def test_single_class(self, populated_db):
        sql = compile_selector(parse_selector("mode.implement"), DIALECT)
        assert query_ids(populated_db, sql) == {50, 53}

    def test_class_excludes_non_matching(self, populated_db):
        sql = compile_selector(parse_selector("mode.explore"), DIALECT)
        assert query_ids(populated_db, sql) == {52}

    def test_multiple_classes_must_all_match(self, populated_db):
        sql = compile_selector(parse_selector("mode.implement.tdd"), DIALECT)
        assert query_ids(populated_db, sql) == {53}

    def test_class_not_present_matches_nothing(self, populated_db):
        sql = compile_selector(parse_selector("mode.deploy"), DIALECT)
        assert query_ids(populated_db, sql) == set()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_compilers_sql/test_compiler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'umwelt.compilers.sql.compiler'`

- [ ] **Step 4: Implement the compiler (levels 1–4)**

Create `src/umwelt/compilers/sql/compiler.py`:

```python
"""Compile umwelt CSS selectors to SQL WHERE clauses.

Walks umwelt's AST (ComplexSelector, SimpleSelector, CompoundPart) and
emits SQL fragments using dialect-specific helpers. The returned strings
are valid SQL expressions for use as: SELECT e.id FROM entities e WHERE <expr>

Entry points:
  compile_selector(selector, dialect) → SQL WHERE clause string
  compile_view(con, view, dialect, source_file) → populates cascade_candidates
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from umwelt.ast import ComplexSelector, SimpleSelector
    from umwelt.compilers.sql.dialects import Dialect


def compile_selector(selector: ComplexSelector, dialect: Dialect) -> str:
    """Compile a ComplexSelector to a SQL WHERE clause."""
    parts = selector.parts
    if not parts:
        return "FALSE"

    target = parts[-1]
    qualifiers = parts[:-1]

    target_sql = _compile_simple(target.selector, "e", dialect)

    qualifier_clauses = []
    for i, qual in enumerate(qualifiers):
        q_alias = f"q{i}"
        is_structural = (
            qual.selector.taxon == target.selector.taxon
            and qual.mode != "context"
        )
        if is_structural:
            qualifier_clauses.append(_compile_structural_ancestor(qual.selector, q_alias, dialect))
        else:
            qualifier_clauses.append(_compile_context_qualifier(qual.selector, q_alias, dialect))

    all_clauses = [target_sql] + qualifier_clauses
    return " AND ".join(all_clauses)


def _compile_simple(simple: SimpleSelector, alias: str, dialect: Dialect) -> str:
    """Compile a SimpleSelector to SQL WHERE fragments."""
    clauses: list[str] = []

    if simple.type_name and simple.type_name != "*":
        clauses.append(f"{alias}.type_name = '{simple.type_name}'")

    if simple.id_value is not None:
        safe_id = simple.id_value.replace("'", "''")
        clauses.append(f"{alias}.entity_id = '{safe_id}'")

    for cls in simple.classes:
        clauses.append(dialect.list_contains(alias, "classes", cls))

    for attr in simple.attributes:
        clauses.append(_compile_attr_filter(attr, alias, dialect))

    for pseudo in simple.pseudo_classes:
        clause = _compile_pseudo(pseudo, alias, dialect)
        if clause:
            clauses.append(clause)

    if not clauses:
        return "TRUE"
    return " AND ".join(clauses)


def _compile_attr_filter(attr, alias: str, dialect: Dialect) -> str:
    """Compile an AttrFilter to a SQL expression."""
    col = dialect.json_attr(alias, attr.name)
    if attr.op is None:
        return f"{col} IS NOT NULL"
    safe_val = (attr.value or "").replace("'", "''")
    if attr.op == "=":
        return f"{col} = '{safe_val}'"
    if attr.op == "^=":
        return f"{col} LIKE '{safe_val}%'"
    if attr.op == "$=":
        return f"{col} LIKE '%{safe_val}'"
    if attr.op == "*=":
        return f"{col} LIKE '%{safe_val}%'"
    if attr.op == "~=":
        safe = safe_val
        return f"EXISTS(SELECT 1 FROM json_each(json_extract({alias}.attributes, '$.{attr.name}')) WHERE value = '{safe}')"
    if attr.op == "|=":
        return f"({col} = '{safe_val}' OR {col} LIKE '{safe_val}-%')"
    return "TRUE"


def _compile_pseudo(pseudo, alias: str, dialect: Dialect) -> str | None:
    """Compile a pseudo-class to a SQL expression."""
    if pseudo.name == "glob":
        pattern = (pseudo.argument or "").strip().strip("'\"")
        sql_pattern = _glob_to_like(pattern)
        col = dialect.json_attr(alias, "path")
        return f"{col} LIKE '{sql_pattern}'"
    return None


def _glob_to_like(pattern: str) -> str:
    result = pattern.replace("**", "\x00")
    result = result.replace("*", "%")
    result = result.replace("?", "_")
    result = result.replace("\x00", "%")
    return result.replace("'", "''")


def _compile_context_qualifier(simple: SimpleSelector, alias: str, dialect: Dialect) -> str:
    """Compile a cross-axis context qualifier to an EXISTS subquery."""
    where = _compile_simple(simple, alias, dialect)
    return f"EXISTS (SELECT 1 FROM entities {alias} WHERE {where})"


def _compile_structural_ancestor(simple: SimpleSelector, alias: str, dialect: Dialect) -> str:
    """Compile a structural-descent qualifier to a closure-table EXISTS."""
    where = _compile_simple(simple, alias, dialect)
    return (
        f"EXISTS ("
        f"SELECT 1 FROM entities {alias} "
        f"JOIN entity_closure ec ON ec.ancestor_id = {alias}.id "
        f"WHERE ec.descendant_id = e.id AND ec.depth > 0 AND {where}"
        f")"
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_compilers_sql/test_compiler.py -v`
Expected: All tests PASS (levels 1–4)

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/compilers/sql/compiler.py tests/test_compilers_sql/conftest.py \
       tests/test_compilers_sql/test_compiler.py
git commit -m "feat(sql): selector-to-SQL compiler — type, id, attr, class"
```

---

### Task 5: Selector-to-SQL Compiler (Levels 5–8)

**Files:**
- Modify: `tests/test_compilers_sql/test_compiler.py`

- [ ] **Step 1: Add tests for levels 5–8**

Append to `tests/test_compilers_sql/test_compiler.py`:

```python
# ============================================================================
# Level 5: Compound selectors — cross-axis
# ============================================================================

class TestCompoundSelectors:
    def test_two_axis_mode_tool(self, populated_db):
        sql = compile_selector(parse_selector("mode.implement tool"), DIALECT)
        assert query_ids(populated_db, sql) == {40, 41, 42, 43, 44, 45, 46}

    def test_two_axis_mode_tool_with_attr(self, populated_db):
        sql = compile_selector(parse_selector('mode.implement tool[name="Bash"]'), DIALECT)
        assert query_ids(populated_db, sql) == {42}

    def test_context_qualifier_nonexistent_mode_produces_nothing(self, populated_db):
        sql = compile_selector(parse_selector("mode.deploy tool"), DIALECT)
        assert query_ids(populated_db, sql) == set()

    def test_two_axis_principal_tool(self, populated_db):
        sql = compile_selector(parse_selector("principal#Teague tool"), DIALECT)
        assert query_ids(populated_db, sql) == {40, 41, 42, 43, 44, 45, 46}

    def test_two_axis_principal_nonexistent(self, populated_db):
        sql = compile_selector(parse_selector("principal#Nobody tool"), DIALECT)
        assert query_ids(populated_db, sql) == set()


# ============================================================================
# Level 6: Three-axis compounds
# ============================================================================

class TestThreeAxisCompounds:
    def test_principal_mode_tool(self, populated_db):
        sql = compile_selector(parse_selector('principal#Teague mode.implement tool[name="Bash"]'), DIALECT)
        assert query_ids(populated_db, sql) == {42}

    def test_three_axis_one_qualifier_fails(self, populated_db):
        sql = compile_selector(parse_selector('principal#Nobody mode.implement tool[name="Bash"]'), DIALECT)
        assert query_ids(populated_db, sql) == set()

    def test_three_axis_different_qualifier_fails(self, populated_db):
        sql = compile_selector(parse_selector('principal#Teague mode.deploy tool[name="Bash"]'), DIALECT)
        assert query_ids(populated_db, sql) == set()


# ============================================================================
# Level 7: Structural descendants
# ============================================================================

class TestStructuralDescendants:
    def test_dir_file_descendant(self, populated_db):
        sql = compile_selector(parse_selector('dir[name="src"] file'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2, 5}

    def test_dir_file_other_dir(self, populated_db):
        sql = compile_selector(parse_selector('dir[name="tests"] file'), DIALECT)
        assert query_ids(populated_db, sql) == {3}

    def test_dir_file_nonexistent_dir(self, populated_db):
        sql = compile_selector(parse_selector('dir[name="lib"] file'), DIALECT)
        assert query_ids(populated_db, sql) == set()


# ============================================================================
# Level 8: Pseudo-classes
# ============================================================================

class TestPseudoClasses:
    def test_glob_pseudo(self, populated_db):
        sql = compile_selector(parse_selector('file:glob("src/*.py")'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2}

    def test_glob_recursive(self, populated_db):
        sql = compile_selector(parse_selector('file:glob("**/*.py")'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2, 3}

    def test_glob_no_match(self, populated_db):
        sql = compile_selector(parse_selector('file:glob("*.rs")'), DIALECT)
        assert query_ids(populated_db, sql) == set()
```

- [ ] **Step 2: Run tests to verify levels 5–8 pass**

The implementation from Task 4 already handles compound selectors, structural descendants, and pseudo-classes via `_compile_context_qualifier`, `_compile_structural_ancestor`, and `_compile_pseudo`.

Run: `python -m pytest tests/test_compilers_sql/test_compiler.py -v`
Expected: All 34 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_compilers_sql/test_compiler.py
git commit -m "test(sql): compound, structural, and pseudo-class selector tests"
```

---

### Task 6: Cascade Resolution Views

**Files:**
- Create: `src/umwelt/compilers/sql/resolution.py`
- Test: `tests/test_compilers_sql/test_resolution.py`

- [ ] **Step 1: Write failing tests for resolution**

Create `tests/test_compilers_sql/test_resolution.py`:

```python
"""Tests for cascade resolution views.

Verifies comparison-aware resolution: exact (highest specificity wins),
<= (tightest bound / MIN), pattern-in (set union).
"""
from __future__ import annotations

import json
import sqlite3
import pytest
from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.schema import create_schema
from umwelt.compilers.sql.resolution import create_resolution_views


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compilers_sql/test_resolution.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'umwelt.compilers.sql.resolution'`

- [ ] **Step 3: Implement resolution views**

Create `src/umwelt/compilers/sql/resolution.py`:

```python
"""Cascade resolution views for the policy database.

Creates SQL views that implement comparison-aware cascade resolution:
- exact: highest specificity wins (document order breaks ties)
- <=: tightest bound (MIN value) wins
- pattern-in: all values aggregate via set union
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from umwelt.compilers.sql.dialects import Dialect


def create_resolution_views(con: sqlite3.Connection, dialect: Dialect) -> str:
    """Create resolution views and return the DDL as SQL text.

    Also executes the DDL against `con` if provided.
    """
    ddl = _resolution_ddl(dialect)
    con.executescript(ddl)
    return ddl


def resolution_ddl(dialect: Dialect) -> str:
    """Return the resolution view DDL as SQL text without executing."""
    return _resolution_ddl(dialect)


def _resolution_ddl(dialect: Dialect) -> str:
    is_sqlite = dialect.name == "sqlite"

    if is_sqlite:
        exact_view = """
CREATE VIEW IF NOT EXISTS _resolved_exact AS
SELECT entity_id, property_name, property_value, comparison,
       specificity, rule_index, source_file, source_line
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY entity_id, property_name
        ORDER BY specificity DESC, rule_index DESC
    ) AS _rn
    FROM cascade_candidates WHERE comparison = 'exact'
) WHERE _rn = 1;"""
    else:
        exact_view = """
CREATE OR REPLACE VIEW _resolved_exact AS
SELECT DISTINCT ON (entity_id, property_name)
    entity_id, property_name, property_value, comparison,
    specificity, rule_index, source_file, source_line
FROM cascade_candidates
WHERE comparison = 'exact'
ORDER BY entity_id, property_name, specificity DESC, rule_index DESC;"""

    cap_view_body = """
WITH ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY entity_id, property_name
        ORDER BY CAST(property_value AS INTEGER) ASC, specificity DESC
    ) AS _rn
    FROM cascade_candidates WHERE comparison = '<='
)
SELECT entity_id, property_name, property_value, comparison,
       specificity, rule_index, source_file, source_line
FROM ranked WHERE _rn = 1"""

    if is_sqlite:
        cap_view = f"CREATE VIEW IF NOT EXISTS _resolved_cap AS\n{cap_view_body};"
    else:
        cap_view = f"CREATE OR REPLACE VIEW _resolved_cap AS\n{cap_view_body};"

    if is_sqlite:
        pattern_view = """
CREATE VIEW IF NOT EXISTS _resolved_pattern AS
WITH agg AS (
    SELECT entity_id, property_name,
        GROUP_CONCAT(DISTINCT property_value) AS property_value,
        'pattern-in' AS comparison,
        MAX(specificity) AS specificity,
        MAX(rule_index) AS rule_index
    FROM cascade_candidates WHERE comparison = 'pattern-in'
    GROUP BY entity_id, property_name
)
SELECT a.entity_id, a.property_name, a.property_value, a.comparison,
       a.specificity, a.rule_index,
       c.source_file, c.source_line
FROM agg a
LEFT JOIN cascade_candidates c
    ON a.entity_id = c.entity_id AND a.property_name = c.property_name
    AND a.specificity = c.specificity AND a.rule_index = c.rule_index
    AND c.comparison = 'pattern-in';"""
    else:
        pattern_view = """
CREATE OR REPLACE VIEW _resolved_pattern AS
WITH agg AS (
    SELECT entity_id, property_name,
        STRING_AGG(DISTINCT property_value, ', ' ORDER BY property_value) AS property_value,
        'pattern-in' AS comparison,
        MAX(specificity) AS specificity,
        MAX(rule_index) AS rule_index
    FROM cascade_candidates WHERE comparison = 'pattern-in'
    GROUP BY entity_id, property_name
)
SELECT a.entity_id, a.property_name, a.property_value, a.comparison,
       a.specificity, a.rule_index,
       c.source_file, c.source_line
FROM agg a
LEFT JOIN cascade_candidates c
    ON a.entity_id = c.entity_id AND a.property_name = c.property_name
    AND a.specificity = c.specificity AND a.rule_index = c.rule_index
    AND c.comparison = 'pattern-in';"""

    union_keyword = "UNION ALL" if is_sqlite else "UNION ALL BY NAME"
    resolved_view_prefix = "CREATE VIEW IF NOT EXISTS" if is_sqlite else "CREATE OR REPLACE VIEW"

    resolved_view = f"""
{resolved_view_prefix} resolved_properties AS
SELECT * FROM _resolved_exact
{union_keyword} SELECT * FROM _resolved_cap
{union_keyword} SELECT * FROM _resolved_pattern;"""

    return "\n".join([exact_view, cap_view, pattern_view, resolved_view])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compilers_sql/test_resolution.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/compilers/sql/resolution.py tests/test_compilers_sql/test_resolution.py
git commit -m "feat(sql): comparison-aware cascade resolution views"
```

---

### Task 7: View Compilation (compile_view)

**Files:**
- Modify: `src/umwelt/compilers/sql/compiler.py`
- Modify: `src/umwelt/compilers/sql/__init__.py`

This task adds `compile_view()` — the function that iterates a parsed View's rules, generates cascade_candidates INSERTs, and creates resolution views.

- [ ] **Step 1: Write failing test for compile_view**

Add to `tests/test_compilers_sql/test_compiler.py`:

```python
from umwelt.compilers.sql.compiler import compile_view
from tests.test_compilers_sql.conftest import parse_view


class TestCompileView:
    def test_compile_view_populates_candidates(self, populated_db):
        view = parse_view('file[path^="src/"] { editable: true; }')
        compile_view(populated_db, view, DIALECT, source_file="test.umw")
        count = populated_db.execute("SELECT COUNT(*) FROM cascade_candidates").fetchone()[0]
        assert count > 0

    def test_compile_view_creates_resolution_views(self, populated_db):
        view = parse_view('file { editable: false; }')
        compile_view(populated_db, view, DIALECT, source_file="test.umw")
        row = populated_db.execute("SELECT COUNT(*) FROM resolved_properties").fetchone()
        assert row[0] > 0

    def test_compile_view_comparison_inference(self, populated_db):
        view = parse_view('tool { max-level: 5; }')
        compile_view(populated_db, view, DIALECT, source_file="test.umw")
        row = populated_db.execute(
            "SELECT comparison FROM cascade_candidates WHERE property_name = 'max-level'"
        ).fetchone()
        assert row[0] == "<="

    def test_compile_view_pattern_comparison(self, populated_db):
        view = parse_view('tool[name="Bash"] { allow-pattern: "git *"; }')
        compile_view(populated_db, view, DIALECT, source_file="test.umw")
        row = populated_db.execute(
            "SELECT comparison FROM cascade_candidates WHERE property_name = 'allow-pattern'"
        ).fetchone()
        assert row[0] == "pattern-in"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compilers_sql/test_compiler.py::TestCompileView -v`
Expected: FAIL — `ImportError: cannot import name 'compile_view'`

- [ ] **Step 3: Add compile_view to compiler.py**

Append to `src/umwelt/compilers/sql/compiler.py`:

```python
def compile_view(
    con: sqlite3.Connection,
    view: View,
    dialect: Dialect,
    source_file: str = "",
) -> None:
    """Compile a parsed View into cascade_candidates rows + resolution views."""
    import sqlite3 as _sqlite3
    from umwelt.compilers.sql.resolution import create_resolution_views

    for rule_idx, rule in enumerate(view.rules):
        for selector in rule.selectors:
            where_sql = compile_selector(selector, dialect)
            spec = selector.specificity if hasattr(selector, "specificity") else (0,) * 8
            spec_str = dialect.format_specificity(spec)
            safe_src = source_file.replace("'", "''")
            src_line = rule.span.line if hasattr(rule, "span") else 0

            for decl in rule.declarations:
                comparison = _infer_comparison(decl.property_name)
                safe_val = ", ".join(decl.values).replace("'", "''")
                con.execute(
                    "INSERT INTO cascade_candidates "
                    "(entity_id, property_name, property_value, comparison, "
                    "specificity, rule_index, source_file, source_line) "
                    f"SELECT e.id, ?, ?, ?, ?, ?, ?, ? "
                    f"FROM entities e WHERE {where_sql}",
                    (decl.property_name, safe_val, comparison,
                     spec_str, rule_idx, safe_src, src_line),
                )
    con.commit()
    create_resolution_views(con, dialect)


def _infer_comparison(property_name: str) -> str:
    if property_name.startswith("max-"):
        return "<="
    if property_name.startswith("min-"):
        return ">="
    if property_name in ("allow-pattern", "deny-pattern"):
        return "pattern-in"
    return "exact"


def _serialize_selector(selector: ComplexSelector) -> str:
    parts = []
    for p in selector.parts:
        s = p.selector
        text = s.type_name or "*"
        if s.id_value:
            text += f"#{s.id_value}"
        for cls in s.classes:
            text += f".{cls}"
        for attr in s.attributes:
            if attr.op and attr.value:
                text += f'[{attr.name}{attr.op}"{attr.value}"]'
            else:
                text += f"[{attr.name}]"
        for pseudo in s.pseudo_classes:
            if pseudo.argument:
                text += f":{pseudo.name}({pseudo.argument})"
            else:
                text += f":{pseudo.name}"
        parts.append(text)
    return " ".join(parts)
```

Also add the `sqlite3` import at the top of `compiler.py` in the `TYPE_CHECKING` block:

```python
if TYPE_CHECKING:
    import sqlite3
    from umwelt.ast import ComplexSelector, SimpleSelector, View
    from umwelt.compilers.sql.dialects import Dialect
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compilers_sql/test_compiler.py -v`
Expected: All tests PASS

- [ ] **Step 5: Update package __init__.py with public API**

Update `src/umwelt/compilers/sql/__init__.py`:

```python
"""SQL policy compiler — translates .umw views to SQL databases.

Public API:
  compile_to_sql(view, dialect, base_dir, source_file) → SQL text
  compile_to_db(con, view, dialect, base_dir, source_file) → None (mutates db)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path
    from umwelt.ast import View
    from umwelt.compilers.sql.dialects import Dialect


def compile_to_db(
    con: sqlite3.Connection,
    view: View,
    dialect: Dialect,
    base_dir: Path | None = None,
    source_file: str = "",
) -> None:
    """Compile a view into an existing database connection."""
    from umwelt.compilers.sql.compiler import compile_view
    from umwelt.compilers.sql.populate import populate_entities
    from umwelt.compilers.sql.schema import create_schema

    con.executescript(create_schema(dialect))
    if base_dir is not None:
        populate_entities(con, base_dir)
    compile_view(con, view, dialect, source_file=source_file)


def compile_to_sql(
    view: View,
    dialect: Dialect,
    base_dir: Path | None = None,
    source_file: str = "",
) -> str:
    """Compile a view to SQL text (schema + inserts + resolution views)."""
    import sqlite3 as _sqlite3
    from umwelt.compilers.sql.compiler import compile_view
    from umwelt.compilers.sql.populate import populate_entities
    from umwelt.compilers.sql.resolution import resolution_ddl
    from umwelt.compilers.sql.schema import create_schema

    parts = [create_schema(dialect)]

    if base_dir is not None:
        con = _sqlite3.connect(":memory:")
        con.executescript(create_schema(dialect))
        populate_entities(con, base_dir)
        # TODO: extract INSERT statements from populated db
        con.close()

    parts.append(resolution_ddl(dialect))
    return "\n\n".join(parts)
```

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/compilers/sql/compiler.py src/umwelt/compilers/sql/__init__.py
git commit -m "feat(sql): compile_view — full View AST to cascade candidates"
```

---

### Task 8: Entity Population from Matchers

**Files:**
- Create: `src/umwelt/compilers/sql/populate.py`
- Test: `tests/test_compilers_sql/test_populate.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_compilers_sql/test_populate.py`:

```python
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

        # Register matchers
        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        from umwelt.registry import register_matcher, clear_registry
        from umwelt.sandbox.world_matcher import WorldMatcher
        from umwelt.sandbox.capability_matcher import CapabilityMatcher
        from umwelt.sandbox.state_matcher import StateMatcher

        clear_registry()
        register_sandbox_vocabulary()
        register_matcher(taxon="world", matcher=WorldMatcher(base_dir=tmp_path))
        register_matcher(taxon="capability", matcher=CapabilityMatcher())
        register_matcher(taxon="state", matcher=StateMatcher())

        populate_entities(con, tmp_path)

        count = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        assert count > 0

        # Check a file was populated
        row = con.execute(
            "SELECT json_extract(attributes, '$.path') FROM entities WHERE type_name = 'file' AND entity_id = 'src/app.py'"
        ).fetchone()
        assert row is not None
        assert row[0] == "src/app.py"

        # Check closure table was built
        closure_count = con.execute("SELECT COUNT(*) FROM entity_closure").fetchone()[0]
        assert closure_count > 0

        clear_registry()
        con.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compilers_sql/test_populate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'umwelt.compilers.sql.populate'`

- [ ] **Step 3: Implement populate.py**

Create `src/umwelt/compilers/sql/populate.py`:

```python
"""Populate the entities table from the matcher registry.

Bridges umwelt's Matcher protocol to SQL INSERT statements. Each
registered matcher is queried for entities, which are serialized
to JSON-column rows and inserted.
"""
from __future__ import annotations

import json
from dataclasses import fields, asdict
from pathlib import Path
from typing import Any

from umwelt.registry.taxa import _current_state


def entity_to_row(taxon: str, type_name: str, entity: Any) -> dict[str, Any]:
    """Convert a matcher entity object to an insertable row dict."""
    entity_id = _extract_id(entity)
    classes = _extract_classes(entity)
    attributes = _extract_attributes(entity)

    return {
        "taxon": taxon,
        "type_name": type_name,
        "entity_id": entity_id,
        "classes": json.dumps(classes) if classes else None,
        "attributes": json.dumps(attributes) if attributes else None,
    }


def _extract_id(entity: Any) -> str | None:
    for attr in ("path", "name", "kind", "id"):
        val = getattr(entity, attr, None)
        if val is not None:
            return str(val)
    return None


def _extract_classes(entity: Any) -> list[str]:
    classes = getattr(entity, "classes", None)
    if classes is not None:
        return list(classes)
    return []


def _extract_attributes(entity: Any) -> dict[str, str]:
    attrs: dict[str, str] = {}
    skip = {"abs_path", "classes"}
    try:
        for f in fields(entity):
            if f.name in skip:
                continue
            val = getattr(entity, f.name)
            if val is not None:
                attrs[f.name] = str(val)
    except TypeError:
        pass
    return attrs


def populate_entities(con: Any, base_dir: Path) -> None:
    """Query all registered matchers and INSERT their entities."""
    state = _current_state()
    entity_id = 0

    for taxon, matcher in state.matchers.items():
        type_names = _get_type_names(taxon)
        for type_name in type_names:
            try:
                entities = matcher.match_type(type_name)
            except Exception:
                continue
            for entity in entities:
                entity_id += 1
                row = entity_to_row(taxon, type_name, entity)
                con.execute(
                    "INSERT INTO entities (id, taxon, type_name, entity_id, classes, attributes, depth) "
                    "VALUES (?, ?, ?, ?, ?, ?, 0)",
                    (entity_id, row["taxon"], row["type_name"], row["entity_id"],
                     row["classes"], row["attributes"]),
                )

    con.commit()
    _rebuild_hierarchy(con, base_dir)
    _rebuild_closure(con)


def _get_type_names(taxon: str) -> list[str]:
    """Return the entity type names to query for a taxon."""
    state = _current_state()
    types = []
    for (t, name), _ in state.entity_types.items():
        if t == taxon:
            types.append(name)
    return types if types else ["*"]


def _rebuild_hierarchy(con: Any, base_dir: Path) -> None:
    """Set parent_id for file/dir entities based on filesystem paths."""
    dirs = con.execute(
        "SELECT id, entity_id FROM entities WHERE type_name = 'dir'"
    ).fetchall()
    dir_map = {path: eid for eid, path in dirs}

    files = con.execute(
        "SELECT id, entity_id FROM entities WHERE type_name IN ('file', 'dir') AND entity_id IS NOT NULL"
    ).fetchall()
    for file_id, file_path in files:
        if file_path is None:
            continue
        parent_path = str(Path(file_path).parent)
        if parent_path == ".":
            continue
        parent_id = dir_map.get(parent_path)
        if parent_id is not None:
            con.execute("UPDATE entities SET parent_id = ? WHERE id = ?", (parent_id, file_id))
    con.commit()


def _rebuild_closure(con: Any) -> None:
    """Rebuild the entity_closure table from parent_id relationships."""
    con.executescript("""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compilers_sql/test_populate.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/compilers/sql/populate.py tests/test_compilers_sql/test_populate.py
git commit -m "feat(sql): entity population from matcher registry"
```

---

### Task 9: Round-Trip Tests

**Files:**
- Test: `tests/test_compilers_sql/test_roundtrip.py`

- [ ] **Step 1: Write round-trip tests**

Create `tests/test_compilers_sql/test_roundtrip.py`:

```python
"""Round-trip tests: parse .umw → compile → SQLite → resolve → verify.

Port of ducklog's test_roundtrip.py adapted for SQLite.
"""
from __future__ import annotations

import pytest
from tests.test_compilers_sql.conftest import parse_view
from umwelt.compilers.sql.compiler import compile_view
from umwelt.compilers.sql.dialects import SQLiteDialect


DIALECT = SQLiteDialect()


@pytest.fixture
def world(populated_db):
    return populated_db


def _resolve(world, umw_text: str):
    view = parse_view(umw_text)
    compile_view(world, view, DIALECT, source_file="test.umw")
    return _Resolved(world)


class _Resolved:
    def __init__(self, con):
        self.con = con

    def property(self, entity_id: str, prop_name: str) -> str | None:
        row = self.con.execute(
            "SELECT rp.property_value FROM resolved_properties rp "
            "JOIN entities e ON rp.entity_id = e.id "
            "WHERE e.entity_id = ? AND rp.property_name = ?",
            (entity_id, prop_name),
        ).fetchone()
        return row[0] if row else None

    def property_by_id(self, entity_db_id: int, prop_name: str) -> str | None:
        row = self.con.execute(
            "SELECT property_value FROM resolved_properties "
            "WHERE entity_id = ? AND property_name = ?",
            (entity_db_id, prop_name),
        ).fetchone()
        return row[0] if row else None

    def all_props(self, entity_id: str) -> dict[str, str]:
        rows = self.con.execute(
            "SELECT rp.property_name, rp.property_value FROM resolved_properties rp "
            "JOIN entities e ON rp.entity_id = e.id WHERE e.entity_id = ?",
            (entity_id,),
        ).fetchall()
        return dict(rows)

    def assert_a1(self):
        dupes = self.con.execute(
            "SELECT entity_id, property_name, COUNT(*) AS n "
            "FROM resolved_properties GROUP BY entity_id, property_name HAVING n > 1"
        ).fetchall()
        assert dupes == [], f"A1 violated: duplicate winners {dupes}"


class TestFilePermissions:
    def test_prefix_match_sets_editable(self, world):
        rv = _resolve(world, '''
            file[path^="src/"] { editable: true; }
            file { editable: false; }
        ''')
        assert rv.property("src/auth.py", "editable") == "true"
        assert rv.property("tests/test_auth.py", "editable") == "false"
        assert rv.property("README.md", "editable") == "false"
        rv.assert_a1()

    def test_suffix_match_hides_pyc(self, world):
        rv = _resolve(world, '''
            file { visible: true; }
            file[path$=".pyc"] { visible: false; }
        ''')
        assert rv.property("src/auth.py", "visible") == "true"
        assert rv.property("src/main.pyc", "visible") == "false"
        rv.assert_a1()

    def test_specificity_ordering(self, world):
        rv = _resolve(world, '''
            file { editable: false; }
            file[path^="src/"] { editable: true; }
        ''')
        assert rv.property("src/auth.py", "editable") == "true"
        rv.assert_a1()

    def test_document_order_breaks_ties(self, world):
        rv = _resolve(world, '''
            file[path^="src/"] { editable: false; }
            file[path^="src/"] { editable: true; }
        ''')
        assert rv.property("src/auth.py", "editable") == "true"
        rv.assert_a1()


class TestToolPermissions:
    def test_tool_allow_deny(self, world):
        rv = _resolve(world, '''
            tool { allow: true; }
            tool[name="Bash"] { allow: false; }
        ''')
        assert rv.property("Read", "allow") == "true"
        assert rv.property("Bash", "allow") == "false"
        rv.assert_a1()

    def test_max_level_tightest_wins(self, world):
        rv = _resolve(world, '''
            tool { max-level: 5; }
            tool[name="Bash"] { max-level: 3; }
        ''')
        assert rv.property("Bash", "max-level") == "3"
        assert rv.property("Read", "max-level") == "5"
        rv.assert_a1()

    def test_allow_pattern_aggregates(self, world):
        rv = _resolve(world, '''
            tool[name="Bash"] { allow-pattern: "git *"; }
            tool[name="Bash"] { allow-pattern: "pytest *"; }
        ''')
        patterns = rv.property("Bash", "allow-pattern")
        assert patterns is not None
        assert "git *" in patterns
        assert "pytest *" in patterns
        rv.assert_a1()


class TestModeGatedTools:
    def test_mode_gates_tool(self, world):
        rv = _resolve(world, '''
            tool { allow: true; }
            mode.explore tool { allow: false; }
        ''')
        assert rv.property("Read", "allow") == "false"
        assert rv.property("Bash", "allow") == "false"
        rv.assert_a1()

    def test_mode_specific_tool_override(self, world):
        rv = _resolve(world, '''
            mode.explore tool { allow: false; }
            mode.explore tool[name="Read"] { allow: true; }
        ''')
        assert rv.property("Read", "allow") == "true"
        assert rv.property("Bash", "allow") == "false"
        rv.assert_a1()

    def test_nonexistent_mode_gates_nothing(self, world):
        rv = _resolve(world, '''
            tool { allow: true; }
            mode.deploy tool { allow: false; }
        ''')
        assert rv.property("Read", "allow") == "true"
        rv.assert_a1()


class TestCrossAxis:
    def test_three_axis_beats_two_axis(self, world):
        rv = _resolve(world, '''
            mode.implement tool[name="Bash"] { allow: false; }
            principal#Teague mode.implement tool[name="Bash"] { allow: true; }
        ''')
        assert rv.property("Bash", "allow") == "true"
        rv.assert_a1()

    def test_two_axis_beats_one_axis(self, world):
        rv = _resolve(world, '''
            tool[name="Bash"] { allow: true; }
            mode.implement tool[name="Bash"] { allow: false; }
        ''')
        assert rv.property("Bash", "allow") == "false"
        rv.assert_a1()


class TestStructuralDescendants:
    def test_dir_file_descendant(self, world):
        rv = _resolve(world, '''
            file { editable: false; }
            dir[name="src"] file { editable: true; }
        ''')
        assert rv.property("src/auth.py", "editable") == "true"
        assert rv.property("tests/test_auth.py", "editable") == "false"
        rv.assert_a1()


class TestFullPolicy:
    def test_realistic_policy(self, world):
        rv = _resolve(world, '''
            file { editable: false; visible: true; }
            file[path^="src/"] { editable: true; }
            file[path$=".pyc"] { visible: false; }

            tool { allow: true; max-level: 3; }
            tool[name="Bash"] { max-level: 2; }
            tool[name="Agent"] { allow: false; }

            tool[name="Bash"] { allow-pattern: "git *"; }
            tool[name="Bash"] { allow-pattern: "pytest *"; }

            network { deny: "*"; }
            resource[kind="memory"] { limit: 512MB; }
        ''')
        assert rv.property("src/auth.py", "editable") == "true"
        assert rv.property("README.md", "editable") == "false"
        assert rv.property("src/main.pyc", "visible") == "false"
        assert rv.property("Read", "allow") == "true"
        assert rv.property("Agent", "allow") == "false"
        assert rv.property("Bash", "max-level") == "2"

        patterns = rv.property("Bash", "allow-pattern")
        assert "git *" in patterns
        assert "pytest *" in patterns

        assert rv.property_by_id(25, "deny") == "*"
        assert rv.property("memory", "limit") == "512MB"
        rv.assert_a1()
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_compilers_sql/test_roundtrip.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_compilers_sql/test_roundtrip.py
git commit -m "test(sql): round-trip tests — .umw to SQLite to resolved properties"
```

---

### Task 10: CLI Integration

**Files:**
- Modify: `src/umwelt/cli.py`

- [ ] **Step 1: Write a CLI integration test**

Add to `tests/test_compilers_sql/test_roundtrip.py`:

```python
import subprocess
import tempfile


class TestCLIIntegration:
    def test_compile_to_sqlite_db(self, tmp_path):
        policy = tmp_path / "policy.umw"
        policy.write_text('file { editable: false; }\nfile[path^="src/"] { editable: true; }')
        db_path = tmp_path / "policy.db"
        result = subprocess.run(
            ["python", "-m", "umwelt", "compile", str(policy), "--target", "sqlite", "--db", str(db_path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert db_path.exists()

    def test_compile_sql_to_stdout(self, tmp_path):
        policy = tmp_path / "policy.umw"
        policy.write_text('file { visible: true; }')
        result = subprocess.run(
            ["python", "-m", "umwelt", "compile", str(policy), "--target", "sqlite"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "CREATE TABLE" in result.stdout

    def test_compile_sql_to_file(self, tmp_path):
        policy = tmp_path / "policy.umw"
        policy.write_text('file { visible: true; }')
        sql_path = tmp_path / "policy.sql"
        result = subprocess.run(
            ["python", "-m", "umwelt", "compile", str(policy), "--target", "sqlite", "-o", str(sql_path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert sql_path.exists()
        assert "CREATE TABLE" in sql_path.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compilers_sql/test_roundtrip.py::TestCLIIntegration -v`
Expected: FAIL — CLI doesn't handle `--target sqlite` yet

- [ ] **Step 3: Update cli.py**

Replace the `_cmd_compile_duckdb` function and update `_cmd_compile` in `src/umwelt/cli.py`. The key changes:

1. Add `--db` argument to the compile subparser
2. Route `sqlite` and `duckdb` targets to `_cmd_compile_sql`
3. Replace `_cmd_compile_duckdb` with `_cmd_compile_sql`
4. Remove `_populate_entities_from_matchers`

In `_cmd_compile`, replace the duckdb routing:

```python
    SQL_TARGETS = {"sqlite", "duckdb"}
    if args.target in SQL_TARGETS:
        return _cmd_compile_sql(args, view)
```

Add `_cmd_compile_sql`:

```python
def _cmd_compile_sql(args: argparse.Namespace, view) -> int:
    """Compile a view to SQL text or a database."""
    try:
        from umwelt.compilers.sql.dialects import get_dialect
        from umwelt.compilers.sql.schema import create_schema
        from umwelt.compilers.sql.compiler import compile_view
        from umwelt.compilers.sql.populate import populate_entities
        from umwelt.compilers.sql.resolution import create_resolution_views
    except ImportError:
        print(
            "error: SQL compilation requires the 'sql' extras. "
            "Install with: pip install umwelt[sql]",
            file=sys.stderr,
        )
        return 1

    dialect = get_dialect(args.target)
    view_path = Path(args.file)
    _register_matchers(view_path)

    db_path = getattr(args, "db", None)
    output_path = getattr(args, "output", None)

    # Generate SQL text
    sql_text = create_schema(dialect)

    if db_path:
        # Execute against database
        if args.target == "sqlite":
            import sqlite3
            con = sqlite3.connect(db_path)
            con.executescript(sql_text)
            populate_entities(con, view_path.resolve().parent)
            compile_view(con, view, dialect, source_file=str(view_path))
            entity_n = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            resolved_n = con.execute("SELECT COUNT(*) FROM resolved_properties").fetchone()[0]
            con.commit()
            con.close()
            print(f"Compiled {db_path}: {entity_n} entities, {resolved_n} resolved properties")
        elif args.target == "duckdb":
            try:
                import duckdb
            except ImportError:
                print("error: --db with duckdb target requires: pip install umwelt[duckdb]", file=sys.stderr)
                return 1
            # DuckDB execution path (future)
            print("error: DuckDB --db execution not yet implemented", file=sys.stderr)
            return 1

    if output_path:
        Path(output_path).write_text(sql_text)
        if not db_path:
            print(f"SQL written to {output_path}")

    if not db_path and not output_path:
        # SQL to stdout
        print(sql_text, end="")

    return 0
```

Add `--db` to the compile subparser in `build_parser()`:

```python
    p_compile.add_argument(
        "-d", "--db", default=None,
        help="database connection string or file path (executes SQL)",
    )
```

Update the `-o` help text:

```python
    p_compile.add_argument(
        "-o", "--output", default=None,
        help="output file path for SQL text",
    )
```

Update the error message in the standard compiler path to list SQL targets:

```python
        print(
            f"error: no compiler registered for target {args.target!r}. "
            f"Available: {names}, sqlite, duckdb",
            file=sys.stderr,
        )
```

- [ ] **Step 4: Run CLI tests to verify they pass**

Run: `python -m pytest tests/test_compilers_sql/test_roundtrip.py::TestCLIIntegration -v`
Expected: All tests PASS

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest tests/ -v --timeout=60`
Expected: All existing tests + new SQL compiler tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/cli.py tests/test_compilers_sql/test_roundtrip.py
git commit -m "feat(cli): umwelt compile --target sqlite [--db path] [-o file]"
```

---

### Task 11: Final Integration Test and Cleanup

**Files:**
- Modify: `src/umwelt/compilers/sql/__init__.py`

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=60`
Expected: All tests PASS

- [ ] **Step 2: Run ruff linter**

Run: `ruff check src/umwelt/compilers/sql/ tests/test_compilers_sql/`
Expected: No errors (fix any that appear)

- [ ] **Step 3: Run mypy**

Run: `mypy src/umwelt/compilers/sql/`
Expected: No errors (fix any that appear, may need type stubs for pypika)

- [ ] **Step 4: Manual smoke test**

Run:
```bash
echo 'file { editable: false; visible: true; }
file[path^="src/"] { editable: true; }
tool { allow: true; }
tool[name="Agent"] { allow: false; }' > /tmp/test-policy.umw

python -m umwelt compile /tmp/test-policy.umw --target sqlite --db /tmp/test-policy.db
python3 -c "
import sqlite3
con = sqlite3.connect('/tmp/test-policy.db')
print('Entities:', con.execute('SELECT COUNT(*) FROM entities').fetchone()[0])
print('Resolved:', con.execute('SELECT COUNT(*) FROM resolved_properties').fetchone()[0])
for row in con.execute('SELECT e.entity_id, rp.property_name, rp.property_value FROM resolved_properties rp JOIN entities e ON rp.entity_id = e.id LIMIT 10'):
    print(f'  {row[0]}: {row[1]} = {row[2]}')
"
```
Expected: Output shows entities, resolved properties, and correct values

- [ ] **Step 5: Commit any cleanup**

```bash
git add -A
git commit -m "chore(sql): lint and type fixes for SQL compiler"
```

---

## Summary

| Task | What it builds | Files | Tests |
|------|---------------|-------|-------|
| 1 | PyPika optional dep | pyproject.toml | — |
| 2 | Dialect abstraction | dialects.py | test_dialects.py |
| 3 | Schema DDL | schema.py | test_schema.py |
| 4 | Compiler L1–4 | compiler.py, conftest.py | test_compiler.py (20 tests) |
| 5 | Compiler L5–8 | test_compiler.py | test_compiler.py (+14 tests) |
| 6 | Resolution views | resolution.py | test_resolution.py |
| 7 | compile_view | compiler.py, __init__.py | test_compiler.py (+4 tests) |
| 8 | Entity population | populate.py | test_populate.py |
| 9 | Round-trip tests | — | test_roundtrip.py |
| 10 | CLI integration | cli.py | test_roundtrip.py (+3 tests) |
| 11 | Cleanup + smoke test | — | — |
