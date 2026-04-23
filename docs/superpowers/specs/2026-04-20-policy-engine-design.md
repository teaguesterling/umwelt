# PolicyEngine Design — Knowledge Query API + SQL Compiler Extensions

*Extends umwelt's existing `compilers/sql/` module with a consumer-facing Python API (`umwelt.policy`) for querying resolved world knowledge, adds typed projection views, lint analysis, structured logging for audit, and integrates world file entity population. Replaces the standalone ducklog package.*

**Status:** draft, pre-implementation.
**Date:** 2026-04-20.
**Depends on:** `compilers/sql/` (merged, PR #4), `world/` layer (merged, PR #7), `docs/vision/world-state.md`.
**Prerequisite:** Phase 1 world state layer complete (YAML parser, materializer, validator, CLI).
**Next step after approval:** invoke `writing-plans` to produce a concrete implementation plan.

---

## 1. Motivation and scope

Umwelt's SQL compiler (`compilers/sql/`) already compiles CSS selectors to SQL WHERE clauses, populates entities from matchers, and resolves cascade properties in SQLite. But there is no consumer-facing API — the only way to read results is via CLI output or raw SQL queries against the compiled database.

Meanwhile, ducklog exists as a separate package doing largely the same compilation for DuckDB, plus consumer packages for Kibitzer and Lackpy that translate SQL views into tool-specific config dicts. This duplication is unnecessary now that umwelt has its own SQL compiler.

This design introduces:

1. **`umwelt.policy.PolicyEngine`** — the consumer-facing Python API. Wraps a compiled SQLite database. Provides knowledge queries (resolve entity properties), trace (explain why a value won), and lint (detect knowledge quality issues).
2. **Typed projection views** — vocabulary-driven SQL views (tools, files, modes, kibitzer_modes) embedded in the compiled database, making it self-contained and queryable without Python.
3. **World file entity population** — entities from `.world.yml` files feed into the SQL database alongside matcher-discovered entities.
4. **Structured logging** — audit observability via stdlib `logging`, not a custom audit module. Consumers attach handlers.
5. **Lint analysis** — Python module that detects fragile or surprising cascade resolutions.

### Deliverables

1. **`umwelt.policy` subpackage** (§3) — PolicyEngine class with three constructors, knowledge query methods, COW extend semantics.
2. **Knowledge query model** (§4) — entity path queries, bulk resolution, trace.
3. **Typed projection views** (§5) — vocabulary-driven pivot views in the compiled database.
4. **Lint module** (§6) — smell detection over cascade_candidates.
5. **World file population path** (§7) — DeclaredEntity → entities table.
6. **Observability** (§8) — structured logging via `umwelt.policy` logger.
7. **Compilation pipeline** (§9) — three paths into a PolicyEngine.
8. **Round-trip** (§10) — `to_files()` for exporting back to source format.

### Explicit non-goals

- **Generator plugin protocol.** The three-tier generator protocol (enumerate/define_query/query) is a future design. This spec builds the infrastructure generators will plug into, but does not define the plugin interface.
- **Full ancestor/depth vocabulary extension.** The ancestor/depth model for entity hierarchy (§11) is documented here as a design direction. Implementation is deferred — the existing parent_id/entity_closure mechanism continues to work.
- **CSS selector parsing at query time.** CSS is the authoring language for policy. The SQL engine evaluates compiled selectors. The PolicyEngine accepts CSS selector strings as a convenience (parsed in Python, compiled to structured queries), but no CSS parsing happens in SQL.
- **DuckDB parity.** SQLite is the default and primary target. DuckDB support continues via the dialect abstraction but is not extended in this spec.
- **Kibitzer/Lackpy adapter packages.** Those live in each tool's repo. This spec defines the API they consume, not their adapters.

---

## 2. Architecture

### Layering

```
┌─────────────────────────────────────────────────────────────┐
│  Consumers: Kibitzer, Lackpy, CLI, custom tools             │
│  (import umwelt.policy or query .db directly with SQL)      │
└──────────────────────────┬─────────��────────────────────────┘
                           │
┌──────────────────────────▼──────────────��─────────────────���─┐
│  umwelt.policy  (this spec)                                  │
│  PolicyEngine: constructors, resolve, trace, lint, extend    │
│  Structured logging via stdlib logging                       │
└──────────────────────────┬─────────────────────────────────���┘
                           │
┌──────────────────────────▼──────��──────────────────���────────┐
│  umwelt.compilers.sql  (existing, unchanged)                 │
│  Schema DDL, selector→SQL, entity population, resolution     │
│  Dialect abstraction (SQLite, DuckDB)                        │
└─────────────��────────────┬──────��───────────────────────────┘
                           │
┌──────���───────────────────▼─────���────────────────────────────┐
│  SQLite database                                             │
│  entities, cascade_candidates, resolved_properties,          │
│  typed projection views                                      │
└──────────────��────────────────────────────────────────���─────┘
```

### Key boundaries

| Component | Responsibility | Depends on |
|---|---|---|
| `compilers/sql/` | CSS → SQL compilation, schema DDL, entity population, resolution views | `ast`, `selector`, `registry` |
| `policy/engine.py` | Lifecycle management, COW semantics, query dispatch | `compilers/sql/`, `world/` |
| `policy/queries.py` | Structured entity/resolution queries → SQL | `sqlite3` only |
| `policy/lint.py` | Smell detection over cascade_candidates | `sqlite3`, `json` |
| `policy/projections.py` | Vocabulary-driven typed projection view DDL | `compilers/sql/dialects` |

### File layout

```
src/umwelt/policy/
├── __init__.py          # Public API: PolicyEngine, LintWarning
├── engine.py            # PolicyEngine class
├── queries.py           # Structured query builders
├── lint.py              # Cascade smell detection
└── projections.py       # Typed projection view DDL generation
```

### What stays in `compilers/sql/`

Everything that exists today — schema, selector compilation, dialect abstraction, entity population, resolution views. No changes needed. The `policy/` package is a layer on top.

---

## 3. PolicyEngine class

### Constructors

**From source files (author time):**

```python
engine = PolicyEngine.from_files(
    world="delegate.world.yml",
    stylesheet="policy.umw",
)
```

Pipeline: parse world YAML → register vocabulary → populate entities → parse CSS → compile selectors to cascade_candidates → create resolution views → create projection views → ready to query.

**From compiled database (consumer time):**

```python
engine = PolicyEngine.from_db("policy.db")
```

Opens existing compiled database. The database is copied into memory on open (COW safety — the source file is never modified). No compilation needed. Immediate query access. For v1, all engines operate on in-memory SQLite databases; large-database support (memory-mapped or file-backed COW) is a future optimization.

**Programmatic (runtime):**

```python
engine = PolicyEngine()
engine.register_vocabulary(register_sandbox_vocabulary)
engine.add_entities([
    {"type": "tool", "id": "Read"},
    {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
    {"type": "mode", "id": "implement"},
])
engine.add_stylesheet("tool.dangerous { max-level: 2; }")
```

### COW extend

Mutations produce a new engine. The original is unchanged.

```python
engine2 = engine.extend(
    entities=[{"type": "mode", "id": "review"}],
    stylesheet='mode#review tool.dangerous { allow: false; }',
)
# engine is unchanged — engine2 has the new state
```

Implementation: `extend()` copies the SQLite database (in-memory or to a temp file), applies mutations to the copy, recompiles cascade_candidates and resolution views, returns a new PolicyEngine wrapping the copy.

### Save and export

```python
# Save compiled database
engine.save("policy.db")

# Export back to source files
engine.to_files(world="delegate.world.yml", stylesheet="policy.umw")
```

### Raw SQL escape hatch

```python
# Direct database access for custom queries
rows = engine.execute("SELECT * FROM resolved_properties WHERE property_name = 'allow'")
```

The compiled database is always accessible. The convenience methods handle the common cases; raw SQL handles everything else.

---

## 4. Knowledge query model

**Core principle: the engine resolves knowledge. Consumers interpret values and decide what to enforce.**

The cascade doesn't just resolve allow/deny — it resolves any property to any value. Permission properties (`allow`, `editable`), constraints (`max-level`, `limit`), behavioral guidance (`strategy`, `risk-note`), and informational metadata (`description`, `convention`) all resolve the same way through the CSS cascade.

A consumer asking `engine.resolve('tool#Bash', "risk-note")` gets back `"Prefer structured tools"` — that is knowledge, not enforcement. The consumer decides what to do with it.

### Query as entity path

A query describes a position in the entity hierarchy — a path from ancestor to target entity. The engine resolves properties at the deepest matching entity.

**CSS selector string (parsed in Python):**

```python
engine.resolve('file[path="src/foo.py"] ast .fn#special', "editable")
```

**Structured path (list of dicts — what gets sent to SQL):**

```python
engine.resolve([
    {"type": "file", "attributes": {"path": "src/foo.py"}},
    {"type": "ast"},
    {"classes": ["fn"], "id": "special"}
], "editable")
```

**Simple case — type + id:**

```python
engine.resolve(type="tool", id="Bash", property="max-level")
```

All three forms are equivalent. The CSS string is parsed in Python and converted to the structured path, which is compiled to a SQL query with entity_closure JOINs.

### API methods

**resolve — single entity, single or all properties:**

```python
# Single property
engine.resolve('tool#Bash', "max-level")  # → "3"

# All properties for an entity
engine.resolve('tool#Bash')
# → {"allow": "true", "max-level": "3", "effects-ceiling": "filesystem",
#     "description": "Shell execution", "risk-note": "Prefer structured tools"}
```

**resolve_all — bulk query:**

```python
# All entities of a type with resolved properties
engine.resolve_all(type="tool")
# → [{"entity": {...}, "properties": {"allow": "true", ...}}, ...]

# With structured filters
engine.resolve_all(type="file", attributes={"path": ("^=", "src/")})
```

**trace — explain a resolution:**

```python
result = engine.trace('tool#Bash', "max-level")
# result.value = "3"
# result.candidates = [
#   Candidate(value="5", rule="tool { max-level: 5; }", specificity=(...), won=False),
#   Candidate(value="3", rule="tool#Bash { max-level: 3; }", specificity=(...), won=True),
# ]
```

Trace reads from `cascade_candidates` (the pre-aggregation table) rather than `resolved_properties` (the post-aggregation view). This shows all competing rules, not just the winner.

### Convenience methods for common consumer patterns

```python
# Check — returns True/False for a specific expected value
engine.check('file[path="src/foo.py"]', editable=True)  # → False

# Require — raises PolicyDenied if check fails
engine.require('file[path="src/foo.py"]', editable=True)
# → raises PolicyDenied(entity=..., property="editable", expected="true", actual="false", trace=[...])
```

These are thin wrappers over `resolve()`. The engine provides them as conveniences; consumers can also implement their own enforcement logic using `resolve()` directly.

### Consumer enforcement examples

```python
# Kibitzer — reads knowledge, enforces in its path guard
props = engine.resolve('file[path="src/foo.py"]')
if props.get("editable") == "false":
    deny_write(reason="policy says not editable")

# Lackpy — reads constraints, caps its own grade
max_level = int(engine.resolve('tool#Bash', "max-level") or "5")
toolspec.grade_w = min(toolspec.grade_w, max_level)

# Kibitzer coach — reads guidance, surfaces to agent
note = engine.resolve('tool#Bash', "risk-note")
if note:
    suggest(f"Consider: {note}")
```

---

## 5. Typed projection views

Consumer-friendly SQL views created at compile time and embedded in the database. These make the compiled database self-contained — any SQLite client can query `SELECT * FROM tools` without importing umwelt.

### Vocabulary-driven generation

Projection views are generated from the registered property schemas. When a vocabulary defines properties for entity type `tool`, the compiler generates:

```sql
CREATE VIEW tools AS
SELECT e.id, e.entity_id AS name, e.classes, e.attributes,
    MAX(CASE WHEN rp.property_name = 'allow' THEN rp.property_value END) AS allow,
    MAX(CASE WHEN rp.property_name = 'visible' THEN rp.property_value END) AS visible,
    MAX(CASE WHEN rp.property_name = 'max-level' THEN rp.property_value END) AS max_level,
    MAX(CASE WHEN rp.property_name = 'allow-pattern' THEN rp.property_value END) AS allow_pattern,
    MAX(CASE WHEN rp.property_name = 'deny-pattern' THEN rp.property_value END) AS deny_pattern
FROM entities e
LEFT JOIN resolved_properties rp ON e.id = rp.entity_id
WHERE e.type_name = 'tool'
GROUP BY e.id, e.entity_id, e.classes, e.attributes;
```

Similarly for `files`, `modes`, `resources`. The column list comes from the property_types table — each registered property becomes a pivoted column.

Custom vocabularies get custom views. A plugin that registers entity type `ast` with properties `complexity` and `test-coverage` would get a `CREATE VIEW ast_entities AS ...` with those columns.

### Consumer-specific views

Views tailored to specific consumers, also vocabulary-driven:

```sql
-- Kibitzer: mode definitions with writable paths and strategy
CREATE VIEW kibitzer_modes AS
SELECT e.entity_id AS mode_name,
    MAX(CASE WHEN rp.property_name = 'writable' THEN rp.property_value END) AS writable,
    MAX(CASE WHEN rp.property_name = 'strategy' THEN rp.property_value END) AS strategy
FROM entities e
LEFT JOIN resolved_properties rp ON e.id = rp.entity_id
WHERE e.type_name = 'mode'
GROUP BY e.entity_id;
```

These can be registered by consumers via the vocabulary system or generated from a projection schema. The compiled database includes all registered projection views.

### Generic resolved_entities view

For consumers that want all entities with all resolved properties as a single map:

```sql
CREATE VIEW resolved_entities AS
SELECT e.id, e.taxon, e.type_name, e.entity_id, e.classes, e.attributes,
    json_group_object(rp.property_name, rp.property_value) AS properties
FROM entities e
LEFT JOIN resolved_properties rp ON e.id = rp.entity_id
GROUP BY e.id, e.taxon, e.type_name, e.entity_id, e.classes, e.attributes;
```

### Compilation metadata

```sql
CREATE TABLE compilation_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Populated at compile time:
-- umwelt_version, compiled_at, source_world, source_stylesheet,
-- entity_count, resolved_count, dialect
```

---

## 6. Lint analysis

Lint detects knowledge quality issues by analyzing cascade_candidates and resolved_properties. It runs in Python, not SQL — it needs to compare candidates across entities and detect patterns.

### API

```python
warnings = engine.lint()
# �� list[LintWarning]
```

Each `LintWarning` has: `type` (string), `severity` ("info" | "warning"), `description` (human-readable), `entities` (affected entity IDs), `candidates` (relevant cascade_candidates rows).

### Smell catalog

| Smell | Detection | Severity |
|---|---|---|
| **narrow_win** | Winner's specificity minus runner-up's specificity ≤ 1 position | warning |
| **shadowed_rule** | A (source_file, source_line) pair appears in cascade_candidates but never appears in resolved_properties | info |
| **conflicting_intent** | Two candidates for same (entity, property) have opposite values (e.g., "true" vs "false") and the winner won by source order alone (equal specificity) | warning |
| **uncovered_entity** | Entity exists in entities table but has zero rows in resolved_properties | info |
| **specificity_escalation** | 3+ candidates for same (entity, property) with strictly increasing specificity | warning |

### Implementation

`policy/lint.py` queries cascade_candidates and resolved_properties, joins them, and applies each smell detector. Results are returned as `LintWarning` objects and also emitted as log events at WARNING level via the `umwelt.policy` logger.

---

## 7. World file entity population

The existing `compilers/sql/populate.py` populates entities from registered matchers. This spec adds a parallel path: entities from parsed `.world.yml` files.

### DeclaredEntity → entities table

A `DeclaredEntity` from the world layer maps directly to an entities row:

| DeclaredEntity field | entities column | Notes |
|---|---|---|
| `type` | `type_name` | Direct mapping |
| `id` | `entity_id` | Direct mapping |
| `classes` | `classes` | Tuple → JSON array |
| `attributes` | `attributes` | Dict �� JSON object |
| `parent` | `parent_id` | Resolved via entity_id lookup |
| `provenance` | (metadata) | Stored in compilation_meta or a provenance column |

### Population function

```python
def populate_from_world(con: sqlite3.Connection, world: WorldFile) -> None:
    """Insert DeclaredEntity instances from a WorldFile into the entities table."""
```

Called during `PolicyEngine.from_files()` after `populate_entities()` (matcher population). World file entities and matcher entities coexist — if both sources produce the same (type, id) entity, the world file version wins (explicit > discovered, per the world layer's merge semantics).

### Projection population

Projections from the world file (`Projection` instances) are inserted as entities with `provenance=PROJECTED`. They participate in cascade resolution like any other entity.

---

## 8. Observability

The engine emits structured log events via Python's stdlib `logging` module. No custom audit module. Consumers attach handlers to capture what they need.

### Logger

```python
logger = logging.getLogger("umwelt.policy")
```

### Events

| Event | Level | Extra data |
|---|---|---|
| `resolve` | INFO | entity_path, property, resolved_value |
| `resolve_all` | INFO | type, filter, result_count |
| `extend` | INFO | entities_added, stylesheet_added |
| `trace` | DEBUG | entity_path, property, all candidates |
| `lint_warning` | WARNING | warning_type, entities, description |
| `compile` | INFO | source_files, entity_count, resolved_count |
| `require_denied` | WARNING | entity_path, property, expected, actual |

### Consumer handler examples

```python
# Kibitzer routes to its existing event store
handler = KibitzerStoreHandler(store)
logging.getLogger("umwelt.policy").addHandler(handler)

# CLI user writes to a file
logging.getLogger("umwelt.policy").addHandler(logging.FileHandler("audit.log"))

# No handler attached = no logging overhead
```

Consumers who want structured audit trails write a handler that captures the `extra` dict from log records. Consumers who do not care attach nothing — zero overhead.

---

## 9. Compilation pipeline

### Three paths, one database format

All three constructors produce the same SQLite database schema. The database is the universal interchange format.

**Path 1: from_files (author time)**

```
.world.yml + .umw
    ↓ parse world YAML
    ↓ register vocabulary
    ↓ create schema DDL
    ↓ populate entities (matchers + world file)
    ↓ parse CSS
    ↓ compile selectors → cascade_candidates
    ↓ create resolution views
    ↓ create projection views
    ↓ create compilation_meta
    ↓
PolicyEngine (wrapping in-memory SQLite)
```

**Path 2: from_db (consumer time)**

```
policy.db
    ↓ copy to in-memory SQLite (COW)
    ↓
PolicyEngine (wrapping in-memory copy)
```

**Path 3: programmatic (runtime)**

```
PolicyEngine()
    ↓ register_vocabulary()
    ↓ add_entities()
    �� add_stylesheet()
    ↓ (internally: compile on first query)
    ���
PolicyEngine (wrapping in-memory SQLite)
```

### Saving

```python
engine.save("policy.db")
```

Writes the in-memory database to a file. This is the "reference database" — the frozen, portable artifact. Any SQLite client can read it.

### The compiled database is self-contained

The saved `.db` file contains everything a consumer needs:

- `entities` — all entities with type, id, classes, attributes
- `entity_closure` — ancestor/descendant hierarchy
- `cascade_candidates` — all selector matches with specificity
- `resolved_properties` — winning value per (entity, property)
- Typed projection views — `tools`, `files`, `modes`, etc.
- `compilation_meta` — provenance (source files, timestamps, version)

A consumer can `sqlite3 policy.db "SELECT * FROM tools"` with no Python, no umwelt, no dependencies.

---

## 10. Round-trip: to_files()

The PolicyEngine can export its current state back to source files:

```python
engine.to_files(world="delegate.world.yml", stylesheet="policy.umw")
```

This produces:
- A `.world.yml` file with entities serialized as YAML (using shorthand syntax where applicable)
- A `.umw` file with the CSS policy declarations

This is useful for:
- Debugging ("show me what this engine actually contains")
- Migration ("I built this programmatically, now I want to version-control it")
- Diffing ("what changed between two snapshots?" — diff the YAML/CSS, not the SQL)

The round-trip is best-effort — programmatically constructed engines may not produce the same CSS that was originally authored. Entity ordering, selector formatting, and shorthand expansion may differ. The semantic content is preserved.

---

## 11. Future: ancestor/depth entity hierarchy

*This section documents a design direction. Implementation is deferred.*

The current entity hierarchy uses `parent_id` on the entities table and `entity_closure` for transitive ancestry. Parent relationships are set by matchers (filesystem convention: file's parent is its containing directory).

A more general model would let entity types declare their position in the hierarchy via vocabulary definitions:

```css
@entity mode {
    ancestor: world;
    depth: 1;           /* direct child of world — scopes everything below */
}

@entity system {
    ancestor: world;
    depth: 5;           /* default — peers with other high-level types */
}

@entity file {
    ancestor: system;
    depth: 5;           /* files live inside systems */
}

@entity ast {
    ancestor: file;
    depth: 5;           /* AST nodes live inside files */
}
```

Key properties:
- **ancestor** declares which entity type this type nests under (not necessarily direct parent).
- **depth** is relative to the ancestor — lower numbers are closer to the ancestor. Default depth (e.g., 5) leaves room for other types to be inserted between.
- A depth of 1 means tight coupling — nothing can be inserted between this type and its ancestor.
- The depth gap enables pluggable hierarchies — a new entity type can slot in at depth 3 between two types at depths 1 and 5 without restructuring.

This makes structural selectors like `world mode#edit filesystem file` work correctly even with plugin-contributed entity types, because the depth ordering validates the structural descent path.

---

## 12. Ducklog replacement path

This spec, once implemented, replaces the standalone ducklog package entirely:

| Ducklog component | Replacement |
|---|---|
| `ducklog/compiler.py` (selector→SQL) | `umwelt.compilers.sql.compiler` (already merged) |
| `ducklog/schema/policy.sql` | `umwelt.compilers.sql.schema` + `umwelt.policy.projections` |
| `ducklog/consumers/kibitzer.py` | Kibitzer's own adapter using `PolicyEngine.resolve_all(type="mode")` |
| `ducklog/consumers/lackpy.py` | Lackpy's own adapter using `PolicyEngine.resolve_all(type="tool")` |
| Live provider views (glob, read_json) | Future: generator plugin protocol (`define_query` tier) |

Consumer packages move into each tool's repository as thin adapters over the PolicyEngine API. The ducklog package can be archived once all consumers have migrated.

---

## 13. Success criteria

1. `PolicyEngine.from_files()` produces a queryable database from `.world.yml` + `.umw` source files.
2. `PolicyEngine.from_db()` opens a compiled database for immediate querying.
3. `engine.resolve()` returns correct resolved values matching the existing cascade resolver output.
4. `engine.trace()` returns all competing candidates with specificity for any (entity, property).
5. `engine.lint()` detects at least: narrow_win, shadowed_rule, uncovered_entity.
6. `engine.extend()` produces a new engine with COW semantics — original unchanged.
7. `engine.save()` produces a self-contained SQLite file queryable without Python.
8. Typed projection views are vocabulary-driven and present in the compiled database.
9. `engine.to_files()` round-trips back to `.world.yml` + `.umw`.
10. Structured log events emitted via `logging.getLogger("umwelt.policy")` for all query and mutation operations.
11. Existing `compilers/sql/` tests continue to pass unchanged.
12. Kibitzer's `load_config_from_duckdb()` can be reimplemented against the PolicyEngine API with equivalent output.
