# SQL Policy Compiler Design

**Date:** 2026-04-18
**Status:** Proposed
**Replaces:** Separate `ducklog` package

## Summary

Add `umwelt.compilers.sql` — a SQL policy compiler that translates `.umw` views into SQL text or executed databases. SQLite is the default dialect, DuckDB is a second dialect, extensible to others via PyPika. This absorbs the compiler half of the `ducklog` package into umwelt; the consumer half (kibitzer, lackpy adapters) moves to those respective tools.

## Motivation

The `ducklog` package exists as a separate repo with a circular optional dependency on umwelt. Its compiler (`compiler.py`, 280 LOC) walks umwelt's AST to emit SQL — structurally identical to how `nsjail.py` walks a `ResolvedView` to emit textproto. The SQL database it produces is an intermediate representation: consumers (kibitzer, lackpy) query it for resolved policy.

Bundling the compiler into umwelt eliminates the circular dependency, gives umwelt a first-class SQL output path, and positions the SQL database as an alternative resolution backend alongside the existing Python cascade resolver.

The separate `ducklog` package dissolves:
- **Compiler + schema** → `umwelt.compilers.sql`
- **Consumer adapters** → `kibitzer.policy`, `lackpy.policy` (each tool's repo)
- **Docs/examples** → umwelt docs

## Architecture

### Module Structure

```
src/umwelt/compilers/sql/
    __init__.py       # Public API: compile_to_sql(), compile_to_db()
    schema.py         # DDL per dialect (PyPika Table defs + CREATE VIEW strings)
    compiler.py       # AST → PyPika Criterion objects (dialect-agnostic)
    resolution.py     # Cascade resolution views per dialect
    populate.py       # Matcher registry → entity INSERTs
    dialects.py       # Dialect registry: sqlite, duckdb expression helpers
```

### Relationship to Existing Compilers

The SQL compiler is a peer of nsjail/bwrap/lackpy, not a prerequisite. Both resolution paths coexist:

```
.umw → parse → resolve (Python) → {nsjail, bwrap, lackpy}     # existing, unchanged
.umw → parse → resolve (SQL)    → policy.db                    # new, optional
                                    ↑
                              kibitzer, lackpy, future consumers query this
```

The SQL compiler implements a different interface than the `Compiler` protocol: it takes a raw `View` (not a `ResolvedView`) and produces a database that *is* the resolution. The CLI routes SQL targets separately, as it already does for `--target duckdb`.

A future `reader.py` module will provide a Python API over the database, enabling nsjail/bwrap/lackpy to migrate to reading from SQL — but that is deferred.

### Data Flow

```
1. Parse:      .umw file → View AST (tinycss2-backed parser, unchanged)
2. Populate:   Registered Matchers → entity rows (INSERT)
3. Compile:    View AST × entities → cascade_candidates rows (INSERT)
4. Resolve:    Resolution views compute winners (CREATE VIEW)
5. Output:     SQL text to stdout/file, or executed against a database
```

## Schema Design

The SQLite schema mirrors ducklog's `policy.sql` with these translations:

| Concept | DuckDB | SQLite |
|---|---|---|
| Entity attributes | `MAP(VARCHAR, VARCHAR)` | `TEXT` (JSON object) |
| Classes | `VARCHAR[]` | `TEXT` (JSON array) |
| Specificity | `INTEGER[]` | `TEXT` (JSON array of 5-digit zero-padded strings) |
| Auto-increment IDs | `CREATE SEQUENCE` + `nextval()` | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| Closure rebuild | `CREATE OR REPLACE MACRO` | `INSERT ... WITH RECURSIVE` |
| Attribute access | `attributes['key']` | `json_extract(attributes, '$.path')` |
| Array membership | `list_contains(classes, 'x')` | `EXISTS(SELECT 1 FROM json_each(classes) WHERE value='x')` |
| Exact resolution | `DISTINCT ON (entity_id, property_name)` | `ROW_NUMBER() OVER(...) = 1` |
| Pattern aggregation | `STRING_AGG(DISTINCT x, ',' ORDER BY x)` | `GROUP_CONCAT(DISTINCT x)` |

### Tables

- **Vocabulary:** `taxa`, `entity_types`, `property_types` (with `comparison` column)
- **World state:** `entities` (JSON attributes + classes, parent_id, depth), `entity_closure` (adjacency list + transitive closure)
- **Cascade:** `cascade_candidates` (materialized rows, not a view — SQLite performs better with materialized data when resolution views query it multiple times)
- **Resolution:** `resolved_properties` (view), composed from `_resolved_exact`, `_resolved_cap`, `_resolved_pattern` sub-views
- **Projections:** `files`, `tools`, `modes`, `uses`, `transitions` — consumer-friendly typed views using `json_extract`
- **Cross-axis:** `use_refs` — links `use[of=...]` entities to their targets
- **Verification:** `assert_a1`, `assert_a2`, `assert_a5`, `assert_a6`, `assert_c1` — evaluation framework claims as SQL assertions

### Specificity Encoding

Specificity is an 8-element tuple where values can reach ~10,100 (packed as `id*10000 + attrs*100 + type`). Stored as a JSON array of 5-digit zero-padded strings:

```json
["00002", "00000", "10100", "00000", "00000", "00100", "00000", "00000"]
```

This enables correct lexicographic comparison via `ORDER BY specificity DESC` without multi-column sort expressions. Values up to 99,999 sort correctly. Consumers can unpack via `json_extract(specificity, '$[0]')`.

### Hierarchy

Adjacency list (parent_id) as source of truth, plus a closure table (`entity_closure`) for fast descendant queries. The closure table is rebuilt after entity population:

```sql
DELETE FROM entity_closure;
INSERT INTO entity_closure
WITH RECURSIVE closure(ancestor_id, descendant_id, depth) AS (
    SELECT id, id, 0 FROM entities
    UNION ALL
    SELECT c.ancestor_id, e.id, c.depth + 1
    FROM closure c JOIN entities e ON e.parent_id = c.descendant_id
)
SELECT * FROM closure;
```

SQLite has supported `WITH RECURSIVE` since 3.8.3 (2014).

## Compiler Design

### Selector → SQL Translation

The compiler walks umwelt's AST (`ComplexSelector` → `CompoundPart` → `SimpleSelector`) and emits PyPika `Criterion` objects. The dialect module converts these to SQL strings.

| CSS Construct | SQL Output (SQLite dialect) |
|---|---|
| `file` | `e.type_name = 'file'` |
| `tool#Read` | `e.type_name = 'tool' AND e.entity_id = 'Read'` |
| `mode.implement` | `e.type_name = 'mode' AND EXISTS(SELECT 1 FROM json_each(e.classes) WHERE value='implement')` |
| `file[path^="src/"]` | `e.type_name = 'file' AND json_extract(e.attributes, '$.path') LIKE 'src/%'` |
| `file:glob("*.py")` | `json_extract(e.attributes, '$.path') LIKE '%.py'` |
| `mode.explore tool` | Context qualifier: `EXISTS(SELECT 1 FROM entities q0 WHERE ...) AND e.type_name='tool'` |
| `dir[name="src"] file` | Structural ancestor: `EXISTS(... JOIN entity_closure ec ON ... WHERE ec.depth > 0 AND ...)` |

### PyPika's Role

PyPika builds `Criterion` objects that abstract dialect differences:

- `json_extract(attributes, '$.path')` (SQLite) vs `attributes['path']` (DuckDB)
- `EXISTS(SELECT 1 FROM json_each(classes) WHERE value='x')` (SQLite) vs `list_contains(classes, 'x')` (DuckDB)
- Proper value escaping (no manual string replacement)
- Composable query fragments

### Cascade Candidates

Unlike ducklog (which creates `cascade_candidates` as a UNION ALL VIEW for lazy evaluation), the SQL compiler materializes candidates as INSERT statements. This is better for SQLite because the resolution views query `cascade_candidates` multiple times — materialized rows avoid re-evaluating selector matches.

### Dialect System

```python
# dialects.py provides per-dialect expression helpers
class SQLiteDialect:
    def json_attr(self, alias, key): ...      # json_extract(alias.attributes, '$.key')
    def list_contains(self, alias, col, val): ... # EXISTS(SELECT 1 FROM json_each(...))
    def distinct_on(self, ...): ...           # ROW_NUMBER() OVER(...) = 1

class DuckDBDialect:
    def json_attr(self, alias, key): ...      # alias.attributes['key']
    def list_contains(self, alias, col, val): ... # list_contains(alias.col, 'val')
    def distinct_on(self, ...): ...           # DISTINCT ON(...)
```

## Entity Population

The `populate.py` module bridges umwelt's Matcher registry to SQL INSERTs.

```python
def populate_entities(con, base_dir: Path) -> None:
    """Query all registered matchers and INSERT their entities."""
```

Flow:
1. Iterate registered matchers from the registry (WorldMatcher, CapabilityMatcher, StateMatcher, etc.)
2. Each matcher's `match()` yields entity objects
3. Serialize each entity to a row: `(taxon, type_name, entity_id, classes_json, attributes_json, parent_id)`
4. Batch INSERT
5. Rebuild closure table

Plugin-registered matchers participate automatically. No hardcoded entity lists.

## CLI Integration

```
umwelt compile <file.umw> --target sqlite|duckdb [-o <file>] [--db <connection>]
```

| Flags | Behavior |
|---|---|
| `--target sqlite` | SQL text to stdout |
| `--target sqlite -o policy.sql` | SQL text to file |
| `--target sqlite --db policy.db` | Execute against SQLite database |
| `--target sqlite -o policy.sql --db policy.db` | Both: write SQL file + create database |
| `--target duckdb` | DuckDB SQL text to stdout (no duckdb dependency) |
| `--target duckdb --db policy.duckdb` | Execute against DuckDB (requires `duckdb` package) |
| `--target postgres --db postgresql://...` | Execute via SQLAlchemy (requires `sqlalchemy` + driver) |

If `--target` is omitted and `--db` is provided, infer dialect from file extension (`.db`/`.sqlite` → sqlite, `.duckdb` → duckdb).

Default target: `sqlite`.

### `--db` Connection Strategy

| Target | `--db` driver |
|---|---|
| sqlite | `sqlite3` (stdlib, always available) |
| duckdb | `duckdb` package (optional) |
| anything else | `sqlalchemy` + appropriate driver (optional) |

## Dependencies

```toml
[project.optional-dependencies]
sql = ["pypika>=0.48"]
duckdb = ["umwelt[sql]", "duckdb>=1.0"]
sqldb = ["umwelt[sql]", "sqlalchemy>=2.0"]
```

Core umwelt remains at `tinycss2` only. The `[sql]` extras group adds PyPika (~61KB). SQLite `--db` execution works at the `[sql]` tier since `sqlite3` is stdlib.

## Testing Strategy

All tests use `sqlite3.connect(":memory:")` — no temp files.

### Unit Tests (`tests/test_compilers_sql/`)

- **`test_schema.py`** — DDL executes cleanly on SQLite, tables exist with correct columns
- **`test_compiler.py`** — Port ducklog's 34 selector-to-SQL tests. CSS selector → SQL WHERE clause → verify against known entities. TDD ladder: type, id, class, attribute operators, pseudo-classes, context qualifiers, structural descent
- **`test_resolution.py`** — Exact wins by specificity, `<=` takes MIN, `pattern-in` unions. Specificity JSON array ordering is correct
- **`test_populate.py`** — Registered matchers produce correct entity rows
- **`test_roundtrip.py`** — Port ducklog's 15 round-trip tests: `.umw` → SQL → query resolved properties → verify values

### Integration Tests

- Port ducklog's 8 bwrap enforcement tests (if bwrap available): `.umw` → SQLite db → query file permissions → verify against real sandbox

## Migration Path

### Phase 1 (this spec)
- Build `umwelt.compilers.sql` with SQLite + DuckDB dialects
- CLI `--target sqlite` and `--target duckdb`
- Tests ported from ducklog

### Phase 2 (future)
- `reader.py` — Python API over the database (query helpers returning dicts)
- nsjail/bwrap/lackpy compilers optionally read from SQL database instead of Python `ResolvedView`
- Consumer adapters move to their respective tool repos (kibitzer, lackpy)

### Phase 3 (future)
- `ducklog` repo archived
- SQL database becomes the canonical IR
- Python resolver optionally replaced by SQL resolution

## Minimum SQLite Version

**3.38** (2022-02-22) — required for built-in JSON functions (`json_extract`, `json_each`). Ships with Python 3.11+.

## What This Does NOT Change

- The existing Python cascade resolver (`cascade/resolver.py`)
- The existing nsjail/bwrap/lackpy compilers (they still consume `ResolvedView`)
- The `Compiler` protocol or registry
- Core umwelt's dependency profile (tinycss2 only)
- The plugin registration pattern (taxa, entities, properties, matchers, compilers)
