# SQL Schema Reference

The SQL compiler produces a SQLite database with a fixed schema. This page documents every table, view, column, and index.

## Overview

The schema has three layers:

1. **Vocabulary tables** — describe the registered taxa, entity types, and property types. Metadata about what *can* exist.
2. **Entity tables** — the materialized world model. What *does* exist right now.
3. **Cascade tables and views** — policy evaluation. Which rules matched which entities, and which values won.

```
vocabulary        entities           cascade
┌──────────┐     ┌──────────┐      ┌────────────────────┐
│ taxa     │     │ entities │──┐   │ cascade_candidates  │
│ entity_  │     │          │  │   │                     │
│  types   │     └──────────┘  │   └────────────────────┘
│ property │     ┌──────────┐  │           │
│  _types  │     │ entity_  │──┘   ┌───────┴────────┐
└──────────┘     │ closure  │      │ resolved_      │
                 └──────────┘      │ properties     │
                                   └────────────────┘
```

## Vocabulary Tables

### `taxa`

Registered taxonomy namespaces. One row per taxon (e.g., `world`, `capability`, `state`).

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT, PK | Taxon identifier |
| `canonical` | TEXT | Canonical name (if aliased) |
| `vsm_system` | TEXT | VSM system mapping |
| `description` | TEXT | Human-readable description |

### `entity_types`

Registered entity types within each taxon.

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT, NOT NULL | Entity type name (e.g., `file`, `tool`) |
| `taxon` | TEXT, NOT NULL, FK → taxa | Owning taxon |
| `parent_type` | TEXT | Parent in the type hierarchy (e.g., `file` → `dir`) |
| `category` | TEXT | Grouping category |
| `description` | TEXT | Human-readable description |

Primary key: `(taxon, name)`

### `property_types`

Declared properties for each entity type.

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT, NOT NULL | Property name (e.g., `editable`, `max-level`) |
| `taxon` | TEXT, NOT NULL | Owning taxon |
| `entity_type` | TEXT, NOT NULL | Entity type this property applies to |
| `value_type` | TEXT, NOT NULL | Expected value type |
| `comparison` | TEXT, DEFAULT `'exact'` | Resolution strategy: `exact`, `<=`, `pattern-in` |
| `description` | TEXT | Human-readable description |

Primary key: `(taxon, entity_type, name)`

## Entity Tables

### `entities`

The materialized world model. One row per entity discovered by the matchers.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER, PK, AUTOINCREMENT | Internal row ID |
| `taxon` | TEXT, NOT NULL | Owning taxon |
| `type_name` | TEXT, NOT NULL | Entity type (e.g., `file`, `tool`, `mode`) |
| `entity_id` | TEXT | Logical identity (file path, tool name, etc.) |
| `classes` | TEXT (JSON array) | CSS-like class labels, e.g., `["test","python"]` |
| `attributes` | TEXT (JSON object) | All entity attributes, e.g., `{"path":"src/main.py","language":"python"}` |
| `parent_id` | INTEGER, FK → entities | Parent entity for structural descent |
| `depth` | INTEGER, DEFAULT 0 | Depth in the entity tree |

Indexes: `taxon`, `type_name`, `entity_id`, `parent_id`

#### JSON column conventions

The `classes` and `attributes` columns store JSON text. Selectors query them via SQLite's `json_extract` and `json_each`:

```sql
-- Attribute selector: file[path^="src/"]
json_extract(e.attributes, '$.path') LIKE 'src/%' ESCAPE '\'

-- Class selector: file.test
EXISTS(SELECT 1 FROM json_each(e.classes) WHERE value = 'test')

-- List-contains: file[tags~="important"]
EXISTS(SELECT 1 FROM json_each(json_extract(e.attributes, '$.tags'))
       WHERE value = 'important')
```

### `entity_closure`

Transitive closure of the `parent_id` hierarchy. Pre-computed for efficient structural-descent queries (`dir[name="src"] file`).

| Column | Type | Description |
|--------|------|-------------|
| `ancestor_id` | INTEGER, NOT NULL, FK → entities | Ancestor entity |
| `descendant_id` | INTEGER, NOT NULL, FK → entities | Descendant entity |
| `depth` | INTEGER, NOT NULL | Steps between ancestor and descendant (0 = self) |

Primary key: `(ancestor_id, descendant_id)`

Every entity has a self-referencing row with `depth = 0`. A file three directories deep has closure rows at depths 0, 1, 2, and 3.

## Cascade Tables

### `cascade_candidates`

Every (entity, property, value) combination that a rule matched. This is the raw output of selector evaluation before resolution. Multiple rows can exist for the same entity and property — the resolution views pick winners.

| Column | Type | Description |
|--------|------|-------------|
| `entity_id` | INTEGER, NOT NULL, FK → entities | Matched entity |
| `property_name` | TEXT, NOT NULL | Property being set |
| `property_value` | TEXT, NOT NULL | Declared value |
| `comparison` | TEXT, NOT NULL, DEFAULT `'exact'` | Resolution strategy |
| `specificity` | TEXT, NOT NULL | JSON array of zero-padded integers for lexicographic ordering |
| `rule_index` | INTEGER, NOT NULL | Document order (0-based) |
| `source_file` | TEXT | Source `.umw` file path |
| `source_line` | INTEGER | Line number in source |

Indexes: `(entity_id, property_name)`, `comparison`

#### Comparison types

The `comparison` column determines how competing values for the same (entity, property) pair are resolved:

| Comparison | Meaning | Resolution |
|------------|---------|------------|
| `exact` | Last-writer-wins | Highest specificity wins; document order breaks ties |
| `<=` | Tightest bound | Smallest numeric value wins (used for `max-*` properties) |
| `pattern-in` | Set union | All values are concatenated (used for `allow-pattern`, `deny-pattern`) |

#### Specificity encoding

Specificity is an 8-element tuple stored as a JSON array of 5-digit zero-padded strings:

```json
["00001","00000","00100","00000","00000","00001","00000","00000"]
```

This encoding enables correct lexicographic ordering via string comparison — SQLite's `ORDER BY specificity DESC` produces the same result as tuple comparison.

## Resolution Views

Resolution views are created after cascade candidates are populated. They implement comparison-aware winner selection.

### `_resolved_exact`

Picks one winner per (entity, property) for `comparison = 'exact'`. Uses `ROW_NUMBER() OVER (PARTITION BY entity_id, property_name ORDER BY specificity DESC, rule_index DESC)` — highest specificity wins, document order breaks ties.

### `_resolved_cap`

Picks the tightest bound per (entity, property) for `comparison = '<='`. Orders by `CAST(property_value AS INTEGER) ASC` — smallest numeric value wins.

### `_resolved_pattern`

Aggregates all values per (entity, property) for `comparison = 'pattern-in'`. Uses `GROUP_CONCAT(DISTINCT property_value)` to produce a comma-separated set union.

### `resolved_properties`

The final query surface. Union of the three resolution views above:

```sql
SELECT * FROM _resolved_exact
UNION ALL SELECT * FROM _resolved_cap
UNION ALL SELECT * FROM _resolved_pattern
```

| Column | Type | Description |
|--------|------|-------------|
| `entity_id` | INTEGER | Matched entity |
| `property_name` | TEXT | Property name |
| `property_value` | TEXT | Winning value |
| `comparison` | TEXT | Resolution strategy used |
| `specificity` | TEXT | Winning specificity |
| `rule_index` | INTEGER | Winning rule's document order |
| `source_file` | TEXT | Source file of the winning rule |
| `source_line` | INTEGER | Source line of the winning rule |

**Invariant (A1):** Every `(entity_id, property_name)` pair appears at most once in `resolved_properties`. This is the single-winner guarantee.

## Common Queries

### Look up a resolved property

```sql
SELECT rp.property_value
FROM resolved_properties rp
JOIN entities e ON rp.entity_id = e.id
WHERE e.entity_id = 'src/auth.py' AND rp.property_name = 'editable';
```

### List all properties for an entity

```sql
SELECT rp.property_name, rp.property_value
FROM resolved_properties rp
JOIN entities e ON rp.entity_id = e.id
WHERE e.entity_id = 'Bash';
```

### Find entities matching a type

```sql
SELECT entity_id, json_extract(attributes, '$.path') AS path
FROM entities
WHERE type_name = 'file' AND taxon = 'world';
```

### Inspect cascade candidates (before resolution)

```sql
SELECT e.entity_id, cc.property_name, cc.property_value,
       cc.specificity, cc.rule_index
FROM cascade_candidates cc
JOIN entities e ON cc.entity_id = e.id
WHERE e.entity_id = 'src/auth.py'
ORDER BY cc.property_name, cc.specificity DESC, cc.rule_index DESC;
```

### Count entities by type

```sql
SELECT taxon, type_name, COUNT(*) AS n
FROM entities
GROUP BY taxon, type_name
ORDER BY n DESC;
```

### Check A1 invariant

```sql
SELECT entity_id, property_name, COUNT(*) AS n
FROM resolved_properties
GROUP BY entity_id, property_name
HAVING n > 1;
-- Should return zero rows
```
