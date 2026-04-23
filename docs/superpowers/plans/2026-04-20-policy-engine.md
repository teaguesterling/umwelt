# PolicyEngine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `umwelt.policy.PolicyEngine` — a consumer-facing Python API that wraps a compiled SQLite database, providing knowledge queries (resolve, trace), lint analysis, typed projection views, world file entity population, and COW extend semantics.

**Architecture:** New `src/umwelt/policy/` subpackage layered on top of `compilers/sql/`. PolicyEngine manages an in-memory SQLite database. Three constructors (from_files, from_db, programmatic) all produce the same schema. Knowledge queries run SQL against `resolved_properties` and `cascade_candidates`. Lint analysis detects cascade smell patterns in Python. Projection views are vocabulary-driven SQL pivots embedded at compile time.

**Tech Stack:** sqlite3 (stdlib), existing `compilers/sql/` (schema, compiler, populate, resolution, dialects), existing `world/` layer (parser, model), existing `parser` (CSS parsing). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-20-policy-engine-design.md`

---

## Design Decisions

**D1: PolicyEngine wraps an in-memory SQLite connection.** All three constructors ultimately produce a `sqlite3.Connection` in memory. `from_db()` copies the file into memory (COW). `from_files()` builds in memory from scratch. Programmatic builds lazily on first query.

**D2: Queries module is pure SQL against sqlite3.** `policy/queries.py` takes a `sqlite3.Connection` and returns dicts/lists. No dependency on `compilers/sql/` at query time — the compiled database is self-contained. CSS selector string parsing at query time uses `umwelt.selector.parse` + `umwelt.compilers.sql.compiler.compile_selector`.

**D3: Lint runs in Python over SQL results.** Each smell detector queries `cascade_candidates` and/or `resolved_properties` and applies pattern detection. Returns `LintWarning` dataclasses.

**D4: Projection views are generated from the registry's property_types table.** At compile time, `projections.py` reads the property_types table from the DB and generates `CREATE VIEW` DDL for each entity type that has registered properties.

**D5: World file population is a separate function in `compilers/sql/populate.py`.** `populate_from_world()` inserts `DeclaredEntity` instances as rows. It runs after matcher population; world file entities win on (type, id) collision.

**D6: Error hierarchy.** `PolicyError(UmweltError)` is the base. `PolicyDenied(PolicyError)` for `require()` failures. `PolicyCompilationError(PolicyError)` for build failures.

**D7: Structured logging via `logging.getLogger("umwelt.policy")`.** Events emitted at INFO/DEBUG/WARNING levels with structured `extra` dicts. Zero overhead when no handlers are attached.

---

## Files

### New files
| File | Purpose |
|---|---|
| `src/umwelt/policy/__init__.py` | Public API: `PolicyEngine`, `LintWarning`, `TraceResult`, `Candidate` |
| `src/umwelt/policy/engine.py` | `PolicyEngine` class with constructors, query dispatch, COW extend, save/export |
| `src/umwelt/policy/queries.py` | Structured query builders: `resolve_entity`, `resolve_all`, `trace_entity`, `select_entities` |
| `src/umwelt/policy/lint.py` | Smell detection: `run_lint()` returning `list[LintWarning]` |
| `src/umwelt/policy/projections.py` | Vocabulary-driven typed projection view DDL + `compilation_meta` table |
| `tests/policy/__init__.py` | Package marker |
| `tests/policy/conftest.py` | Shared fixtures (compiled DBs, sample worlds + stylesheets) |
| `tests/policy/test_queries.py` | Query method tests |
| `tests/policy/test_engine.py` | PolicyEngine lifecycle, COW, save/load tests |
| `tests/policy/test_lint.py` | Lint smell detection tests |
| `tests/policy/test_projections.py` | Typed projection view tests |
| `tests/policy/test_populate_world.py` | World file entity population tests |
| `tests/policy/test_integration.py` | End-to-end: from_files → resolve → trace → lint |

### Modified files
| File | Change |
|---|---|
| `src/umwelt/errors.py` | Add `PolicyError`, `PolicyDenied`, `PolicyCompilationError` |
| `src/umwelt/compilers/sql/populate.py` | Add `populate_from_world()` function |

---

## Tasks

### Task 1: Error classes + data models

**Files:**
- Modify: `src/umwelt/errors.py`
- Create: `src/umwelt/policy/__init__.py`, `src/umwelt/policy/engine.py` (stub)
- Create: `tests/policy/__init__.py`, `tests/policy/test_engine.py` (model tests only)

- [ ] **Step 1: Write tests for error classes and data models**

```python
# tests/policy/test_engine.py
import pytest
from umwelt.errors import PolicyDenied, PolicyError, PolicyCompilationError, UmweltError


class TestErrorHierarchy:
    def test_policy_error_is_umwelt_error(self):
        assert issubclass(PolicyError, UmweltError)

    def test_policy_denied_is_policy_error(self):
        assert issubclass(PolicyDenied, PolicyError)

    def test_policy_compilation_error_is_policy_error(self):
        assert issubclass(PolicyCompilationError, PolicyError)

    def test_policy_denied_fields(self):
        exc = PolicyDenied(
            entity="tool#Bash",
            property="editable",
            expected="true",
            actual="false",
        )
        assert exc.entity == "tool#Bash"
        assert exc.property == "editable"
        assert exc.expected == "true"
        assert exc.actual == "false"
        assert "tool#Bash" in str(exc)
        assert "editable" in str(exc)


class TestDataModels:
    def test_lint_warning_construction(self):
        from umwelt.policy import LintWarning
        w = LintWarning(
            smell="narrow_win",
            severity="warning",
            description="Winner won by 1 specificity point",
            entities=("tool#Bash",),
            property="max-level",
        )
        assert w.smell == "narrow_win"
        assert w.severity == "warning"

    def test_trace_result_construction(self):
        from umwelt.policy import TraceResult, Candidate
        c = Candidate(
            value="3",
            specificity="00001,00000,00001",
            rule_index=2,
            source_file="policy.umw",
            source_line=10,
            won=True,
        )
        tr = TraceResult(
            entity="tool#Bash",
            property="max-level",
            value="3",
            candidates=(c,),
        )
        assert tr.value == "3"
        assert len(tr.candidates) == 1
        assert tr.candidates[0].won is True

    def test_lint_warning_frozen(self):
        from umwelt.policy import LintWarning
        w = LintWarning(smell="narrow_win", severity="warning", description="test", entities=(), property=None)
        with pytest.raises(AttributeError):
            w.smell = "other"

    def test_candidate_frozen(self):
        from umwelt.policy import Candidate
        c = Candidate(value="3", specificity="x", rule_index=0, source_file="", source_line=0, won=True)
        with pytest.raises(AttributeError):
            c.value = "5"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/policy/test_engine.py -v
```

- [ ] **Step 3: Implement error classes and data models**

Add to `src/umwelt/errors.py`:

```python
class PolicyError(UmweltError):
    """Base class for policy engine errors."""


class PolicyDenied(PolicyError):
    """Raised when a require() check fails."""

    def __init__(
        self,
        entity: str,
        property: str,
        expected: str,
        actual: str | None,
    ) -> None:
        self.entity = entity
        self.property = property
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"policy denied: {entity} {property}={actual!r} (expected {expected!r})"
        )


class PolicyCompilationError(PolicyError):
    """Raised when compilation of policy sources fails."""
```

Create `src/umwelt/policy/__init__.py`:

```python
from umwelt.policy.engine import Candidate, LintWarning, TraceResult

__all__ = [
    "Candidate",
    "LintWarning",
    "TraceResult",
]
```

Create `src/umwelt/policy/engine.py` (data models only for now):

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    value: str
    specificity: str
    rule_index: int
    source_file: str
    source_line: int
    won: bool


@dataclass(frozen=True)
class TraceResult:
    entity: str
    property: str
    value: str | None
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class LintWarning:
    smell: str
    severity: str
    description: str
    entities: tuple[str, ...]
    property: str | None
```

Create `tests/policy/__init__.py` (empty).

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/policy/test_engine.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/policy/ src/umwelt/errors.py tests/policy/
git commit -m "feat(policy): error hierarchy + data models for PolicyEngine"
```

---

### Task 2: Query functions (`queries.py`)

**Files:**
- Create: `src/umwelt/policy/queries.py`
- Create: `tests/policy/conftest.py`, `tests/policy/test_queries.py`

These functions operate on a raw `sqlite3.Connection` — no PolicyEngine yet. They are the SQL query layer.

- [ ] **Step 1: Write conftest fixtures**

```python
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
```

- [ ] **Step 2: Write query tests**

```python
# tests/policy/test_queries.py
import pytest

from umwelt.policy.queries import resolve_entity, resolve_all_entities, trace_entity, select_entities


class TestResolveEntity:
    def test_resolve_single_property(self, policy_db):
        val = resolve_entity(policy_db, type="tool", id="Read", property="allow")
        assert val == "true"

    def test_resolve_all_properties(self, policy_db):
        props = resolve_entity(policy_db, type="tool", id="Bash")
        assert props["risk-note"] == "Prefer structured"
        assert props["allow"] == "false"  # rule 4 wins (higher specificity class selector)

    def test_resolve_cap_comparison(self, policy_db):
        props = resolve_entity(policy_db, type="tool", id="Bash")
        assert props["max-level"] == "3"  # cap: MIN wins

    def test_resolve_nonexistent_entity(self, policy_db):
        val = resolve_entity(policy_db, type="tool", id="NonExistent", property="allow")
        assert val is None

    def test_resolve_nonexistent_property(self, policy_db):
        val = resolve_entity(policy_db, type="tool", id="Read", property="nonexistent")
        assert val is None

    def test_resolve_mode_entity(self, policy_db):
        val = resolve_entity(policy_db, type="mode", id="implement", property="allow")
        assert val == "true"


class TestResolveAll:
    def test_resolve_all_tools(self, policy_db):
        results = resolve_all_entities(policy_db, type="tool")
        assert len(results) == 3
        ids = {r["entity_id"] for r in results}
        assert ids == {"Read", "Edit", "Bash"}

    def test_resolve_all_includes_properties(self, policy_db):
        results = resolve_all_entities(policy_db, type="tool")
        bash = next(r for r in results if r["entity_id"] == "Bash")
        assert bash["properties"]["allow"] == "false"
        assert bash["properties"]["max-level"] == "3"

    def test_resolve_all_modes(self, policy_db):
        results = resolve_all_entities(policy_db, type="mode")
        assert len(results) == 2

    def test_resolve_all_unknown_type(self, policy_db):
        results = resolve_all_entities(policy_db, type="nonexistent")
        assert results == []


class TestTraceEntity:
    def test_trace_returns_all_candidates(self, policy_db):
        result = trace_entity(policy_db, type="tool", id="Bash", property="allow")
        assert len(result.candidates) >= 2  # rule 0 and rule 4

    def test_trace_marks_winner(self, policy_db):
        result = trace_entity(policy_db, type="tool", id="Bash", property="allow")
        winners = [c for c in result.candidates if c.won]
        assert len(winners) == 1
        assert winners[0].value == "false"

    def test_trace_value_matches_resolve(self, policy_db):
        result = trace_entity(policy_db, type="tool", id="Bash", property="allow")
        resolved = resolve_entity(policy_db, type="tool", id="Bash", property="allow")
        assert result.value == resolved

    def test_trace_nonexistent(self, policy_db):
        result = trace_entity(policy_db, type="tool", id="NonExistent", property="allow")
        assert result.value is None
        assert result.candidates == ()

    def test_trace_candidates_ordered_by_specificity(self, policy_db):
        result = trace_entity(policy_db, type="tool", id="Bash", property="max-level")
        specs = [c.specificity for c in result.candidates]
        assert specs == sorted(specs, reverse=True)


class TestSelectEntities:
    def test_select_by_type(self, policy_db):
        entities = select_entities(policy_db, type="tool")
        assert len(entities) == 3

    def test_select_by_type_and_id(self, policy_db):
        entities = select_entities(policy_db, type="tool", id="Bash")
        assert len(entities) == 1
        assert entities[0]["entity_id"] == "Bash"

    def test_select_by_classes(self, policy_db):
        entities = select_entities(policy_db, type="tool", classes=["dangerous"])
        assert len(entities) == 1
        assert entities[0]["entity_id"] == "Bash"

    def test_select_returns_entity_fields(self, policy_db):
        entities = select_entities(policy_db, type="tool", id="Read")
        e = entities[0]
        assert "entity_id" in e
        assert "type_name" in e
        assert "classes" in e
        assert "attributes" in e
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
pytest tests/policy/test_queries.py -v
```

- [ ] **Step 4: Implement queries.py**

```python
# src/umwelt/policy/queries.py
from __future__ import annotations

import json
import sqlite3

from umwelt.policy.engine import Candidate, TraceResult


def resolve_entity(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str,
    property: str | None = None,
) -> str | dict[str, str] | None:
    """Resolve properties for a single entity.

    If *property* is given, returns that property's value (or None).
    If *property* is omitted, returns a dict of all resolved properties.
    """
    entity_row = _find_entity(con, type=type, id=id)
    if entity_row is None:
        return None if property else {}

    entity_pk = entity_row[0]

    if property is not None:
        row = con.execute(
            "SELECT property_value FROM resolved_properties "
            "WHERE entity_id = ? AND property_name = ?",
            (entity_pk, property),
        ).fetchone()
        return row[0] if row else None

    rows = con.execute(
        "SELECT property_name, property_value FROM resolved_properties WHERE entity_id = ?",
        (entity_pk,),
    ).fetchall()
    return {name: value for name, value in rows}


def resolve_all_entities(
    con: sqlite3.Connection,
    *,
    type: str,
) -> list[dict]:
    """Resolve all entities of a type with their properties."""
    entities = con.execute(
        "SELECT id, entity_id, classes, attributes FROM entities WHERE type_name = ?",
        (type,),
    ).fetchall()

    results = []
    for eid, entity_id, classes_json, attrs_json in entities:
        props_rows = con.execute(
            "SELECT property_name, property_value FROM resolved_properties WHERE entity_id = ?",
            (eid,),
        ).fetchall()
        props = {name: value for name, value in props_rows}
        results.append({
            "entity_id": entity_id,
            "type_name": type,
            "classes": json.loads(classes_json) if classes_json else [],
            "attributes": json.loads(attrs_json) if attrs_json else {},
            "properties": props,
        })
    return results


def trace_entity(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str,
    property: str,
) -> TraceResult:
    """Trace all cascade candidates for an (entity, property) pair."""
    entity_row = _find_entity(con, type=type, id=id)
    if entity_row is None:
        return TraceResult(
            entity=f"{type}#{id}",
            property=property,
            value=None,
            candidates=(),
        )

    entity_pk = entity_row[0]

    # Get winning value
    winner_row = con.execute(
        "SELECT property_value FROM resolved_properties "
        "WHERE entity_id = ? AND property_name = ?",
        (entity_pk, property),
    ).fetchone()
    winning_value = winner_row[0] if winner_row else None

    # Get all candidates
    rows = con.execute(
        "SELECT property_value, specificity, rule_index, source_file, source_line "
        "FROM cascade_candidates "
        "WHERE entity_id = ? AND property_name = ? "
        "ORDER BY specificity DESC, rule_index DESC",
        (entity_pk, property),
    ).fetchall()

    candidates = []
    for value, spec, rule_idx, src_file, src_line in rows:
        candidates.append(Candidate(
            value=value,
            specificity=spec,
            rule_index=rule_idx,
            source_file=src_file or "",
            source_line=src_line or 0,
            won=(value == winning_value and not any(c.won for c in candidates)),
        ))

    return TraceResult(
        entity=f"{type}#{id}",
        property=property,
        value=winning_value,
        candidates=tuple(candidates),
    )


def select_entities(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str | None = None,
    classes: list[str] | None = None,
) -> list[dict]:
    """Select entities matching type, optional id, and optional classes."""
    sql = "SELECT id, entity_id, type_name, classes, attributes FROM entities WHERE type_name = ?"
    params: list = [type]

    if id is not None:
        sql += " AND entity_id = ?"
        params.append(id)

    rows = con.execute(sql, params).fetchall()

    results = []
    for eid, entity_id, type_name, classes_json, attrs_json in rows:
        entity_classes = json.loads(classes_json) if classes_json else []
        if classes and not all(c in entity_classes for c in classes):
            continue
        results.append({
            "id": eid,
            "entity_id": entity_id,
            "type_name": type_name,
            "classes": entity_classes,
            "attributes": json.loads(attrs_json) if attrs_json else {},
        })
    return results


def _find_entity(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str,
) -> tuple | None:
    """Find an entity by (type, id). Returns the row or None."""
    return con.execute(
        "SELECT id, entity_id, type_name, classes, attributes FROM entities "
        "WHERE type_name = ? AND entity_id = ?",
        (type, id),
    ).fetchone()
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/policy/test_queries.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/policy/queries.py tests/policy/conftest.py tests/policy/test_queries.py
git commit -m "feat(policy): query functions — resolve, trace, select"
```

---

### Task 3: World file entity population

**Files:**
- Modify: `src/umwelt/compilers/sql/populate.py`
- Create: `tests/policy/test_populate_world.py`

- [ ] **Step 1: Write tests**

```python
# tests/policy/test_populate_world.py
import json
import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.populate import populate_from_world
from umwelt.compilers.sql.schema import create_schema
from umwelt.world.model import DeclaredEntity, Projection, Provenance, WorldFile


@pytest.fixture
def empty_db():
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))
    yield con
    con.close()


class TestPopulateFromWorld:
    def test_basic_entity_insertion(self, empty_db):
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Read"),),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        row = empty_db.execute(
            "SELECT type_name, entity_id FROM entities WHERE entity_id = 'Read'"
        ).fetchone()
        assert row == ("tool", "Read")

    def test_classes_stored_as_json(self, empty_db):
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Bash", classes=("dangerous", "shell")),),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        row = empty_db.execute(
            "SELECT classes FROM entities WHERE entity_id = 'Bash'"
        ).fetchone()
        assert json.loads(row[0]) == ["dangerous", "shell"]

    def test_attributes_stored_as_json(self, empty_db):
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Read", attributes={"description": "read files"}),),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        row = empty_db.execute(
            "SELECT attributes FROM entities WHERE entity_id = 'Read'"
        ).fetchone()
        assert json.loads(row[0])["description"] == "read files"

    def test_multiple_entities(self, empty_db):
        wf = WorldFile(
            entities=(
                DeclaredEntity(type="tool", id="Read"),
                DeclaredEntity(type="tool", id="Edit"),
                DeclaredEntity(type="mode", id="implement"),
            ),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        count = empty_db.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        assert count == 3

    def test_projection_inserted_as_entity(self, empty_db):
        wf = WorldFile(
            entities=(),
            projections=(Projection(type="dir", id="node_modules", attributes={"path": "node_modules/"}),),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        row = empty_db.execute(
            "SELECT type_name, entity_id FROM entities WHERE entity_id = 'node_modules'"
        ).fetchone()
        assert row == ("dir", "node_modules")

    def test_world_entity_wins_on_collision(self, empty_db):
        # Pre-insert a matcher-discovered entity
        empty_db.execute(
            "INSERT INTO entities (taxon, type_name, entity_id, classes, attributes, depth) "
            "VALUES ('capability', 'tool', 'Bash', NULL, NULL, 0)"
        )
        empty_db.commit()

        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Bash", classes=("dangerous",)),),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)

        rows = empty_db.execute(
            "SELECT classes FROM entities WHERE entity_id = 'Bash'"
        ).fetchall()
        assert len(rows) == 1
        assert json.loads(rows[0][0]) == ["dangerous"]

    def test_closure_table_rebuilt(self, empty_db):
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Read"),),
            projections=(),
            warnings=(),
        )
        populate_from_world(empty_db, wf)
        closure = empty_db.execute(
            "SELECT COUNT(*) FROM entity_closure"
        ).fetchone()[0]
        assert closure >= 1  # at least self-closure
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/policy/test_populate_world.py -v
```

- [ ] **Step 3: Implement populate_from_world**

Add to `src/umwelt/compilers/sql/populate.py`:

```python
def populate_from_world(con: Any, world: WorldFile) -> None:
    """Insert DeclaredEntity instances from a WorldFile into the entities table.

    World file entities win on (type_name, entity_id) collision with
    existing matcher-discovered entities.
    """
    from umwelt.world.model import WorldFile  # deferred to avoid circular

    for entity in world.entities:
        _upsert_declared_entity(con, entity)

    for proj in world.projections:
        _upsert_projection(con, proj)

    con.commit()
    _rebuild_closure(con)


def _upsert_declared_entity(con: Any, entity: Any) -> None:
    """Insert or replace a DeclaredEntity into the entities table."""
    import json as _json

    classes_json = _json.dumps(list(entity.classes)) if entity.classes else None
    attrs_json = _json.dumps(entity.attributes) if entity.attributes else None

    existing = con.execute(
        "SELECT id FROM entities WHERE type_name = ? AND entity_id = ?",
        (entity.type, entity.id),
    ).fetchone()

    if existing:
        con.execute(
            "UPDATE entities SET classes = ?, attributes = ? WHERE id = ?",
            (classes_json, attrs_json, existing[0]),
        )
    else:
        taxon = _guess_taxon(entity.type)
        con.execute(
            "INSERT INTO entities (taxon, type_name, entity_id, classes, attributes, depth) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (taxon, entity.type, entity.id, classes_json, attrs_json),
        )


def _upsert_projection(con: Any, proj: Any) -> None:
    """Insert a Projection as an entity."""
    import json as _json

    attrs_json = _json.dumps(proj.attributes) if proj.attributes else None

    existing = con.execute(
        "SELECT id FROM entities WHERE type_name = ? AND entity_id = ?",
        (proj.type, proj.id),
    ).fetchone()

    if existing:
        con.execute(
            "UPDATE entities SET attributes = ? WHERE id = ?",
            (attrs_json, existing[0]),
        )
    else:
        taxon = _guess_taxon(proj.type)
        con.execute(
            "INSERT INTO entities (taxon, type_name, entity_id, attributes, depth) "
            "VALUES (?, ?, ?, ?, 0)",
            (taxon, proj.type, proj.id, attrs_json),
        )


def _guess_taxon(type_name: str) -> str:
    """Look up the taxon for an entity type from the registry, or default."""
    try:
        from umwelt.registry.entities import resolve_entity_type
        taxa = resolve_entity_type(type_name)
        if taxa:
            return taxa[0]
    except Exception:
        pass
    return type_name
```

The import of `WorldFile` in the type annotation uses a string to avoid circular imports. The function signature uses `Any` for the `world` parameter but documents that it expects a `WorldFile`.

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/policy/test_populate_world.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/compilers/sql/populate.py tests/policy/test_populate_world.py
git commit -m "feat(policy): world file entity population via populate_from_world()"
```

---

### Task 4: Typed projection views (`projections.py`)

**Files:**
- Create: `src/umwelt/policy/projections.py`
- Create: `tests/policy/test_projections.py`

- [ ] **Step 1: Write tests**

```python
# tests/policy/test_projections.py
import json
import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.resolution import create_resolution_views
from umwelt.compilers.sql.schema import create_schema
from umwelt.policy.projections import create_projection_views, create_compilation_meta


@pytest.fixture
def projection_db():
    """DB with entities, candidates, resolution views, and property_types."""
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))

    # Register property types
    prop_types = [
        ("capability", "tool", "allow", "str", "exact", ""),
        ("capability", "tool", "visible", "str", "exact", ""),
        ("capability", "tool", "max-level", "int", "<=", ""),
        ("state", "mode", "writable", "str", "exact", ""),
        ("state", "mode", "strategy", "str", "exact", ""),
    ]
    con.executemany(
        "INSERT INTO property_types (taxon, entity_type, name, value_type, comparison, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        prop_types,
    )

    # Entities
    entities = [
        (1, "capability", "tool", "Read", None, json.dumps({"name": "Read"}), None, 0),
        (2, "capability", "tool", "Bash", json.dumps(["dangerous"]), json.dumps({"name": "Bash"}), None, 0),
        (3, "state", "mode", "implement", None, json.dumps({}), None, 0),
    ]
    con.executemany(
        "INSERT INTO entities (id, taxon, type_name, entity_id, classes, attributes, parent_id, depth) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        entities,
    )

    # Cascade candidates + resolution views
    spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
    candidates = [
        (1, "allow", "true", "exact", spec, 0, "", 0),
        (2, "allow", "true", "exact", spec, 0, "", 0),
        (2, "max-level", "3", "<=", spec, 0, "", 0),
        (3, "writable", "src/", "exact", spec, 0, "", 0),
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


class TestProjectionViews:
    def test_creates_tools_view(self, projection_db):
        create_projection_views(projection_db)
        rows = projection_db.execute("SELECT * FROM tools").fetchall()
        assert len(rows) == 2  # Read and Bash

    def test_tools_view_has_pivoted_columns(self, projection_db):
        create_projection_views(projection_db)
        row = projection_db.execute(
            "SELECT name, allow, max_level FROM tools WHERE name = 'Bash'"
        ).fetchone()
        assert row is not None
        assert row[1] == "true"  # allow
        assert row[2] == "3"    # max_level

    def test_creates_modes_view(self, projection_db):
        create_projection_views(projection_db)
        rows = projection_db.execute("SELECT * FROM modes").fetchall()
        assert len(rows) == 1

    def test_modes_view_columns(self, projection_db):
        create_projection_views(projection_db)
        row = projection_db.execute(
            "SELECT name, writable FROM modes WHERE name = 'implement'"
        ).fetchone()
        assert row is not None
        assert row[1] == "src/"

    def test_creates_resolved_entities_view(self, projection_db):
        create_projection_views(projection_db)
        rows = projection_db.execute("SELECT * FROM resolved_entities").fetchall()
        assert len(rows) >= 2  # at least the entities with resolved properties

    def test_no_property_types_still_works(self):
        dialect = SQLiteDialect()
        con = sqlite3.connect(":memory:")
        con.executescript(create_schema(dialect))
        create_resolution_views(con, dialect)
        create_projection_views(con)
        # No views to create, but should not error


class TestCompilationMeta:
    def test_creates_meta_table(self, projection_db):
        create_compilation_meta(projection_db, source_world="test.world.yml", source_stylesheet="policy.umw")
        row = projection_db.execute(
            "SELECT value FROM compilation_meta WHERE key = 'source_world'"
        ).fetchone()
        assert row[0] == "test.world.yml"

    def test_meta_has_entity_count(self, projection_db):
        create_compilation_meta(projection_db)
        row = projection_db.execute(
            "SELECT value FROM compilation_meta WHERE key = 'entity_count'"
        ).fetchone()
        assert int(row[0]) == 3

    def test_meta_has_compiled_at(self, projection_db):
        create_compilation_meta(projection_db)
        row = projection_db.execute(
            "SELECT value FROM compilation_meta WHERE key = 'compiled_at'"
        ).fetchone()
        assert row[0]  # non-empty ISO timestamp
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/policy/test_projections.py -v
```

- [ ] **Step 3: Implement projections.py**

```python
# src/umwelt/policy/projections.py
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def create_projection_views(con: sqlite3.Connection) -> None:
    """Create vocabulary-driven typed projection views.

    Reads entity types and their properties from property_types table,
    generates a pivot view for each entity type.
    """
    _create_resolved_entities_view(con)

    type_props = _get_type_properties(con)
    for entity_type, props in type_props.items():
        _create_typed_view(con, entity_type, props)


def create_compilation_meta(
    con: sqlite3.Connection,
    *,
    source_world: str | None = None,
    source_stylesheet: str | None = None,
) -> None:
    """Create and populate the compilation_meta table."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS compilation_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    entity_count = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]

    resolved_count_row = con.execute(
        "SELECT COUNT(*) FROM resolved_properties"
    ).fetchone()
    resolved_count = resolved_count_row[0] if resolved_count_row else 0

    meta = {
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": str(entity_count),
        "resolved_count": str(resolved_count),
        "dialect": "sqlite",
    }
    if source_world:
        meta["source_world"] = source_world
    if source_stylesheet:
        meta["source_stylesheet"] = source_stylesheet

    for key, value in meta.items():
        con.execute(
            "INSERT OR REPLACE INTO compilation_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
    con.commit()


def _get_type_properties(con: sqlite3.Connection) -> dict[str, list[str]]:
    """Read property_types and group property names by entity_type."""
    rows = con.execute(
        "SELECT entity_type, name FROM property_types ORDER BY entity_type, name"
    ).fetchall()
    result: dict[str, list[str]] = {}
    for entity_type, prop_name in rows:
        result.setdefault(entity_type, []).append(prop_name)
    return result


def _create_typed_view(
    con: sqlite3.Connection,
    entity_type: str,
    properties: list[str],
) -> None:
    """Create a typed projection view for one entity type."""
    view_name = entity_type + "s"  # tool -> tools, mode -> modes
    safe_view = view_name.replace('"', '""')

    pivot_cols = []
    for prop in properties:
        col_name = prop.replace("-", "_")
        safe_col = col_name.replace('"', '""')
        safe_prop = prop.replace("'", "''")
        pivot_cols.append(
            f'    MAX(CASE WHEN rp.property_name = \'{safe_prop}\' '
            f'THEN rp.property_value END) AS "{safe_col}"'
        )

    pivot_sql = ",\n".join(pivot_cols)
    safe_type = entity_type.replace("'", "''")

    ddl = f"""
CREATE VIEW IF NOT EXISTS "{safe_view}" AS
SELECT e.entity_id AS name, e.classes, e.attributes,
{pivot_sql}
FROM entities e
LEFT JOIN resolved_properties rp ON e.id = rp.entity_id
WHERE e.type_name = '{safe_type}'
GROUP BY e.id, e.entity_id, e.classes, e.attributes;
"""
    con.executescript(ddl)


def _create_resolved_entities_view(con: sqlite3.Connection) -> None:
    """Create the generic resolved_entities view with JSON property map."""
    con.executescript("""
CREATE VIEW IF NOT EXISTS resolved_entities AS
SELECT e.id, e.taxon, e.type_name, e.entity_id, e.classes, e.attributes,
    json_group_object(rp.property_name, rp.property_value) AS properties
FROM entities e
LEFT JOIN resolved_properties rp ON e.id = rp.entity_id
GROUP BY e.id, e.taxon, e.type_name, e.entity_id, e.classes, e.attributes;
""")
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/policy/test_projections.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/policy/projections.py tests/policy/test_projections.py
git commit -m "feat(policy): typed projection views + compilation_meta"
```

---

### Task 5: Lint analysis (`lint.py`)

**Files:**
- Create: `src/umwelt/policy/lint.py`
- Create: `tests/policy/test_lint.py`

- [ ] **Step 1: Write tests**

```python
# tests/policy/test_lint.py
import json
import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.resolution import create_resolution_views
from umwelt.compilers.sql.schema import create_schema
from umwelt.policy.engine import LintWarning
from umwelt.policy.lint import run_lint


@pytest.fixture
def lint_db():
    """DB set up for lint testing with various smell scenarios."""
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))

    entities = [
        (1, "capability", "tool", "Read", None, json.dumps({"name": "Read"}), None, 0),
        (2, "capability", "tool", "Bash", json.dumps(["dangerous"]), json.dumps({"name": "Bash"}), None, 0),
        (3, "capability", "tool", "Orphan", None, json.dumps({"name": "Orphan"}), None, 0),
    ]
    con.executemany(
        "INSERT INTO entities (id, taxon, type_name, entity_id, classes, attributes, parent_id, depth) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        entities,
    )
    con.executescript("""
        DELETE FROM entity_closure;
        INSERT INTO entity_closure (ancestor_id, descendant_id, depth)
        SELECT id, id, 0 FROM entities;
    """)
    return con


class TestNarrowWin:
    def test_detects_narrow_win(self, lint_db):
        dialect = SQLiteDialect()
        spec_low = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
        spec_high = '["00000","00000","00000","00001","00000","00001","00000","00000"]'

        # Two rules for same entity/property, specificity differs by one position
        candidates = [
            (2, "allow", "true", "exact", spec_low, 0, "a.umw", 1),
            (2, "allow", "false", "exact", spec_high, 1, "a.umw", 3),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        narrow = [w for w in warnings if w.smell == "narrow_win"]
        assert len(narrow) >= 1


class TestShadowedRule:
    def test_detects_shadowed_rule(self, lint_db):
        dialect = SQLiteDialect()
        spec_low = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
        spec_high = '["00000","00000","00000","00001","00000","00001","00000","00000"]'

        # Rule at a.umw:5 sets allow for entity 2, but higher-spec rule always wins
        candidates = [
            (2, "allow", "true", "exact", spec_low, 0, "a.umw", 5),
            (2, "allow", "false", "exact", spec_high, 1, "a.umw", 10),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        shadowed = [w for w in warnings if w.smell == "shadowed_rule"]
        assert len(shadowed) >= 1


class TestUncoveredEntity:
    def test_detects_uncovered_entity(self, lint_db):
        dialect = SQLiteDialect()
        spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'

        # Rules for entities 1 and 2 only — entity 3 (Orphan) has no candidates
        candidates = [
            (1, "allow", "true", "exact", spec, 0, "a.umw", 1),
            (2, "allow", "true", "exact", spec, 0, "a.umw", 1),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        uncovered = [w for w in warnings if w.smell == "uncovered_entity"]
        assert len(uncovered) >= 1
        assert any("Orphan" in w.description for w in uncovered)


class TestConflictingIntent:
    def test_detects_conflicting_intent(self, lint_db):
        dialect = SQLiteDialect()
        spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'

        # Same specificity, opposite values — winner decided by source order alone
        candidates = [
            (2, "allow", "true", "exact", spec, 0, "a.umw", 1),
            (2, "allow", "false", "exact", spec, 1, "a.umw", 5),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        conflicting = [w for w in warnings if w.smell == "conflicting_intent"]
        assert len(conflicting) >= 1


class TestSpecificityEscalation:
    def test_detects_escalation(self, lint_db):
        dialect = SQLiteDialect()
        spec1 = '["00000","00000","00000","00001","00000","00000","00000","00000"]'
        spec2 = '["00000","00000","00000","00001","00000","00001","00000","00000"]'
        spec3 = '["00000","00000","00001","00001","00000","00001","00000","00000"]'

        # 3+ candidates with strictly increasing specificity
        candidates = [
            (2, "max-level", "5", "<=", spec1, 0, "a.umw", 1),
            (2, "max-level", "3", "<=", spec2, 1, "a.umw", 3),
            (2, "max-level", "1", "<=", spec3, 2, "a.umw", 5),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        escalation = [w for w in warnings if w.smell == "specificity_escalation"]
        assert len(escalation) >= 1


class TestNoSmells:
    def test_clean_db_no_warnings(self, lint_db):
        dialect = SQLiteDialect()
        spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'

        # Simple, non-overlapping rules
        candidates = [
            (1, "allow", "true", "exact", spec, 0, "a.umw", 1),
            (2, "allow", "true", "exact", spec, 0, "a.umw", 1),
            (3, "allow", "true", "exact", spec, 0, "a.umw", 1),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        # No narrow_win, conflicting_intent, or escalation — possibly uncovered if no candidates match all
        serious = [w for w in warnings if w.severity == "warning"]
        assert len(serious) == 0
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/policy/test_lint.py -v
```

- [ ] **Step 3: Implement lint.py**

```python
# src/umwelt/policy/lint.py
from __future__ import annotations

import json
import logging
import sqlite3

from umwelt.policy.engine import LintWarning

logger = logging.getLogger("umwelt.policy")


def run_lint(con: sqlite3.Connection) -> list[LintWarning]:
    """Run all lint smell detectors and return warnings."""
    warnings: list[LintWarning] = []
    warnings.extend(_detect_narrow_win(con))
    warnings.extend(_detect_shadowed_rule(con))
    warnings.extend(_detect_conflicting_intent(con))
    warnings.extend(_detect_uncovered_entity(con))
    warnings.extend(_detect_specificity_escalation(con))

    for w in warnings:
        logger.warning(
            "lint: %s — %s",
            w.smell,
            w.description,
            extra={"smell": w.smell, "entities": w.entities, "severity": w.severity},
        )
    return warnings


def _detect_narrow_win(con: sqlite3.Connection) -> list[LintWarning]:
    """Detect cases where the winner's specificity is barely higher than the runner-up."""
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT cc.entity_id, cc.property_name, cc.property_value, cc.specificity, cc.rule_index
        FROM cascade_candidates cc
        WHERE cc.comparison = 'exact'
        ORDER BY cc.entity_id, cc.property_name, cc.specificity DESC, cc.rule_index DESC
    """).fetchall()

    groups: dict[tuple[int, str], list[tuple]] = {}
    for row in rows:
        key = (row[0], row[1])
        groups.setdefault(key, []).append(row)

    for (entity_id, prop_name), candidates in groups.items():
        if len(candidates) < 2:
            continue
        winner_spec = _parse_specificity(candidates[0][3])
        runner_spec = _parse_specificity(candidates[1][3])
        if winner_spec is None or runner_spec is None:
            continue
        diff = sum(w - r for w, r in zip(winner_spec, runner_spec))
        if 0 < diff <= 1:
            entity_name = _entity_name(con, entity_id)
            warnings.append(LintWarning(
                smell="narrow_win",
                severity="warning",
                description=f"{entity_name} '{prop_name}' won by specificity margin of {diff}",
                entities=(entity_name,),
                property=prop_name,
            ))
    return warnings


def _detect_shadowed_rule(con: sqlite3.Connection) -> list[LintWarning]:
    """Detect rules that never win for any entity."""
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT cc.source_file, cc.source_line, cc.property_name, cc.entity_id
        FROM cascade_candidates cc
        LEFT JOIN resolved_properties rp
            ON cc.entity_id = rp.entity_id
            AND cc.property_name = rp.property_name
            AND cc.property_value = rp.property_value
            AND cc.specificity = rp.specificity
            AND cc.rule_index = rp.rule_index
        WHERE rp.entity_id IS NULL
          AND cc.source_file IS NOT NULL
          AND cc.source_file != ''
    """).fetchall()

    shadowed_rules: dict[tuple[str, int], set[str]] = {}
    for src_file, src_line, prop_name, entity_id in rows:
        key = (src_file, src_line)
        shadowed_rules.setdefault(key, set()).add(prop_name)

    for (src_file, src_line), props in shadowed_rules.items():
        warnings.append(LintWarning(
            smell="shadowed_rule",
            severity="info",
            description=f"Rule at {src_file}:{src_line} never wins for properties: {', '.join(sorted(props))}",
            entities=(),
            property=None,
        ))
    return warnings


def _detect_conflicting_intent(con: sqlite3.Connection) -> list[LintWarning]:
    """Detect same-specificity candidates with opposite values."""
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT c1.entity_id, c1.property_name,
               c1.property_value, c2.property_value,
               c1.specificity
        FROM cascade_candidates c1
        JOIN cascade_candidates c2
            ON c1.entity_id = c2.entity_id
            AND c1.property_name = c2.property_name
            AND c1.specificity = c2.specificity
            AND c1.rule_index < c2.rule_index
        WHERE c1.property_value != c2.property_value
          AND c1.comparison = 'exact'
          AND c2.comparison = 'exact'
    """).fetchall()

    seen: set[tuple[int, str]] = set()
    for entity_id, prop_name, val1, val2, spec in rows:
        key = (entity_id, prop_name)
        if key in seen:
            continue
        seen.add(key)
        entity_name = _entity_name(con, entity_id)
        warnings.append(LintWarning(
            smell="conflicting_intent",
            severity="warning",
            description=f"{entity_name} '{prop_name}': '{val1}' vs '{val2}' at same specificity — winner decided by source order",
            entities=(entity_name,),
            property=prop_name,
        ))
    return warnings


def _detect_uncovered_entity(con: sqlite3.Connection) -> list[LintWarning]:
    """Detect entities with no resolved properties."""
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT e.id, e.type_name, e.entity_id
        FROM entities e
        LEFT JOIN resolved_properties rp ON e.id = rp.entity_id
        WHERE rp.entity_id IS NULL
    """).fetchall()

    for eid, type_name, entity_id in rows:
        name = f"{type_name}#{entity_id}" if entity_id else f"{type_name}(id={eid})"
        warnings.append(LintWarning(
            smell="uncovered_entity",
            severity="info",
            description=f"{name} has no resolved properties",
            entities=(name,),
            property=None,
        ))
    return warnings


def _detect_specificity_escalation(con: sqlite3.Connection) -> list[LintWarning]:
    """Detect 3+ candidates with strictly increasing specificity."""
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT entity_id, property_name, specificity
        FROM cascade_candidates
        ORDER BY entity_id, property_name, specificity ASC
    """).fetchall()

    groups: dict[tuple[int, str], list[str]] = {}
    for entity_id, prop_name, spec in rows:
        key = (entity_id, prop_name)
        groups.setdefault(key, []).append(spec)

    for (entity_id, prop_name), specs in groups.items():
        unique_specs = sorted(set(specs))
        if len(unique_specs) >= 3:
            entity_name = _entity_name(con, entity_id)
            warnings.append(LintWarning(
                smell="specificity_escalation",
                severity="warning",
                description=f"{entity_name} '{prop_name}' has {len(unique_specs)} specificity levels — possible escalation war",
                entities=(entity_name,),
                property=prop_name,
            ))
    return warnings


def _parse_specificity(spec_str: str) -> list[int] | None:
    """Parse a JSON-encoded specificity array."""
    try:
        parts = json.loads(spec_str)
        return [int(p) for p in parts]
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def _entity_name(con: sqlite3.Connection, entity_id: int) -> str:
    """Look up a human-readable entity name by PK."""
    row = con.execute(
        "SELECT type_name, entity_id FROM entities WHERE id = ?",
        (entity_id,),
    ).fetchone()
    if row is None:
        return f"entity({entity_id})"
    type_name, eid = row
    return f"{type_name}#{eid}" if eid else f"{type_name}(id={entity_id})"
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/policy/test_lint.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/policy/lint.py tests/policy/test_lint.py
git commit -m "feat(policy): lint analysis — five cascade smell detectors"
```

---

### Task 6: PolicyEngine class (`engine.py`)

**Files:**
- Modify: `src/umwelt/policy/engine.py`
- Modify: `tests/policy/test_engine.py`

This task adds the full `PolicyEngine` class — three constructors, query dispatch, COW extend, save/export, logging.

- [ ] **Step 1: Write tests**

```python
# Add to tests/policy/test_engine.py (after existing TestErrorHierarchy and TestDataModels)

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from umwelt.errors import PolicyDenied
from umwelt.policy.engine import PolicyEngine


@pytest.fixture
def sample_world_yml(tmp_path):
    p = tmp_path / "test.world.yml"
    p.write_text("""
entities:
  - type: tool
    id: Read
  - type: tool
    id: Bash
    classes: [dangerous]
  - type: mode
    id: implement
""")
    return p


@pytest.fixture
def sample_stylesheet(tmp_path):
    p = tmp_path / "policy.umw"
    p.write_text("""
tool { allow: true; max-level: 5; }
tool.dangerous { max-level: 3; allow: false; }
mode { allow: true; }
""")
    return p


class TestFromFiles:
    def test_creates_engine(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        assert engine is not None

    def test_resolve_after_from_files(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        val = engine.resolve(type="tool", id="Read", property="allow")
        assert val == "true"

    def test_resolve_all_properties(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        props = engine.resolve(type="tool", id="Bash")
        assert isinstance(props, dict)
        assert "allow" in props
        assert "max-level" in props


class TestFromDb:
    def test_roundtrip_save_load(self, sample_world_yml, sample_stylesheet, tmp_path):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        db_path = tmp_path / "policy.db"
        engine1.save(str(db_path))

        engine2 = PolicyEngine.from_db(str(db_path))
        val = engine2.resolve(type="tool", id="Read", property="allow")
        assert val == "true"

    def test_from_db_is_cow(self, sample_world_yml, sample_stylesheet, tmp_path):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        db_path = tmp_path / "policy.db"
        engine1.save(str(db_path))

        engine2 = PolicyEngine.from_db(str(db_path))
        # Modifying engine2 should not affect the file
        # (We can't easily test this without extend, but from_db copies to memory)
        assert engine2.resolve(type="tool", id="Read", property="allow") == "true"


class TestProgrammatic:
    def test_programmatic_build(self):
        engine = PolicyEngine()
        engine.add_entities([
            {"type": "tool", "id": "Read"},
            {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
        ])
        engine.add_stylesheet("tool { allow: true; }\ntool.dangerous { allow: false; }")

        val = engine.resolve(type="tool", id="Read", property="allow")
        assert val == "true"

        val = engine.resolve(type="tool", id="Bash", property="allow")
        assert val == "false"


class TestExtend:
    def test_extend_produces_new_engine(self, sample_world_yml, sample_stylesheet):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        engine2 = engine1.extend(
            entities=[{"type": "mode", "id": "review"}],
        )
        assert engine2 is not engine1

    def test_extend_preserves_original(self, sample_world_yml, sample_stylesheet):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        engine1.extend(
            entities=[{"type": "mode", "id": "review"}],
        )
        # Original should still have only implement
        modes = engine1.resolve_all(type="mode")
        assert len(modes) == 1

    def test_extend_adds_entities(self, sample_world_yml, sample_stylesheet):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        engine2 = engine1.extend(
            entities=[{"type": "mode", "id": "review"}],
        )
        modes = engine2.resolve_all(type="mode")
        assert len(modes) == 2

    def test_extend_with_stylesheet(self, sample_world_yml, sample_stylesheet):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        engine2 = engine1.extend(
            stylesheet="tool#Read { visible: false; }",
        )
        val = engine2.resolve(type="tool", id="Read", property="visible")
        assert val == "false"


class TestConvenience:
    def test_check_true(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        assert engine.check(type="tool", id="Read", allow="true") is True

    def test_check_false(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        assert engine.check(type="tool", id="Bash", allow="true") is False

    def test_require_passes(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        engine.require(type="tool", id="Read", allow="true")  # should not raise

    def test_require_raises_policy_denied(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        with pytest.raises(PolicyDenied) as exc_info:
            engine.require(type="tool", id="Bash", allow="true")
        assert exc_info.value.actual == "false"


class TestTrace:
    def test_trace_returns_candidates(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        result = engine.trace(type="tool", id="Bash", property="allow")
        assert result.value is not None
        assert len(result.candidates) >= 1


class TestLint:
    def test_lint_returns_list(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        warnings = engine.lint()
        assert isinstance(warnings, list)


class TestExecute:
    def test_raw_sql(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        rows = engine.execute("SELECT COUNT(*) FROM entities")
        assert rows[0][0] >= 3
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/policy/test_engine.py -v
```

- [ ] **Step 3: Implement PolicyEngine class**

Replace `src/umwelt/policy/engine.py` with the full implementation:

```python
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from umwelt.errors import PolicyCompilationError, PolicyDenied

logger = logging.getLogger("umwelt.policy")


@dataclass(frozen=True)
class Candidate:
    value: str
    specificity: str
    rule_index: int
    source_file: str
    source_line: int
    won: bool


@dataclass(frozen=True)
class TraceResult:
    entity: str
    property: str
    value: str | None
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class LintWarning:
    smell: str
    severity: str
    description: str
    entities: tuple[str, ...]
    property: str | None


class PolicyEngine:
    """Consumer-facing API for querying resolved world knowledge."""

    def __init__(self) -> None:
        self._con: sqlite3.Connection | None = None
        self._pending_entities: list[dict[str, Any]] = []
        self._pending_stylesheets: list[str] = []
        self._compiled = False

    @classmethod
    def from_files(
        cls,
        *,
        world: str | Path,
        stylesheet: str | Path,
    ) -> PolicyEngine:
        """Build a PolicyEngine from source files."""
        from umwelt.compilers.sql.compiler import compile_view
        from umwelt.compilers.sql.dialects import SQLiteDialect
        from umwelt.compilers.sql.populate import populate_from_world
        from umwelt.compilers.sql.schema import create_schema
        from umwelt.parser import parse
        from umwelt.policy.projections import create_compilation_meta, create_projection_views
        from umwelt.world.parser import load_world

        world_path = Path(world)
        stylesheet_path = Path(stylesheet)

        try:
            _load_default_vocabulary()
        except Exception:
            pass

        world_file = load_world(world_path)

        view = parse(stylesheet_path)

        dialect = SQLiteDialect()
        con = sqlite3.connect(":memory:")
        con.executescript(create_schema(dialect))

        populate_from_world(con, world_file)
        compile_view(con, view, dialect, source_file=str(stylesheet_path))

        try:
            create_projection_views(con)
        except Exception:
            pass
        try:
            create_compilation_meta(
                con,
                source_world=str(world_path),
                source_stylesheet=str(stylesheet_path),
            )
        except Exception:
            pass

        engine = cls.__new__(cls)
        engine._con = con
        engine._pending_entities = []
        engine._pending_stylesheets = []
        engine._compiled = True

        logger.info(
            "compile",
            extra={
                "source_files": [str(world_path), str(stylesheet_path)],
                "entity_count": con.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
            },
        )
        return engine

    @classmethod
    def from_db(cls, path: str | Path) -> PolicyEngine:
        """Open a compiled database (copied into memory for COW safety)."""
        source = sqlite3.connect(str(path))
        con = sqlite3.connect(":memory:")
        source.backup(con)
        source.close()

        engine = cls.__new__(cls)
        engine._con = con
        engine._pending_entities = []
        engine._pending_stylesheets = []
        engine._compiled = True
        return engine

    def add_entities(self, entities: list[dict[str, Any]]) -> None:
        """Add entities for programmatic construction."""
        self._pending_entities.extend(entities)
        self._compiled = False

    def add_stylesheet(self, css: str) -> None:
        """Add CSS stylesheet text for programmatic construction."""
        self._pending_stylesheets.append(css)
        self._compiled = False

    def register_vocabulary(self, registrar: Any) -> None:
        """Register vocabulary via a callable (e.g., register_sandbox_vocabulary)."""
        registrar()

    def _ensure_compiled(self) -> sqlite3.Connection:
        """Lazily compile on first query for programmatic construction."""
        if self._con is not None and self._compiled:
            return self._con

        from umwelt.compilers.sql.compiler import compile_view
        from umwelt.compilers.sql.dialects import SQLiteDialect
        from umwelt.compilers.sql.populate import populate_from_world
        from umwelt.compilers.sql.schema import create_schema
        from umwelt.parser import parse as parse_css
        from umwelt.policy.projections import create_projection_views
        from umwelt.world.model import DeclaredEntity, WorldFile

        dialect = SQLiteDialect()
        con = self._con or sqlite3.connect(":memory:")
        if not self._compiled:
            con.executescript(create_schema(dialect))

        if self._pending_entities:
            declared = []
            for e in self._pending_entities:
                classes = tuple(e.get("classes", ()))
                declared.append(DeclaredEntity(
                    type=e["type"],
                    id=e["id"],
                    classes=classes,
                    attributes=e.get("attributes", {}),
                    parent=e.get("parent"),
                ))
            wf = WorldFile(entities=tuple(declared), projections=(), warnings=())
            populate_from_world(con, wf)
            self._pending_entities = []

        for css_text in self._pending_stylesheets:
            view = parse_css(css_text, validate=False)
            compile_view(con, view, dialect)
        self._pending_stylesheets = []

        try:
            create_projection_views(con)
        except Exception:
            pass

        self._con = con
        self._compiled = True
        return con

    def resolve(
        self,
        *,
        type: str,
        id: str,
        property: str | None = None,
    ) -> str | dict[str, str] | None:
        """Resolve properties for a single entity."""
        from umwelt.policy.queries import resolve_entity

        con = self._ensure_compiled()
        result = resolve_entity(con, type=type, id=id, property=property)
        logger.info(
            "resolve",
            extra={"entity": f"{type}#{id}", "property": property, "value": result},
        )
        return result

    def resolve_all(self, *, type: str) -> list[dict]:
        """Resolve all entities of a type with their properties."""
        from umwelt.policy.queries import resolve_all_entities

        con = self._ensure_compiled()
        results = resolve_all_entities(con, type=type)
        logger.info(
            "resolve_all",
            extra={"type": type, "result_count": len(results)},
        )
        return results

    def trace(
        self,
        *,
        type: str,
        id: str,
        property: str,
    ) -> TraceResult:
        """Trace all cascade candidates for an (entity, property) pair."""
        from umwelt.policy.queries import trace_entity

        con = self._ensure_compiled()
        result = trace_entity(con, type=type, id=id, property=property)
        logger.debug(
            "trace",
            extra={"entity": f"{type}#{id}", "property": property, "candidates": len(result.candidates)},
        )
        return result

    def lint(self) -> list[LintWarning]:
        """Run lint analysis on the compiled database."""
        from umwelt.policy.lint import run_lint

        con = self._ensure_compiled()
        return run_lint(con)

    def check(self, *, type: str, id: str, **expected: str) -> bool:
        """Check whether resolved properties match expected values."""
        for prop_name, expected_val in expected.items():
            actual = self.resolve(type=type, id=id, property=prop_name)
            if actual != expected_val:
                return False
        return True

    def require(self, *, type: str, id: str, **expected: str) -> None:
        """Raise PolicyDenied if resolved properties don't match."""
        for prop_name, expected_val in expected.items():
            actual = self.resolve(type=type, id=id, property=prop_name)
            if actual != expected_val:
                logger.warning(
                    "require_denied",
                    extra={"entity": f"{type}#{id}", "property": prop_name, "expected": expected_val, "actual": actual},
                )
                raise PolicyDenied(
                    entity=f"{type}#{id}",
                    property=prop_name,
                    expected=expected_val,
                    actual=actual or "(none)",
                )

    def extend(
        self,
        *,
        entities: list[dict[str, Any]] | None = None,
        stylesheet: str | None = None,
    ) -> PolicyEngine:
        """Create a new engine with additional entities and/or stylesheet rules."""
        con = self._ensure_compiled()

        new_con = sqlite3.connect(":memory:")
        con.backup(new_con)

        new_engine = PolicyEngine.__new__(PolicyEngine)
        new_engine._con = new_con
        new_engine._pending_entities = list(entities) if entities else []
        new_engine._pending_stylesheets = [stylesheet] if stylesheet else []
        new_engine._compiled = False

        if new_engine._pending_entities or new_engine._pending_stylesheets:
            new_engine._recompile_incremental()

        logger.info(
            "extend",
            extra={
                "entities_added": len(entities) if entities else 0,
                "stylesheet_added": bool(stylesheet),
            },
        )
        return new_engine

    def _recompile_incremental(self) -> None:
        """Recompile after extend — add new entities/rules to existing DB."""
        from umwelt.compilers.sql.compiler import compile_view
        from umwelt.compilers.sql.dialects import SQLiteDialect
        from umwelt.compilers.sql.populate import _rebuild_closure, populate_from_world
        from umwelt.compilers.sql.resolution import create_resolution_views
        from umwelt.parser import parse as parse_css
        from umwelt.policy.projections import create_projection_views
        from umwelt.world.model import DeclaredEntity, WorldFile

        con = self._con
        dialect = SQLiteDialect()

        if self._pending_entities:
            declared = []
            for e in self._pending_entities:
                classes = tuple(e.get("classes", ()))
                declared.append(DeclaredEntity(
                    type=e["type"],
                    id=e["id"],
                    classes=classes,
                    attributes=e.get("attributes", {}),
                    parent=e.get("parent"),
                ))
            wf = WorldFile(entities=tuple(declared), projections=(), warnings=())
            populate_from_world(con, wf)
            self._pending_entities = []

        # Drop and recreate resolution views before adding new rules
        for view_name in ("resolved_properties", "_resolved_exact", "_resolved_cap", "_resolved_pattern"):
            con.execute(f"DROP VIEW IF EXISTS {view_name}")

        for css_text in self._pending_stylesheets:
            view = parse_css(css_text, validate=False)
            compile_view(con, view, dialect)
        self._pending_stylesheets = []

        if not self._pending_stylesheets:
            # Resolution views were recreated by compile_view if we had stylesheets.
            # If we only added entities (no new stylesheet), recreate them now.
            try:
                con.execute("SELECT 1 FROM resolved_properties LIMIT 1")
            except sqlite3.OperationalError:
                create_resolution_views(con, dialect)

        # Recreate projection views
        for view_name in ("resolved_entities", "tools", "modes"):
            con.execute(f"DROP VIEW IF EXISTS {view_name}")
        try:
            create_projection_views(con)
        except Exception:
            pass

        self._compiled = True

    def save(self, path: str | Path) -> None:
        """Save the compiled database to a file."""
        con = self._ensure_compiled()
        target = sqlite3.connect(str(path))
        con.backup(target)
        target.close()

    def to_files(
        self,
        *,
        world: str | Path,
        stylesheet: str | Path,
    ) -> None:
        """Export the engine state back to source files (best-effort round-trip)."""
        con = self._ensure_compiled()

        # Export entities as world YAML
        entities = con.execute(
            "SELECT type_name, entity_id, classes, attributes FROM entities ORDER BY type_name, entity_id"
        ).fetchall()

        import json

        import yaml

        entity_dicts = []
        for type_name, entity_id, classes_json, attrs_json in entities:
            d: dict[str, Any] = {"type": type_name, "id": entity_id}
            if classes_json:
                classes = json.loads(classes_json)
                if classes:
                    d["classes"] = classes
            if attrs_json:
                attrs = json.loads(attrs_json)
                if attrs:
                    d["attributes"] = attrs
            entity_dicts.append(d)

        world_data = {"entities": entity_dicts}
        Path(world).write_text(yaml.dump(world_data, default_flow_style=False, sort_keys=False))

        # Export cascade candidates as CSS (best-effort)
        rules = con.execute(
            "SELECT DISTINCT source_file, source_line FROM cascade_candidates "
            "WHERE source_file IS NOT NULL AND source_file != '' "
            "ORDER BY source_file, source_line"
        ).fetchall()

        css_lines: list[str] = []
        seen_rules: set[tuple] = set()
        candidates = con.execute(
            "SELECT cc.entity_id, e.type_name, e.entity_id, e.classes, "
            "cc.property_name, cc.property_value, cc.source_file, cc.source_line "
            "FROM cascade_candidates cc "
            "JOIN entities e ON cc.entity_id = e.id "
            "ORDER BY cc.source_file, cc.source_line, cc.rule_index"
        ).fetchall()

        current_rule: tuple | None = None
        current_decls: list[str] = []
        current_selector: str = ""

        for eid, type_name, entity_id_str, classes_json, prop_name, prop_value, src_file, src_line in candidates:
            rule_key = (src_file, src_line)
            selector = type_name
            if entity_id_str:
                selector += f"#{entity_id_str}"

            if rule_key != current_rule:
                if current_rule is not None and current_decls:
                    css_lines.append(f"{current_selector} {{ {'; '.join(current_decls)}; }}")
                current_rule = rule_key
                current_selector = selector
                current_decls = []

            decl = f"{prop_name}: {prop_value}"
            if decl not in current_decls:
                current_decls.append(decl)

        if current_rule is not None and current_decls:
            css_lines.append(f"{current_selector} {{ {'; '.join(current_decls)}; }}")

        Path(stylesheet).write_text("\n".join(css_lines) + "\n")

    def execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Execute raw SQL against the compiled database."""
        con = self._ensure_compiled()
        return con.execute(sql, params).fetchall()


def _load_default_vocabulary() -> None:
    """Auto-load the sandbox vocabulary if available."""
    try:
        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        register_sandbox_vocabulary()
    except ImportError:
        pass
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/policy/test_engine.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/policy/engine.py tests/policy/test_engine.py
git commit -m "feat(policy): PolicyEngine class — constructors, queries, COW extend, save/export"
```

---

### Task 7: Update `__init__.py` public API

**Files:**
- Modify: `src/umwelt/policy/__init__.py`

- [ ] **Step 1: Update exports**

```python
# src/umwelt/policy/__init__.py
from umwelt.policy.engine import Candidate, LintWarning, PolicyEngine, TraceResult

__all__ = [
    "Candidate",
    "LintWarning",
    "PolicyEngine",
    "TraceResult",
]
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from umwelt.policy import PolicyEngine, LintWarning, TraceResult, Candidate; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/umwelt/policy/__init__.py
git commit -m "feat(policy): public API exports"
```

---

### Task 8: Integration test

**Files:**
- Create: `tests/policy/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/policy/test_integration.py
import yaml
from pathlib import Path

from umwelt.errors import PolicyDenied
from umwelt.policy import PolicyEngine


def test_full_pipeline(tmp_path):
    """End-to-end: from_files → resolve → trace → lint → save → from_db → resolve."""
    world_path = tmp_path / "delegate.world.yml"
    world_path.write_text("""
entities:
  - type: tool
    id: Read
  - type: tool
    id: Edit
    classes: [edit]
  - type: tool
    id: Bash
    classes: [dangerous, shell]
  - type: mode
    id: implement
""")
    style_path = tmp_path / "policy.umw"
    style_path.write_text("""
tool { allow: true; max-level: 5; }
tool.dangerous { max-level: 3; allow: false; }
tool#Bash { risk-note: Prefer structured tools; }
mode { allow: true; }
""")

    # Build from files
    engine = PolicyEngine.from_files(world=world_path, stylesheet=style_path)

    # Resolve
    assert engine.resolve(type="tool", id="Read", property="allow") == "true"
    assert engine.resolve(type="tool", id="Bash", property="allow") == "false"
    assert engine.resolve(type="tool", id="Bash", property="max-level") == "3"

    bash_props = engine.resolve(type="tool", id="Bash")
    assert isinstance(bash_props, dict)
    assert "risk-note" in bash_props

    # Resolve all
    tools = engine.resolve_all(type="tool")
    assert len(tools) == 3

    # Trace
    trace = engine.trace(type="tool", id="Bash", property="allow")
    assert trace.value == "false"
    assert len(trace.candidates) >= 2

    # Lint
    warnings = engine.lint()
    assert isinstance(warnings, list)

    # Check / require
    assert engine.check(type="tool", id="Read", allow="true") is True
    assert engine.check(type="tool", id="Bash", allow="true") is False

    import pytest
    with pytest.raises(PolicyDenied):
        engine.require(type="tool", id="Bash", allow="true")

    # Save and reload
    db_path = tmp_path / "policy.db"
    engine.save(str(db_path))
    assert db_path.exists()

    engine2 = PolicyEngine.from_db(str(db_path))
    assert engine2.resolve(type="tool", id="Read", property="allow") == "true"
    assert engine2.resolve(type="tool", id="Bash", property="allow") == "false"

    # Raw SQL
    rows = engine2.execute("SELECT COUNT(*) FROM entities")
    assert rows[0][0] >= 4


def test_extend_cow_semantics(tmp_path):
    """Extend produces a new engine; original is unchanged."""
    world_path = tmp_path / "w.world.yml"
    world_path.write_text("entities:\n  - type: tool\n    id: Read\n")
    style_path = tmp_path / "p.umw"
    style_path.write_text("tool { allow: true; }\n")

    engine1 = PolicyEngine.from_files(world=world_path, stylesheet=style_path)
    engine2 = engine1.extend(
        entities=[{"type": "tool", "id": "Bash", "classes": ["dangerous"]}],
        stylesheet="tool.dangerous { allow: false; }",
    )

    # Original unchanged
    tools1 = engine1.resolve_all(type="tool")
    assert len(tools1) == 1

    # Extended has both
    tools2 = engine2.resolve_all(type="tool")
    assert len(tools2) == 2
    assert engine2.resolve(type="tool", id="Bash", property="allow") == "false"


def test_programmatic_construction():
    """Build engine entirely in code."""
    engine = PolicyEngine()
    engine.add_entities([
        {"type": "tool", "id": "Read"},
        {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
    ])
    engine.add_stylesheet("tool { allow: true; }\ntool.dangerous { allow: false; }")

    assert engine.resolve(type="tool", id="Read", property="allow") == "true"
    assert engine.resolve(type="tool", id="Bash", property="allow") == "false"


def test_to_files_roundtrip(tmp_path):
    """Export to files and verify they contain expected data."""
    engine = PolicyEngine()
    engine.add_entities([
        {"type": "tool", "id": "Read"},
        {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
    ])
    engine.add_stylesheet("tool { allow: true; }")

    world_out = tmp_path / "out.world.yml"
    style_out = tmp_path / "out.umw"
    engine.to_files(world=world_out, stylesheet=style_out)

    assert world_out.exists()
    assert style_out.exists()

    world_data = yaml.safe_load(world_out.read_text())
    assert len(world_data["entities"]) >= 2
    ids = {e["id"] for e in world_data["entities"]}
    assert "Read" in ids
    assert "Bash" in ids
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/policy/test_integration.py -v
```

- [ ] **Step 3: Run full test suite to check for regressions**

```bash
pytest tests/ -v
```

- [ ] **Step 4: Run lint**

```bash
ruff check src/umwelt/policy/ tests/policy/
```

- [ ] **Step 5: Commit**

```bash
git add tests/policy/test_integration.py
git commit -m "feat(policy): integration tests for full PolicyEngine pipeline"
```

---

## Verification

After all tasks:

1. **Unit tests pass:** `pytest tests/policy/ -v` — all green
2. **Full suite passes:** `pytest tests/ -v` — no regressions in `compilers/sql/`, `world/`, etc.
3. **Lint passes:** `ruff check src/umwelt/policy/ tests/policy/`
4. **Python API works:**
   ```python
   from umwelt.policy import PolicyEngine

   # Programmatic
   engine = PolicyEngine()
   engine.add_entities([{"type": "tool", "id": "Read"}, {"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
   engine.add_stylesheet("tool { allow: true; }\ntool.dangerous { allow: false; }")
   print(engine.resolve(type="tool", id="Read", property="allow"))  # "true"
   print(engine.resolve(type="tool", id="Bash", property="allow"))  # "false"
   print(engine.trace(type="tool", id="Bash", property="allow"))
   print(engine.lint())

   # From files
   engine2 = PolicyEngine.from_files(world="delegate.world.yml", stylesheet="policy.umw")
   engine2.save("policy.db")

   # From compiled DB
   engine3 = PolicyEngine.from_db("policy.db")
   print(engine3.resolve_all(type="tool"))

   # COW extend
   engine4 = engine3.extend(entities=[{"type": "mode", "id": "review"}])
   ```
5. **Compiled DB is self-contained:**
   ```bash
   sqlite3 policy.db "SELECT * FROM tools"
   sqlite3 policy.db "SELECT * FROM resolved_entities"
   sqlite3 policy.db "SELECT * FROM compilation_meta"
   ```
