# SQL Compiler Integration Guide

The SQL compiler translates `.umw` views into queryable SQLite databases. This guide covers the CLI, Python API, and integration patterns.

## Quick Start

### CLI: compile a view to a SQLite database

```bash
umwelt compile policy.umw --target sqlite --db policy.db
```

This parses `policy.umw`, discovers entities in the current directory tree, evaluates all selectors, resolves the cascade, and writes the result to `policy.db`. The output reports entity and property counts:

```
Compiled policy.db: 22802 entities, 35992 resolved properties
```

### CLI: emit SQL to stdout or a file

```bash
# Schema + resolution views to stdout
umwelt compile policy.umw --target sqlite

# Write to a file
umwelt compile policy.umw --target sqlite -o policy.sql
```

### Python API: compile into a database

```python
import sqlite3
from pathlib import Path
from umwelt.parser import parse
from umwelt.compilers.sql import compile_to_db
from umwelt.compilers.sql.dialects import SQLiteDialect

view = parse("policy.umw")
con = sqlite3.connect("policy.db")
compile_to_db(con, view, SQLiteDialect(), base_dir=Path.cwd())

# Query the results
row = con.execute("""
    SELECT rp.property_value
    FROM resolved_properties rp
    JOIN entities e ON rp.entity_id = e.id
    WHERE e.entity_id = 'src/auth.py' AND rp.property_name = 'editable'
""").fetchone()
print(row[0])  # "true"
con.close()
```

### Python API: compile to a SQL script

```python
from umwelt.parser import parse
from umwelt.compilers.sql import compile_to_sql
from umwelt.compilers.sql.dialects import SQLiteDialect

view = parse("policy.umw")
sql = compile_to_sql(view, SQLiteDialect(), base_dir=Path.cwd())
Path("policy.sql").write_text(sql)
```

## Compilation Pipeline

The compiler runs four stages in sequence:

```
.umw text
    │
    ▼
┌─────────┐     ┌──────────┐     ┌──────────┐     ┌────────────┐
│ Schema  │ ──▶ │ Populate │ ──▶ │ Compile  │ ──▶ │ Resolution │
│  DDL    │     │ entities │     │ selectors│     │   views    │
└─────────┘     └──────────┘     └──────────┘     └────────────┘
```

1. **Schema DDL** — creates the six tables and indexes (see [Schema Reference](sql-schema.md))
2. **Populate entities** — queries all registered matchers and inserts entities into the `entities` table, then builds the `entity_closure` table from parent-child relationships
3. **Compile selectors** — for each rule in the view, translates CSS selectors to SQL WHERE clauses and inserts matching (entity, property, value) rows into `cascade_candidates`
4. **Resolution views** — creates the `_resolved_exact`, `_resolved_cap`, `_resolved_pattern`, and `resolved_properties` views that implement cascade resolution

## API Reference

### `compile_to_db(con, view, dialect, base_dir=None, source_file="")`

Compiles a view into an existing database connection. Runs all four stages.

| Parameter | Type | Description |
|-----------|------|-------------|
| `con` | `sqlite3.Connection` | Target database connection |
| `view` | `View` | Parsed umwelt AST |
| `dialect` | `Dialect` | SQL dialect (`SQLiteDialect()` or `DuckDBDialect()`) |
| `base_dir` | `Path \| None` | Project root for entity discovery. If `None`, no entities are populated — only the schema and selector compilation run. |
| `source_file` | `str` | Source file path recorded in `cascade_candidates.source_file` |

### `compile_to_sql(view, dialect, base_dir=None, source_file="")`

Compiles a view to a self-contained SQL script. Builds an in-memory SQLite database, runs `compile_to_db`, then dumps the result via `iterdump()`.

Returns: `str` — the full SQL script.

### `compile_selector(selector, dialect)`

Translates a single `ComplexSelector` to a SQL WHERE clause string. Useful for debugging or building custom queries.

```python
from umwelt.compilers.sql.compiler import compile_selector
from umwelt.compilers.sql.dialects import SQLiteDialect

where = compile_selector(selector, SQLiteDialect())
# e.g.: "e.type_name = 'file' AND json_extract(e.attributes, '$.path') LIKE 'src/%' ESCAPE '\'"
```

### Dialects

Two dialects are provided:

| Dialect | Class | Notes |
|---------|-------|-------|
| SQLite | `SQLiteDialect()` | Fully supported. JSON via `json_extract`/`json_each`. |
| DuckDB | `DuckDBDialect()` | Schema generation and query building supported. DuckDB can also read SQLite databases natively via `sqlite_scan`. |

```python
from umwelt.compilers.sql.dialects import get_dialect

dialect = get_dialect("sqlite")  # or "duckdb"
```

Custom dialects can be registered:

```python
from umwelt.compilers.sql.dialects import register_dialect, Dialect

class MyDialect(Dialect):
    name = "mydb"
    # implement abstract methods...

register_dialect("mydb", MyDialect)
```

## Integration Patterns

### Pattern 1: Policy evaluation at tool-call time

Compile the policy once at session start, then query `resolved_properties` at each tool call:

```python
import sqlite3
from umwelt.parser import parse
from umwelt.compilers.sql import compile_to_db
from umwelt.compilers.sql.dialects import SQLiteDialect

view = parse("policy.umw")
con = sqlite3.connect(":memory:")
compile_to_db(con, view, SQLiteDialect(), base_dir=project_root)

def is_tool_allowed(tool_name: str) -> bool:
    row = con.execute("""
        SELECT rp.property_value
        FROM resolved_properties rp
        JOIN entities e ON rp.entity_id = e.id
        WHERE e.entity_id = ? AND rp.property_name = 'allow'
    """, (tool_name,)).fetchone()
    return row is not None and row[0] == "true"

def get_tool_patterns(tool_name: str) -> list[str]:
    row = con.execute("""
        SELECT rp.property_value
        FROM resolved_properties rp
        JOIN entities e ON rp.entity_id = e.id
        WHERE e.entity_id = ? AND rp.property_name = 'allow-pattern'
    """, (tool_name,)).fetchone()
    if row is None:
        return []
    return row[0].split(",")
```

### Pattern 2: File permission checks

```python
def check_file_access(file_path: str) -> dict[str, str]:
    """Return all resolved properties for a file."""
    rows = con.execute("""
        SELECT rp.property_name, rp.property_value
        FROM resolved_properties rp
        JOIN entities e ON rp.entity_id = e.id
        WHERE e.entity_id = ?
    """, (file_path,)).fetchall()
    return dict(rows)

props = check_file_access("src/auth.py")
# {"editable": "true", "visible": "true"}
```

### Pattern 3: DuckDB reads SQLite natively

Compile to a SQLite file, then query from DuckDB without any conversion:

```bash
umwelt compile policy.umw --target sqlite --db policy.db
```

```sql
-- In DuckDB
INSTALL sqlite;
LOAD sqlite;

SELECT e.entity_id, rp.property_name, rp.property_value
FROM sqlite_scan('policy.db', 'resolved_properties') rp
JOIN sqlite_scan('policy.db', 'entities') e ON rp.entity_id = e.id
WHERE rp.property_name = 'editable' AND rp.property_value = 'true';
```

### Pattern 4: Without entity population

If you want to compile selectors against a pre-populated entity set (e.g., from a different source), pass `base_dir=None` and populate the `entities` table yourself:

```python
con = sqlite3.connect(":memory:")
compile_to_db(con, view, SQLiteDialect())  # schema only, no entity discovery

# Insert your own entities
con.execute(
    "INSERT INTO entities (taxon, type_name, entity_id, attributes) VALUES (?, ?, ?, ?)",
    ("world", "file", "README.md", '{"path": "README.md"}'),
)
con.commit()

# Now compile the view against your entities
from umwelt.compilers.sql.compiler import compile_view
compile_view(con, view, SQLiteDialect())
```

## Context Qualifiers

Cross-axis selectors (e.g., `mode.explore tool`) are evaluated as global existence checks — the qualifier matches if any entity of that type/id exists in the database. This means the populator controls which context is "active" by choosing which entities to insert.

For example, to evaluate policy for mode `explore`:

```python
# Insert only the active mode entity
con.execute(
    "INSERT INTO entities (taxon, type_name, entity_id) VALUES (?, ?, ?)",
    ("state", "mode", "explore"),
)
```

Rules qualified with `mode.explore` will now match; rules qualified with `mode.deploy` will not.

## Selector-to-SQL Translation

The compiler translates each CSS selector form to SQL:

| Selector | SQL Fragment |
|----------|-------------|
| `file` | `e.type_name = 'file'` |
| `file#README.md` | `e.type_name = 'file' AND e.entity_id = 'README.md'` |
| `file.test` | `EXISTS(SELECT 1 FROM json_each(e.classes) WHERE value = 'test')` |
| `file[path="x"]` | `json_extract(e.attributes, '$.path') = 'x'` |
| `file[path^="src/"]` | `json_extract(e.attributes, '$.path') LIKE 'src/%' ESCAPE '\'` |
| `file[path$=".py"]` | `json_extract(e.attributes, '$.path') LIKE '%.py' ESCAPE '\'` |
| `file[path*="auth"]` | `json_extract(e.attributes, '$.path') LIKE '%auth%' ESCAPE '\'` |
| `file:glob("src/**")` | `json_extract(e.attributes, '$.path') LIKE 'src/%' ESCAPE '\'` |
| `dir[name="src"] file` | Structural descent via `entity_closure` JOIN |
| `mode.explore tool` | Cross-axis `EXISTS` subquery |

## Troubleshooting

### No entities in the database

If `resolved_properties` is empty, check that entities were populated:

```sql
SELECT COUNT(*) FROM entities;
-- If 0, base_dir was None or matchers found no entities
```

Ensure the sandbox vocabulary is registered before parsing:

```python
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
register_sandbox_vocabulary()
```

### A1 invariant violation

If a query returns multiple values for the same (entity, property), the A1 invariant is broken:

```sql
SELECT entity_id, property_name, COUNT(*) AS n
FROM resolved_properties
GROUP BY entity_id, property_name
HAVING n > 1;
```

This should never happen. If it does, file a bug.

### Inspecting cascade candidates

To understand why a property resolved to a particular value, query the raw candidates:

```sql
SELECT cc.property_value, cc.specificity, cc.rule_index, cc.comparison
FROM cascade_candidates cc
JOIN entities e ON cc.entity_id = e.id
WHERE e.entity_id = 'src/auth.py' AND cc.property_name = 'editable'
ORDER BY cc.specificity DESC, cc.rule_index DESC;
```

The first row (highest specificity, then highest rule_index) is the winner for `exact` comparison.
