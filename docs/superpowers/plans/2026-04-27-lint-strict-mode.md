# Lint, Warnings, and Strict Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the PolicyEngine's lint system with five new detectors, a configurable severity system (LintConfig), compile-time lint integration, and CLI `--lint` flag.

**Architecture:** New `LintConfig` dataclass + `process_lint_results()` in `lint.py` handle severity mapping. Five new `_detect_*` functions follow the existing pattern. `PolicyEngine` gains a `lint_mode` parameter that triggers lint after compilation. CLI passes `--lint` flag through to the engine.

**Tech Stack:** Python stdlib only (dataclasses, warnings, logging, sqlite3). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-27-lint-strict-mode-design.md`

---

## Design Decisions

**D1: LintConfig lives in lint.py.** It's the severity mapping — closely related to lint processing, not to the engine. The engine stores the raw `lint_mode` and a computed `LintConfig` instance.

**D2: process_lint_results uses stdlib warnings module.** The `warn` tier calls `warnings.warn(UserWarning)`, which integrates with Python's existing warning filter system. Callers can suppress with `warnings.filterwarnings` if needed.

**D3: Detectors don't know about LintConfig.** Each `_detect_*` function returns `list[LintWarning]` with a recommended severity. `process_lint_results` applies the effective severity from config. This keeps detectors pure and testable.

**D4: Env var only supports string presets.** `UMWELT_LINT=warn` works. Dict form requires the Python API. This avoids JSON-in-env-var complexity.

**D5: run_lint logging changes.** Currently `run_lint` logs every warning at `logger.warning`. After this work, `run_lint` returns warnings silently — logging/warning/raising is done by `process_lint_results` based on config. The explicit `engine.lint()` method continues to call `run_lint` directly (no config processing).

---

## Files

### New files
| File | Purpose |
|---|---|
| `tests/policy/test_lint_config.py` | Tests for `LintConfig` and `process_lint_results` |
| `tests/policy/test_lint_new_detectors.py` | Tests for the 5 new detectors |
| `tests/policy/test_lint_integration.py` | Engine-level compile-time lint tests |
| `tests/policy/test_lint_cli.py` | CLI `--lint` flag tests |

### Modified files
| File | Change |
|---|---|
| `src/umwelt/errors.py` | Add `PolicyLintError(PolicyError)` |
| `src/umwelt/policy/lint.py` | Add `LintConfig`, `process_lint_results`, 5 new detectors, rename `conflicting_intent` → `source_order_dependence`, remove per-warning logging from `run_lint` |
| `src/umwelt/policy/engine.py` | Add `lint_mode` parameter to `__init__`, `from_files`, `from_db`, `extend`; call lint after compilation in `_ensure_compiled` and `_recompile_incremental` |
| `src/umwelt/policy/__init__.py` | Export `LintConfig` |
| `src/umwelt/cli.py` | Add `--lint` flag to `check`, `dry-run`, `compile` subparsers; format and print lint results |
| `tests/policy/test_lint.py` | Update `conflicting_intent` → `source_order_dependence` in existing test |

---

## Tasks

### Task 1: PolicyLintError + LintConfig

**Files:**
- Modify: `src/umwelt/errors.py`
- Modify: `src/umwelt/policy/lint.py`
- Create: `tests/policy/test_lint_config.py`

- [ ] **Step 1: Write tests for LintConfig and process_lint_results**

```python
# tests/policy/test_lint_config.py
from __future__ import annotations

import logging
import warnings as warnings_mod

import pytest

from umwelt.errors import PolicyLintError
from umwelt.policy.engine import LintWarning
from umwelt.policy.lint import LintConfig, process_lint_results


class TestLintConfigFromString:
    def test_off(self):
        cfg = LintConfig.from_lint_mode("off")
        assert cfg.default == "off"
        assert cfg.overrides == {}

    def test_warn(self):
        cfg = LintConfig.from_lint_mode("warn")
        assert cfg.default == "warn"

    def test_error(self):
        cfg = LintConfig.from_lint_mode("error")
        assert cfg.default == "error"

    def test_notice(self):
        cfg = LintConfig.from_lint_mode("notice")
        assert cfg.default == "notice"


class TestLintConfigFromDict:
    def test_dict_with_default(self):
        cfg = LintConfig.from_lint_mode({
            "error": ["cross_axis_dominance"],
            "warn": ["narrow_win"],
            "notice": ["uncovered_entity"],
            "off": ["shadowed_rule"],
            "default": "notice",
        })
        assert cfg.default == "notice"
        assert cfg.severity_for("cross_axis_dominance") == "error"
        assert cfg.severity_for("narrow_win") == "warn"
        assert cfg.severity_for("uncovered_entity") == "notice"
        assert cfg.severity_for("shadowed_rule") == "off"

    def test_dict_default_fallback(self):
        cfg = LintConfig.from_lint_mode({"default": "warn"})
        assert cfg.severity_for("anything") == "warn"

    def test_dict_missing_default_uses_warn(self):
        cfg = LintConfig.from_lint_mode({"error": ["narrow_win"]})
        assert cfg.default == "warn"
        assert cfg.severity_for("narrow_win") == "error"
        assert cfg.severity_for("other") == "warn"

    def test_empty_dict(self):
        cfg = LintConfig.from_lint_mode({})
        assert cfg.default == "warn"


class TestSeverityFor:
    def test_override_wins(self):
        cfg = LintConfig(default="warn", overrides={"narrow_win": "error"})
        assert cfg.severity_for("narrow_win") == "error"

    def test_default_when_no_override(self):
        cfg = LintConfig(default="notice", overrides={})
        assert cfg.severity_for("narrow_win") == "notice"


def _make_warning(smell: str = "narrow_win", desc: str = "test") -> LintWarning:
    return LintWarning(smell=smell, severity="warning", description=desc, entities=(), property=None)


class TestProcessLintResults:
    def test_off_suppresses(self):
        cfg = LintConfig.from_lint_mode("off")
        result = process_lint_results([_make_warning()], cfg)
        assert result == []

    def test_notice_logs(self, caplog):
        cfg = LintConfig.from_lint_mode("notice")
        with caplog.at_level(logging.INFO, logger="umwelt.policy"):
            result = process_lint_results([_make_warning()], cfg)
        assert len(result) == 1
        assert "narrow_win" in caplog.text

    def test_warn_emits_warning(self):
        cfg = LintConfig.from_lint_mode("warn")
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            result = process_lint_results([_make_warning()], cfg)
        assert len(result) == 1
        assert len(caught) == 1
        assert "narrow_win" in str(caught[0].message)

    def test_error_raises(self):
        cfg = LintConfig.from_lint_mode("error")
        with pytest.raises(PolicyLintError) as exc_info:
            process_lint_results([_make_warning()], cfg)
        assert len(exc_info.value.warnings) == 1

    def test_mixed_severities(self):
        cfg = LintConfig.from_lint_mode({
            "error": ["narrow_win"],
            "off": ["shadowed_rule"],
            "default": "notice",
        })
        ws = [
            _make_warning("narrow_win", "bad"),
            _make_warning("shadowed_rule", "ok"),
            _make_warning("other_smell", "meh"),
        ]
        with pytest.raises(PolicyLintError) as exc_info:
            process_lint_results(ws, cfg)
        assert len(exc_info.value.warnings) == 1
        assert exc_info.value.warnings[0].smell == "narrow_win"

    def test_no_warnings_returns_empty(self):
        cfg = LintConfig.from_lint_mode("error")
        result = process_lint_results([], cfg)
        assert result == []
```

- [ ] **Step 2: Run tests — verify they fail (imports not found)**

```bash
pytest tests/policy/test_lint_config.py -v
```

- [ ] **Step 3: Add PolicyLintError to errors.py**

Add after the `PolicyCompilationError` class at the end of `src/umwelt/errors.py`:

```python
class PolicyLintError(PolicyError):
    """Raised when lint smells fire at error severity."""

    def __init__(self, warnings: list) -> None:
        self.warnings = warnings
        descriptions = "; ".join(
            f"{w.smell}: {w.description}" for w in warnings
        )
        super().__init__(f"Lint errors: {descriptions}")
```

- [ ] **Step 4: Add LintConfig and process_lint_results to lint.py**

Add these at the top of `src/umwelt/policy/lint.py`, after the existing imports:

```python
import warnings as warnings_mod
from dataclasses import dataclass, field
from typing import Any

from umwelt.errors import PolicyLintError
```

Then add `LintConfig` and `process_lint_results` before `run_lint`:

```python
@dataclass(frozen=True)
class LintConfig:
    """Maps smell names to effective severity tiers."""

    default: str
    overrides: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_lint_mode(cls, mode: str | dict[str, Any]) -> LintConfig:
        if isinstance(mode, str):
            return cls(default=mode, overrides={})
        default = mode.get("default", "warn")
        overrides: dict[str, str] = {}
        for level in ("error", "warn", "notice", "off"):
            for smell in mode.get(level, []):
                overrides[smell] = level
        return cls(default=default, overrides=overrides)

    def severity_for(self, smell: str) -> str:
        return self.overrides.get(smell, self.default)


def process_lint_results(
    lint_warnings: list[LintWarning], config: LintConfig,
) -> list[LintWarning]:
    """Apply severity mapping. Returns non-suppressed warnings.

    Raises PolicyLintError if any smell maps to 'error'.
    """
    errors: list[LintWarning] = []
    kept: list[LintWarning] = []
    for w in lint_warnings:
        effective = config.severity_for(w.smell)
        if effective == "off":
            continue
        elif effective == "notice":
            logger.info("lint [notice]: %s — %s", w.smell, w.description)
            kept.append(w)
        elif effective == "warn":
            warnings_mod.warn(
                f"umwelt lint: {w.smell} — {w.description}",
                UserWarning,
                stacklevel=2,
            )
            kept.append(w)
        elif effective == "error":
            errors.append(w)
            kept.append(w)
    if errors:
        raise PolicyLintError(errors)
    return kept
```

- [ ] **Step 5: Remove per-warning logging from run_lint**

In `run_lint`, remove the logging loop at the end. Change from:

```python
def run_lint(con: sqlite3.Connection) -> list[LintWarning]:
    warnings: list[LintWarning] = []
    warnings.extend(_detect_narrow_win(con))
    warnings.extend(_detect_shadowed_rule(con))
    warnings.extend(_detect_conflicting_intent(con))
    warnings.extend(_detect_uncovered_entity(con))
    warnings.extend(_detect_specificity_escalation(con))
    warnings.extend(_detect_fixed_override(con))
    warnings.extend(_detect_unrealizable_altitude(con))

    for w in warnings:
        logger.warning(
            "lint: %s — %s",
            w.smell,
            w.description,
            extra={"smell": w.smell, "entities": w.entities, "severity": w.severity},
        )
    return warnings
```

To:

```python
def run_lint(con: sqlite3.Connection) -> list[LintWarning]:
    results: list[LintWarning] = []
    results.extend(_detect_narrow_win(con))
    results.extend(_detect_shadowed_rule(con))
    results.extend(_detect_source_order_dependence(con))
    results.extend(_detect_uncovered_entity(con))
    results.extend(_detect_specificity_escalation(con))
    results.extend(_detect_fixed_override(con))
    results.extend(_detect_unrealizable_altitude(con))
    results.extend(_detect_cross_axis_dominance(con))
    results.extend(_detect_ceiling_ineffective(con))
    results.extend(_detect_specificity_tie(con))
    results.extend(_detect_cross_axis_tie(con))
    results.extend(_detect_ceiling_conflict(con))
    return results
```

Note: the new detector functions are stubs for now (added in Task 3). Also rename `_detect_conflicting_intent` to `_detect_source_order_dependence` — see Task 2.

- [ ] **Step 6: Run tests — verify they pass**

```bash
pytest tests/policy/test_lint_config.py -v
```

- [ ] **Step 7: Commit**

```bash
git add src/umwelt/errors.py src/umwelt/policy/lint.py tests/policy/test_lint_config.py
git commit -m "feat(lint): add LintConfig, process_lint_results, PolicyLintError"
```

---

### Task 2: Rename conflicting_intent → source_order_dependence

**Files:**
- Modify: `src/umwelt/policy/lint.py`
- Modify: `tests/policy/test_lint.py`

- [ ] **Step 1: Rename the function and update the smell name**

In `src/umwelt/policy/lint.py`, rename `_detect_conflicting_intent` to `_detect_source_order_dependence`. Change the `smell=` from `"conflicting_intent"` to `"source_order_dependence"`. Update the description message from:

```python
            description=(
                f"{entity_name} '{prop_name}': '{val1}' vs '{val2}'"
                " at same specificity — winner decided by source order"
            ),
```

To:

```python
            description=(
                f"{entity_name} '{prop_name}': '{val1}' vs '{val2}'"
                " at same specificity — resolved by source order (later rule wins)"
            ),
```

Also update the `run_lint` call from `_detect_conflicting_intent` to `_detect_source_order_dependence` (already done in Task 1 Step 5).

- [ ] **Step 2: Update the existing test**

In `tests/policy/test_lint.py`, rename `TestConflictingIntent` to `TestSourceOrderDependence` and update the smell filter from `"conflicting_intent"` to `"source_order_dependence"`:

```python
class TestSourceOrderDependence:
    def test_detects_source_order_dependence(self, lint_db):
        dialect = SQLiteDialect()
        spec = '["00000","00000","00000","00001","00000","00000","00000","00000"]'

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
        source_order = [w for w in warnings if w.smell == "source_order_dependence"]
        assert len(source_order) >= 1
```

- [ ] **Step 3: Run existing lint tests — verify they pass**

```bash
pytest tests/policy/test_lint.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/umwelt/policy/lint.py tests/policy/test_lint.py
git commit -m "refactor(lint): rename conflicting_intent to source_order_dependence"
```

---

### Task 3: Five new detectors

**Files:**
- Modify: `src/umwelt/policy/lint.py`
- Create: `tests/policy/test_lint_new_detectors.py`

- [ ] **Step 1: Write tests for all five new detectors**

```python
# tests/policy/test_lint_new_detectors.py
from __future__ import annotations

import json
import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.resolution import create_resolution_views
from umwelt.compilers.sql.schema import create_schema
from umwelt.policy.lint import run_lint


@pytest.fixture
def lint_db():
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))

    entities = [
        (1, "capability", "tool", "Read", None, json.dumps({"name": "Read"}), None, 0),
        (2, "capability", "tool", "Bash", json.dumps(["dangerous"]), json.dumps({"name": "Bash"}), None, 0),
        (3, "capability", "tool", "Deploy", json.dumps(["dangerous", "infrastructure"]), json.dumps({"name": "Deploy"}), None, 0),
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


def _spec(cross=0, id_val=0, cls=0):
    """Build a specificity string. Position 0 = cross-axis, position 3 = id, position 5 = class."""
    parts = ["00000"] * 8
    parts[0] = f"{cross:05d}"
    parts[3] = f"{id_val:05d}"
    parts[5] = f"{cls:05d}"
    return json.dumps(parts)


class TestCrossAxisDominance:
    def test_detects_cross_axis_over_id(self, lint_db):
        """Cross-axis rule beating single-axis ID rule should fire."""
        dialect = SQLiteDialect()
        candidates = [
            # Single-axis ID rule: tool#Deploy { allow: false } — spec has id=1, cross=0
            (3, "allow", "false", "exact", _spec(cross=0, id_val=1), 0, "a.umw", 1),
            # Cross-axis rule: principal#admin tool { allow: true } — spec has cross=1
            (3, "allow", "true", "exact", _spec(cross=1, id_val=0), 1, "a.umw", 5),
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
        hits = [w for w in warnings if w.smell == "cross_axis_dominance"]
        assert len(hits) >= 1
        assert "cross-axis" in hits[0].description.lower()

    def test_no_false_positive_same_axis(self, lint_db):
        """Two single-axis rules at different specificity should not fire."""
        dialect = SQLiteDialect()
        candidates = [
            (2, "allow", "false", "exact", _spec(cross=0, id_val=0, cls=1), 0, "a.umw", 1),
            (2, "allow", "true", "exact", _spec(cross=0, id_val=1), 1, "a.umw", 3),
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
        hits = [w for w in warnings if w.smell == "cross_axis_dominance"]
        assert len(hits) == 0


class TestCeilingIneffective:
    def test_detects_ineffective_ceiling(self, lint_db):
        """Higher-specificity rule trying to raise a <= ceiling should fire."""
        dialect = SQLiteDialect()
        candidates = [
            # Lower specificity sets ceiling to 3
            (2, "max-level", "3", "<=", _spec(cls=1), 0, "a.umw", 1),
            # Higher specificity tries to set ceiling to 5 — ineffective
            (2, "max-level", "5", "<=", _spec(id_val=1, cls=1), 1, "a.umw", 3),
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
        hits = [w for w in warnings if w.smell == "ceiling_ineffective"]
        assert len(hits) >= 1
        assert "ineffective" in hits[0].description.lower()

    def test_no_false_positive_lowering_ceiling(self, lint_db):
        """Higher-specificity rule lowering a ceiling should not fire."""
        dialect = SQLiteDialect()
        candidates = [
            (2, "max-level", "5", "<=", _spec(cls=1), 0, "a.umw", 1),
            (2, "max-level", "3", "<=", _spec(id_val=1, cls=1), 1, "a.umw", 3),
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
        hits = [w for w in warnings if w.smell == "ceiling_ineffective"]
        assert len(hits) == 0


class TestSpecificityTie:
    def test_detects_tie(self, lint_db):
        """Same specificity + same rule_index + different values should fire."""
        dialect = SQLiteDialect()
        spec = _spec(cls=1)
        candidates = [
            (2, "require", "sandbox", "exact", spec, 0, "a.umw", 1),
            (2, "require", "none", "exact", spec, 0, "b.umw", 1),
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
        hits = [w for w in warnings if w.smell == "specificity_tie"]
        assert len(hits) >= 1
        assert "nondeterministic" in hits[0].description.lower()

    def test_no_false_positive_different_rule_index(self, lint_db):
        """Same specificity but different rule_index is source_order_dependence, not tie."""
        dialect = SQLiteDialect()
        spec = _spec(cls=1)
        candidates = [
            (2, "require", "sandbox", "exact", spec, 0, "a.umw", 1),
            (2, "require", "none", "exact", spec, 1, "a.umw", 5),
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
        hits = [w for w in warnings if w.smell == "specificity_tie"]
        assert len(hits) == 0


class TestCrossAxisTie:
    def test_detects_different_axis_competition(self, lint_db):
        """Two cross-axis rules from different qualifier axes should fire."""
        dialect = SQLiteDialect()
        spec_a = _spec(cross=1, cls=1)
        spec_b = _spec(cross=1)
        candidates = [
            (3, "allow", "true", "exact", spec_a, 0, "a.umw", 1),
            (3, "allow", "false", "exact", spec_b, 1, "a.umw", 5),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        # Add context qualifiers from different axes
        rowid_base = lint_db.execute("SELECT MAX(rowid) FROM cascade_candidates").fetchone()[0]
        lint_db.execute(
            "INSERT INTO cascade_context_qualifiers (candidate_rowid, taxon, type_name, entity_id) "
            "VALUES (?, 'principal', 'principal', 'ops')",
            (rowid_base - 1,),
        )
        lint_db.execute(
            "INSERT INTO cascade_context_qualifiers (candidate_rowid, taxon, type_name, entity_id) "
            "VALUES (?, 'state', 'mode', 'review')",
            (rowid_base,),
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        hits = [w for w in warnings if w.smell == "cross_axis_tie"]
        assert len(hits) >= 1

    def test_no_false_positive_same_axis(self, lint_db):
        """Two cross-axis rules from the same axis should not fire cross_axis_tie."""
        dialect = SQLiteDialect()
        spec_a = _spec(cross=1, cls=1)
        spec_b = _spec(cross=1)
        candidates = [
            (3, "allow", "true", "exact", spec_a, 0, "a.umw", 1),
            (3, "allow", "false", "exact", spec_b, 1, "a.umw", 5),
        ]
        lint_db.executemany(
            "INSERT INTO cascade_candidates "
            "(entity_id, property_name, property_value, comparison, specificity, rule_index, source_file, source_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            candidates,
        )
        rowid_base = lint_db.execute("SELECT MAX(rowid) FROM cascade_candidates").fetchone()[0]
        # Both from the same axis (mode)
        lint_db.execute(
            "INSERT INTO cascade_context_qualifiers (candidate_rowid, taxon, type_name, entity_id) "
            "VALUES (?, 'state', 'mode', 'deploy')",
            (rowid_base - 1,),
        )
        lint_db.execute(
            "INSERT INTO cascade_context_qualifiers (candidate_rowid, taxon, type_name, entity_id) "
            "VALUES (?, 'state', 'mode', 'review')",
            (rowid_base,),
        )
        lint_db.commit()
        create_resolution_views(lint_db, dialect)

        warnings = run_lint(lint_db)
        hits = [w for w in warnings if w.smell == "cross_axis_tie"]
        assert len(hits) == 0


class TestCeilingConflict:
    def test_detects_competing_ceilings(self, lint_db):
        """Two <= candidates at same specificity with different values should fire."""
        dialect = SQLiteDialect()
        spec = _spec(cls=1)
        candidates = [
            (2, "max-level", "3", "<=", spec, 0, "a.umw", 1),
            (2, "max-level", "5", "<=", spec, 1, "a.umw", 3),
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
        hits = [w for w in warnings if w.smell == "ceiling_conflict"]
        assert len(hits) >= 1

    def test_no_false_positive_same_value(self, lint_db):
        """Two <= candidates at same specificity with same value should not fire."""
        dialect = SQLiteDialect()
        spec = _spec(cls=1)
        candidates = [
            (2, "max-level", "3", "<=", spec, 0, "a.umw", 1),
            (2, "max-level", "3", "<=", spec, 1, "a.umw", 3),
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
        hits = [w for w in warnings if w.smell == "ceiling_conflict"]
        assert len(hits) == 0
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/policy/test_lint_new_detectors.py -v
```

- [ ] **Step 3: Implement the five detectors**

Add to the end of `src/umwelt/policy/lint.py` (before `_detect_unrealizable_altitude`):

```python
def _detect_cross_axis_dominance(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when a cross-axis rule beats a single-axis ID rule."""
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
        winner_cross = winner_spec[0]
        runner_cross = runner_spec[0]
        if winner_cross > 0 and runner_cross == 0 and candidates[0][2] != candidates[1][2]:
            entity_name = _entity_name(con, entity_id)
            warnings.append(LintWarning(
                smell="cross_axis_dominance",
                severity="warning",
                description=(
                    f"{entity_name} '{prop_name}': cross-axis rule dominates"
                    f" single-axis selector — value '{candidates[0][2]}'"
                    f" overrides '{candidates[1][2]}'"
                ),
                entities=(entity_name,),
                property=prop_name,
            ))
    return warnings


def _detect_ceiling_ineffective(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when a higher-specificity <= rule tries to raise a ceiling."""
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT entity_id, property_name, property_value, specificity
        FROM cascade_candidates
        WHERE comparison = '<='
        ORDER BY entity_id, property_name, specificity ASC
    """).fetchall()

    groups: dict[tuple[int, str], list[tuple[str, str]]] = {}
    for entity_id, prop_name, prop_value, spec in rows:
        key = (entity_id, prop_name)
        groups.setdefault(key, []).append((prop_value, spec))

    for (entity_id, prop_name), entries in groups.items():
        if len(entries) < 2:
            continue
        min_val = min(int(v) for v, _ in entries)
        for value, spec in entries:
            if int(value) > min_val:
                entity_name = _entity_name(con, entity_id)
                warnings.append(LintWarning(
                    smell="ceiling_ineffective",
                    severity="notice",
                    description=(
                        f"{entity_name} '{prop_name}': value '{value}'"
                        f" at higher specificity is ineffective"
                        f" — ceiling clamped to '{min_val}'"
                        f" by lower-specificity rule"
                    ),
                    entities=(entity_name,),
                    property=prop_name,
                ))
                break
    return warnings


def _detect_specificity_tie(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when two candidates tie on both specificity and rule_index."""
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
            AND c1.rule_index = c2.rule_index
            AND c1.rowid < c2.rowid
        WHERE c1.property_value != c2.property_value
          AND c1.comparison = 'exact'
          AND c2.comparison = 'exact'
    """).fetchall()

    seen: set[tuple[int, str]] = set()
    for entity_id, prop_name, val1, val2, _spec in rows:
        key = (entity_id, prop_name)
        if key in seen:
            continue
        seen.add(key)
        entity_name = _entity_name(con, entity_id)
        warnings.append(LintWarning(
            smell="specificity_tie",
            severity="warning",
            description=(
                f"{entity_name} '{prop_name}': specificity tie"
                f" between '{val1}' and '{val2}'"
                f" — resolution order is nondeterministic"
            ),
            entities=(entity_name,),
            property=prop_name,
        ))
    return warnings


def _detect_cross_axis_tie(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when cross-axis rules from different qualifier axes compete."""
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT c1.entity_id, c1.property_name,
               c1.property_value, c2.property_value,
               c1.rowid AS r1, c2.rowid AS r2
        FROM cascade_candidates c1
        JOIN cascade_candidates c2
            ON c1.entity_id = c2.entity_id
            AND c1.property_name = c2.property_name
            AND c1.rowid < c2.rowid
        WHERE c1.property_value != c2.property_value
          AND c1.comparison = 'exact'
          AND c2.comparison = 'exact'
    """).fetchall()

    for entity_id, prop_name, val1, val2, r1, r2 in rows:
        quals1 = con.execute(
            "SELECT taxon, type_name FROM cascade_context_qualifiers WHERE candidate_rowid = ?",
            (r1,),
        ).fetchall()
        quals2 = con.execute(
            "SELECT taxon, type_name FROM cascade_context_qualifiers WHERE candidate_rowid = ?",
            (r2,),
        ).fetchall()
        if not quals1 or not quals2:
            continue
        axes1 = {(t, tn) for t, tn in quals1}
        axes2 = {(t, tn) for t, tn in quals2}
        if axes1 != axes2 and not axes1.issubset(axes2) and not axes2.issubset(axes1):
            entity_name = _entity_name(con, entity_id)
            axis1_str = ", ".join(f"{tn}" for _, tn in sorted(axes1))
            axis2_str = ", ".join(f"{tn}" for _, tn in sorted(axes2))
            warnings.append(LintWarning(
                smell="cross_axis_tie",
                severity="warning",
                description=(
                    f"{entity_name} '{prop_name}': cross-axis rules"
                    f" from different axes compete"
                    f" — {axis1_str} ({val1}) vs {axis2_str} ({val2})"
                ),
                entities=(entity_name,),
                property=prop_name,
            ))
    return warnings


def _detect_ceiling_conflict(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when two <= candidates at same specificity set different values."""
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
          AND c1.comparison = '<='
          AND c2.comparison = '<='
    """).fetchall()

    seen: set[tuple[int, str]] = set()
    for entity_id, prop_name, val1, val2, _spec in rows:
        key = (entity_id, prop_name)
        if key in seen:
            continue
        seen.add(key)
        min_val = min(val1, val2, key=lambda v: int(v))
        entity_name = _entity_name(con, entity_id)
        warnings.append(LintWarning(
            smell="ceiling_conflict",
            severity="notice",
            description=(
                f"{entity_name} '{prop_name}': competing ceiling values"
                f" '{val1}' and '{val2}' at same specificity"
                f" — MIN ('{min_val}') wins regardless of order"
            ),
            entities=(entity_name,),
            property=prop_name,
        ))
    return warnings
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/policy/test_lint_new_detectors.py -v
```

- [ ] **Step 5: Run all lint tests — verify no regressions**

```bash
pytest tests/policy/test_lint.py tests/policy/test_lint_config.py tests/policy/test_lint_new_detectors.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/policy/lint.py tests/policy/test_lint_new_detectors.py
git commit -m "feat(lint): add 5 new detectors — cross-axis, ceiling, tie smells"
```

---

### Task 4: PolicyEngine lint_mode integration

**Files:**
- Modify: `src/umwelt/policy/engine.py`
- Modify: `src/umwelt/policy/__init__.py`
- Create: `tests/policy/test_lint_integration.py`

- [ ] **Step 1: Write integration tests**

```python
# tests/policy/test_lint_integration.py
from __future__ import annotations

import os
import warnings as warnings_mod

import pytest

from umwelt.errors import PolicyLintError
from umwelt.policy import PolicyEngine


@pytest.fixture
def engine_with_narrow_win():
    """Engine with two rules that produce a narrow_win smell."""
    engine = PolicyEngine()
    engine.add_entities([
        {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
    ])
    engine.add_stylesheet("""\
tool.dangerous { allow: false; }
tool#Bash { allow: true; }
""")
    return engine


class TestLintModeOff:
    def test_default_is_off(self, engine_with_narrow_win):
        """Default lint_mode is off — no warnings emitted."""
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            engine_with_narrow_win.resolve(type="tool", id="Bash", property="allow")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) == 0

    def test_explicit_off(self):
        engine = PolicyEngine(lint_mode="off")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            engine.resolve(type="tool", id="Bash", property="allow")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) == 0


class TestLintModeWarn:
    def test_warn_emits_on_compile(self):
        engine = PolicyEngine(lint_mode="warn")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            engine.resolve(type="tool", id="Bash", property="allow")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) >= 1


class TestLintModeError:
    def test_error_raises_on_compile(self):
        engine = PolicyEngine(lint_mode="error")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        with pytest.raises(PolicyLintError):
            engine.resolve(type="tool", id="Bash", property="allow")


class TestLintModeNotice:
    def test_notice_does_not_raise(self):
        engine = PolicyEngine(lint_mode="notice")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        val = engine.resolve(type="tool", id="Bash", property="allow")
        assert val == "true"


class TestLintModeDict:
    def test_custom_config(self):
        engine = PolicyEngine(lint_mode={
            "error": ["narrow_win"],
            "default": "off",
        })
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        with pytest.raises(PolicyLintError) as exc_info:
            engine.resolve(type="tool", id="Bash", property="allow")
        assert exc_info.value.warnings[0].smell == "narrow_win"


class TestFromFilesLintMode:
    def test_from_files_with_lint(self, tmp_path):
        world = tmp_path / "test.world.yml"
        world.write_text("entities:\n  - type: tool\n    id: Bash\n    classes: [dangerous]\n")
        style = tmp_path / "test.umw"
        style.write_text("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }\n")
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            engine = PolicyEngine.from_files(world=world, stylesheet=style, lint_mode="warn")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) >= 1


class TestFromDbLintMode:
    def test_from_db_with_lint(self, tmp_path):
        engine = PolicyEngine()
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        db_path = tmp_path / "test.db"
        engine.save(str(db_path))
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            PolicyEngine.from_db(str(db_path), lint_mode="warn")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) >= 1


class TestExtendInheritance:
    def test_extend_inherits_lint_mode(self):
        engine = PolicyEngine(lint_mode="error")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        # Calling extend should use parent's lint_mode
        with pytest.raises(PolicyLintError):
            engine.extend(
                entities=[{"type": "tool", "id": "Read", "classes": ["safe"]}],
            )

    def test_extend_overrides_lint_mode(self):
        engine = PolicyEngine(lint_mode="error")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        # Override to off — should not raise
        extended = engine.extend(
            entities=[{"type": "tool", "id": "Read", "classes": ["safe"]}],
            lint_mode="off",
        )
        assert extended.resolve(type="tool", id="Read", property="allow") is None


class TestEnvVar:
    def test_env_var_sets_default(self, monkeypatch):
        monkeypatch.setenv("UMWELT_LINT", "warn")
        engine = PolicyEngine()
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            engine.resolve(type="tool", id="Bash", property="allow")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) >= 1

    def test_explicit_overrides_env(self, monkeypatch):
        monkeypatch.setenv("UMWELT_LINT", "error")
        engine = PolicyEngine(lint_mode="off")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        val = engine.resolve(type="tool", id="Bash", property="allow")
        assert val == "true"


class TestExplicitLintUnchanged:
    def test_lint_returns_all_regardless_of_mode(self):
        engine = PolicyEngine(lint_mode="off")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
        engine.resolve(type="tool", id="Bash", property="allow")
        results = engine.lint()
        assert len(results) >= 1
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/policy/test_lint_integration.py -v
```

- [ ] **Step 3: Add lint_mode to PolicyEngine.__init__**

In `src/umwelt/policy/engine.py`, modify `__init__`:

```python
def __init__(self, lint_mode: str | dict | None = None) -> None:
    self._con: sqlite3.Connection | None = None
    self._pending_entities: list[dict[str, Any]] = []
    self._pending_stylesheets: list[str] = []
    self._compiled = False
    self._lint_mode = lint_mode
    self._lint_config = self._resolve_lint_config(lint_mode)
```

Add the config resolution helper as a static method:

```python
@staticmethod
def _resolve_lint_config(lint_mode: str | dict | None) -> Any:
    import os
    from umwelt.policy.lint import LintConfig
    if lint_mode is None:
        lint_mode = os.environ.get("UMWELT_LINT", "off")
    return LintConfig.from_lint_mode(lint_mode)
```

- [ ] **Step 4: Add lint_mode to from_files**

Change the `from_files` signature to accept `lint_mode`:

```python
@classmethod
def from_files(
    cls,
    *,
    world: str | Path,
    stylesheet: str | Path,
    lint_mode: str | dict | None = None,
) -> PolicyEngine:
```

And after the engine is created (after `engine._compiled = True`), add:

```python
engine._lint_mode = lint_mode
engine._lint_config = cls._resolve_lint_config(lint_mode)
engine._run_compile_lint()
```

- [ ] **Step 5: Add lint_mode to from_db**

Change `from_db`:

```python
@classmethod
def from_db(cls, path: str | Path, lint_mode: str | dict | None = None) -> PolicyEngine:
    source = sqlite3.connect(str(path))
    con = sqlite3.connect(":memory:")
    source.backup(con)
    source.close()

    engine = cls.__new__(cls)
    engine._con = con
    engine._pending_entities = []
    engine._pending_stylesheets = []
    engine._compiled = True
    engine._lint_mode = lint_mode
    engine._lint_config = cls._resolve_lint_config(lint_mode)
    engine._run_compile_lint()
    return engine
```

- [ ] **Step 6: Add lint_mode to extend**

Change `extend`:

```python
def extend(
    self,
    *,
    entities: list[dict[str, Any]] | None = None,
    stylesheet: str | None = None,
    lint_mode: str | dict | None = None,
) -> PolicyEngine:
    con = self._ensure_compiled()

    new_con = sqlite3.connect(":memory:")
    con.backup(new_con)

    effective_lint = lint_mode if lint_mode is not None else self._lint_mode

    new_engine = PolicyEngine.__new__(PolicyEngine)
    new_engine._con = new_con
    new_engine._pending_entities = list(entities) if entities else []
    new_engine._pending_stylesheets = [stylesheet] if stylesheet else []
    new_engine._compiled = False
    new_engine._lint_mode = effective_lint
    new_engine._lint_config = self._resolve_lint_config(effective_lint)

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
```

- [ ] **Step 7: Add _run_compile_lint helper and call it from _ensure_compiled and _recompile_incremental**

Add the helper method to `PolicyEngine`:

```python
def _run_compile_lint(self) -> None:
    if self._lint_config.default == "off" and not self._lint_config.overrides:
        return
    from umwelt.policy.lint import process_lint_results, run_lint
    con = self._con
    if con is None:
        return
    lint_warnings = run_lint(con)
    if lint_warnings:
        process_lint_results(lint_warnings, self._lint_config)
```

At the end of `_ensure_compiled` (after `self._compiled = True`), add:

```python
self._run_compile_lint()
```

At the end of `_recompile_incremental` (after `self._compiled = True`), add:

```python
self._run_compile_lint()
```

- [ ] **Step 8: Update __init__.py exports**

In `src/umwelt/policy/__init__.py`:

```python
from umwelt.policy.engine import Candidate, LintWarning, PolicyEngine, TraceResult
from umwelt.policy.lint import LintConfig

__all__ = [
    "Candidate",
    "LintConfig",
    "LintWarning",
    "PolicyEngine",
    "TraceResult",
]
```

- [ ] **Step 9: Run integration tests — verify they pass**

```bash
pytest tests/policy/test_lint_integration.py -v
```

- [ ] **Step 10: Run all tests — verify no regressions**

```bash
pytest tests/ -q
```

- [ ] **Step 11: Commit**

```bash
git add src/umwelt/policy/engine.py src/umwelt/policy/__init__.py tests/policy/test_lint_integration.py
git commit -m "feat(policy): add lint_mode parameter to PolicyEngine"
```

---

### Task 5: CLI --lint flag

**Files:**
- Modify: `src/umwelt/cli.py`
- Create: `tests/policy/test_lint_cli.py`

- [ ] **Step 1: Write CLI tests**

```python
# tests/policy/test_lint_cli.py
from __future__ import annotations

from pathlib import Path

import pytest

from umwelt.cli import build_parser, main


@pytest.fixture
def narrow_win_files(tmp_path):
    """World + stylesheet that produce a narrow_win lint smell."""
    world = tmp_path / "test.world.yml"
    world.write_text("entities:\n  - type: tool\n    id: Bash\n    classes: [dangerous]\n")
    style = tmp_path / "test.umw"
    style.write_text("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }\n")
    return world, style


class TestCheckLintFlag:
    def test_check_parser_accepts_lint(self):
        parser = build_parser()
        args = parser.parse_args(["check", "test.umw", "--lint", "warn"])
        assert args.lint == "warn"

    def test_check_default_no_lint(self):
        parser = build_parser()
        args = parser.parse_args(["check", "test.umw"])
        assert args.lint is None


class TestCompileLintFlag:
    def test_compile_parser_accepts_lint(self):
        parser = build_parser()
        args = parser.parse_args(["compile", "test.umw", "--target", "sqlite", "--lint", "error"])
        assert args.lint == "error"


class TestDryRunLintFlag:
    def test_dry_run_parser_accepts_lint(self):
        parser = build_parser()
        args = parser.parse_args(["dry-run", "test.umw", "--lint", "notice"])
        assert args.lint == "notice"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/policy/test_lint_cli.py -v
```

- [ ] **Step 3: Add --lint flag to CLI subparsers**

In `src/umwelt/cli.py`, in `build_parser()`, add `--lint` to the three subparsers. After each subparser is created, add:

For `p_check` (after `p_check.add_argument("file", ...)`):
```python
p_check.add_argument(
    "--lint", default=None, choices=["off", "notice", "warn", "error"],
    help="lint severity level (default: off unless UMWELT_LINT is set)",
)
```

For `p_dry` (after `p_dry.add_argument("--world", ...)`):
```python
p_dry.add_argument(
    "--lint", default=None, choices=["off", "notice", "warn", "error"],
    help="lint severity level (default: off unless UMWELT_LINT is set)",
)
```

For `p_compile` (after `p_compile.add_argument("-d", ...)`):
```python
p_compile.add_argument(
    "--lint", default=None, choices=["off", "notice", "warn", "error"],
    help="lint severity level (default: off unless UMWELT_LINT is set)",
)
```

- [ ] **Step 4: Add lint output formatting helper**

Add to `src/umwelt/cli.py` (near the top, after imports):

```python
def _format_lint_output(lint_warnings: list, lint_level: str) -> str:
    """Format lint warnings for CLI output."""
    if not lint_warnings:
        return "Lint: clean"
    counts: dict[str, int] = {}
    for w in lint_warnings:
        sev = w.severity
        counts[sev] = counts.get(sev, 0) + 1
    summary_parts = []
    for sev in ("warning", "notice"):
        if sev in counts:
            summary_parts.append(f"{counts[sev]} {sev}{'s' if counts[sev] != 1 else ''}")
    lines = [f"Lint: {', '.join(summary_parts) if summary_parts else 'clean'}"]
    for w in lint_warnings:
        lines.append(f"  [{w.severity:7s}] {w.smell}: {w.description}")
    return "\n".join(lines)
```

- [ ] **Step 5: Wire lint into _cmd_check**

Update `_cmd_check` to run lint after the existing check output. Replace the function:

```python
def _cmd_check(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _register_matchers(Path(args.file))
    print(format_check(view))

    lint_level = getattr(args, "lint", None)
    if lint_level and lint_level != "off":
        from umwelt.policy.lint import LintConfig, process_lint_results, run_lint
        try:
            from umwelt.policy import PolicyEngine
            engine = PolicyEngine.from_files(
                world=_find_world_file(Path(args.file)),
                stylesheet=Path(args.file),
                lint_mode="off",
            )
            lint_warnings = engine.lint()
            print(_format_lint_output(lint_warnings, lint_level))
            config = LintConfig.from_lint_mode(lint_level)
            process_lint_results(lint_warnings, config)
        except FileNotFoundError:
            print("Lint: skipped (no world file found)", file=sys.stderr)
        except Exception as exc:
            print(f"Lint: error — {exc}", file=sys.stderr)
            if lint_level == "error":
                return 1
    return 0
```

Add the world file finder helper:

```python
def _find_world_file(stylesheet_path: Path) -> Path:
    """Find the world file for a stylesheet by convention."""
    stem = stylesheet_path.stem
    parent = stylesheet_path.parent
    for suffix in (".world.yml", ".world.yaml"):
        candidate = parent / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    for f in parent.iterdir():
        if f.name.endswith(".world.yml") or f.name.endswith(".world.yaml"):
            return f
    raise FileNotFoundError(f"No world file found for {stylesheet_path}")
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
pytest tests/policy/test_lint_cli.py -v
```

- [ ] **Step 7: Run full test suite**

```bash
pytest tests/ -q
```

- [ ] **Step 8: Commit**

```bash
git add src/umwelt/cli.py tests/policy/test_lint_cli.py
git commit -m "feat(cli): add --lint flag to check, dry-run, compile commands"
```

---

### Task 6: Full integration test + existing test updates

**Files:**
- Modify: `tests/policy/test_lint.py` (if not already updated in Task 2)

- [ ] **Step 1: Run the full test suite to verify everything works together**

```bash
pytest tests/ -q
```

- [ ] **Step 2: Run ruff**

```bash
ruff check src/umwelt/policy/lint.py src/umwelt/policy/engine.py src/umwelt/errors.py src/umwelt/cli.py
```

- [ ] **Step 3: Fix any ruff issues**

Address any linting errors or import ordering issues.

- [ ] **Step 4: Run mypy (if it passes on this package)**

```bash
mypy src/umwelt/policy/lint.py src/umwelt/policy/engine.py src/umwelt/errors.py || true
```

- [ ] **Step 5: Commit any fixups**

```bash
git add -u
git commit -m "chore: lint/type fixups for lint strict mode"
```

---

## Verification

After all tasks:

1. **New detector tests pass:** `pytest tests/policy/test_lint_new_detectors.py -v` — all green
2. **LintConfig tests pass:** `pytest tests/policy/test_lint_config.py -v` — all green
3. **Integration tests pass:** `pytest tests/policy/test_lint_integration.py -v` — all green
4. **CLI tests pass:** `pytest tests/policy/test_lint_cli.py -v` — all green
5. **Existing lint tests pass:** `pytest tests/policy/test_lint.py -v` — all green (with rename)
6. **Full suite passes:** `pytest tests/ -q` — no regressions
7. **Ruff passes:** `ruff check src/umwelt/policy/ src/umwelt/errors.py src/umwelt/cli.py`
8. **Python API works:**
   ```python
   from umwelt.policy import PolicyEngine
   engine = PolicyEngine(lint_mode="warn")
   engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
   engine.add_stylesheet("tool.dangerous { allow: false; }\ntool#Bash { allow: true; }")
   engine.resolve(type="tool", id="Bash", property="allow")
   # Should emit UserWarning about narrow_win
   ```
