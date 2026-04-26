# Plugin API Gaps — Design Specification

*Addressing seven gaps in the umwelt plugin API that block multi-tool coexistence in the retritis ecosystem.*

## Context

umwelt's plugin API provides registration surfaces for taxa, entities, properties, matchers, validators, compilers, and world-file shorthands. The sandbox consumer demonstrates the pattern. But when blq, kibitzer, jetsam, fledgling, and squackit all need to coexist as plugins, seven gaps emerge — ranging from hard blockers (one matcher per taxon) to missing contracts (altitude filtering).

This spec designs solutions for all seven, prioritized by impact.

### Consumer tools and their needs

| Tool | Purpose | Key entity types | Taxon needs |
|------|---------|-----------------|-------------|
| blq | Build/test event capture and query | build-run, build-command, build-error | state |
| kibitzer | Tool call observation, mode enforcement | mode, hook, tool-call, path-restriction | state, capability |
| jetsam | Git workflow with confirmation plans | git-operation, branch, git-plan | state, world |
| fledgling | DuckDB code analysis and conversation audit | ast-node, definition, conversation-message | audit, world |
| squackit | MCP server wrapping fledgling/sitting_duck | query, cache-entry, response | state |
| pluckit | Code mutation chains with CSS selectors | selector, mutation, chain | capability, world |

---

## P0: CompositeMatcher — Multi-Matcher Per Taxon

### Problem

`registry/matchers.py:75` raises `RegistryError` if a second matcher is registered for the same taxon. Storage is `dict[str, MatcherProtocol]`. blq, kibitzer, and sandbox all need to provide entities in the `state` taxon.

### Design

Add `CompositeMatcher` to `umwelt.registry.matchers` that delegates to an ordered list of child matchers:

```python
class CompositeMatcher:
    """Delegates to multiple matchers for the same taxon."""
    
    def __init__(self, *delegates: MatcherProtocol):
        self._delegates = list(delegates)
    
    def add(self, matcher: MatcherProtocol) -> None:
        self._delegates.append(matcher)
    
    def match_type(self, type_name, context=None):
        results = []
        for d in self._delegates:
            results.extend(d.match_type(type_name, context))
        return results
    
    def children(self, parent, child_type):
        results = []
        for d in self._delegates:
            results.extend(d.children(parent, child_type))
        return results
    
    def condition_met(self, selector, context=None):
        return any(d.condition_met(selector, context) for d in self._delegates)
    
    def get_attribute(self, entity, name):
        for d in self._delegates:
            val = d.get_attribute(entity, name)
            if val is not None:
                return val
        return None
    
    def get_id(self, entity):
        for d in self._delegates:
            val = d.get_id(entity)
            if val is not None:
                return val
        return None
```

### Auto-composition on collision

Change `register_matcher()` behavior: instead of raising on duplicate, wrap in a CompositeMatcher:

```python
def register_matcher(*, taxon: str, matcher: MatcherProtocol) -> None:
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
```

Consumers call `register_matcher()` independently. Order is registration order. No coordination required.

### Semantics

- `match_type()`: union of all delegates' results
- `condition_met()`: OR — any delegate satisfied means the gate passes
- `get_id()` / `get_attribute()`: first non-None wins (registration order)
- `children()`: union of all delegates' results

### Files changed

- `src/umwelt/registry/matchers.py` — add CompositeMatcher class, change register_matcher
- Tests for CompositeMatcher behavior and auto-composition

---

## P0: Fixed Constraints — Post-Cascade Clamping

### Problem

World files can declare `fixed:` blocks but they're captured as raw dicts and never processed. Without this, there's no way to express hard boundaries that policy cannot override.

### Design

#### New SQL table

```sql
CREATE TABLE fixed_constraints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER REFERENCES entities(id),
    property_name TEXT NOT NULL,
    property_value TEXT NOT NULL,
    selector TEXT NOT NULL
);
```

#### Processing — two phases

**Phase A (during entity population):** After entities are inserted into the database but before cascade resolution, process `fixed_raw`:

1. For each selector string in `fixed_raw`, compile to SQL WHERE clause (reuse `compile_selector()` from the SQL compiler)
2. Query matching entity IDs
3. For each property in the constraint dict, INSERT into `fixed_constraints`

**Phase B (after cascade resolution):** The `effective_properties` view reads from both `resolved_properties` (cascade output) and `fixed_constraints`, with fixed values winning via COALESCE. This view is created as part of the schema, not as a processing step — it's always available once the tables exist.

#### Effective properties view

```sql
CREATE VIEW effective_properties AS
SELECT 
    rp.entity_id,
    rp.property_name,
    COALESCE(fc.property_value, rp.resolved_value) AS effective_value,
    CASE WHEN fc.id IS NOT NULL THEN 'fixed' ELSE 'cascade' END AS source
FROM resolved_properties rp
LEFT JOIN fixed_constraints fc 
    ON fc.entity_id = rp.entity_id 
    AND fc.property_name = rp.property_name;
```

#### PolicyEngine integration

- `resolve()` and `resolve_all()` read from `effective_properties` instead of `resolved_properties`
- `trace()` includes fixed constraints in output — when a fixed constraint overrides the cascade, the trace shows both the cascade winner and the fixed clamp
- `lint()` warns when a cascade-resolved value is overridden by a fixed constraint (informational, not an error — the author should know their rule is being clamped)

#### Parser changes

Remove "not yet implemented" warning for `fixed:` key in `parser.py`.

### Files changed

- `src/umwelt/compilers/sql/schema.py` — add fixed_constraints table, effective_properties view
- `src/umwelt/compilers/sql/populate.py` — process fixed_raw in populate_from_world()
- `src/umwelt/policy/queries.py` — read effective_properties
- `src/umwelt/policy/engine.py` — trace includes fixed constraints
- `src/umwelt/world/parser.py` — remove warning for fixed key
- Tests for fixed constraint processing, clamping, and trace output

---

## P1: Plugin Autodiscovery

### Problem

CLI hardcodes `from umwelt.sandbox.vocabulary import register_sandbox_vocabulary`. Third-party plugins can't register without explicit import code.

### Design

#### Entry point group

Single group: `umwelt.plugins`. Each plugin provides one callable that does all registration.

```toml
# umwelt's pyproject.toml:
[project.entry-points."umwelt.plugins"]
sandbox = "umwelt.sandbox.vocabulary:register_sandbox_vocabulary"

# blq's pyproject.toml (example):
[project.entry-points."umwelt.plugins"]
blq = "blq.umwelt_plugin:register"
```

#### Discovery function

```python
# umwelt/registry/plugins.py
def discover_plugins() -> list[str]:
    """Load all registered umwelt plugins. Returns names of loaded plugins."""
    from importlib.metadata import entry_points
    loaded = []
    for ep in entry_points(group="umwelt.plugins"):
        try:
            register_fn = ep.load()
            register_fn()
            loaded.append(ep.name)
        except Exception:
            pass  # broken plugin doesn't take down the CLI
    return loaded
```

#### CLI integration

`_load_default_vocabulary()` calls `discover_plugins()` instead of hardcoded imports. Existing `try/except ImportError` fallback stays for environments without working entry points.

#### Idempotent registration

`register_taxon()` changes: if called with a name that's already registered with matching description, silently return. Raise only on conflicting re-registration (same name, different description). This enables plugins to `require` dependencies without worrying about load order.

### Files changed

- New file: `src/umwelt/registry/plugins.py`
- `src/umwelt/registry/taxa.py` — idempotent register_taxon
- `src/umwelt/cli.py` — use discover_plugins()
- `pyproject.toml` — add sandbox entry point
- Tests for discovery, idempotent registration, broken plugin handling

---

## P1: Cross-Taxon Validators

### Problem

Validators receive only rules for their taxon. Invariants spanning multiple taxa (e.g., "if tool#Bash is allowed, resource#wall-time must have a limit") can't be expressed.

### Design

#### New protocol

```python
class CrossTaxonValidatorProtocol(Protocol):
    def validate(self, view: View, warnings: list) -> None: ...
```

Receives the full View — all rules across all taxa.

#### Registration

```python
def register_cross_taxon_validator(validator: CrossTaxonValidatorProtocol) -> None:
    state = _current_state()
    state.cross_validators.append(validator)
```

Storage: `cross_validators: list[CrossTaxonValidatorProtocol]` on RegistryState.

#### Dispatch

In `validate.py`, after the existing per-taxon pass:

```python
# Existing: per-taxon validators
for taxon in list_taxa():
    rules = grouped.get(taxon.name, [])
    for validator in get_validators(taxon.name):
        validator.validate(rules, warnings_list)

# New: cross-taxon validators
for validator in get_cross_taxon_validators():
    validator.validate(view, warnings_list)
```

#### No first-party validators initially

The infrastructure ships empty. The linter spec describes the cross-taxon checks; those become validators once consumers implement them.

### Files changed

- `src/umwelt/registry/validators.py` — new protocol, registration, retrieval
- `src/umwelt/registry/taxa.py` — add cross_validators to RegistryState
- `src/umwelt/validate.py` — add cross-taxon dispatch pass
- Tests for cross-taxon validator registration and dispatch

---

## P1: World File Composition — `require:`, `include:`, `exclude:`

### Problem

Every delegation needs a complete world file. Can't compose from reusable components or layer project-specific overrides.

### Design

#### Three mechanisms

- **`require: [filesystem, executables, resources]`** — Named collections. Idempotent. Order-independent.
- **`include: [./team-tools.world.yml, ./project.world.yml]`** — File paths relative to including file. Ordered (later overrides earlier).
- **`exclude: [tool#Bash, file#/etc/passwd]`** — Selector-based entity removal. Applied after all requires and includes. For v1, supports type selectors (`tool`), ID selectors (`tool#Bash`), and type+ID combinations. Attribute selectors (`file[path^="src/"]`) are deferred — emit a warning and skip.

#### Merge order

```
1. require: collections loaded (idempotent, unordered)
2. include: files loaded (ordered, later overrides earlier)  
3. own entities (override everything)
4. exclude: removals applied last
```

Keyed by `(type, id)` — same merge logic as existing shorthand/explicit merge.

#### Collection registry

```python
# umwelt/registry/collections.py
def register_collection(
    name: str, 
    loader: Callable[[], list[DeclaredEntity]],
    matcher_factory: Callable[[], MatcherProtocol] | None = None,
) -> None: ...

def require_collection(name: str) -> None: ...  # idempotent
```

Collections bundle:
- Entities (the things that exist when this collection is active)
- Optionally a matcher factory (activated when the collection is required)

Sandbox registers collections instead of bulk-loading everything:
- `filesystem` — file, dir entities + WorldMatcher
- `executables` — tool entities for Bash, subprocess + CapabilityMatcher
- `mcp-tools` — tool entities for MCP server tools
- `resources` — memory, wall-time, CPU budget entities
- `networking` — network, endpoint entities
- `inferencers` — model/inferencer entities + ActorMatcher
- `principals` — user/agent entities + PrincipalMatcher
- `modes` — mode entities + StateMatcher for modes
- `hooks` — hook entities + StateMatcher for hooks

#### Default world is empty

`register_sandbox_vocabulary()` registers taxa, entity types, and property schemas. It does NOT register matchers or populate entities. Collections do that. A world file with no `require:` has an empty entity graph.

#### Matchers follow collections

When `require("filesystem")` is called, it loads the file/dir entities AND registers the WorldMatcher. No collection required = no matcher = empty results.

Multiple collections may register matchers for the same taxon (e.g., `modes` and `hooks` both register state-taxon matchers). The CompositeMatcher from the P0 design handles this — auto-composition on collision means collections don't need to coordinate.

#### Cycle detection for include

Track resolved absolute paths during recursive loading. Skip on cycle, emit warning.

#### Provenance

- Required entities: `provenance: Provenance.REQUIRED` with collection name
- Included entities: `provenance: Provenance.INCLUDED` with source path
- Excluded entities: removed entirely (not marked)

#### Fragment references deferred

`file.yml#section` syntax is not in scope. Plain file paths only. Warning on fragment syntax.

### Files changed

- New file: `src/umwelt/registry/collections.py`
- `src/umwelt/world/model.py` — add Provenance.REQUIRED, Provenance.INCLUDED
- `src/umwelt/world/parser.py` — process require/include/exclude, remove warnings
- `src/umwelt/sandbox/vocabulary.py` — register collections instead of bulk registration
- Tests for composition, merge order, cycle detection, provenance

---

## P2: Shared Event Schema

### Problem

Seven tools emit observations with no common schema. The audit taxon registers only minimal observation entities.

### Design

#### Extended audit vocabulary

Properties on the `observation` entity:

| Property | Type | Description |
|----------|------|-------------|
| `source` | str | Which tool produced it (existing) |
| `enabled` | bool | Whether active (existing) |
| `type` | str | Event category: tool_call, build_run, failure, etc. |
| `timestamp` | str | ISO 8601 |
| `session_id` | str | Claude Code session ID |
| `severity` | str | info, warning, error, critical |
| `tags` | list | Classification: repeated_pattern, permission_denial, etc. |
| `payload` | str | JSON blob with tool-specific structure |

#### Sub-types via classes

`observation.kibitzer`, `observation.blq`, `observation.ratchet` — classes distinguish the source while sharing the schema.

#### Collection registration

Audit vocabulary becomes a collection: `require("audit")`. Tools that emit observations require it.

#### Write protocol

Lives outside umwelt core (in `retritis.substrate` or similar):

```python
def emit_observation(
    source: str, type: str, payload: dict,
    severity: str = "info", tags: list[str] = (),
    session_id: str | None = None,
) -> None: ...
```

Backed by the DuckDB append-only store from the integration-layer-plan.

#### Umwelt's role

Umwelt owns the vocabulary (what observations look like). The substrate owns storage. The ratchet owns consumption. Clear separation.

### Files changed

- `src/umwelt/sandbox/vocabulary.py` — extend audit entity properties
- Substrate package (outside umwelt) — write protocol and DuckDB storage
- Tests for extended vocabulary registration

---

## P3: Compiler Options — Bless `**kwargs`

### Problem

`compile(view: ResolvedView)` has no options channel. Compilers hack `**kwargs`.

### Design

#### Protocol change

```python
class Compiler(Protocol):
    target_name: str
    target_format: str
    altitude: Altitude
    
    def compile(self, view: ResolvedView, **options: Any) -> str | list[str] | dict[str, Any]: ...
```

#### Backward compatible

Existing compilers already accept `**kwargs`. This change documents the convention.

#### Caller changes

CLI, check_util, and audit pass relevant context through:

```python
compiler.compile(resolved_view, workspace_root="/workspace", mode="implement")
```

#### Documentation

Compiler protocol docstring explains: compilers accept `**kwargs`, document which options they use, silently ignore unknown options.

### Files changed

- `src/umwelt/compilers/protocol.py` — update protocol signature and docstring
- Minimal caller updates to pass options through

---

## P3: Altitude Filtering — Core Enforcement

### Problem

Altitude is declared on compilers but never used for filtering. A property meant for the conversational layer could silently end up as a no-op in an OS compiler config with no feedback to the author.

### Design

#### Altitude on PropertySchema

```python
@dataclass(frozen=True)
class PropertySchema:
    # ... existing fields ...
    altitude: Altitude | None = None
```

When a property is registered with an altitude, it participates in enforcement.

#### Altitude ordering

```
os < language < semantic < conversational
```

A compiler at `language` altitude receives OS and language properties. A compiler at `conversational` receives everything. Lower altitudes are always realizable at higher ones.

#### Pre-filtering in compilation pipeline

Before calling `compile()`, the pipeline filters the `ResolvedView`:

```python
def _filter_by_altitude(view: ResolvedView, max_altitude: Altitude) -> ResolvedView:
    """Return a ResolvedView containing only properties at or below max_altitude."""
    filtered = ResolvedView()
    rank = _ALTITUDE_RANK[max_altitude]
    for taxon in view.taxa():
        for entity, props in view.entries(taxon):
            kept = {k: v for k, v in props.items() 
                    if _property_altitude_rank(taxon, entity, k) <= rank}
            if kept:
                filtered.add(taxon, entity, kept)
    return filtered
```

Compilers receive pre-filtered views. No more self-filtering contract.

#### Unrealizable rule warnings

The linter warns when a rule sets a property at an altitude no registered compiler can handle:

> "Rule sets `coaching-message` (conversational) but no conversational compiler is registered."

#### Default altitude

Properties registered without an explicit altitude default to the lowest altitude of their taxon. For the sandbox vocabulary: world-taxon properties default to `os`, capability-taxon properties default to `semantic`, state-taxon properties default to `semantic`, audit-taxon properties default to `conversational`.

### Files changed

- `src/umwelt/registry/properties.py` — add altitude to PropertySchema
- `src/umwelt/compilers/protocol.py` — add _filter_by_altitude, altitude ranking
- `src/umwelt/sandbox/vocabulary.py` — declare altitude on property registrations
- `src/umwelt/policy/lint.py` — unrealizable rule warning
- Tests for altitude filtering, ordering, default inference, linter warning

---

## Implementation Roadmap

| Priority | Gap | Estimated effort | Key risk |
|----------|-----|-----------------|----------|
| P0 | CompositeMatcher | ~80 lines | Delegation semantics for get_id/get_attribute need care |
| P0 | Fixed constraints | ~200 lines | Selector-to-SQL reuse may need refactoring |
| P1 | Plugin autodiscovery | ~60 lines | Idempotent registration edge cases |
| P1 | Cross-taxon validators | ~50 lines | Low risk — purely additive |
| P1 | World composition | ~400 lines | Collection registry + include recursion + merge logic |
| P2 | Shared event schema | ~80 lines (umwelt side) | Substrate is separate package |
| P3 | Compiler options | ~20 lines | Backward-compatible by construction |
| P3 | Altitude filtering | ~150 lines | Default altitude inference, taxon-level defaults |

Total: ~1,040 lines of new code across 7 features.
