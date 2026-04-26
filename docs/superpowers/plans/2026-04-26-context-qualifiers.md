# Generic Context Qualifiers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mode-specific SQL plumbing with a generic context-qualifier mechanism so any entity type can gate rules, not just `mode`.

**Architecture:** Add a `cascade_context_qualifiers` table that stores (taxon, type_name, entity_id) per candidate row. Replace `_extract_mode_qualifier()` with `_extract_context_qualifiers()` that finds all cross-taxon context parts. Replace `_MODE_FILTER` with a temp-table-based approach. Add `context=` parameter to PolicyEngine methods alongside deprecated `mode=`.

**Tech Stack:** Python 3.11+, SQLite, pytest

---

### Task 1: Schema — Add cascade_context_qualifiers table

**Files:**
- Modify: `src/umwelt/compilers/sql/schema.py`
- Create: `tests/policy/test_context_qualifiers.py`

- [ ] **Step 1: Write failing test for new table**

Create `tests/policy/test_context_qualifiers.py`:

```python
"""Tests for generic context qualifier mechanism."""
from __future__ import annotations

import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.schema import EXPECTED_TABLES, create_schema


def test_context_qualifiers_table_exists():
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "cascade_context_qualifiers" in tables


def test_context_qualifiers_in_expected_tables():
    assert "cascade_context_qualifiers" in EXPECTED_TABLES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/policy/test_context_qualifiers.py -v`
Expected: FAIL — table doesn't exist, not in EXPECTED_TABLES

- [ ] **Step 3: Add table to schema**

In `src/umwelt/compilers/sql/schema.py`, add `"cascade_context_qualifiers"` to `EXPECTED_TABLES`:

```python
EXPECTED_TABLES = [
    "taxa",
    "entity_types",
    "property_types",
    "entities",
    "entity_closure",
    "cascade_candidates",
    "cascade_context_qualifiers",
    "fixed_constraints",
]
```

Add the table DDL after the cascade_candidates section (after the `idx_candidates_comparison` index, before the fixed_constraints section):

```python
    # -- Context qualifiers (normalized from cascade_candidates)
    sections.append(f"""
CREATE TABLE IF NOT EXISTS cascade_context_qualifiers (
    candidate_rowid {int_type} NOT NULL,
    taxon           {text_type} NOT NULL,
    type_name       {text_type} NOT NULL,
    entity_id       {text_type} NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ccq_candidate ON cascade_context_qualifiers(candidate_rowid);
CREATE INDEX IF NOT EXISTS idx_ccq_lookup ON cascade_context_qualifiers(taxon, type_name, entity_id);""")
```

Note: Uses `candidate_rowid` referencing SQLite's implicit `rowid` on `cascade_candidates`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/policy/test_context_qualifiers.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/compilers/sql/schema.py tests/policy/test_context_qualifiers.py
git commit -m "feat(sql): add cascade_context_qualifiers table

Generic normalized table for cross-taxon context qualifiers. Replaces
the mode_qualifier column approach with (taxon, type_name, entity_id)
triples per cascade candidate."
```

---

### Task 2: Compiler — Extract and store generic context qualifiers

**Files:**
- Modify: `src/umwelt/compilers/sql/compiler.py`
- Modify: `tests/policy/test_context_qualifiers.py`

- [ ] **Step 1: Write failing tests for context qualifier extraction and storage**

Append to `tests/policy/test_context_qualifiers.py`:

```python
from umwelt.policy import PolicyEngine


@pytest.fixture
def context_engine(tmp_path):
    world = tmp_path / "w.world.yml"
    world.write_text("""
entities:
  - type: tool
    id: Read
  - type: tool
    id: Bash
    classes: [dangerous]
  - type: mode
    id: review
  - type: mode
    id: implement
  - type: principal
    id: Teague
""")
    style = tmp_path / "p.umw"
    style.write_text("""
tool { allow: true; }
mode#review tool { allow: false; }
mode#review tool[name="Read"] { allow: true; }
mode#implement tool.dangerous { max-level: 3; }
principal#Teague tool { visible: true; }
""")
    return PolicyEngine.from_files(world=world, stylesheet=style)


class TestContextQualifierStorage:
    def test_unscoped_rule_has_no_qualifiers(self, context_engine):
        """Unscoped rules should have zero rows in cascade_context_qualifiers."""
        rows = context_engine.execute("""
            SELECT cc.rowid
            FROM cascade_candidates cc
            WHERE cc.mode_qualifier IS NULL
            AND NOT EXISTS (
                SELECT 1 FROM cascade_context_qualifiers ccq
                WHERE ccq.candidate_rowid = cc.rowid
            )
        """)
        assert len(rows) > 0, "Expected unscoped rules with no context qualifiers"

    def test_mode_gated_rule_has_context_qualifier(self, context_engine):
        """mode#review gated rules should have a context qualifier row."""
        rows = context_engine.execute("""
            SELECT ccq.taxon, ccq.type_name, ccq.entity_id
            FROM cascade_context_qualifiers ccq
            JOIN cascade_candidates cc ON ccq.candidate_rowid = cc.rowid
            WHERE ccq.type_name = 'mode' AND ccq.entity_id = 'review'
        """)
        assert len(rows) > 0

    def test_principal_gated_rule_has_context_qualifier(self, context_engine):
        """principal#Teague gated rules should have a context qualifier row."""
        rows = context_engine.execute("""
            SELECT ccq.taxon, ccq.type_name, ccq.entity_id
            FROM cascade_context_qualifiers ccq
            WHERE ccq.type_name = 'principal' AND ccq.entity_id = 'Teague'
        """)
        assert len(rows) > 0

    def test_qualifier_taxon_is_correct(self, context_engine):
        """Context qualifier should store the correct taxon."""
        rows = context_engine.execute("""
            SELECT DISTINCT ccq.taxon, ccq.type_name
            FROM cascade_context_qualifiers ccq
            ORDER BY ccq.type_name
        """)
        result = {(r[0], r[1]) for r in rows}
        assert ("state", "mode") in result
        assert ("principal", "principal") in result

    def test_backward_compat_mode_qualifier_still_populated(self, context_engine):
        """mode_qualifier column still populated for backward compatibility."""
        rows = context_engine.execute(
            "SELECT DISTINCT mode_qualifier FROM cascade_candidates "
            "WHERE mode_qualifier IS NOT NULL ORDER BY mode_qualifier"
        )
        qualifiers = {r[0] for r in rows}
        assert "review" in qualifiers
        assert "implement" in qualifiers
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/policy/test_context_qualifiers.py::TestContextQualifierStorage -v`
Expected: FAIL — cascade_context_qualifiers is empty (no rows inserted)

- [ ] **Step 3: Add `_extract_context_qualifiers` and update `compile_view`**

In `src/umwelt/compilers/sql/compiler.py`, add after `_extract_mode_qualifier`:

```python
def _extract_context_qualifiers(
    selector: ComplexSelector,
) -> list[tuple[str, str, str]]:
    """Extract (taxon, type_name, entity_id) for all cross-taxon context qualifier parts."""
    qualifiers = []
    for part in selector.parts:
        if (
            part.mode == "context"
            and part.selector.id_value is not None
        ):
            qualifiers.append((
                part.selector.taxon,
                part.selector.type_name,
                part.selector.id_value,
            ))
    return qualifiers
```

Then update `compile_view` to insert context qualifier rows after each candidate batch. Replace the body of the `for rule_idx, rule in enumerate(view.rules):` loop with:

```python
    for rule_idx, rule in enumerate(view.rules):
        for selector in rule.selectors:
            where_sql = compile_selector(selector, dialect)
            spec = selector.specificity if hasattr(selector, "specificity") else (0,) * 8
            spec_str = dialect.format_specificity(spec)
            src_line = rule.span.line if hasattr(rule, "span") else 0
            mode_qual = _extract_mode_qualifier(selector)
            context_quals = _extract_context_qualifiers(selector)

            for decl in rule.declarations:
                comparison = _infer_comparison(decl.property_name)
                value = ", ".join(decl.values)
                con.execute(
                    "INSERT INTO cascade_candidates "
                    "(entity_id, property_name, property_value, comparison, "
                    "specificity, rule_index, source_file, source_line, mode_qualifier) "
                    f"SELECT e.id, ?, ?, ?, ?, ?, ?, ?, ? "
                    f"FROM entities e WHERE {where_sql}",
                    (decl.property_name, value, comparison,
                     spec_str, rule_idx, source_file, src_line, mode_qual),
                )

            if context_quals:
                # Find the rowids of candidates just inserted for this selector
                candidate_rows = con.execute(
                    "SELECT rowid FROM cascade_candidates "
                    "WHERE rule_index = ? AND source_file = ? AND source_line = ? "
                    "ORDER BY rowid DESC",
                    (rule_idx, source_file, src_line),
                ).fetchall()

                for (candidate_rowid,) in candidate_rows:
                    # Only insert for candidates from this selector batch
                    existing = con.execute(
                        "SELECT 1 FROM cascade_context_qualifiers WHERE candidate_rowid = ?",
                        (candidate_rowid,),
                    ).fetchone()
                    if existing:
                        continue
                    for taxon, type_name, entity_id in context_quals:
                        con.execute(
                            "INSERT INTO cascade_context_qualifiers "
                            "(candidate_rowid, taxon, type_name, entity_id) "
                            "VALUES (?, ?, ?, ?)",
                            (candidate_rowid, taxon, type_name, entity_id),
                        )
```

**Wait** — this approach of finding "just inserted" rows by rule_index is fragile. A better approach: track rowids directly. Since SQLite `INSERT ... SELECT` doesn't return rowids easily, use a simpler method — query for the max rowid before the insert, then grab everything above it after:

Replace the loop body with:

```python
    for rule_idx, rule in enumerate(view.rules):
        for selector in rule.selectors:
            where_sql = compile_selector(selector, dialect)
            spec = selector.specificity if hasattr(selector, "specificity") else (0,) * 8
            spec_str = dialect.format_specificity(spec)
            src_line = rule.span.line if hasattr(rule, "span") else 0
            mode_qual = _extract_mode_qualifier(selector)
            context_quals = _extract_context_qualifiers(selector)

            # Track max rowid before insert to find new rows
            max_before = con.execute(
                "SELECT COALESCE(MAX(rowid), 0) FROM cascade_candidates"
            ).fetchone()[0] if context_quals else 0

            for decl in rule.declarations:
                comparison = _infer_comparison(decl.property_name)
                value = ", ".join(decl.values)
                con.execute(
                    "INSERT INTO cascade_candidates "
                    "(entity_id, property_name, property_value, comparison, "
                    "specificity, rule_index, source_file, source_line, mode_qualifier) "
                    f"SELECT e.id, ?, ?, ?, ?, ?, ?, ?, ? "
                    f"FROM entities e WHERE {where_sql}",
                    (decl.property_name, value, comparison,
                     spec_str, rule_idx, source_file, src_line, mode_qual),
                )

            if context_quals:
                new_rows = con.execute(
                    "SELECT rowid FROM cascade_candidates WHERE rowid > ?",
                    (max_before,),
                ).fetchall()
                for (candidate_rowid,) in new_rows:
                    for taxon, type_name, entity_id in context_quals:
                        con.execute(
                            "INSERT INTO cascade_context_qualifiers "
                            "(candidate_rowid, taxon, type_name, entity_id) "
                            "VALUES (?, ?, ?, ?)",
                            (candidate_rowid, taxon, type_name, entity_id),
                        )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/policy/test_context_qualifiers.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures. mode_qualifier is still populated (backward compat).

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/compilers/sql/compiler.py tests/policy/test_context_qualifiers.py
git commit -m "feat(sql): extract and store generic context qualifiers

_extract_context_qualifiers() finds all cross-taxon context parts in a
selector (not just mode). Populates cascade_context_qualifiers alongside
existing mode_qualifier for backward compatibility."
```

---

### Task 3: Queries — Generic context filtering replaces _MODE_FILTER

**Files:**
- Modify: `src/umwelt/policy/queries.py`
- Modify: `tests/policy/test_context_qualifiers.py`

- [ ] **Step 1: Write failing tests for context-filtered resolution**

Append to `tests/policy/test_context_qualifiers.py`:

```python
class TestContextFilteredResolve:
    def test_context_mode_review_denies_bash(self, context_engine):
        val = context_engine.resolve(
            type="tool", id="Bash", property="allow",
            context=[("state", "mode", "review")],
        )
        assert val == "false"

    def test_context_mode_review_allows_read(self, context_engine):
        val = context_engine.resolve(
            type="tool", id="Read", property="allow",
            context=[("state", "mode", "review")],
        )
        assert val == "true"

    def test_context_mode_implement_caps_level(self, context_engine):
        val = context_engine.resolve(
            type="tool", id="Bash", property="max-level",
            context=[("state", "mode", "implement")],
        )
        assert val == "3"

    def test_context_none_returns_all(self, context_engine):
        """No context should return the same as no mode (unfiltered)."""
        val_no_ctx = context_engine.resolve(type="tool", id="Bash", property="allow")
        val_ctx_none = context_engine.resolve(
            type="tool", id="Bash", property="allow", context=None,
        )
        assert val_no_ctx == val_ctx_none

    def test_context_unscoped_rules_always_apply(self, context_engine):
        val = context_engine.resolve(
            type="tool", id="Read", property="allow",
            context=[("state", "mode", "implement")],
        )
        assert val == "true"

    def test_context_dict_shorthand(self, context_engine):
        """Dict form: {"mode": "review"} should work like tuple form."""
        val = context_engine.resolve(
            type="tool", id="Bash", property="allow",
            context={"mode": "review"},
        )
        assert val == "false"

    def test_context_multi_qualifier(self, context_engine):
        """Multiple context qualifiers can be passed."""
        val = context_engine.resolve(
            type="tool", id="Bash", property="allow",
            context=[("state", "mode", "review"), ("principal", "principal", "Teague")],
        )
        assert val == "false"


class TestContextFilteredResolveAll:
    def test_resolve_all_with_context(self, context_engine):
        tools = context_engine.resolve_all(
            type="tool",
            context=[("state", "mode", "review")],
        )
        bash = next(t for t in tools if t["entity_id"] == "Bash")
        assert bash["properties"]["allow"] == "false"


class TestContextFilteredTrace:
    def test_trace_with_context(self, context_engine):
        result = context_engine.trace(
            type="tool", id="Bash", property="max-level",
            context=[("state", "mode", "implement")],
        )
        assert result.value == "3"


class TestContextFilteredCheck:
    def test_check_with_context(self, context_engine):
        assert context_engine.check(
            type="tool", id="Bash",
            context=[("state", "mode", "review")],
            allow="false",
        )

    def test_require_with_context(self, context_engine):
        context_engine.require(
            type="tool", id="Read",
            context=[("state", "mode", "review")],
            allow="true",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/policy/test_context_qualifiers.py::TestContextFilteredResolve -v`
Expected: FAIL — resolve() doesn't accept `context` parameter

- [ ] **Step 3: Add context-aware resolution to queries.py**

In `src/umwelt/policy/queries.py`, add context-aware query templates and a helper to populate the active_context temp table. Add these after the existing `_MODE_FILTER` and template definitions:

```python
ContextQualifier = tuple[str, str, str]  # (taxon, type_name, entity_id)

_CONTEXT_FILTER = """
AND NOT EXISTS (
    SELECT 1 FROM cascade_context_qualifiers ccq
    WHERE ccq.candidate_rowid = cascade_candidates.rowid
    AND NOT EXISTS (
        SELECT 1 FROM _active_context ac
        WHERE ac.taxon = ccq.taxon
          AND ac.type_name = ccq.type_name
          AND ac.entity_id = ccq.entity_id
    )
)
"""

_RESOLVE_CTX_EXACT = """
SELECT property_name, property_value FROM (
    SELECT property_name, property_value, ROW_NUMBER() OVER (
        PARTITION BY property_name
        ORDER BY specificity DESC, rule_index DESC
    ) AS _rn
    FROM cascade_candidates
    WHERE entity_id = ? AND comparison = 'exact'
    {context_clause}
) WHERE _rn = 1
"""

_RESOLVE_CTX_CAP = """
SELECT property_name, property_value FROM (
    SELECT property_name, property_value, ROW_NUMBER() OVER (
        PARTITION BY property_name
        ORDER BY CAST(property_value AS INTEGER) ASC, specificity DESC
    ) AS _rn
    FROM cascade_candidates
    WHERE entity_id = ? AND comparison = '<='
    {context_clause}
) WHERE _rn = 1
"""

_RESOLVE_CTX_PATTERN = """
SELECT property_name, GROUP_CONCAT(DISTINCT property_value) AS property_value
FROM cascade_candidates
WHERE entity_id = ? AND comparison = 'pattern-in'
{context_clause}
GROUP BY property_name
"""


def _setup_active_context(
    con: sqlite3.Connection,
    context: list[ContextQualifier],
) -> None:
    """Create and populate the _active_context temp table."""
    con.execute("CREATE TEMP TABLE IF NOT EXISTS _active_context (taxon TEXT, type_name TEXT, entity_id TEXT)")
    con.execute("DELETE FROM _active_context")
    for taxon, type_name, entity_id in context:
        con.execute(
            "INSERT INTO _active_context (taxon, type_name, entity_id) VALUES (?, ?, ?)",
            (taxon, type_name, entity_id),
        )


def _teardown_active_context(con: sqlite3.Connection) -> None:
    """Drop the temp table."""
    con.execute("DROP TABLE IF EXISTS _active_context")


def _normalize_context(context) -> list[ContextQualifier] | None:
    """Normalize context from dict or list form to list of tuples."""
    if context is None:
        return None
    if isinstance(context, dict):
        from umwelt.registry.entities import resolve_entity_type
        result = []
        for type_name, entity_id in context.items():
            try:
                taxon = resolve_entity_type(type_name)
            except Exception:
                taxon = type_name
            result.append((taxon, type_name, entity_id))
        return result
    return list(context)
```

Now update `resolve_entity` to accept `context`:

```python
def resolve_entity(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str,
    property: str | None = None,
    mode: str | None = None,
    context: list[ContextQualifier] | dict | None = None,
) -> str | dict[str, str] | None:
    entity_row = _find_entity(con, type=type, id=id)
    if entity_row is None:
        return None if property else {}

    entity_pk = entity_row[0]

    # Normalize: mode= translates to context for backward compat
    resolved_context = _normalize_context(context)
    if resolved_context is None and mode is not None:
        resolved_context = [("state", "mode", mode)]

    if resolved_context is None:
        return _resolve_from_view(con, entity_pk, property)
    return _resolve_with_context(con, entity_pk, property, resolved_context)


def _resolve_with_context(
    con: sqlite3.Connection,
    entity_pk: int,
    property: str | None,
    context: list[ContextQualifier],
) -> str | dict[str, str] | None:
    _setup_active_context(con, context)
    try:
        props: dict[str, str] = {}
        for sql_template in (_RESOLVE_CTX_EXACT, _RESOLVE_CTX_CAP, _RESOLVE_CTX_PATTERN):
            sql = sql_template.format(context_clause=_CONTEXT_FILTER)
            rows = con.execute(sql, (entity_pk,)).fetchall()
            for name, value in rows:
                props[name] = value

        # Fixed constraints override cascade results regardless of context
        try:
            fixed_rows = con.execute(
                "SELECT property_name, property_value FROM fixed_constraints WHERE entity_id = ?",
                (entity_pk,),
            ).fetchall()
            for name, value in fixed_rows:
                if name in props:
                    props[name] = value
        except sqlite3.OperationalError:
            pass

        if property is not None:
            return props.get(property)
        return props
    finally:
        _teardown_active_context(con)
```

Update `resolve_all_entities` to accept `context`:

```python
def resolve_all_entities(
    con: sqlite3.Connection,
    *,
    type: str,
    mode: str | None = None,
    context: list[ContextQualifier] | dict | None = None,
) -> list[dict]:
    resolved_context = _normalize_context(context)
    if resolved_context is None and mode is not None:
        resolved_context = [("state", "mode", mode)]

    entities = con.execute(
        "SELECT id, entity_id, classes, attributes FROM entities WHERE type_name = ?",
        (type,),
    ).fetchall()

    results = []
    for eid, entity_id, classes_json, attrs_json in entities:
        if resolved_context is None:
            props_rows = con.execute(
                "SELECT property_name, effective_value FROM effective_properties WHERE entity_id = ?",
                (eid,),
            ).fetchall()
            props = {name: value for name, value in props_rows}
        else:
            props = _resolve_with_context(con, eid, None, resolved_context) or {}

        results.append({
            "entity_id": entity_id,
            "type_name": type,
            "classes": json.loads(classes_json) if classes_json else [],
            "attributes": json.loads(attrs_json) if attrs_json else {},
            "properties": props,
        })
    return results
```

Update `trace_entity` to accept `context`:

```python
def trace_entity(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str,
    property: str,
    mode: str | None = None,
    context: list[ContextQualifier] | dict | None = None,
) -> TraceResult:
    entity_row = _find_entity(con, type=type, id=id)
    if entity_row is None:
        return TraceResult(
            entity=f"{type}#{id}",
            property=property,
            value=None,
            candidates=(),
        )

    entity_pk = entity_row[0]

    resolved_context = _normalize_context(context)
    if resolved_context is None and mode is not None:
        resolved_context = [("state", "mode", mode)]

    if resolved_context is not None:
        result = _resolve_with_context(con, entity_pk, property, resolved_context)
        winning_value = result if isinstance(result, str) else None
    else:
        winner_row = con.execute(
            "SELECT effective_value FROM effective_properties "
            "WHERE entity_id = ? AND property_name = ?",
            (entity_pk, property),
        ).fetchone()
        winning_value = winner_row[0] if winner_row else None

    # Fetch candidates, filtered by context if provided
    if resolved_context is not None:
        _setup_active_context(con, resolved_context)
        try:
            rows = con.execute(
                "SELECT property_value, specificity, rule_index, "
                "source_file, source_line "
                "FROM cascade_candidates "
                f"WHERE entity_id = ? AND property_name = ? {_CONTEXT_FILTER} "
                "ORDER BY specificity DESC, rule_index DESC",
                (entity_pk, property),
            ).fetchall()
        finally:
            _teardown_active_context(con)
    else:
        rows = con.execute(
            "SELECT property_value, specificity, rule_index, "
            "source_file, source_line "
            "FROM cascade_candidates "
            "WHERE entity_id = ? AND property_name = ? "
            "ORDER BY specificity DESC, rule_index DESC",
            (entity_pk, property),
        ).fetchall()

    candidates = []
    winner_marked = False
    for value, spec, rule_idx, src_file, src_line in rows:
        is_winner = not winner_marked and value == winning_value
        if is_winner:
            winner_marked = True
        candidates.append(Candidate(
            value=value,
            specificity=spec,
            rule_index=rule_idx,
            source_file=src_file or "",
            source_line=src_line or 0,
            won=is_winner,
        ))

    return TraceResult(
        entity=f"{type}#{id}",
        property=property,
        value=winning_value,
        candidates=tuple(candidates),
    )
```

- [ ] **Step 4: Run context qualifier tests**

Run: `pytest tests/policy/test_context_qualifiers.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures. Existing mode= tests still pass (backward compat through translation).

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/policy/queries.py tests/policy/test_context_qualifiers.py
git commit -m "feat(policy): generic context= parameter for filtered resolution

Replace _MODE_FILTER with cascade_context_qualifiers-based filtering.
context= accepts list of (taxon, type_name, entity_id) tuples or a dict.
mode= still works via internal translation for backward compatibility."
```

---

### Task 4: PolicyEngine — Wire context= through engine methods

**Files:**
- Modify: `src/umwelt/policy/engine.py`
- Modify: `tests/policy/test_context_qualifiers.py`

- [ ] **Step 1: Write failing tests for engine-level context parameter**

Append to `tests/policy/test_context_qualifiers.py`:

```python
class TestDeprecatedModeStillWorks:
    """Existing mode= parameter must continue working."""

    def test_mode_param_translates_to_context(self, context_engine):
        val_mode = context_engine.resolve(
            type="tool", id="Bash", property="allow", mode="review",
        )
        val_ctx = context_engine.resolve(
            type="tool", id="Bash", property="allow",
            context=[("state", "mode", "review")],
        )
        assert val_mode == val_ctx

    def test_mode_resolve_all(self, context_engine):
        tools_mode = context_engine.resolve_all(type="tool", mode="review")
        tools_ctx = context_engine.resolve_all(
            type="tool", context=[("state", "mode", "review")],
        )
        mode_bash = next(t for t in tools_mode if t["entity_id"] == "Bash")
        ctx_bash = next(t for t in tools_ctx if t["entity_id"] == "Bash")
        assert mode_bash["properties"] == ctx_bash["properties"]

    def test_mode_trace(self, context_engine):
        result_mode = context_engine.trace(
            type="tool", id="Bash", property="max-level", mode="implement",
        )
        result_ctx = context_engine.trace(
            type="tool", id="Bash", property="max-level",
            context=[("state", "mode", "implement")],
        )
        assert result_mode.value == result_ctx.value

    def test_mode_check(self, context_engine):
        assert context_engine.check(
            type="tool", id="Bash", mode="review", allow="false",
        )

    def test_mode_require(self, context_engine):
        context_engine.require(
            type="tool", id="Read", mode="review", allow="true",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/policy/test_context_qualifiers.py::TestDeprecatedModeStillWorks -v`
Expected: FAIL — engine methods don't accept `context` (or the query layer translation doesn't work through the engine yet)

- [ ] **Step 3: Update PolicyEngine methods to accept context=**

In `src/umwelt/policy/engine.py`, update each method. Add the import at top of file:

```python
import warnings
```

Update `resolve`:

```python
    def resolve(
        self,
        *,
        type: str,
        id: str,
        property: str | None = None,
        mode: str | None = None,
        context: list | dict | None = None,
    ) -> str | dict[str, str] | None:
        from umwelt.policy.queries import resolve_entity

        if mode is not None and context is not None:
            raise ValueError("Cannot specify both mode= and context=")
        if mode is not None:
            warnings.warn(
                "mode= is deprecated, use context={'mode': value} instead",
                DeprecationWarning,
                stacklevel=2,
            )

        con = self._ensure_compiled()
        result = resolve_entity(con, type=type, id=id, property=property, mode=mode, context=context)
        logger.info(
            "resolve",
            extra={"entity": f"{type}#{id}", "property": property, "context": context, "value": result},
        )
        return result
```

Update `resolve_all`:

```python
    def resolve_all(
        self,
        *,
        type: str,
        mode: str | None = None,
        context: list | dict | None = None,
    ) -> list[dict]:
        from umwelt.policy.queries import resolve_all_entities

        if mode is not None and context is not None:
            raise ValueError("Cannot specify both mode= and context=")
        if mode is not None:
            warnings.warn(
                "mode= is deprecated, use context={'mode': value} instead",
                DeprecationWarning,
                stacklevel=2,
            )

        con = self._ensure_compiled()
        results = resolve_all_entities(con, type=type, mode=mode, context=context)
        logger.info(
            "resolve_all",
            extra={"type": type, "context": context, "result_count": len(results)},
        )
        return results
```

Update `trace`:

```python
    def trace(
        self,
        *,
        type: str,
        id: str,
        property: str,
        mode: str | None = None,
        context: list | dict | None = None,
    ) -> TraceResult:
        from umwelt.policy.queries import trace_entity

        if mode is not None and context is not None:
            raise ValueError("Cannot specify both mode= and context=")
        if mode is not None:
            warnings.warn(
                "mode= is deprecated, use context={'mode': value} instead",
                DeprecationWarning,
                stacklevel=2,
            )

        con = self._ensure_compiled()
        result = trace_entity(con, type=type, id=id, property=property, mode=mode, context=context)
        logger.debug(
            "trace",
            extra={
                "entity": f"{type}#{id}",
                "property": property,
                "context": context,
                "candidates": len(result.candidates),
            },
        )
        return result
```

Update `check`:

```python
    def check(
        self,
        *,
        type: str,
        id: str,
        mode: str | None = None,
        context: list | dict | None = None,
        **expected: str,
    ) -> bool:
        if mode is not None and context is not None:
            raise ValueError("Cannot specify both mode= and context=")
        if mode is not None:
            warnings.warn(
                "mode= is deprecated, use context={'mode': value} instead",
                DeprecationWarning,
                stacklevel=2,
            )
        for prop_name, expected_val in expected.items():
            actual = self.resolve(type=type, id=id, property=prop_name, mode=mode, context=context)
            if actual != expected_val:
                return False
        return True
```

Update `require`:

```python
    def require(
        self,
        *,
        type: str,
        id: str,
        mode: str | None = None,
        context: list | dict | None = None,
        **expected: str,
    ) -> None:
        if mode is not None and context is not None:
            raise ValueError("Cannot specify both mode= and context=")
        if mode is not None:
            warnings.warn(
                "mode= is deprecated, use context={'mode': value} instead",
                DeprecationWarning,
                stacklevel=2,
            )
        for prop_name, expected_val in expected.items():
            actual = self.resolve(type=type, id=id, property=prop_name, mode=mode, context=context)
            if actual != expected_val:
                logger.warning(
                    "require_denied",
                    extra={
                        "entity": f"{type}#{id}",
                        "property": prop_name,
                        "expected": expected_val,
                        "actual": actual,
                    },
                )
                raise PolicyDenied(
                    entity=f"{type}#{id}",
                    property=prop_name,
                    expected=expected_val,
                    actual=actual or "(none)",
                )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/policy/test_context_qualifiers.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures. The existing `test_mode_filtering.py` tests still pass because `mode=` is translated internally.

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/policy/engine.py tests/policy/test_context_qualifiers.py
git commit -m "feat(engine): add context= parameter, deprecate mode=

All PolicyEngine query methods (resolve, resolve_all, trace, check,
require) now accept context= alongside the deprecated mode= parameter.
mode= translates internally to context=[('state', 'mode', value)]."
```

---

### Task 5: Migrate existing mode tests to also exercise context=

**Files:**
- Modify: `tests/policy/test_mode_filtering.py`

- [ ] **Step 1: Add context= equivalence tests to existing mode test file**

In `tests/policy/test_mode_filtering.py`, add a new test class at the end:

```python
class TestContextEquivalence:
    """Every mode= test has an equivalent context= form that produces the same result."""

    def test_matching_mode_fires_via_context(self, mode_engine):
        val = mode_engine.resolve(
            type="tool", id="Bash", property="max-level",
            context={"mode": "implement"},
        )
        assert val == "3"

    def test_review_denies_via_context(self, mode_engine):
        val = mode_engine.resolve(
            type="tool", id="Bash", property="allow",
            context={"mode": "review"},
        )
        assert val == "false"

    def test_review_allows_read_via_context(self, mode_engine):
        val = mode_engine.resolve(
            type="tool", id="Read", property="allow",
            context={"mode": "review"},
        )
        assert val == "true"

    def test_resolve_all_via_context(self, mode_engine):
        tools = mode_engine.resolve_all(
            type="tool", context={"mode": "review"},
        )
        bash = next(t for t in tools if t["entity_id"] == "Bash")
        assert bash["properties"]["allow"] == "false"

    def test_trace_via_context(self, mode_engine):
        result = mode_engine.trace(
            type="tool", id="Bash", property="max-level",
            context={"mode": "implement"},
        )
        assert result.value == "3"

    def test_check_via_context(self, mode_engine):
        assert mode_engine.check(
            type="tool", id="Bash",
            context={"mode": "review"},
            allow="false",
        )

    def test_require_via_context(self, mode_engine):
        mode_engine.require(
            type="tool", id="Read",
            context={"mode": "review"},
            allow="true",
        )
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/policy/test_mode_filtering.py -v`
Expected: All PASS (both old mode= tests and new context= equivalence tests)

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: No new failures

- [ ] **Step 4: Commit**

```bash
git add tests/policy/test_mode_filtering.py
git commit -m "test: add context= equivalence tests alongside mode= tests

Every mode-filtered test now has a context= counterpart confirming
identical behavior through the generic path."
```

---

### Task 6: Push all changes

- [ ] **Step 1: Push**

```bash
git push origin main
```
