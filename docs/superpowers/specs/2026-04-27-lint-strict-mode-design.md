# PolicyEngine Lint, Warnings, and Strict Mode

## Goal

Extend the PolicyEngine's existing lint infrastructure with new detectors for surprising cascade behaviors, a configurable severity system (`LintConfig`), compile-time lint integration, and CLI surface — so that cross-axis dominance, ceiling semantics, specificity ties, and source-order dependence are surfaced rather than silently producing unexpected results.

## Background

Pressure testing the PolicyEngine API across three novel domains (data pipeline governance, multi-tenant access control, CI/CD pipeline policy) revealed correct-but-surprising cascade behaviors that took significant debugging to understand:

1. **Cross-axis specificity dominance** — `principal#admin tool { allow: true }` beats `tool#Deploy { allow: false }` in unfiltered resolution because cross-axis selectors always outrank single-axis selectors.
2. **Ceiling ineffectiveness** — `mode#implement tool.dangerous { max-level: 4 }` can't raise a ceiling set by `tool.dangerous { max-level: 3 }` because `<=` comparison takes MIN.
3. **Source-order dependence** — same-specificity rules with different values are decided by rule_index (source order), which is fragile.

These are working-as-designed, but a linter should flag them. Additionally, several other detectable conditions emerged during analysis.

## Design

### Severity Tiers

Four tiers, ordered by visibility:

| Tier | Behavior |
|---|---|
| `off` | Suppressed entirely |
| `notice` | Logged via `logging.info` — visible in `--verbose` / debug output |
| `warn` | Emitted via `warnings.warn(UserWarning)` — visible by default |
| `error` | Collected and raised as `PolicyLintError` — aborts compilation |

### LintConfig

A frozen dataclass that maps smell names to effective severity tiers.

```python
@dataclass(frozen=True)
class LintConfig:
    default: str   # "off" | "notice" | "warn" | "error"
    overrides: dict[str, str]  # smell_name -> severity tier
```

Constructed from a `lint_mode` value via `LintConfig.from_lint_mode()`:

```python
# Preset strings — set all smells to this tier
lint_mode = "off"       # LintConfig(default="off", overrides={})
lint_mode = "warn"      # LintConfig(default="warn", overrides={})
lint_mode = "error"     # LintConfig(default="error", overrides={})

# Dict form — per-smell control with a default fallback
lint_mode = {
    "error": ["cross_axis_dominance", "specificity_tie"],
    "warn": ["ceiling_ineffective", "source_order_dependence"],
    "notice": ["uncovered_entity"],
    "off": ["shadowed_rule"],
    "default": "warn",
}
```

`LintConfig.severity_for(smell)` returns the effective tier: override if present, else `default`.

Note: `LintWarning.severity` (set by the detector) is the *recommended* severity — a hint for display. `LintConfig` determines the *effective* severity — what actually happens (log, warn, raise). The config can promote or demote any smell regardless of its recommended severity.

### Env Var Default

`UMWELT_LINT` env var provides the default `lint_mode` when none is passed to the engine. Only string presets are supported via env var (not the dict form). Falls back to `"off"` if unset.

### New Detectors

Added to `lint.py` alongside the existing seven, following the same `_detect_*(con) -> list[LintWarning]` pattern.

**`cross_axis_dominance`** (recommended severity: `warning`)

Fires when a cross-axis rule wins over a single-axis ID rule for the same entity+property in the unfiltered cascade. Detects by comparing specificity tuple position 0 (cross-axis count) between winner and runner-up — if winner has nonzero cross-axis and runner-up has zero, that's dominance.

Message: `"tool#Deploy 'allow': cross-axis rule dominates single-axis ID selector — value 'true' overrides 'false'"`

**`ceiling_ineffective`** (recommended severity: `notice`)

Fires when a `<=` candidate at higher specificity sets a higher value than a lower-specificity candidate. The MIN semantics mean the higher-specificity rule's value is never used.

Message: `"tool#Bash 'max-level': value '4' at higher specificity is ineffective — ceiling clamped to '3' by lower-specificity rule"`

**`specificity_tie`** (recommended severity: `warning`)

Fires when two candidates for the same entity+property have identical specificity AND identical rule_index but different values. This indicates nondeterministic resolution — can happen across `extend()` boundaries.

Message: `"tool#Bash 'require': specificity tie between 'sandbox' and 'none' — resolution order is nondeterministic"`

**`cross_axis_tie`** (recommended severity: `warning`)

Fires when two cross-axis rules from different qualifier axes (e.g., one mode-gated, one principal-gated) compete for the same entity+property. Both have nonzero cross-axis components but gate on different things — the policy author likely didn't consider the interaction.

Message: `"tool#Deploy 'allow': cross-axis rules from different axes compete — principal#ops (allow: true) vs mode#review (allow: false)"`

**`ceiling_conflict`** (recommended severity: `notice`)

Fires when two `<=` candidates at the same specificity set different values. Unlike exact comparison where source order picks the winner, `<=` takes MIN regardless — but having competing ceilings suggests confused intent.

Message: `"tool#Bash 'max-level': competing ceiling values '3' and '5' at same specificity — MIN ('3') wins regardless of order"`

### Renamed Detector

**`conflicting_intent` → `source_order_dependence`**

Same detection logic (same specificity, different values, exact comparison). Updated message to explicitly state resolution mechanism: `"tool#Bash 'allow': 'true' vs 'false' at same specificity — resolved by source order (later rule wins)"`.

### Complete Smell Catalog

After this work, the full set of detectable smells:

| Smell | Category | Recommended Severity |
|---|---|---|
| `narrow_win` | Specificity | warning |
| `specificity_escalation` | Specificity | warning |
| `source_order_dependence` | Specificity | warning |
| `specificity_tie` | Specificity | warning |
| `cross_axis_dominance` | Cross-axis | warning |
| `cross_axis_tie` | Cross-axis | warning |
| `ceiling_ineffective` | Ceiling | notice |
| `ceiling_conflict` | Ceiling | notice |
| `uncovered_entity` | Coverage | notice |
| `shadowed_rule` | Coverage | notice |
| `fixed_override` | Enforcement | notice |
| `unrealizable_altitude` | Enforcement | warning |

### process_lint_results

```python
def process_lint_results(
    warnings: list[LintWarning], config: LintConfig,
) -> list[LintWarning]:
```

Iterates warnings, applies `config.severity_for(w.smell)`:
- `off` → skip
- `notice` → `logger.info(...)`, keep in returned list
- `warn` → `warnings.warn(UserWarning, ...)`, keep in returned list
- `error` → collect, keep in returned list

After iteration, if any errors collected, raises `PolicyLintError(errors)`.

Returns the non-suppressed warnings (useful for programmatic inspection).

### PolicyLintError

New exception in `src/umwelt/errors.py`:

```python
class PolicyLintError(UmweltError):
    def __init__(self, warnings: list[LintWarning]):
        self.warnings = warnings
        descriptions = "; ".join(f"{w.smell}: {w.description}" for w in warnings)
        super().__init__(f"Lint errors: {descriptions}")
```

### PolicyEngine Integration

**Constructor parameter:**

All construction paths accept `lint_mode`:

```python
PolicyEngine(lint_mode="warn")
PolicyEngine.from_files(world=..., stylesheet=..., lint_mode="error")
PolicyEngine.from_db(path, lint_mode={...})
```

When `lint_mode` is `None` (the default), reads `UMWELT_LINT` env var, falls back to `"off"`.

**Stored state:**

Engine stores both `_lint_mode` (raw value for inheritance/serialization) and `_lint_config` (computed `LintConfig` instance).

**Compile-time integration:**

After `_ensure_compiled()` and `_recompile_incremental()` finish building resolution views, if `lint_mode != "off"`:
1. `run_lint(con)` → `list[LintWarning]`
2. `process_lint_results(warnings, self._lint_config)` → logs/warns/raises per config

**extend() inheritance:**

```python
def extend(self, *, entities=None, stylesheet=None, lint_mode=None):
    effective_lint = lint_mode if lint_mode is not None else self._lint_mode
```

**Explicit lint() unchanged:**

`engine.lint()` continues to return raw `list[LintWarning]` regardless of `lint_mode`. It's the "give me everything" path.

### CLI Integration

Lint integrates into existing commands via `--lint` flag, not a new subcommand.

**Flag:**
```
--lint off|notice|warn|error
```

Dict form is not available via CLI — programmatic API only. `UMWELT_LINT` env var provides default if `--lint` not passed.

**Commands that gain `--lint`:**
- `umwelt check` — lint runs after parse/validate/compiler coverage
- `umwelt dry-run` — lint runs after cascade resolution
- `umwelt compile` — lint runs after compilation; with `--lint error`, exits non-zero

**Output format:**
```
Lint: 2 warnings, 1 notice
  [warning] cross_axis_dominance: tool#Deploy 'allow': cross-axis rule dominates single-axis ID selector
  [warning] specificity_tie: tool#Bash 'require': specificity tie — nondeterministic
  [notice]  ceiling_ineffective: tool#Bash 'max-level': value '4' ineffective — clamped to '3'
```

**Exit codes:**
- `--lint error` + errors found → exit 1
- `--lint warn` + warnings found → exit 0 (output to stderr)
- `--lint notice` → exit 0

### Files Changed

| File | Change |
|---|---|
| `src/umwelt/policy/lint.py` | Add 5 new detectors, rename `conflicting_intent`, add `LintConfig`, `process_lint_results` |
| `src/umwelt/policy/engine.py` | Add `lint_mode` param to all constructors, compile-time lint call |
| `src/umwelt/errors.py` | Add `PolicyLintError` |
| `src/umwelt/cli.py` | Add `--lint` flag to check, dry-run, compile |
| `src/umwelt/policy/__init__.py` | Export `LintConfig`, `PolicyLintError` |
| `tests/policy/test_lint.py` | Tests for 5 new detectors, `LintConfig`, `process_lint_results` |
| `tests/policy/test_lint_integration.py` | Engine-level compile-time lint tests |
| `tests/policy/test_lint_cli.py` | CLI `--lint` flag tests |

### What This Does NOT Include

- **Lint rule plugin registry** — detectors are hardcoded in `lint.py`. The `_detect_*(con) -> list[LintWarning]` signature is the future registry interface; migration is mechanical when needed.
- **Per-file lint suppression** — no `/* lint-disable */` comment syntax. Future work if needed.
- **Context-aware lint** — detectors analyze the compiled cascade, not per-query resolution. A future `resolve(..., lint=True)` could flag issues specific to a particular context query.
