# Plugin API Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close seven plugin API gaps that block multi-tool coexistence in the retritis ecosystem, implementing P0 through P3 features with a commit per feature.

**Architecture:** Each feature is additive — P0 items unblock P1 items (CompositeMatcher enables collections, fixed constraints enable world composition). Features are isolated enough to implement and commit independently. TDD throughout: failing test first, minimal implementation, verify, commit.

**Tech Stack:** Python 3.10+, pytest, sqlite3, PyYAML, tinycss2

---

### Task 1: P0 — CompositeMatcher

**Files:**
- Modify: `src/umwelt/registry/matchers.py:1-88`
- Modify: `src/umwelt/registry/__init__.py` (export CompositeMatcher)
- Modify: `tests/core/test_registry_matchers.py:1-67`

- [ ] **Step 1: Write failing tests for CompositeMatcher**

Add to `tests/core/test_registry_matchers.py`:

```python
from umwelt.registry.matchers import CompositeMatcher


class CountingMatcher:
    """A matcher that returns entities from a fixed list, for composition tests."""

    def __init__(self, entities: list, id_attr: str = "id"):
        self._entities = entities
        self._id_attr = id_attr

    def match_type(self, type_name: str, context=None) -> list:
        return [e for e in self._entities if getattr(e, "type_name", None) == type_name or type_name == "*"]

    def children(self, parent, child_type: str) -> list:
        return []

    def condition_met(self, selector, context=None) -> bool:
        return any(getattr(e, "active", False) for e in self._entities)

    def get_attribute(self, entity, name: str):
        return getattr(entity, name, None)

    def get_id(self, entity) -> str | None:
        return getattr(entity, self._id_attr, None)


class _SimpleEntity:
    def __init__(self, type_name, id, active=False, **attrs):
        self.type_name = type_name
        self.id = id
        self.active = active
        for k, v in attrs.items():
            setattr(self, k, v)


def test_composite_match_type_unions_results():
    m1 = CountingMatcher([_SimpleEntity("tool", "Bash")])
    m2 = CountingMatcher([_SimpleEntity("tool", "Read")])
    composite = CompositeMatcher(m1, m2)
    results = composite.match_type("tool")
    ids = [composite.get_id(e) for e in results]
    assert ids == ["Bash", "Read"]


def test_composite_children_unions_results():
    m1 = CountingMatcher([])
    m2 = CountingMatcher([])
    composite = CompositeMatcher(m1, m2)
    assert composite.children(None, "x") == []


def test_composite_condition_met_is_or():
    m1 = CountingMatcher([_SimpleEntity("tool", "a", active=False)])
    m2 = CountingMatcher([_SimpleEntity("tool", "b", active=True)])
    composite = CompositeMatcher(m1, m2)
    assert composite.condition_met(None) is True


def test_composite_condition_met_all_false():
    m1 = CountingMatcher([_SimpleEntity("tool", "a", active=False)])
    m2 = CountingMatcher([_SimpleEntity("tool", "b", active=False)])
    composite = CompositeMatcher(m1, m2)
    assert composite.condition_met(None) is False


def test_composite_get_id_first_non_none_wins():
    m1 = CountingMatcher([], id_attr="nonexistent")
    m2 = CountingMatcher([])
    entity = _SimpleEntity("tool", "Bash")
    composite = CompositeMatcher(m1, m2)
    assert composite.get_id(entity) is None
    # m1 returns None (no "nonexistent" attr), m2 returns "Bash"
    m1_returns_none = CountingMatcher([])
    m1_returns_none.get_id = lambda e: None
    m2_returns_val = CountingMatcher([])
    m2_returns_val.get_id = lambda e: "found"
    composite2 = CompositeMatcher(m1_returns_none, m2_returns_val)
    assert composite2.get_id(entity) == "found"


def test_composite_get_attribute_first_non_none_wins():
    m1 = CountingMatcher([])
    m1.get_attribute = lambda e, n: None
    m2 = CountingMatcher([])
    m2.get_attribute = lambda e, n: "val2"
    composite = CompositeMatcher(m1, m2)
    assert composite.get_attribute(None, "x") == "val2"


def test_composite_add_appends_delegate():
    m1 = CountingMatcher([_SimpleEntity("tool", "A")])
    composite = CompositeMatcher(m1)
    assert len(composite.match_type("tool")) == 1
    m2 = CountingMatcher([_SimpleEntity("tool", "B")])
    composite.add(m2)
    assert len(composite.match_type("tool")) == 2


def test_register_matcher_auto_composes_on_collision():
    with registry_scope():
        register_taxon(name="world", description="w")
        m1 = NullMatcher()
        m2 = NullMatcher()
        register_matcher(taxon="world", matcher=m1)
        register_matcher(taxon="world", matcher=m2)
        result = get_matcher("world")
        assert isinstance(result, CompositeMatcher)


def test_register_matcher_triple_composition():
    with registry_scope():
        register_taxon(name="world", description="w")
        m1 = NullMatcher()
        m2 = NullMatcher()
        m3 = NullMatcher()
        register_matcher(taxon="world", matcher=m1)
        register_matcher(taxon="world", matcher=m2)
        register_matcher(taxon="world", matcher=m3)
        result = get_matcher("world")
        assert isinstance(result, CompositeMatcher)
        assert len(result._delegates) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_registry_matchers.py -v`
Expected: ImportError for CompositeMatcher, failures on auto-composition tests

- [ ] **Step 3: Implement CompositeMatcher and change register_matcher**

In `src/umwelt/registry/matchers.py`, add CompositeMatcher class and modify `register_matcher`:

```python
"""Matcher protocol and registration.

A matcher is the consumer-supplied bridge between a `ComplexSelector`
and the consumer's world. The parser, selector engine, and cascade
resolver are matcher-agnostic — they know how to call these methods
but not what the implementation does. A filesystem matcher walks
real paths; an in-memory test matcher walks a dict.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from umwelt.errors import RegistryError
from umwelt.registry.taxa import _current_state, get_taxon, resolve_taxon


@runtime_checkable
class MatcherProtocol(Protocol):
    """Consumer-supplied access to a world for selector evaluation.

    The protocol is deliberately thin. Each method takes selector-space
    inputs and returns opaque entity handles that only the matcher knows
    how to interpret — the core selector engine treats them as tokens.
    """

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        """Return all entities of this type in the matcher's world.

        For structural lookups where no parent entity is pre-selected,
        this returns every entity of the type.
        """
        ...

    def children(self, parent: Any, child_type: str) -> list[Any]:
        """Return `child_type` entities that are descendants of `parent`.

        Used for within-taxon structural descendant selectors (e.g.,
        `dir[name="src"] file[name$=".py"]` — the matcher walks the
        dir -> file parent-child relationship).
        """
        ...

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        """Return True if a cross-taxon context qualifier is satisfied.

        Called by the selector engine when a compound selector crosses
        taxa (`tool[name="Bash"] file[...]`). The qualifier taxon's
        matcher is consulted with the qualifier selector to determine
        whether the rule's context condition holds.
        """
        ...

    def get_attribute(self, entity: Any, name: str) -> Any:
        """Return the value of an attribute on an entity, or None if absent.

        Used by the selector match engine to evaluate attribute filters.
        """
        ...

    def get_id(self, entity: Any) -> str | None:
        """Return the entity's identity value (used by `#id` selectors).

        Return None when the entity has no natural identity; `#id` selectors
        won't match such entities.
        """
        ...


class CompositeMatcher:
    """Delegates to multiple matchers for the same taxon.

    Auto-created when register_matcher() is called twice for the same taxon.
    Union semantics for match_type/children, OR for condition_met,
    first-non-None for get_id/get_attribute.
    """

    def __init__(self, *delegates: MatcherProtocol):
        self._delegates: list[MatcherProtocol] = list(delegates)

    def add(self, matcher: MatcherProtocol) -> None:
        self._delegates.append(matcher)

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        results: list[Any] = []
        for d in self._delegates:
            results.extend(d.match_type(type_name, context))
        return results

    def children(self, parent: Any, child_type: str) -> list[Any]:
        results: list[Any] = []
        for d in self._delegates:
            results.extend(d.children(parent, child_type))
        return results

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        return any(d.condition_met(selector, context) for d in self._delegates)

    def get_attribute(self, entity: Any, name: str) -> Any:
        for d in self._delegates:
            val = d.get_attribute(entity, name)
            if val is not None:
                return val
        return None

    def get_id(self, entity: Any) -> str | None:
        for d in self._delegates:
            val = d.get_id(entity)
            if val is not None:
                return val
        return None


def register_matcher(*, taxon: str, matcher: MatcherProtocol) -> None:
    """Register a matcher for a taxon. Auto-composes on collision."""
    get_taxon(taxon)  # raises if unknown
    canonical = resolve_taxon(taxon)
    state = _current_state()
    if canonical in state.matchers:
        existing = state.matchers[canonical]
        if isinstance(existing, CompositeMatcher):
            existing.add(matcher)
        else:
            state.matchers[canonical] = CompositeMatcher(existing, matcher)
    else:
        state.matchers[canonical] = matcher


def get_matcher(taxon: str) -> MatcherProtocol:
    """Look up the matcher for a taxon. Resolves taxon aliases."""
    state = _current_state()
    canonical = resolve_taxon(taxon)
    try:
        return state.matchers[canonical]
    except KeyError as exc:
        raise RegistryError(f"no matcher registered for taxon {taxon!r}") from exc
```

- [ ] **Step 4: Update registry __init__.py exports**

Add `CompositeMatcher` to imports and `__all__` in `src/umwelt/registry/__init__.py`:

```python
from umwelt.registry.matchers import (
    CompositeMatcher,
    MatcherProtocol,
    get_matcher,
    register_matcher,
)
```

And add `"CompositeMatcher"` to the `__all__` list.

- [ ] **Step 5: Fix the existing duplicate-matcher test**

The test `test_duplicate_matcher_raises` in `tests/core/test_registry_matchers.py` currently expects `RegistryError` on duplicate registration. Change it to expect auto-composition:

```python
def test_duplicate_matcher_auto_composes():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_matcher(taxon="world", matcher=NullMatcher())
        register_matcher(taxon="world", matcher=NullMatcher())
        result = get_matcher("world")
        assert isinstance(result, CompositeMatcher)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/core/test_registry_matchers.py -v`
Expected: All tests PASS

- [ ] **Step 7: Run full test suite to check for regressions**

Run: `pytest tests/ -x -q`
Expected: No new failures beyond the pre-existing 34

- [ ] **Step 8: Commit**

```bash
git add src/umwelt/registry/matchers.py src/umwelt/registry/__init__.py tests/core/test_registry_matchers.py
git commit -m "feat(registry): add CompositeMatcher for multi-matcher per taxon

register_matcher() auto-composes on collision instead of raising.
Union semantics for match_type/children, OR for condition_met,
first-non-None for get_id/get_attribute."
```

---

### Task 2: P0 — Fixed Constraints (Post-Cascade Clamping)

**Files:**
- Modify: `src/umwelt/compilers/sql/schema.py:14-112`
- Modify: `src/umwelt/compilers/sql/populate.py:142-211`
- Modify: `src/umwelt/policy/queries.py:10-36`
- Modify: `src/umwelt/policy/lint.py:13-28`
- Modify: `src/umwelt/world/parser.py:76-91`
- Create: `tests/policy/test_fixed_constraints.py`

- [ ] **Step 1: Write failing tests for fixed constraints**

Create `tests/policy/test_fixed_constraints.py`:

```python
"""Tests for fixed constraint processing and effective_properties view."""
from __future__ import annotations

import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.schema import EXPECTED_TABLES, create_schema


def _make_db():
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))
    return con, dialect


def test_fixed_constraints_table_exists():
    con, _ = _make_db()
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    assert "fixed_constraints" in tables


def test_effective_properties_view_exists():
    con, _ = _make_db()
    views = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    ).fetchall()]
    assert "effective_properties" in views


def test_fixed_constraint_overrides_cascade():
    """Fixed constraint value wins over cascade-resolved value."""
    con, dialect = _make_db()

    # Insert an entity
    con.execute(
        "INSERT INTO entities (taxon, type_name, entity_id, depth) VALUES ('cap', 'tool', 'Bash', 0)"
    )
    entity_id = con.execute("SELECT id FROM entities WHERE entity_id = 'Bash'").fetchone()[0]

    # Insert a cascade candidate and create resolution views
    con.execute(
        "INSERT INTO cascade_candidates (entity_id, property_name, property_value, comparison, specificity, rule_index) "
        "VALUES (?, 'available', 'true', 'exact', '[0,0,1]', 0)",
        (entity_id,),
    )
    from umwelt.compilers.sql.resolution import create_resolution_views
    create_resolution_views(con, dialect)
    con.commit()

    # Verify cascade says 'true'
    row = con.execute(
        "SELECT property_value FROM resolved_properties WHERE entity_id = ? AND property_name = 'available'",
        (entity_id,),
    ).fetchone()
    assert row[0] == "true"

    # Insert fixed constraint
    con.execute(
        "INSERT INTO fixed_constraints (entity_id, property_name, property_value, selector) "
        "VALUES (?, 'available', 'false', 'tool#Bash')",
        (entity_id,),
    )
    con.commit()

    # Effective properties should show 'false' with source='fixed'
    row = con.execute(
        "SELECT effective_value, source FROM effective_properties "
        "WHERE entity_id = ? AND property_name = 'available'",
        (entity_id,),
    ).fetchone()
    assert row[0] == "false"
    assert row[1] == "fixed"


def test_effective_properties_passthrough_without_fixed():
    """Without a fixed constraint, effective_properties passes through cascade value."""
    con, dialect = _make_db()

    con.execute(
        "INSERT INTO entities (taxon, type_name, entity_id, depth) VALUES ('cap', 'tool', 'Read', 0)"
    )
    entity_id = con.execute("SELECT id FROM entities WHERE entity_id = 'Read'").fetchone()[0]

    con.execute(
        "INSERT INTO cascade_candidates (entity_id, property_name, property_value, comparison, specificity, rule_index) "
        "VALUES (?, 'available', 'true', 'exact', '[0,0,1]', 0)",
        (entity_id,),
    )
    from umwelt.compilers.sql.resolution import create_resolution_views
    create_resolution_views(con, dialect)
    con.commit()

    row = con.execute(
        "SELECT effective_value, source FROM effective_properties "
        "WHERE entity_id = ? AND property_name = 'available'",
        (entity_id,),
    ).fetchone()
    assert row[0] == "true"
    assert row[1] == "cascade"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/policy/test_fixed_constraints.py -v`
Expected: FAIL — no `fixed_constraints` table, no `effective_properties` view

- [ ] **Step 3: Add fixed_constraints table and effective_properties view to schema**

In `src/umwelt/compilers/sql/schema.py`, add to `EXPECTED_TABLES`:

```python
EXPECTED_TABLES = [
    "taxa",
    "entity_types",
    "property_types",
    "entities",
    "entity_closure",
    "cascade_candidates",
    "fixed_constraints",
]
```

And add new sections at the end of `create_schema()`, before the `return` statement:

```python
    # -- Fixed constraints (post-cascade clamping)
    sections.append(f"""
CREATE TABLE IF NOT EXISTS fixed_constraints (
    id              {autoincrement if is_sqlite else f'{int_type} PRIMARY KEY DEFAULT nextval(\\'fc_seq\\')'},
    entity_id       {int_type} REFERENCES entities(id),
    property_name   {text_type} NOT NULL,
    property_value  {text_type} NOT NULL,
    selector        {text_type} NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fc_entity_prop ON fixed_constraints(entity_id, property_name);""")
```

Note: the autoincrement handling needs to match the existing pattern. Here is the precise replacement — add after the cascade_candidates section (line ~110), before `return`:

```python
    # -- Fixed constraints (post-cascade clamping)
    fc_pk = autoincrement if is_sqlite else f"{int_type} PRIMARY KEY"
    sections.append(f"""
CREATE TABLE IF NOT EXISTS fixed_constraints (
    id              {fc_pk},
    entity_id       {int_type} REFERENCES entities(id),
    property_name   {text_type} NOT NULL,
    property_value  {text_type} NOT NULL,
    selector        {text_type} NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fc_entity_prop ON fixed_constraints(entity_id, property_name);""")

    # -- Effective properties (fixed constraints override cascade)
    sections.append("""
CREATE VIEW IF NOT EXISTS effective_properties AS
SELECT
    rp.entity_id,
    rp.property_name,
    COALESCE(fc.property_value, rp.property_value) AS effective_value,
    CASE WHEN fc.id IS NOT NULL THEN 'fixed' ELSE 'cascade' END AS source,
    rp.specificity,
    rp.rule_index,
    rp.source_file,
    rp.source_line
FROM resolved_properties rp
LEFT JOIN fixed_constraints fc
    ON fc.entity_id = rp.entity_id
    AND fc.property_name = rp.property_name;""")
```

Important: The `effective_properties` view references `resolved_properties` which is created later by `create_resolution_views()`. The view is defined as `IF NOT EXISTS`, so if `resolved_properties` doesn't exist yet at schema creation time, this view creation will fail. We need to move the effective_properties view creation into `resolution.py` instead, appended after `resolved_properties` is created.

**Revised approach:** Add only the `fixed_constraints` table to `schema.py`. Add the `effective_properties` view to `resolution.py` at the end of `_resolution_ddl()`.

In `src/umwelt/compilers/sql/schema.py`, add only:

```python
    # -- Fixed constraints (post-cascade clamping)
    sections.append(f"""
CREATE TABLE IF NOT EXISTS fixed_constraints (
    id              {autoincrement},
    entity_id       {int_type} REFERENCES entities(id),
    property_name   {text_type} NOT NULL,
    property_value  {text_type} NOT NULL,
    selector        {text_type} NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fc_entity_prop ON fixed_constraints(entity_id, property_name);""")
```

In `src/umwelt/compilers/sql/resolution.py`, append the effective_properties view at the end of `_resolution_ddl()`:

```python
    effective_view_prefix = "CREATE VIEW IF NOT EXISTS" if is_sqlite else "CREATE OR REPLACE VIEW"
    effective_view = f"""
{effective_view_prefix} effective_properties AS
SELECT
    rp.entity_id,
    rp.property_name,
    COALESCE(fc.property_value, rp.property_value) AS effective_value,
    CASE WHEN fc.id IS NOT NULL THEN 'fixed' ELSE 'cascade' END AS source,
    rp.specificity,
    rp.rule_index,
    rp.source_file,
    rp.source_line
FROM resolved_properties rp
LEFT JOIN fixed_constraints fc
    ON fc.entity_id = rp.entity_id
    AND fc.property_name = rp.property_name;"""

    return "\n".join([exact_view, cap_view, pattern_view, resolved_view, effective_view])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/policy/test_fixed_constraints.py -v`
Expected: All PASS

- [ ] **Step 5: Write tests for fixed constraint processing from world files**

Add to `tests/policy/test_fixed_constraints.py`:

```python
def test_populate_fixed_constraints_from_world():
    """populate_from_world processes fixed_raw into fixed_constraints table."""
    from umwelt.compilers.sql.populate import populate_from_world
    from umwelt.compilers.sql.resolution import create_resolution_views
    from umwelt.registry import register_entity, register_taxon, registry_scope
    from umwelt.registry.entities import AttrSchema
    from umwelt.world.model import DeclaredEntity, Provenance, WorldFile

    con, dialect = _make_db()

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(
            taxon="capability", name="tool",
            attributes={"name": AttrSchema(type=str)},
            description="a tool",
        )

        world = WorldFile(
            entities=(
                DeclaredEntity(type="tool", id="Bash", provenance=Provenance.EXPLICIT),
                DeclaredEntity(type="tool", id="Read", provenance=Provenance.EXPLICIT),
            ),
            projections=(),
            warnings=(),
            fixed_raw={"tool#Bash": {"available": "false"}},
        )
        populate_from_world(con, world)

        rows = con.execute("SELECT entity_id, property_name, property_value FROM fixed_constraints").fetchall()
        assert len(rows) == 1
        eid = con.execute("SELECT id FROM entities WHERE entity_id = 'Bash'").fetchone()[0]
        assert rows[0] == (eid, "available", "false")
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/policy/test_fixed_constraints.py::test_populate_fixed_constraints_from_world -v`
Expected: FAIL — populate_from_world doesn't process fixed_raw

- [ ] **Step 7: Implement fixed constraint processing in populate.py**

Add to `src/umwelt/compilers/sql/populate.py`, at the end of `populate_from_world()` (before `con.commit()`):

```python
def populate_from_world(con: Any, world: Any) -> None:
    """Insert DeclaredEntity instances from a WorldFile into the entities table.

    World file entities win on (type_name, entity_id) collision with
    existing matcher-discovered entities.
    """
    for entity in world.entities:
        _upsert_declared_entity(con, entity)

    for proj in world.projections:
        _upsert_projection(con, proj)

    # Process fixed constraints
    fixed_raw = getattr(world, "fixed_raw", {})
    if fixed_raw:
        _process_fixed_constraints(con, fixed_raw)

    con.commit()
    _rebuild_closure(con)


def _process_fixed_constraints(con: Any, fixed_raw: dict) -> None:
    """Insert fixed constraints by matching selectors against entities."""
    for selector_str, props in fixed_raw.items():
        if not isinstance(props, dict):
            continue
        # Parse selector: support type#id and type forms
        matching_ids = _match_fixed_selector(con, selector_str)
        for entity_pk in matching_ids:
            for prop_name, prop_value in props.items():
                con.execute(
                    "INSERT INTO fixed_constraints (entity_id, property_name, property_value, selector) "
                    "VALUES (?, ?, ?, ?)",
                    (entity_pk, prop_name, str(prop_value), selector_str),
                )


def _match_fixed_selector(con: Any, selector_str: str) -> list[int]:
    """Match a fixed constraint selector against entities. Supports type#id and type."""
    if "#" in selector_str:
        type_name, entity_id = selector_str.split("#", 1)
        rows = con.execute(
            "SELECT id FROM entities WHERE type_name = ? AND entity_id = ?",
            (type_name, entity_id),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id FROM entities WHERE type_name = ?",
            (selector_str,),
        ).fetchall()
    return [r[0] for r in rows]
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/policy/test_fixed_constraints.py -v`
Expected: All PASS

- [ ] **Step 9: Write test for queries using effective_properties**

Add to `tests/policy/test_fixed_constraints.py`:

```python
def test_resolve_entity_uses_effective_properties():
    """PolicyEngine.resolve() returns fixed-clamped values."""
    from umwelt.compilers.sql.compiler import compile_view
    from umwelt.compilers.sql.populate import populate_from_world
    from umwelt.compilers.sql.resolution import create_resolution_views
    from umwelt.parser import parse as parse_css
    from umwelt.registry import (
        register_entity,
        register_matcher,
        register_property,
        register_taxon,
        registry_scope,
    )
    from umwelt.registry.entities import AttrSchema
    from umwelt.policy.queries import resolve_entity
    from umwelt.world.model import DeclaredEntity, Provenance, WorldFile

    con, dialect = _make_db()

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(
            taxon="capability", name="tool",
            attributes={"name": AttrSchema(type=str)},
            description="a tool",
        )
        register_property(
            taxon="capability", entity="tool", name="available",
            value_type=str, description="whether available",
        )

        world = WorldFile(
            entities=(
                DeclaredEntity(type="tool", id="Bash", provenance=Provenance.EXPLICIT),
            ),
            projections=(),
            warnings=(),
            fixed_raw={"tool#Bash": {"available": "false"}},
        )
        populate_from_world(con, world)

        view = parse_css("tool { available: true; }", validate=False)
        compile_view(con, view, dialect)

        # Without fixed constraints, cascade says 'true'
        # With fixed constraints, effective value should be 'false'
        result = resolve_entity(con, type="tool", id="Bash", property="available")
        assert result == "false"
```

- [ ] **Step 10: Run test to verify it fails**

Run: `pytest tests/policy/test_fixed_constraints.py::test_resolve_entity_uses_effective_properties -v`
Expected: FAIL — resolve_entity reads `resolved_properties`, not `effective_properties`

- [ ] **Step 11: Update queries.py to read effective_properties**

In `src/umwelt/policy/queries.py`, replace all references to `resolved_properties` with `effective_properties`:

Line 24-25: Change:
```python
        row = con.execute(
            "SELECT property_value FROM resolved_properties "
```
To:
```python
        row = con.execute(
            "SELECT effective_value FROM effective_properties "
```

Line 31-32: Change:
```python
    rows = con.execute(
        "SELECT property_name, property_value FROM resolved_properties WHERE entity_id = ?",
```
To:
```python
    rows = con.execute(
        "SELECT property_name, effective_value FROM effective_properties WHERE entity_id = ?",
```

Line 52-53: Change:
```python
        props_rows = con.execute(
            "SELECT property_name, property_value FROM resolved_properties WHERE entity_id = ?",
```
To:
```python
        props_rows = con.execute(
            "SELECT property_name, effective_value FROM effective_properties WHERE entity_id = ?",
```

Line 83-88 (trace_entity): Change:
```python
    winner_row = con.execute(
        "SELECT property_value, specificity, rule_index "
        "FROM resolved_properties "
```
To:
```python
    winner_row = con.execute(
        "SELECT effective_value, specificity, rule_index "
        "FROM effective_properties "
```

Note: `trace_entity` still reads `cascade_candidates` for all candidates. The winner check reads `effective_properties` to pick up fixed-clamped winners. However, when a fixed constraint overrides, the winner_row from `effective_properties` will have a different value than any cascade candidate. We need to handle this in trace output.

Add to trace_entity, after building candidates list:

```python
    # Check if a fixed constraint overrode the cascade winner
    if winning_value is not None:
        fc_row = con.execute(
            "SELECT property_value, selector FROM fixed_constraints "
            "WHERE entity_id = ? AND property_name = ?",
            (entity_pk, property),
        ).fetchone()
        if fc_row and fc_row[0] != winning_value:
            # Fixed constraint is active but value matches override
            pass  # The effective_properties already has the right value
```

Actually, the simpler approach: keep trace reading from both. The TraceResult.value already reflects the effective value. Candidates show what the cascade computed. The trace consumer sees the discrepancy (value != winning candidate's value) and knows a fixed constraint intervened.

For now, just update the winner_row query and leave the candidates from cascade_candidates. This is enough for P0.

- [ ] **Step 12: Remove "not yet implemented" warning for fixed key in parser.py**

In `src/umwelt/world/parser.py`, change the Phase 2-3 key handling so `fixed` doesn't emit a warning:

```python
    for key in _PHASE2_KEYS:
        if key in data:
            if key != "fixed":
                warnings.append(WorldWarning(
                    message=f"'{key}' is not yet implemented (Phase 2-3)",
                    key=key,
                ))
```

- [ ] **Step 13: Run tests to verify they pass**

Run: `pytest tests/policy/test_fixed_constraints.py -v`
Expected: All PASS

- [ ] **Step 14: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures. Some existing tests may read `resolved_properties` directly — check for breakage in lint.py tests.

Note: `lint.py` reads `resolved_properties` directly for shadowed_rule detection and `cascade_candidates` for other checks. It does NOT read `effective_properties`. This is correct — lint analyzes cascade behavior, not fixed-clamped results. No changes needed to lint.py for P0.

- [ ] **Step 15: Add lint warning for fixed-clamped rules**

Add to `src/umwelt/policy/lint.py`:

```python
def _detect_fixed_override(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when cascade-resolved value is overridden by a fixed constraint."""
    warnings: list[LintWarning] = []
    try:
        rows = con.execute("""
            SELECT ep.entity_id, ep.property_name, rp.property_value AS cascade_value,
                   fc.property_value AS fixed_value
            FROM effective_properties ep
            JOIN resolved_properties rp ON rp.entity_id = ep.entity_id AND rp.property_name = ep.property_name
            JOIN fixed_constraints fc ON fc.entity_id = ep.entity_id AND fc.property_name = ep.property_name
            WHERE ep.source = 'fixed'
        """).fetchall()
    except Exception:
        return warnings

    for entity_pk, prop_name, cascade_val, fixed_val in rows:
        entity_name = _entity_name(con, entity_pk)
        warnings.append(LintWarning(
            smell="fixed_override",
            severity="info",
            description=(
                f"{entity_name} '{prop_name}': cascade resolved to '{cascade_val}'"
                f" but fixed constraint clamps to '{fixed_val}'"
            ),
            entities=(entity_name,),
            property=prop_name,
        ))
    return warnings
```

And add it to `run_lint()`:

```python
def run_lint(con: sqlite3.Connection) -> list[LintWarning]:
    warnings: list[LintWarning] = []
    warnings.extend(_detect_narrow_win(con))
    warnings.extend(_detect_shadowed_rule(con))
    warnings.extend(_detect_conflicting_intent(con))
    warnings.extend(_detect_uncovered_entity(con))
    warnings.extend(_detect_specificity_escalation(con))
    warnings.extend(_detect_fixed_override(con))
    # ...
```

- [ ] **Step 16: Run all tests**

Run: `pytest tests/ -x -q`
Expected: No new failures

- [ ] **Step 17: Commit**

```bash
git add src/umwelt/compilers/sql/schema.py src/umwelt/compilers/sql/resolution.py \
  src/umwelt/compilers/sql/populate.py src/umwelt/policy/queries.py \
  src/umwelt/policy/lint.py src/umwelt/world/parser.py \
  tests/policy/test_fixed_constraints.py
git commit -m "feat(policy): add fixed constraints for post-cascade clamping

World files declare fixed: blocks with selector-keyed property overrides.
Fixed values win over cascade-resolved values via effective_properties view.
Lint warns when cascade rules are clamped by fixed constraints."
```

---

### Task 3: P1 — Plugin Autodiscovery

**Files:**
- Create: `src/umwelt/registry/plugins.py`
- Modify: `src/umwelt/registry/taxa.py:60-74`
- Modify: `src/umwelt/registry/__init__.py`
- Modify: `src/umwelt/policy/engine.py:445-451`
- Modify: `pyproject.toml`
- Create: `tests/registry/test_plugins.py`

- [ ] **Step 1: Write failing tests for plugin discovery and idempotent registration**

Create `tests/registry/test_plugins.py`:

```python
"""Tests for plugin autodiscovery and idempotent taxon registration."""
from __future__ import annotations

import pytest

from umwelt.errors import RegistryError
from umwelt.registry import register_taxon, registry_scope
from umwelt.registry.plugins import discover_plugins


def test_idempotent_register_taxon_same_description():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_taxon(name="world", description="w")  # should not raise


def test_idempotent_register_taxon_different_description_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        with pytest.raises(RegistryError, match="conflicting"):
            register_taxon(name="world", description="different")


def test_discover_plugins_returns_list():
    with registry_scope():
        result = discover_plugins()
        assert isinstance(result, list)


def test_discover_plugins_loads_sandbox_entry_point(monkeypatch):
    """If sandbox entry point is registered, it gets loaded."""
    loaded = []

    class FakeEntryPoint:
        name = "test_plugin"
        def load(self):
            def register():
                loaded.append("called")
            return register

    monkeypatch.setattr(
        "umwelt.registry.plugins.entry_points",
        lambda group: [FakeEntryPoint()],
    )

    with registry_scope():
        names = discover_plugins()
    assert "test_plugin" in names
    assert loaded == ["called"]


def test_discover_plugins_survives_broken_plugin(monkeypatch):
    """A broken plugin doesn't take down discovery."""
    class BrokenEntryPoint:
        name = "broken"
        def load(self):
            raise ImportError("bad plugin")

    class GoodEntryPoint:
        name = "good"
        def load(self):
            return lambda: None

    monkeypatch.setattr(
        "umwelt.registry.plugins.entry_points",
        lambda group: [BrokenEntryPoint(), GoodEntryPoint()],
    )

    with registry_scope():
        names = discover_plugins()
    assert "good" in names
    assert "broken" not in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/registry/test_plugins.py -v`
Expected: ImportError for `umwelt.registry.plugins`, failure on idempotent registration

- [ ] **Step 3: Make register_taxon idempotent**

In `src/umwelt/registry/taxa.py`, change `register_taxon`:

```python
def register_taxon(
    *,
    name: str,
    description: str,
    ma_concept: str | None = None,
) -> None:
    """Register a taxon with the active registry scope.

    Idempotent: re-registration with matching description is a no-op.
    Raises on conflicting re-registration (same name, different description).
    """
    state = _current_state()
    if name in state.taxa:
        existing = state.taxa[name]
        if existing.description == description:
            return  # idempotent
        raise RegistryError(
            f"taxon {name!r} already registered with conflicting description"
        )
    state.taxa[name] = TaxonSchema(
        name=name,
        description=description,
        ma_concept=ma_concept,
    )
```

- [ ] **Step 4: Create plugins.py**

Create `src/umwelt/registry/plugins.py`:

```python
"""Plugin autodiscovery via entry points."""
from __future__ import annotations

import logging

from importlib.metadata import entry_points

logger = logging.getLogger("umwelt.registry")

ENTRY_POINT_GROUP = "umwelt.plugins"


def discover_plugins() -> list[str]:
    """Load all registered umwelt plugins. Returns names of loaded plugins."""
    loaded: list[str] = []
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            register_fn = ep.load()
            register_fn()
            loaded.append(ep.name)
        except Exception:
            logger.debug("plugin %s failed to load", ep.name, exc_info=True)
    return loaded
```

- [ ] **Step 5: Update registry __init__.py**

Add to imports in `src/umwelt/registry/__init__.py`:

```python
from umwelt.registry.plugins import discover_plugins
```

Add `"discover_plugins"` to `__all__`.

- [ ] **Step 6: Update _load_default_vocabulary in engine.py**

In `src/umwelt/policy/engine.py`, change `_load_default_vocabulary`:

```python
def _load_default_vocabulary() -> None:
    from umwelt.registry.plugins import discover_plugins
    discover_plugins()
```

- [ ] **Step 7: Add sandbox entry point to pyproject.toml**

Add to `pyproject.toml`:

```toml
[project.entry-points."umwelt.plugins"]
sandbox = "umwelt.sandbox.vocabulary:register_sandbox_vocabulary"
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/registry/test_plugins.py -v`
Expected: All PASS

- [ ] **Step 9: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures. The idempotent register_taxon should fix some existing tests that used `contextlib.suppress(RegistryError)` around duplicate registrations.

- [ ] **Step 10: Commit**

```bash
git add src/umwelt/registry/plugins.py src/umwelt/registry/taxa.py \
  src/umwelt/registry/__init__.py src/umwelt/policy/engine.py \
  pyproject.toml tests/registry/test_plugins.py
git commit -m "feat(registry): add plugin autodiscovery via entry points

discover_plugins() loads umwelt.plugins entry point group.
register_taxon() is now idempotent on matching description.
_load_default_vocabulary() delegates to discover_plugins()."
```

---

### Task 4: P1 — Cross-Taxon Validators

**Files:**
- Modify: `src/umwelt/registry/validators.py:1-34`
- Modify: `src/umwelt/registry/taxa.py:30-50`
- Modify: `src/umwelt/registry/__init__.py`
- Modify: `src/umwelt/validate.py:1-33`
- Create: `tests/registry/test_cross_validators.py`

- [ ] **Step 1: Write failing tests for cross-taxon validators**

Create `tests/registry/test_cross_validators.py`:

```python
"""Tests for cross-taxon validator protocol, registration, and dispatch."""
from __future__ import annotations

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.parser import parse
from umwelt.registry import registry_scope
from umwelt.registry.validators import (
    CrossTaxonValidatorProtocol,
    get_cross_taxon_validators,
    register_cross_taxon_validator,
)


class _RecordingCrossValidator:
    """Records the full view it receives."""

    def __init__(self):
        self.views_seen: list = []

    def validate(self, view, warnings):
        self.views_seen.append(view)


def test_cross_validator_protocol_is_runtime_checkable():
    assert isinstance(_RecordingCrossValidator(), CrossTaxonValidatorProtocol)


def test_register_and_retrieve_cross_validator():
    with registry_scope():
        v = _RecordingCrossValidator()
        register_cross_taxon_validator(v)
        assert v in get_cross_taxon_validators()


def test_cross_validator_receives_full_view():
    with registry_scope():
        install_toy_taxonomy()
        v = _RecordingCrossValidator()
        register_cross_taxon_validator(v)
        parse("thing { paint: red; } actor { allowed: true; }")
    assert len(v.views_seen) == 1
    view = v.views_seen[0]
    assert len(view.rules) == 2


def test_cross_validator_runs_after_per_taxon():
    """Cross-taxon validators see rules from all taxa."""
    with registry_scope():
        install_toy_taxonomy()
        order = []

        class PerTaxon:
            def validate(self, rules, warnings):
                order.append("per-taxon")

        class CrossTaxon:
            def validate(self, view, warnings):
                order.append("cross-taxon")

        from umwelt.registry import register_validator
        register_validator(taxon="shapes", validator=PerTaxon())
        register_cross_taxon_validator(CrossTaxon())
        parse("thing { paint: red; }")

    assert order == ["per-taxon", "cross-taxon"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/registry/test_cross_validators.py -v`
Expected: ImportError for CrossTaxonValidatorProtocol, get_cross_taxon_validators

- [ ] **Step 3: Add CrossTaxonValidatorProtocol and registration**

In `src/umwelt/registry/validators.py`:

```python
"""Validator protocol and registration."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from umwelt.registry.taxa import _current_state, get_taxon, resolve_taxon


@runtime_checkable
class ValidatorProtocol(Protocol):
    """A validator inspects rules in its taxon and emits warnings or errors.

    `rules` is the full list of RuleBlocks whose target_taxon equals the
    validator's registered taxon. The validator mutates the shared `warnings`
    list for soft findings and raises ViewValidationError for hard failures.
    """

    def validate(self, rules: list[Any], warnings: list[Any]) -> None:
        ...


@runtime_checkable
class CrossTaxonValidatorProtocol(Protocol):
    """A validator that receives the full View across all taxa."""

    def validate(self, view: Any, warnings: list[Any]) -> None:
        ...


def register_validator(*, taxon: str, validator: ValidatorProtocol) -> None:
    get_taxon(taxon)
    canonical = resolve_taxon(taxon)
    state = _current_state()
    state.validators.setdefault(canonical, []).append(validator)


def get_validators(taxon: str) -> list[ValidatorProtocol]:
    state = _current_state()
    canonical = resolve_taxon(taxon)
    return list(state.validators.get(canonical, []))


def register_cross_taxon_validator(validator: CrossTaxonValidatorProtocol) -> None:
    state = _current_state()
    state.cross_validators.append(validator)


def get_cross_taxon_validators() -> list[CrossTaxonValidatorProtocol]:
    state = _current_state()
    return list(state.cross_validators)
```

- [ ] **Step 4: Add cross_validators to RegistryState**

In `src/umwelt/registry/taxa.py`, add to `RegistryState`:

```python
@dataclass
class RegistryState:
    taxa: dict[str, TaxonSchema] = field(default_factory=dict)
    taxon_aliases: dict[str, str] = field(default_factory=dict)
    entities: dict[tuple[str, str], EntitySchema] = field(default_factory=dict)
    properties: dict[tuple[str, str, str], PropertySchema] = field(default_factory=dict)
    matchers: dict[str, MatcherProtocol] = field(default_factory=dict)
    validators: dict[str, list[ValidatorProtocol]] = field(default_factory=dict)
    shorthands: dict[str, Any] = field(default_factory=dict)
    cross_validators: list[Any] = field(default_factory=list)
```

- [ ] **Step 5: Update validate.py to dispatch cross-taxon validators**

In `src/umwelt/validate.py`:

```python
"""Dispatch registered per-taxon validators over a parsed view."""

from __future__ import annotations

from umwelt.ast import ParseWarning, RuleBlock, View
from umwelt.registry import get_validators, list_taxa
from umwelt.registry.validators import get_cross_taxon_validators


def validate(view: View) -> View:
    """Run every registered validator over its taxon's rules.

    Returns a new `View` with any accumulated warnings attached. Hard
    failures raise ViewValidationError from the validator itself.
    """
    warnings_list: list[ParseWarning] = list(view.warnings)
    # Group rules by the rightmost selector's target_taxon.
    grouped: dict[str, list[RuleBlock]] = {}
    for rule in view.rules:
        for sel in rule.selectors:
            grouped.setdefault(sel.target_taxon, []).append(rule)
            break  # One rule -> one taxon group per rule; use first selector's taxon.
    for taxon in list_taxa():
        rules = grouped.get(taxon.name, [])
        for validator in get_validators(taxon.name):
            validator.validate(rules, warnings_list)

    # Cross-taxon validators receive the full view
    for validator in get_cross_taxon_validators():
        validator.validate(view, warnings_list)

    return View(
        rules=view.rules,
        unknown_at_rules=view.unknown_at_rules,
        warnings=tuple(warnings_list),
        source_text=view.source_text,
        source_path=view.source_path,
    )
```

- [ ] **Step 6: Update registry __init__.py exports**

Add to `src/umwelt/registry/__init__.py`:

```python
from umwelt.registry.validators import (
    CrossTaxonValidatorProtocol,
    ValidatorProtocol,
    get_cross_taxon_validators,
    get_validators,
    register_cross_taxon_validator,
    register_validator,
)
```

Add `"CrossTaxonValidatorProtocol"`, `"get_cross_taxon_validators"`, `"register_cross_taxon_validator"` to `__all__`.

- [ ] **Step 7: Run tests**

Run: `pytest tests/registry/test_cross_validators.py -v`
Expected: All PASS

- [ ] **Step 8: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures

- [ ] **Step 9: Commit**

```bash
git add src/umwelt/registry/validators.py src/umwelt/registry/taxa.py \
  src/umwelt/registry/__init__.py src/umwelt/validate.py \
  tests/registry/test_cross_validators.py
git commit -m "feat(registry): add cross-taxon validator protocol

CrossTaxonValidatorProtocol receives full View for multi-taxon invariants.
Dispatched after per-taxon validators in validate()."
```

---

### Task 5: P1 — World File Composition (require/include/exclude)

**Files:**
- Create: `src/umwelt/registry/collections.py`
- Modify: `src/umwelt/world/model.py:20-25`
- Modify: `src/umwelt/world/parser.py:20-111`
- Modify: `src/umwelt/registry/__init__.py`
- Modify: `src/umwelt/registry/taxa.py:30-50`
- Create: `tests/world/test_composition.py`

- [ ] **Step 1: Write failing tests for collection registry**

Create `tests/world/test_composition.py`:

```python
"""Tests for world file composition: require, include, exclude."""
from __future__ import annotations

from pathlib import Path

import pytest

from umwelt.registry import registry_scope
from umwelt.registry.collections import (
    register_collection,
    require_collection,
    get_collection_entities,
)
from umwelt.world.model import DeclaredEntity, Provenance


def _tool_entity(name):
    return DeclaredEntity(type="tool", id=name, provenance=Provenance.REQUIRED)


def test_register_and_require_collection():
    with registry_scope():
        register_collection(
            name="executables",
            loader=lambda: [_tool_entity("Bash"), _tool_entity("Read")],
        )
        require_collection("executables")
        entities = get_collection_entities()
        ids = [e.id for e in entities]
        assert "Bash" in ids
        assert "Read" in ids


def test_require_is_idempotent():
    with registry_scope():
        call_count = 0
        def loader():
            nonlocal call_count
            call_count += 1
            return [_tool_entity("Bash")]

        register_collection(name="executables", loader=loader)
        require_collection("executables")
        require_collection("executables")
        assert call_count == 1


def test_require_unknown_collection_raises():
    with registry_scope():
        with pytest.raises(KeyError, match="ghost"):
            require_collection("ghost")


def test_provenance_is_required():
    with registry_scope():
        register_collection(
            name="executables",
            loader=lambda: [_tool_entity("Bash")],
        )
        require_collection("executables")
        entities = get_collection_entities()
        assert entities[0].provenance == Provenance.REQUIRED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/world/test_composition.py -v`
Expected: ImportError for collections module

- [ ] **Step 3: Add Provenance.REQUIRED to model**

In `src/umwelt/world/model.py`, add to Provenance enum:

```python
class Provenance(Enum):
    EXPLICIT = "explicit"
    DISCOVERED = "discovered"
    PROJECTED = "projected"
    INCLUDED = "included"
    REQUIRED = "required"
```

- [ ] **Step 4: Create collections.py**

Create `src/umwelt/registry/collections.py`:

```python
"""Collection registry for named entity bundles.

Collections group entities (and optionally matchers) that a world file
can require by name. require("filesystem") loads file/dir entities and
the WorldMatcher. The default world is empty until collections are required.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from umwelt.registry.taxa import _current_state

if TYPE_CHECKING:
    from umwelt.registry.matchers import MatcherProtocol
    from umwelt.world.model import DeclaredEntity


def register_collection(
    name: str,
    loader: Callable[[], list[DeclaredEntity]],
    matcher_factory: Callable[[], MatcherProtocol] | None = None,
) -> None:
    """Register a named collection of entities with an optional matcher factory."""
    state = _current_state()
    state.collections[name] = _CollectionDef(
        name=name,
        loader=loader,
        matcher_factory=matcher_factory,
    )


def require_collection(name: str) -> None:
    """Activate a named collection. Idempotent — second call is a no-op."""
    state = _current_state()
    if name in state.required_collections:
        return
    if name not in state.collections:
        raise KeyError(f"unknown collection {name!r}")
    defn = state.collections[name]
    entities = defn.loader()
    state.collection_entities.extend(entities)
    if defn.matcher_factory is not None:
        from umwelt.registry.matchers import register_matcher
        matcher = defn.matcher_factory()
        taxon = _infer_taxon(entities)
        if taxon:
            register_matcher(taxon=taxon, matcher=matcher)
    state.required_collections.add(name)


def get_collection_entities() -> list[DeclaredEntity]:
    """Return all entities loaded by required collections."""
    state = _current_state()
    return list(state.collection_entities)


def _infer_taxon(entities: list[DeclaredEntity]) -> str | None:
    """Infer taxon from entity types via the entity registry."""
    if not entities:
        return None
    try:
        from umwelt.registry.entities import resolve_entity_type
        taxa = resolve_entity_type(entities[0].type)
        return taxa[0] if taxa else None
    except Exception:
        return None


class _CollectionDef:
    __slots__ = ("name", "loader", "matcher_factory")

    def __init__(
        self,
        name: str,
        loader: Callable[[], list[Any]],
        matcher_factory: Callable[[], Any] | None,
    ):
        self.name = name
        self.loader = loader
        self.matcher_factory = matcher_factory
```

- [ ] **Step 5: Add collection state to RegistryState**

In `src/umwelt/registry/taxa.py`, add to `RegistryState`:

```python
@dataclass
class RegistryState:
    taxa: dict[str, TaxonSchema] = field(default_factory=dict)
    taxon_aliases: dict[str, str] = field(default_factory=dict)
    entities: dict[tuple[str, str], EntitySchema] = field(default_factory=dict)
    properties: dict[tuple[str, str, str], PropertySchema] = field(default_factory=dict)
    matchers: dict[str, MatcherProtocol] = field(default_factory=dict)
    validators: dict[str, list[ValidatorProtocol]] = field(default_factory=dict)
    shorthands: dict[str, Any] = field(default_factory=dict)
    cross_validators: list[Any] = field(default_factory=list)
    collections: dict[str, Any] = field(default_factory=dict)
    collection_entities: list[Any] = field(default_factory=list)
    required_collections: set[str] = field(default_factory=set)
```

- [ ] **Step 6: Run collection tests**

Run: `pytest tests/world/test_composition.py -v`
Expected: All PASS

- [ ] **Step 7: Write failing tests for include and exclude in parser**

Add to `tests/world/test_composition.py`:

```python
import yaml


def test_include_loads_entities_from_file(tmp_path):
    """include: loads entities from another world file."""
    from umwelt.registry import register_entity, register_taxon
    from umwelt.registry.entities import AttrSchema
    from umwelt.world.parser import load_world

    base = tmp_path / "base.world.yml"
    base.write_text(yaml.dump({
        "entities": [
            {"type": "tool", "id": "Bash"},
            {"type": "tool", "id": "Read"},
        ]
    }))

    main = tmp_path / "main.world.yml"
    main.write_text(yaml.dump({
        "include": ["./base.world.yml"],
        "entities": [
            {"type": "tool", "id": "Edit"},
        ],
    }))

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(taxon="capability", name="tool",
                       attributes={"name": AttrSchema(type=str)}, description="t")
        world = load_world(main)
    ids = [e.id for e in world.entities]
    assert "Bash" in ids
    assert "Read" in ids
    assert "Edit" in ids


def test_include_later_overrides_earlier(tmp_path):
    """Later include files override earlier ones on (type, id) collision."""
    base1 = tmp_path / "base1.world.yml"
    base1.write_text(yaml.dump({
        "entities": [{"type": "tool", "id": "Bash", "attributes": {"level": "1"}}]
    }))
    base2 = tmp_path / "base2.world.yml"
    base2.write_text(yaml.dump({
        "entities": [{"type": "tool", "id": "Bash", "attributes": {"level": "2"}}]
    }))
    main = tmp_path / "main.world.yml"
    main.write_text(yaml.dump({
        "include": ["./base1.world.yml", "./base2.world.yml"],
    }))

    from umwelt.registry import register_entity, register_taxon
    from umwelt.registry.entities import AttrSchema
    from umwelt.world.parser import load_world

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(taxon="capability", name="tool",
                       attributes={"name": AttrSchema(type=str)}, description="t")
        world = load_world(main)
    bash = [e for e in world.entities if e.id == "Bash"][0]
    assert bash.attributes.get("level") == "2"


def test_exclude_removes_entities(tmp_path):
    """exclude: removes matching entities."""
    main = tmp_path / "main.world.yml"
    main.write_text(yaml.dump({
        "entities": [
            {"type": "tool", "id": "Bash"},
            {"type": "tool", "id": "Read"},
            {"type": "tool", "id": "Edit"},
        ],
        "exclude": ["tool#Bash"],
    }))

    from umwelt.registry import register_entity, register_taxon
    from umwelt.registry.entities import AttrSchema
    from umwelt.world.parser import load_world

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(taxon="capability", name="tool",
                       attributes={"name": AttrSchema(type=str)}, description="t")
        world = load_world(main)
    ids = [e.id for e in world.entities]
    assert "Bash" not in ids
    assert "Read" in ids
    assert "Edit" in ids


def test_include_cycle_detection(tmp_path):
    """Circular includes are detected and skipped."""
    a = tmp_path / "a.world.yml"
    b = tmp_path / "b.world.yml"
    a.write_text(yaml.dump({"include": ["./b.world.yml"], "entities": [{"type": "tool", "id": "A"}]}))
    b.write_text(yaml.dump({"include": ["./a.world.yml"], "entities": [{"type": "tool", "id": "B"}]}))

    from umwelt.registry import register_entity, register_taxon
    from umwelt.registry.entities import AttrSchema
    from umwelt.world.parser import load_world

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(taxon="capability", name="tool",
                       attributes={"name": AttrSchema(type=str)}, description="t")
        world = load_world(a)
    ids = [e.id for e in world.entities]
    assert "A" in ids
    assert "B" in ids
    assert any("cycle" in w.message.lower() or "skip" in w.message.lower() for w in world.warnings)


def test_require_in_world_file(tmp_path):
    """require: activates named collections."""
    main = tmp_path / "main.world.yml"
    main.write_text(yaml.dump({
        "require": ["test_tools"],
        "entities": [{"type": "tool", "id": "Extra"}],
    }))

    from umwelt.registry import register_entity, register_taxon
    from umwelt.registry.entities import AttrSchema
    from umwelt.registry.collections import register_collection
    from umwelt.world.parser import load_world

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(taxon="capability", name="tool",
                       attributes={"name": AttrSchema(type=str)}, description="t")
        register_collection(
            name="test_tools",
            loader=lambda: [_tool_entity("Bash"), _tool_entity("Read")],
        )
        world = load_world(main)
    ids = [e.id for e in world.entities]
    assert "Bash" in ids
    assert "Read" in ids
    assert "Extra" in ids
```

- [ ] **Step 8: Run tests to verify they fail**

Run: `pytest tests/world/test_composition.py -v`
Expected: Failures on include/exclude/require tests — parser doesn't process them

- [ ] **Step 9: Implement include/exclude/require processing in parser.py**

Update `src/umwelt/world/parser.py` to add `require` to structural keys, add a `_PHASE2_KEYS` adjustment, and implement processing:

```python
"""YAML parser for .world.yml files.

Reads a world file, expands shorthand keys into ``DeclaredEntity`` instances,
merges shorthand-derived entities with explicit ``entities:`` block entries
(explicit wins on ``(type, id)`` collision), and processes composition
directives (require, include, exclude).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from umwelt.errors import WorldParseError
from umwelt.world.model import DeclaredEntity, Projection, Provenance, WorldFile, WorldWarning
from umwelt.world.shorthands import get_shorthand

_STRUCTURAL_KEYS = frozenset({"entities", "discover", "projections", "overrides", "fixed", "include", "exclude", "require"})
_RESERVED_KEYS = frozenset({"vars", "when", "version"})
_PHASE2_KEYS = frozenset({"discover", "overrides"})


def load_world(path: str | Path, *, _seen: frozenset[str] | None = None) -> WorldFile:
    """Parse a .world.yml file and return a :class:`WorldFile`."""
    path = Path(path).resolve()
    if _seen is None:
        _seen = frozenset()

    text = path.read_text()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WorldParseError(f"invalid YAML: {exc}") from exc
    if data is None:
        data = {}

    warnings: list[WorldWarning] = []

    # --- 1. require: collections (idempotent, unordered) ---
    require_raw: tuple[str, ...] = ()
    if "require" in data:
        raw = data["require"]
        if isinstance(raw, list):
            require_raw = tuple(str(x) for x in raw)
            _process_requires(require_raw, warnings)

    # --- 2. include: files (ordered, later overrides earlier) ---
    include_raw: tuple[str, ...] = ()
    included_entities: list[DeclaredEntity] = []
    if "include" in data:
        raw = data["include"]
        if isinstance(raw, list):
            include_raw = tuple(str(x) for x in raw)
            included_entities, inc_warnings = _process_includes(
                include_raw, path.parent, _seen | {str(path)}
            )
            warnings.extend(inc_warnings)

    # --- 3. Expand shorthands ---
    shorthand_entities, sh_warnings = _expand_shorthands(data)
    warnings.extend(sh_warnings)

    # --- 4. Parse explicit entities block ---
    explicit_entities: list[DeclaredEntity] = []
    if "entities" in data:
        raw = data["entities"]
        if isinstance(raw, list):
            for item in raw:
                explicit_entities.append(_parse_entity_dict(item))

    # --- 5. Merge: require → include → shorthand → explicit (later wins) ---
    from umwelt.registry.collections import get_collection_entities
    collection_entities = get_collection_entities()

    merged: dict[tuple[str, str], DeclaredEntity] = {}
    for e in collection_entities:
        merged[(e.type, e.id)] = e
    for e in included_entities:
        merged[(e.type, e.id)] = e
    for e in shorthand_entities:
        merged[(e.type, e.id)] = e
    for e in explicit_entities:
        merged[(e.type, e.id)] = e

    # --- 6. exclude: removals applied last ---
    exclude_raw: tuple[str, ...] = ()
    if "exclude" in data:
        raw = data["exclude"]
        if isinstance(raw, list):
            exclude_raw = tuple(str(x) for x in raw)
            merged = _apply_excludes(merged, exclude_raw, warnings)

    # Parse projections block
    projections: list[Projection] = []
    if "projections" in data:
        raw = data["projections"]
        if isinstance(raw, list):
            projections = _parse_projections(raw)

    # Handle Phase 2-3 keys: stash raw values + emit warnings
    discover_raw: tuple[dict[str, Any], ...] = ()
    overrides_raw: dict[str, Any] = {}
    fixed_raw: dict[str, Any] = {}

    for key in _PHASE2_KEYS:
        if key in data:
            warnings.append(WorldWarning(
                message=f"'{key}' is not yet implemented (Phase 2-3)",
                key=key,
            ))
            if key == "discover":
                discover_raw = tuple(data[key]) if isinstance(data[key], list) else ()
            elif key == "overrides":
                overrides_raw = data[key] if isinstance(data[key], dict) else {}

    if "fixed" in data:
        fixed_raw = data["fixed"] if isinstance(data["fixed"], dict) else {}

    # Warn on reserved and unknown keys
    known_keys = _STRUCTURAL_KEYS | _RESERVED_KEYS
    for key in data:
        if key in _RESERVED_KEYS:
            warnings.append(WorldWarning(message=f"'{key}' is a reserved key", key=key))
        elif key not in known_keys and get_shorthand(key) is None:
            warnings.append(WorldWarning(message=f"unknown key '{key}'", key=key))

    return WorldFile(
        entities=tuple(merged.values()),
        projections=tuple(projections),
        warnings=tuple(warnings),
        source_path=str(path),
        discover_raw=discover_raw,
        overrides_raw=overrides_raw,
        fixed_raw=fixed_raw,
        include_raw=include_raw,
        exclude_raw=exclude_raw,
    )


def _process_requires(names: tuple[str, ...], warnings: list[WorldWarning]) -> None:
    """Activate named collections."""
    from umwelt.registry.collections import require_collection
    for name in names:
        try:
            require_collection(name)
        except KeyError:
            warnings.append(WorldWarning(
                message=f"unknown collection '{name}'",
                key="require",
            ))


def _process_includes(
    paths: tuple[str, ...],
    base_dir: Path,
    seen: frozenset[str],
) -> tuple[list[DeclaredEntity], list[WorldWarning]]:
    """Load entities from included world files, in order."""
    entities: list[DeclaredEntity] = []
    warnings: list[WorldWarning] = []
    for rel_path in paths:
        abs_path = (base_dir / rel_path).resolve()
        if str(abs_path) in seen:
            warnings.append(WorldWarning(
                message=f"skipping circular include: {rel_path}",
                key="include",
            ))
            continue
        try:
            included = load_world(abs_path, _seen=seen)
            for e in included.entities:
                entities.append(DeclaredEntity(
                    type=e.type,
                    id=e.id,
                    classes=e.classes,
                    attributes=e.attributes,
                    parent=e.parent,
                    provenance=Provenance.INCLUDED,
                ))
            warnings.extend(included.warnings)
        except FileNotFoundError:
            warnings.append(WorldWarning(
                message=f"included file not found: {rel_path}",
                key="include",
            ))
    return entities, warnings


def _apply_excludes(
    merged: dict[tuple[str, str], DeclaredEntity],
    selectors: tuple[str, ...],
    warnings: list[WorldWarning],
) -> dict[tuple[str, str], DeclaredEntity]:
    """Remove entities matching exclude selectors."""
    for sel_str in selectors:
        if "[" in sel_str:
            warnings.append(WorldWarning(
                message=f"attribute selectors in exclude not yet supported: {sel_str}",
                key="exclude",
            ))
            continue
        if "#" in sel_str:
            type_name, entity_id = sel_str.split("#", 1)
            key = (type_name, entity_id)
            merged.pop(key, None)
        else:
            to_remove = [k for k in merged if k[0] == sel_str]
            for k in to_remove:
                del merged[k]
    return merged


# ... rest of file unchanged (_parse_entity_dict, _expand_shorthands, _parse_projections)
```

- [ ] **Step 10: Add `require` to WorldFile model**

In `src/umwelt/world/model.py`, add `require_raw` field to `WorldFile`:

```python
@dataclass(frozen=True)
class WorldFile:
    entities: tuple[DeclaredEntity, ...]
    projections: tuple[Projection, ...]
    warnings: tuple[WorldWarning, ...]
    source_path: str | None = None
    discover_raw: tuple[dict[str, Any], ...] = ()
    overrides_raw: dict[str, Any] = field(default_factory=dict)
    fixed_raw: dict[str, Any] = field(default_factory=dict)
    include_raw: tuple[str, ...] = ()
    exclude_raw: tuple[str, ...] = ()
    require_raw: tuple[str, ...] = ()
```

Update the `return WorldFile(...)` in parser.py to include `require_raw=require_raw`.

- [ ] **Step 11: Update registry __init__.py**

Add to `src/umwelt/registry/__init__.py`:

```python
from umwelt.registry.collections import (
    get_collection_entities,
    register_collection,
    require_collection,
)
```

Add all three to `__all__`.

- [ ] **Step 12: Run tests**

Run: `pytest tests/world/test_composition.py -v`
Expected: All PASS

- [ ] **Step 13: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures. Parser changes are backward-compatible — files without require/include/exclude work as before.

- [ ] **Step 14: Commit**

```bash
git add src/umwelt/registry/collections.py src/umwelt/world/model.py \
  src/umwelt/world/parser.py src/umwelt/registry/__init__.py \
  src/umwelt/registry/taxa.py tests/world/test_composition.py
git commit -m "feat(world): add require/include/exclude world file composition

Collections bundle entities + optional matchers. require: activates them.
include: loads entities from other world files with cycle detection.
exclude: removes entities by type or type#id selector."
```

---

### Task 6: P2 — Shared Event Schema

**Files:**
- Modify: `src/umwelt/sandbox/vocabulary.py`
- Create: `tests/sandbox/test_event_schema.py`

- [ ] **Step 1: Write failing test for extended audit vocabulary**

Create `tests/sandbox/test_event_schema.py`:

```python
"""Tests for shared event schema on the audit taxon's observation entity."""
from __future__ import annotations

from umwelt.registry import get_property, list_properties, registry_scope


def test_observation_has_event_properties():
    with registry_scope():
        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        register_sandbox_vocabulary()

        props = list_properties("audit", "observation")
        prop_names = {p.name for p in props}
        assert "type" in prop_names
        assert "timestamp" in prop_names
        assert "session_id" in prop_names
        assert "severity" in prop_names
        assert "tags" in prop_names
        assert "payload" in prop_names


def test_observation_event_property_types():
    with registry_scope():
        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        register_sandbox_vocabulary()

        assert get_property("audit", "observation", "type").value_type == str
        assert get_property("audit", "observation", "timestamp").value_type == str
        assert get_property("audit", "observation", "session_id").value_type == str
        assert get_property("audit", "observation", "severity").value_type == str
        assert get_property("audit", "observation", "tags").value_type == str
        assert get_property("audit", "observation", "payload").value_type == str
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/sandbox/test_event_schema.py -v`
Expected: FAIL — missing properties on observation

- [ ] **Step 3: Add event properties to observation in vocabulary.py**

In `src/umwelt/sandbox/vocabulary.py`, find the section that registers audit/observation properties and add:

```python
    # Event schema properties on observation
    register_property(
        taxon="audit", entity="observation", name="type",
        value_type=str, description="event category: tool_call, build_run, failure, etc.",
    )
    register_property(
        taxon="audit", entity="observation", name="timestamp",
        value_type=str, description="ISO 8601 timestamp",
    )
    register_property(
        taxon="audit", entity="observation", name="session_id",
        value_type=str, description="Claude Code session ID",
    )
    register_property(
        taxon="audit", entity="observation", name="severity",
        value_type=str, description="info, warning, error, critical",
    )
    register_property(
        taxon="audit", entity="observation", name="tags",
        value_type=str, description="classification tags: repeated_pattern, permission_denial, etc.",
    )
    register_property(
        taxon="audit", entity="observation", name="payload",
        value_type=str, description="JSON blob with tool-specific structure",
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/sandbox/test_event_schema.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/sandbox/vocabulary.py tests/sandbox/test_event_schema.py
git commit -m "feat(audit): add shared event schema to observation entity

Six new properties: type, timestamp, session_id, severity, tags, payload.
Common vocabulary for tool observation events across all consumer plugins."
```

---

### Task 7: P3 — Compiler Options (Bless **kwargs)

**Files:**
- Modify: `src/umwelt/compilers/protocol.py:20-36`
- Create: `tests/core/test_compiler_options.py`

- [ ] **Step 1: Write failing test for compiler protocol with options**

Create `tests/core/test_compiler_options.py`:

```python
"""Tests for compiler protocol with **options support."""
from __future__ import annotations

from typing import Any

from umwelt.cascade.resolver import ResolvedView
from umwelt.compilers.protocol import Compiler


class OptionsCapturingCompiler:
    target_name = "test"
    target_format = "json"
    altitude = "semantic"

    def __init__(self):
        self.last_options: dict = {}

    def compile(self, view: ResolvedView, **options: Any) -> dict[str, Any]:
        self.last_options = options
        return {"options": options}


def test_compiler_with_options_satisfies_protocol():
    c = OptionsCapturingCompiler()
    assert isinstance(c, Compiler)


def test_compiler_receives_options():
    c = OptionsCapturingCompiler()
    c.compile(ResolvedView(), workspace_root="/workspace", mode="implement")
    assert c.last_options == {"workspace_root": "/workspace", "mode": "implement"}


def test_compiler_works_without_options():
    c = OptionsCapturingCompiler()
    c.compile(ResolvedView())
    assert c.last_options == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_compiler_options.py -v`
Expected: Possible failure on protocol check if Compiler protocol doesn't accept **options, or PASS if Protocol matching is structural and already accepts it

- [ ] **Step 3: Update Compiler protocol signature**

In `src/umwelt/compilers/protocol.py`, change the compile method:

```python
    def compile(self, view: ResolvedView, **options: Any) -> str | list[str] | dict[str, Any]:
        ...
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_compiler_options.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/compilers/protocol.py tests/core/test_compiler_options.py
git commit -m "feat(compilers): bless **options in Compiler protocol

Compiler.compile() now explicitly accepts **options for caller context
(workspace_root, mode, etc.). Backward compatible — existing compilers
already use **kwargs."
```

---

### Task 8: P3 — Altitude Filtering (Core Enforcement)

**Files:**
- Modify: `src/umwelt/registry/properties.py:22-37`
- Modify: `src/umwelt/compilers/protocol.py:1-67`
- Modify: `src/umwelt/policy/lint.py`
- Create: `tests/core/test_altitude_filtering.py`

- [ ] **Step 1: Write failing tests for altitude on PropertySchema**

Create `tests/core/test_altitude_filtering.py`:

```python
"""Tests for altitude filtering: PropertySchema.altitude, pre-filtering, linting."""
from __future__ import annotations

import pytest

from umwelt.compilers.protocol import Altitude, _ALTITUDE_RANK, _filter_by_altitude
from umwelt.registry import register_entity, register_property, register_taxon, registry_scope
from umwelt.registry.entities import AttrSchema
from umwelt.registry.properties import PropertySchema


def test_property_schema_has_altitude():
    schema = PropertySchema(
        name="editable", taxon="world", entity="file",
        value_type=bool, altitude="os",
    )
    assert schema.altitude == "os"


def test_property_schema_altitude_defaults_to_none():
    schema = PropertySchema(
        name="editable", taxon="world", entity="file",
        value_type=bool,
    )
    assert schema.altitude is None


def test_altitude_ranking():
    assert _ALTITUDE_RANK["os"] < _ALTITUDE_RANK["language"]
    assert _ALTITUDE_RANK["language"] < _ALTITUDE_RANK["semantic"]
    assert _ALTITUDE_RANK["semantic"] < _ALTITUDE_RANK["conversational"]


def test_register_property_with_altitude():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file",
                       attributes={"path": AttrSchema(type=str)}, description="f")
        register_property(
            taxon="world", entity="file", name="editable",
            value_type=bool, description="can edit",
            altitude="os",
        )
        from umwelt.registry import get_property
        prop = get_property("world", "file", "editable")
        assert prop.altitude == "os"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_altitude_filtering.py -v`
Expected: FAIL — PropertySchema has no altitude field, no _ALTITUDE_RANK or _filter_by_altitude

- [ ] **Step 3: Add altitude to PropertySchema**

In `src/umwelt/registry/properties.py`, add to PropertySchema:

```python
@dataclass(frozen=True)
class PropertySchema:
    """Metadata for a registered declaration property."""

    name: str
    taxon: str
    entity: str
    value_type: type
    comparison: Comparison = "exact"
    restrictive_direction: RestrictiveDirection | None = None
    value_attribute: str | None = None
    value_unit: str | None = None
    value_range: tuple[Any, Any] | None = None
    description: str = ""
    category: str | None = None
    altitude: str | None = None
```

Add `altitude` parameter to `register_property()`:

```python
def register_property(
    *,
    taxon: str,
    entity: str,
    name: str,
    value_type: type,
    description: str,
    comparison: Comparison = "exact",
    restrictive_direction: RestrictiveDirection | None = None,
    value_attribute: str | None = None,
    value_unit: str | None = None,
    value_range: tuple[Any, Any] | None = None,
    category: str | None = None,
    altitude: str | None = None,
) -> None:
    """Register a property on a (taxon, entity) pair."""
    get_entity(taxon, entity)
    canonical = resolve_taxon(taxon)
    state = _current_state()
    key = (canonical, entity, name)
    if key in state.properties:
        raise RegistryError(
            f"property {name!r} already registered on {taxon}.{entity}"
        )
    state.properties[key] = PropertySchema(
        name=name,
        taxon=canonical,
        entity=entity,
        value_type=value_type,
        comparison=comparison,
        restrictive_direction=restrictive_direction,
        value_attribute=value_attribute,
        value_unit=value_unit,
        value_range=value_range,
        description=description,
        category=category,
        altitude=altitude,
    )
```

- [ ] **Step 4: Add altitude ranking and filter to protocol.py**

In `src/umwelt/compilers/protocol.py`, add:

```python
_ALTITUDE_RANK: dict[str, int] = {
    "os": 0,
    "language": 1,
    "semantic": 2,
    "conversational": 3,
}


def _filter_by_altitude(view: ResolvedView, max_altitude: Altitude) -> ResolvedView:
    """Return a ResolvedView containing only properties at or below max_altitude."""
    from umwelt.registry.properties import get_property

    max_rank = _ALTITUDE_RANK[max_altitude]
    filtered = ResolvedView()

    for taxon in view.taxa():
        for entity_id, props in view.entries(taxon):
            kept: dict[str, str] = {}
            for prop_name, prop_value in props.items():
                try:
                    schema = get_property(taxon, entity_id.split("#")[0] if "#" in entity_id else "*", prop_name)
                    prop_altitude = schema.altitude
                except Exception:
                    prop_altitude = None

                if prop_altitude is None or _ALTITUDE_RANK.get(prop_altitude, 0) <= max_rank:
                    kept[prop_name] = prop_value
            if kept:
                filtered.add(taxon, entity_id, kept)

    return filtered
```

Note: `ResolvedView` has `taxa() -> list[str]`, `entries(taxon) -> Iterator[(entity, dict)]`, `add(taxon, entity, props)`. The entity is an opaque handle (not a string ID). To look up property schemas, we need the entity's type_name, which requires asking the matcher or inspecting the entity. For P3, a pragmatic approach: look up altitude from `(taxon, type_name, prop_name)` where type_name comes from `getattr(entity, 'type_name', None)` or from the entity_type registry. If lookup fails, include the property (conservative default).

- [ ] **Step 5: Run tests**

Run: `pytest tests/core/test_altitude_filtering.py -v`
Expected: All PASS

- [ ] **Step 6: Add linter warning for unrealizable rules**

Add to `src/umwelt/policy/lint.py`:

```python
def _detect_unrealizable_altitude(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when a resolved property is at an altitude no compiler handles."""
    warnings: list[LintWarning] = []
    try:
        from umwelt.compilers.protocol import _ALTITUDE_RANK, available
        from umwelt.registry.properties import get_property

        registered = available()
        if not registered:
            return warnings

        from umwelt.compilers.protocol import get as get_compiler
        compiler_altitudes = set()
        for name in registered:
            try:
                c = get_compiler(name)
                compiler_altitudes.add(c.altitude)
            except Exception:
                continue

        if not compiler_altitudes:
            return warnings

        max_rank = max(_ALTITUDE_RANK.get(a, 0) for a in compiler_altitudes)

        rows = con.execute(
            "SELECT DISTINCT property_name FROM resolved_properties"
        ).fetchall()

        for (prop_name,) in rows:
            try:
                # Try to find property schema — best effort
                state_rows = con.execute(
                    "SELECT DISTINCT e.type_name, e.taxon FROM entities e "
                    "JOIN resolved_properties rp ON e.id = rp.entity_id "
                    "WHERE rp.property_name = ? LIMIT 1",
                    (prop_name,),
                ).fetchall()
                if not state_rows:
                    continue
                type_name, taxon = state_rows[0]
                schema = get_property(taxon, type_name, prop_name)
                if schema.altitude and _ALTITUDE_RANK.get(schema.altitude, 0) > max_rank:
                    warnings.append(LintWarning(
                        smell="unrealizable_altitude",
                        severity="warning",
                        description=(
                            f"Property '{prop_name}' ({schema.altitude}) has no compiler "
                            f"at that altitude"
                        ),
                        entities=(),
                        property=prop_name,
                    ))
            except Exception:
                continue
    except ImportError:
        pass
    return warnings
```

Add it to `run_lint()`:

```python
    warnings.extend(_detect_unrealizable_altitude(con))
```

- [ ] **Step 7: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures

- [ ] **Step 8: Commit**

```bash
git add src/umwelt/registry/properties.py src/umwelt/compilers/protocol.py \
  src/umwelt/policy/lint.py tests/core/test_altitude_filtering.py
git commit -m "feat(compilers): add altitude filtering with core enforcement

PropertySchema gains altitude field. _filter_by_altitude() pre-filters
ResolvedView before passing to compilers. Linter warns on unrealizable
altitude properties."
```

---

### Task 9: Push all changes

- [ ] **Step 1: Push**

```bash
git push origin main
```
