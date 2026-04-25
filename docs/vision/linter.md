# Cross-Format Linter

*A lint pass that operates over the world file and policy as a pair, catching what format-level safety and vocabulary defaults cannot.*

## Why a linter

umwelt's three-layer architecture provides format-level safety guarantees:

- **YAML world files** can't express conditionals — policy logic can't leak into world declaration.
- **CSS policy** ignores unknown properties and selectors — unrecognized constructs fall back to vocabulary defaults.
- **Vocabulary** defines restrictive `initial-value` for every property — unknown = restricted.

These guarantees are real but incomplete. They don't catch:

- A permissive CSS rule that defeats a restrictive one via higher specificity
- A world-file entity that no vocabulary plugin handles (outside the policy pipeline)
- A CSS selector that targets entities absent from the world (dead rule)
- Gradual permissive drift across policy edits

The linter fills these gaps. It operates across both formats simultaneously, comparing the world file and the policy as a pair. It makes implicit cascade outcomes visible without deciding whether they're correct — the human reviews, the ratchet commits.

## Prerequisite: directional properties

The linter's most important capability — detecting specificity conflicts that weaken security — requires a vocabulary extension: **directional metadata on properties.**

### Extension to `PropertySchema`

```python
@dataclass(frozen=True)
class PropertySchema:
    name: str
    taxon: str
    entity: str
    value_type: type
    comparison: Comparison = "exact"
    restrictive_direction: RestrictiveDirection | None = None  # NEW
    # ... existing fields ...

RestrictiveDirection = Literal["false", "true", "min", "max", "subset", "superset"]
```

Three directionality kinds cover the property types:

| Kind | Meaning | Example |
|---|---|---|
| `"false"` / `"true"` | One boolean value is restrictive | `editable`: restrictive is `false` |
| `"min"` / `"max"` | Numeric ordering | `max-output-tokens`: restrictive is `min` (lower) |
| `"subset"` / `"superset"` | Set containment | `allowed-hosts`: restrictive is `subset` (fewer) |

### Registration example

```python
register_property(
    taxon="world", entity="file", name="editable",
    value_type=bool, comparison="exact",
    restrictive_direction="false",
    description="Whether the file can be edited.",
)

register_property(
    taxon="capability", entity="tool", name="max-level",
    value_type=int, comparison="<=",
    restrictive_direction="min",
    description="Maximum computation level.",
)
```

### Migration from `_WIDENING_TRANSITIONS`

The existing `audit.py` module hardcodes widening transitions:

```python
_WIDENING_TRANSITIONS = {
    "editable": [("false", "true")],
    "allow": [("false", "true")],
    "visible": [("false", "true")],
    "deny": [("*", "")],
}
```

With `restrictive_direction` on `PropertySchema`, widening detection becomes generic:

```python
def is_widening(prop: PropertySchema, old_value: str, new_value: str) -> bool:
    match prop.restrictive_direction:
        case "false": return old_value == "false" and new_value == "true"
        case "true": return old_value == "true" and new_value == "false"
        case "min": return float(new_value) > float(old_value)
        case "max": return float(new_value) < float(old_value)
        case "subset": return not set(new_value).issubset(set(old_value))
        case _: return False  # no directionality declared
```

The hardcoded table becomes the fallback for properties that predate the extension. New properties get directionality at registration.

### Vocabulary invariant

Every property registered with the sandbox vocabulary MUST declare `restrictive_direction`. The linter flags properties that lack it — the restrict-by-default invariant depends on the vocabulary knowing which direction is restrictive.

## Check categories

### World-file checks

| Check | What it detects | Severity |
|---|---|---|
| **Unknown entities** | Entity types no registered vocabulary plugin handles | Warning |
| **Safe-subset violations** | YAML features outside safe parsing: `!!python/object`, `!!binary`, anchors creating circular references, non-string keys, Norway-problem coercion (`no`/`on`/`off` as booleans) | Error |
| **Templating artifacts** | Jinja2 `{{ }}` markers, Helm `{{ .Values }}`, shell `${VAR}` interpolation — evidence of a preprocessing layer that defeats format-level guarantees | Warning |
| **Duplicate entity IDs** | Same ID used twice within a type (e.g., two `tool#Edit` declarations) | Error |
| **Empty discovery** | `discover:` patterns that resolve to zero entities at materialization time | Info |
| **Include cycles** | `include:` chains that form cycles | Error |
| **Fixed-constraint conflicts** | Fixed blocks that set contradictory values for the same property | Error |

### Policy-file checks

| Check | What it detects | Severity |
|---|---|---|
| **Dead selectors** | Selectors that match no entity in the current world file | Warning |
| **Unknown types** | Entity types in selectors that no vocabulary plugin defines | Warning |
| **Unknown properties** | Property names in declarations that no vocabulary declares | Warning |
| **Missing restrictive-direction** | `@property` declarations or registered properties that lack `restrictive_direction` | Warning |
| **Permissive initial values** | Properties whose `initial-value` is not the restrictive direction | Error |
| **`!important` audit** | Every `!important` declaration reported as an audit entry | Info |
| **Redundant rules** | Rules completely shadowed — every entity they match is also matched by a higher-specificity rule setting the same property | Info |

### Specificity and cascade checks

These operate over the *computed* cascade — all rules resolved against all entities.

#### Permissive override detection

For each (entity, property) pair:
1. Compute the cascade winner (highest specificity)
2. Collect all matching rules for that property
3. If the winner's value is more permissive than a lower-specificity matching rule's value (using `restrictive_direction`), flag it

Report format:
```
WARN: permissive override
  entity: file#auth.py
  property: editable
  winner: true  (specificity: axis=3, principal=10001, world=10001, capability=10001)
    from: principal#Teague mode#implement tool#Edit file#auth.py { editable: true }
    at: policy.umw:47
  defeated: false  (specificity: axis=2, state=10001, world=1)
    from: mode#review file { editable: false }
    at: policy.umw:12
```

The human decides whether the override is intentional.

#### Shadowed restrictive rules

Flag restrictive rules that never win for any entity in the current world file. These are rules someone wrote expecting them to enforce a constraint, but higher-specificity permissive rules always override them.

Different from dead selectors: dead selectors match nothing. Shadowed rules match entities but always lose the cascade.

#### Permissive drift detection

Compare the effective policy against a baseline (previous materialization, or the vocabulary's initial values). Report entities whose effective policy became more permissive.

Input: two materialized policy databases (SQLite), or one database and the vocabulary defaults.

Output: per-entity, per-property diff with directionality:
```
DRIFT: file#auth.py
  editable: false → true  (WIDENING)
  visible: true → true    (unchanged)

DRIFT: tool#Bash
  allow: false → true     (WIDENING)
```

This catches gradual weakening across policy edits — no single edit looks dangerous, but the cumulative effect widens.

#### Axis-coverage depth

For each entity, report which authorization axes (S0–S5) the winning rule qualifies. The axis count comes directly from the specificity tuple's first element.

```
SHALLOW: file#auth.py
  editable: true  (axis_count=1, world only)
  ← consider: qualify with mode, principal, or harness for narrower grant

DEEP: file#auth.py
  editable: true  (axis_count=4, principal + state + capability + world)
  ← well-qualified grant
```

Shallow grants (few axes) deserve more scrutiny than deep grants (many axes). The linter surfaces this without requiring human annotation — `axis_count` from the specificity tuple provides it mechanically.

#### Fixed-constraint conflicts

Flag CSS rules that set a property to a value that the world file's `fixed:` block clamps. These rules are inert — fixed constraints apply after cascade resolution — but they indicate confusion about what the policy controls vs what the environment enforces.

```
INFO: fixed-constraint override
  entity: tool#Bash
  property: allow
  css value: true  (from policy.umw:23)
  fixed value: false  (from world.yml fixed block)
  effective: false  (fixed wins)
```

### Cross-format checks

| Check | What it detects | Severity |
|---|---|---|
| **Coverage** | Entities in the world file that no CSS rule targets for any property (governed only by defaults) | Info |
| **Consistency** | Entity types in CSS selectors that exist in neither the world file nor the vocabulary | Warning |
| **Effective policy report** | Per-entity, per-property effective value after cascade, with source rule, specificity, and whether any restrictive rule was overridden | Report |

### What's mechanical vs what needs human judgment

| Check | Mechanical? | Notes |
|---|---|---|
| Dead selectors | Yes | Compare selectors against world entities |
| Unknown types/properties | Yes | Compare against vocabulary |
| Permissive overrides | Yes, given `restrictive_direction` | Compare winner against lower-specificity matches |
| Shadowed restrictive rules | Yes | Compute which rules never win |
| Permissive drift | Yes, given baseline | Diff effective policy against prior materialization |
| Axis-coverage depth | Yes | Read from specificity tuple |
| Fixed-constraint conflicts | Yes | Compare cascade values against fixed block |
| Intentional vs accidental override | No | Linter flags; human decides |
| Whether a permissive grant is appropriate | No | Context-dependent |
| Vocabulary completeness | Partial | Can flag missing properties; can't know what *should* exist |

## CLI integration

```
umwelt lint <policy.umw> --world <world.yml>
umwelt lint <policy.umw> --world <world.yml> --baseline <previous.db>
umwelt lint <policy.umw> --world <world.yml> --report effective-policy
umwelt lint <policy.umw> --world <world.yml> --severity warning  # filter by min severity
```

The `--baseline` flag enables permissive-drift detection. Without it, drift checks are skipped.

The `--report effective-policy` flag emits the full effective-policy report (all entities, all properties, all provenance) instead of just lint findings. This is the audit artifact.

## Output formats

- **Human-readable** (default): grouped by severity, with source locations and rule text
- **JSON**: structured findings for CI integration
- **SQLite**: findings as rows in a lint database, joinable with the policy database

The SQLite output enables the ratchet to consume lint findings as observations — a lint finding that persists across multiple edits is evidence that the policy author is intentionally maintaining the permissive override.

## Design notes

### The linter is not an enforcer

The linter reports. It doesn't block. Enforcement is the job of nsjail, bwrap, lackpy, and the CSS cascade itself. The linter is Layer 2 (observation) applied to the policy layer — it watches the policy and produces evidence, same as blq watches the delegate.

### Relationship to `umwelt audit`

The existing `umwelt audit` command does widening detection and enforcement coverage reporting. The linter subsumes and extends it:

- `audit` → linter's permissive-override and widening checks
- `audit --enforcement-coverage` → unchanged (orthogonal)
- `lint` adds: dead selectors, unknown types, axis depth, cross-format consistency, drift detection, fixed-constraint conflicts

Migration path: `umwelt audit` becomes an alias for `umwelt lint --checks widening,enforcement-coverage` in v0.7.

### Relationship to the ratchet

The ratchet observes delegate behavior and proposes tighter policy. The linter observes policy structure and flags potential weaknesses. They're complementary:

- Ratchet: "the delegate only used tools {Read, Edit} — propose removing Bash"
- Linter: "the policy grants tool#Bash access but a mode#review lockdown tried to deny it and lost on specificity"

Both produce observations. Both feed the human review loop. Neither decides.

### Mode-as-ID refinement

The vocabulary registers modes as ID selectors (`mode#review`, `mode#implement`). The linter design assumes mode-as-ID because:

1. Modes are named instances — there's one "review" mode, not a category of review-like things
2. ID selectors contribute to axis weight, ensuring mode-qualified rules dominate over entity-level grants
3. Classes remain available for mode *categories* (`mode#review.read-only`, `mode#implement.destructive`)

Mode instances are declared in the world file as named entities:

```yaml
modes:
  - review
  - implement
  - test
```

And referenced in policy as IDs:

```css
mode#review file { editable: false; }
mode#implement tool#Bash { allow: true; }
```
