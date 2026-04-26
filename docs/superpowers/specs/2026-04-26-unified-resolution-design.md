# Unified Resolution Model — Design Specification

*Replacing mode-specific plumbing with a generic context-qualifier mechanism and bridging table/predicate resolution paths.*

## Problem

umwelt has two resolution paths that don't compose:

**Table mode** (SQL/PolicyEngine): All entities declared upfront, cascade pre-computed, queries are lookups. Fast, auditable, traceable. But can't handle entities that don't exist yet.

**Predicate mode** (matcher/in-memory): Selectors evaluated on-demand against matchers. Handles runtime entities (AST nodes, HTML tags, query rows). But no audit trail, no trace, no candidates table.

Between them, **mode filtering** is special-cased: `_extract_mode_qualifier` hardcodes `type_name == "mode"`, the schema has a `mode_qualifier` column, and the query API has a `mode` parameter. This violates core's vocabulary-agnostic principle. Any entity type used as a cross-taxon context qualifier should get the same treatment.

## Design Principles

1. **Core is vocabulary-agnostic.** No entity type name appears in core code. Not `mode`, not `world`, not `file`.
2. **Same policy, same answer.** Whether an entity is resolved via table lookup or predicate evaluation, the cascade must produce identical results.
3. **Context qualifiers are generic.** Any entity can gate a rule. The mechanism is the selector engine, not a special column.
4. **On-demand entities are first-class.** Asking "what would the policy say about this entity?" shouldn't require materializing it into a table.

## Current Architecture (v0.6)

### Selector classification

At parse time (`selector/parse.py:144-164`), each compound part is classified:

- **structural** — same taxon as previous part → parent-child navigation
- **context** — different taxon → gating condition

At evaluation time (`selector/match.py:123-126`), the classification is re-evaluated against the actual target taxon. A part acts as a context gate when `part.selector.taxon != target_taxon`.

### Resolution paths

**In-memory** (`cascade/resolver.py`): `resolve(view, eval_context, world)` walks rules, calls `match_complex()` per selector, groups matches by taxon, picks winners by specificity + document order. Context qualifiers call `matcher.condition_met()`.

**SQL** (`compilers/sql/compiler.py`): `compile_view()` compiles each selector to a WHERE clause, evaluates against the `entities` table, inserts into `cascade_candidates`. Context qualifiers compile to EXISTS subqueries. Mode qualifiers are extracted separately into `mode_qualifier`.

### Mode special-casing (to remove)

| Location | What | Line |
|---|---|---|
| `compilers/sql/schema.py` | `mode_qualifier TEXT` column on `cascade_candidates` | 108 |
| `compilers/sql/compiler.py` | `_extract_mode_qualifier()` scans for `type_name == "mode"` | 189-198 |
| `compilers/sql/compiler.py` | Stores extracted mode into `mode_qualifier` column | 171, 183 |
| `policy/queries.py` | `_MODE_FILTER = "AND (mode_qualifier IS NULL OR mode_qualifier = ?)"` | 9 |
| `policy/queries.py` | `mode` parameter on `resolve_entity`, `resolve_all_entities`, `trace_entity` | 50, 117, 151 |
| `policy/engine.py` | `mode` parameter on `resolve`, `resolve_all`, `trace`, `check`, `require` | 192, 204, 221, 244, 251 |

## Proposed Design

### 1. Generic context qualifiers in the SQL path

Replace `mode_qualifier` with a general `context_qualifiers` mechanism.

**Schema change:** Replace the single `mode_qualifier TEXT` column with a normalized table:

```sql
CREATE TABLE cascade_context_qualifiers (
    candidate_id INTEGER NOT NULL REFERENCES cascade_candidates(id),
    taxon        TEXT NOT NULL,
    type_name    TEXT NOT NULL,
    entity_id    TEXT NOT NULL
);
CREATE INDEX idx_ccq_candidate ON cascade_context_qualifiers(candidate_id);
CREATE INDEX idx_ccq_lookup ON cascade_context_qualifiers(taxon, type_name, entity_id);
```

**Compiler change:** Replace `_extract_mode_qualifier()` with `_extract_context_qualifiers()` that finds ALL cross-taxon context parts in a selector, not just mode:

```python
def _extract_context_qualifiers(selector: ComplexSelector) -> list[tuple[str, str, str]]:
    """Extract (taxon, type_name, entity_id) for all context qualifier parts."""
    qualifiers = []
    for part in selector.parts:
        if (part.mode == "context"
            and part.selector.id_value is not None):
            qualifiers.append((
                part.selector.taxon,
                part.selector.type_name,
                part.selector.id_value,
            ))
    return qualifiers
```

After inserting a `cascade_candidates` row, insert one `cascade_context_qualifiers` row per qualifier.

**Query change:** Replace `_MODE_FILTER` with a generic filter that checks whether ALL required context qualifiers are active:

```sql
-- A candidate is eligible when every qualifier it requires is in the active set
AND NOT EXISTS (
    SELECT 1 FROM cascade_context_qualifiers ccq
    WHERE ccq.candidate_id = cc.id
    AND NOT EXISTS (
        SELECT 1 FROM active_context
        WHERE taxon = ccq.taxon
          AND type_name = ccq.type_name
          AND entity_id = ccq.entity_id
    )
)
```

The `active_context` is a temporary table populated by the caller before querying.

### 2. PolicyEngine API change

Replace the `mode` parameter with a generic `context` parameter:

```python
# Before (v0.6 — deprecated)
engine.resolve(type="tool", id="Bash", property="allow", mode="review")

# After (v0.7+)
engine.resolve(type="tool", id="Bash", property="allow",
               context=[("state", "mode", "review")])

# Or with a convenience helper:
engine.resolve(type="tool", id="Bash", property="allow",
               context={"mode": "review"})
```

The `context` parameter is a list of `(taxon, type_name, entity_id)` tuples — or a dict that resolves entity types through the registry. This replaces the mode-specific parameter with one that works for any context qualifier:

```python
# Mode + principal + world environment — all generic
engine.resolve(
    type="tool", id="Bash", property="allow",
    context={
        "mode": "review",
        "principal": "Teague",
        "world": "ci",
    },
)
```

**Migration:** Accept both `mode=` (deprecated, translates to context) and `context=` during the transition period. Remove `mode=` before 1.0.

### 3. Predicate resolution with audit trail

For on-demand entities (not in the entities table), add a `resolve_hypothetical` path:

```python
engine.resolve_hypothetical(
    entity={"type": "file", "id": "/tmp/new.py", "classes": ["generated"],
            "attributes": {"path": "/tmp/new.py", "language": "python"}},
    property="editable",
    context={"mode": "implement"},
)
```

Implementation: temporarily insert the entity, evaluate the cascade against it, return the result, roll back. SQLite's transaction isolation makes this cheap. The entity never persists, but the resolution follows the same code path as table mode — same answer, full traceability.

For high-throughput predicate evaluation (AST nodes, HTML tags), this per-entity approach is too slow. The matcher path remains the right choice for bulk on-demand evaluation. The goal isn't to replace it — it's to ensure that when a consumer *needs* auditability for a single on-demand entity, they can get it without materializing an entire world.

### 4. Context resolution from the world

"What mode is active?" becomes a resolution question, not a parameter:

```python
# The world file declares modes
# modes: [implement, review, test]

# The stylesheet sets which is active based on context
# principal#Teague mode { active: implement; }

# Consumer resolves the active mode
active = engine.resolve(type="mode", id="*", property="active")
# Then uses it as context for subsequent queries
engine.resolve(type="tool", id="Bash", property="allow",
               context={"mode": active})
```

This two-step pattern (resolve what's active, then use it as context) is explicit and composable. The policy itself determines what's active — not a hardcoded parameter.

For convenience, `engine.resolve_in_context()` could chain these:

```python
# Resolves active context from the world, then applies it
engine.resolve_in_context(type="tool", id="Bash", property="allow")
```

But the two-step version remains available for consumers that need to control context explicitly.

## Migration Path

### Phase 1: Add generic context (non-breaking)

- Add `cascade_context_qualifiers` table alongside `mode_qualifier`
- Populate both during compilation (backward compatible)
- Add `context` parameter to PolicyEngine methods
- `mode=` continues to work, translated internally to context

### Phase 2: Deprecate mode parameter

- Emit deprecation warning on `mode=` usage
- Documentation references `context=` exclusively
- Update all consumers (kibitzer, lackpy, etc.)

### Phase 3: Remove mode-specific code (breaking)

- Drop `mode_qualifier` column from `cascade_candidates`
- Remove `_extract_mode_qualifier()`, `_MODE_FILTER`
- Remove `mode=` parameter from all methods
- Bump to 1.0

## What This Doesn't Address

- **Matcher composability with audit trails** — the in-memory matcher path still can't produce `cascade_candidates`-style trace data. Bridging this fully is a deeper architectural question (instrumenting matchers to emit candidates) that's out of scope here.
- **Predicate-mode bulk evaluation** — evaluating thousands of on-demand entities (AST nodes in a large file) through `resolve_hypothetical` would be too slow. The matcher path remains necessary for bulk cases. The design ensures the two paths agree, not that they're interchangeable for all workloads.
- **Multi-context composition** — when multiple contexts are active simultaneously (e.g., two principals in a delegation chain), the semantics of "all qualifiers must match" vs "any qualifier matches" needs further design.
- **Schema migration tooling** — compiled `.db` files from v0.6 will need migration when `mode_qualifier` is dropped. The `from_db()` path should detect and migrate transparently.

## Files Affected

| File | Change |
|---|---|
| `compilers/sql/schema.py` | Add `cascade_context_qualifiers` table |
| `compilers/sql/compiler.py` | Replace `_extract_mode_qualifier` with `_extract_context_qualifiers` |
| `policy/queries.py` | Replace `_MODE_FILTER` with generic qualifier filter, add `context` parameter |
| `policy/engine.py` | Add `context` parameter to all query methods, deprecate `mode` |
| `policy/engine.py` | Add `resolve_hypothetical()` method |
| `compilers/sql/resolution.py` | Update resolution views to join through context qualifiers |
| `tests/policy/test_mode_filtering.py` | Migrate to `context=` API |
| `tests/policy/test_context_qualifiers.py` | New: generic context qualifier tests |
| `tests/policy/test_hypothetical.py` | New: on-demand resolution tests |
