# Plugins

umwelt's core is vocabulary-agnostic. It provides the parser, selector engine, cascade resolver, and compiler protocol — but knows nothing about files, tools, modes, or networks. All of that comes from plugins.

This guide explains the philosophy, shows how the first-party sandbox plugin works, and walks through building your own.

## Philosophy

### The common language problem

Every enforcement tool in a multi-agent system invents its own configuration format. nsjail has protobuf textproto, bwrap has argv flags, lackpy has Python namespace dicts, kibitzer has hook rules. They all describe variants of the same thing — what the actor can see, edit, call, and consume — but none of them can read each other's descriptions, and none of them compose.

umwelt is the lingua franca those tools translate from. A single view file describes the policy; compilers translate it into whatever native format each tool expects. The policy is written once; each tool reads the subset it cares about.

### Two plugin roles

Plugins interact with umwelt in exactly two ways:

**Generators** populate the world — they declare what entities exist. A filesystem scanner adds `file` and `dir` entities. A tool registry adds `tool` entities. A runtime monitor adds `resource` and `budget` entities. Generators run before compilation; their output is the DOM that stylesheets match against.

**Interactors** consume resolved policy — they query what the cascade decided and act on it. Kibitzer queries tool visibility. Lackpy queries the tool namespace. A workspace builder queries file editability. Interactors run after compilation; their input is the PolicyEngine.

Most real plugins are interactors. Generators are less common because world files handle most entity declaration.

### umwelt declares, consumers enforce

This is the load-bearing design principle. umwelt resolves policy ("tool#Bash has max-level: 3"). Consumers enforce it ("I will reject Bash invocations above level 3"). umwelt never interprets what a value *means* — it resolves what the cascade says the value *is*.

This separation is why the PolicyEngine returns strings, not typed values. `"true"` is a string. Your consumer decides whether to treat it as a boolean, a feature flag, or a sentinel value. umwelt is a specification engine; the semantics live in consumers.

### Vocabulary is the extension surface

The plugin registration API has six hooks:

| Registration | What it adds | Who uses it |
|---|---|---|
| `register_taxon()` | A namespace for entity types | Anyone adding a new domain |
| `register_entity()` | An entity type within a taxon | Anyone adding matchable entities |
| `register_property()` | A property on an entity type | Anyone adding policy-controllable attributes |
| `register_shorthand()` | A world file shorthand key | Anyone simplifying YAML authoring |
| `register_matcher()` | A matcher for a taxon | Anyone evaluating selectors at runtime |
| `register_validator()` | A validator for a taxon | Anyone adding structural validation |

The first four are the most common. Matchers and validators are advanced — most interactors don't need them because they query the compiled database, not the live DOM.

## The sandbox plugin: a worked example

The first-party sandbox plugin (`umwelt.sandbox`) registers the entire sandbox vocabulary. It's the best example of how a real plugin works.

### Taxa registration

```python
from umwelt.registry import register_taxon

register_taxon(
    name="world",
    description="Entities the actor can couple to: filesystem, network, environment.",
    ma_concept="world_coupling_axis",
)

register_taxon(
    name="capability",
    description="What the actor can do: tools, kits, effects.",
    ma_concept="decision_surface_axis",
)

register_taxon(
    name="state",
    description="What the Harness tracks: hooks, jobs, budgets, modes.",
    ma_concept="observation_layer",
)
```

A **taxon** is a namespace. Selectors within a taxon compete in the same cascade; selectors across taxa never interfere. The sandbox registers three: `world` (what exists), `capability` (what the actor can do), and `state` (what the system tracks).

### Entity registration

```python
from umwelt.registry import register_entity, AttrSchema

register_entity(
    taxon="capability",
    name="tool",
    attributes={
        "name": AttrSchema(type=str, required=True, description="Tool name"),
        "kit": AttrSchema(type=str, description="Kit this tool belongs to"),
        "level": AttrSchema(type=int, description="Computation level 0-8"),
    },
    description="A tool the actor can call.",
    category="tools",
)
```

An **entity type** is a CSS element type. Once `tool` is registered, selectors like `tool#Bash`, `tool.dangerous`, and `tool[kit="filesystem"]` become valid. The `attributes` schema defines what attribute selectors can match against.

### Property registration

```python
from umwelt.registry import register_property

register_property(
    taxon="capability",
    entity="tool",
    name="visible",
    value_type=bool,
    description="Whether the tool is displayed to the delegate.",
)

register_property(
    taxon="capability",
    entity="tool",
    name="max-level",
    value_type=int,
    comparison="<=",
    value_attribute="level",
    value_range=(0, 8),
    description="Maximum computation level permitted.",
    category="effects_ceiling",
)
```

A **property** is what declarations set. `tool { visible: true; }` sets the `visible` property. Properties have comparison semantics:

| Comparison | Resolution rule | Use case |
|---|---|---|
| `exact` (default) | Highest specificity wins | Boolean flags, string values |
| `<=` | Tightest bound (MIN) wins | Numeric caps (max-level, limits) |
| `pattern-in` | Set union of all matching values | Allow/deny pattern lists |

### Shorthand registration

```python
from umwelt.world.shorthands import register_shorthand

register_shorthand(key="tools", entity_type="tool", form="list")
register_shorthand(key="modes", entity_type="mode", form="list")
register_shorthand(key="principal", entity_type="principal", form="scalar")
register_shorthand(key="resources", entity_type="resource", form="map", attribute_key="limit")
```

Shorthands let world file authors write `tools: [Read, Edit]` instead of explicit entity blocks. Three forms:

| Form | YAML syntax | Expansion |
|---|---|---|
| `list` | `tools: [Read, Edit]` | One entity per list item, item becomes the `id` |
| `scalar` | `principal: Teague` | One entity, value becomes the `id` |
| `map` | `resources: {memory: 512MB}` | One entity per key, key is `id`, value goes to `attribute_key` |

### Wiring it together

The sandbox plugin's entry point calls all registrations:

```python
def register_sandbox_vocabulary():
    _register_world()        # world, file, dir, resource, network, env, mount
    _register_capability()   # tool, kit
    _register_state()        # hook, job, budget, mode
    _register_actor()        # inferencer, executor
    _register_principal()    # principal (identity axis)
    _register_audit()        # observation, manifest (observer axis)
    _register_validators()   # structural validation
    _register_sugar()        # @-rule desugaring
    _register_world_shorthands()  # world file shorthands
```

PolicyEngine calls `register_sandbox_vocabulary()` automatically when you use `from_files()` or the programmatic builder. Consumers using `from_db()` skip this — the vocabulary is already baked into the compiled database.

## Building your own plugin

### Example: a rate-limiting policy domain

Suppose you're building a system that rate-limits API calls per endpoint. You want to express this as policy:

```css
endpoint#/api/users { rate-limit: 100; burst: 20; }
endpoint#/api/admin { rate-limit: 10; burst: 5; }
endpoint.public { rate-limit: 1000; }
```

#### Step 1: Register the vocabulary

```python
# my_plugin/vocabulary.py
from umwelt.registry import register_taxon, register_entity, register_property, AttrSchema
from umwelt.world.shorthands import register_shorthand

def register_rate_limit_vocabulary():
    register_taxon(
        name="api",
        description="API endpoints and their rate-limiting policy.",
    )

    register_entity(
        taxon="api",
        name="endpoint",
        attributes={
            "path": AttrSchema(type=str, required=True, description="URL path pattern"),
            "method": AttrSchema(type=str, description="HTTP method (GET, POST, etc.)"),
        },
        description="An API endpoint.",
    )

    register_property(
        taxon="api", entity="endpoint",
        name="rate-limit",
        value_type=int,
        comparison="<=",
        description="Requests per minute.",
    )

    register_property(
        taxon="api", entity="endpoint",
        name="burst",
        value_type=int,
        comparison="<=",
        description="Burst capacity above the rate limit.",
    )

    register_property(
        taxon="api", entity="endpoint",
        name="auth-required",
        value_type=bool,
        description="Whether authentication is required.",
    )

    register_shorthand(key="endpoints", entity_type="endpoint", form="list")
```

#### Step 2: Write a world file

```yaml
# api.world.yml
endpoints: [/api/users, /api/admin, /api/health]

entities:
  - type: endpoint
    id: /api/admin
    classes: [admin, restricted]
  - type: endpoint
    id: /api/health
    classes: [public]
```

#### Step 3: Write a stylesheet

```css
/* api-policy.umw */
endpoint { rate-limit: 100; burst: 20; auth-required: true; }
endpoint.public { rate-limit: 1000; auth-required: false; }
endpoint.restricted { rate-limit: 10; burst: 5; }
```

#### Step 4: Query from your consumer

```python
from umwelt.policy import PolicyEngine

engine = PolicyEngine()
engine.register_vocabulary(register_rate_limit_vocabulary)
engine.add_entities([
    {"type": "endpoint", "id": "/api/users"},
    {"type": "endpoint", "id": "/api/admin", "classes": ["admin", "restricted"]},
    {"type": "endpoint", "id": "/api/health", "classes": ["public"]},
])
engine.add_stylesheet("""
    endpoint { rate-limit: 100; burst: 20; auth-required: true; }
    endpoint.public { rate-limit: 1000; auth-required: false; }
    endpoint.restricted { rate-limit: 10; burst: 5; }
""")

# Now use it in your rate limiter
def get_rate_config(engine, path):
    props = engine.resolve(type="endpoint", id=path)
    return {
        "rate_limit": int(props.get("rate-limit", "100")),
        "burst": int(props.get("burst", "20")),
        "auth_required": props.get("auth-required") == "true",
    }

config = get_rate_config(engine, "/api/admin")
# → {"rate_limit": 10, "burst": 5, "auth_required": True}
```

#### Step 5: Use the compiled database

For production, compile once and distribute:

```python
# At build time
engine.save("api-policy.db")

# At runtime (fast — no parsing)
engine = PolicyEngine.from_db("api-policy.db")
config = get_rate_config(engine, "/api/admin")
```

### Example: extending the sandbox vocabulary

You don't need a new taxon for every extension. If your entities fit an existing taxon, add them there:

```python
from umwelt.registry import register_entity, register_property, AttrSchema

register_entity(
    taxon="world",
    name="secret",
    parent="dir",
    attributes={
        "path": AttrSchema(type=str, required=True),
        "sensitivity": AttrSchema(type=str, description="Classification: low, medium, high, critical"),
    },
    description="A secret file requiring special access policy.",
)

register_property(
    taxon="world", entity="secret",
    name="visible",
    value_type=bool,
    description="Whether the agent can see this secret.",
)

register_property(
    taxon="world", entity="secret",
    name="audit",
    value_type=bool,
    description="Whether access to this secret is audited.",
)
```

Now `secret[sensitivity="critical"] { visible: false; audit: true; }` works in any view.

## The matcher protocol

Most consumers query the compiled database through the PolicyEngine and never need a matcher. But if your plugin needs to evaluate selectors against a live world (not a pre-compiled snapshot), you implement the `MatcherProtocol`:

```python
from umwelt.registry.matchers import MatcherProtocol, register_matcher

class FilesystemMatcher:
    """Evaluate selectors against actual filesystem state."""

    def __init__(self, root: str):
        self.root = root

    def match_type(self, type_name: str, context=None) -> list:
        """Return all entities of this type in your world."""
        if type_name == "dir":
            return [p for p in Path(self.root).iterdir() if p.is_dir()]
        if type_name == "file":
            return [p for p in Path(self.root).rglob("*") if p.is_file()]
        return []

    def children(self, parent, child_type: str) -> list:
        """Return child entities of `parent` matching `child_type`."""
        if child_type == "file":
            return [p for p in parent.iterdir() if p.is_file()]
        if child_type == "dir":
            return [p for p in parent.iterdir() if p.is_dir()]
        return []

    def condition_met(self, selector, context=None) -> bool:
        """Evaluate a cross-taxon context qualifier."""
        return True

    def get_attribute(self, entity, name: str):
        """Return an attribute value on an entity."""
        if name == "path":
            return str(entity)
        if name == "name":
            return entity.name
        return None

    def get_id(self, entity) -> str | None:
        """Return the entity's #id for selector matching."""
        return entity.name
```

The five methods:

| Method | When it's called | What it returns |
|---|---|---|
| `match_type(type_name)` | Type selector (`file`, `dir`) | All entities of that type |
| `children(parent, child_type)` | Descendant selector (`dir file`) | Children of `parent` matching `child_type` |
| `condition_met(selector)` | Cross-taxon qualifier | Whether the context condition holds |
| `get_attribute(entity, name)` | Attribute selector (`[path$=".py"]`) | The attribute value, or None |
| `get_id(entity)` | ID selector (`#auth.py`) | The entity's identity string |

Register it for a taxon:

```python
register_matcher(taxon="world", matcher=FilesystemMatcher("/workspace"))
```

The selector engine calls your matcher methods but never interprets the entity handles — they're opaque to the core. A filesystem matcher returns `Path` objects; an in-memory test matcher returns dicts; a database-backed matcher returns row IDs. The core doesn't care.

**When you don't need a matcher:** If your entities are declared in world files and compiled via `PolicyEngine.from_files()`, the compilation pipeline handles selector matching internally. You only need a custom matcher for live evaluation against runtime state.

## Desugaring and stability

umwelt provides `@`-rule syntactic sugar that desugars into standard selectors and declarations:

```css
/* Sugar */
@tools Read, Edit, Bash { visible: true; }

/* Desugars to */
tool#Read { visible: true; }
tool#Edit { visible: true; }
tool#Bash { visible: true; }
```

This desugaring implicitly commits to specific entity type names and property names. `@tools` assumes a `tool` entity type exists; `visible` assumes the property is registered. If you're building on the sandbox vocabulary, these names are stable. If you're extending with your own vocabulary, be aware that your `@`-rules create dependencies on your entity and property names.

The desugaring happens at parse time — the compiled database never sees `@`-rules, only the expanded selectors. This means `trace()` shows the desugared form, which can be surprising if you're debugging a stylesheet that uses sugar heavily.

## Registry isolation in tests

The vocabulary registry is global by default. In tests, use `registry_scope()` to isolate:

```python
from umwelt.registry.taxa import registry_scope

def test_my_vocabulary():
    with registry_scope():
        register_rate_limit_vocabulary()
        # Registry state is isolated to this block
        # — won't interfere with other tests

    # Registry is restored to its previous state here
```

`registry_scope()` creates a fresh registry state and restores the previous state on exit. This means tests can register whatever vocabulary they need without polluting each other.

## The compilation pipeline

Understanding what happens when the PolicyEngine compiles helps you write better plugins.

```
World file (.world.yml)          Stylesheet (.umw)
         │                              │
    load_world()                    parse()
         │                              │
    WorldFile                        View (AST)
         │                              │
    populate_from_world()       compile_view()
         │                              │
    ┌────┴──────────────────────────────┴────┐
    │          SQLite database               │
    │                                        │
    │  entities table ← from world file      │
    │  selectors table ← from stylesheet     │
    │  cascade_candidates ← selector × entity│
    │  resolved_properties ← cascade winner  │
    │  projection views ← vocabulary-driven  │
    │  compilation_meta ← provenance         │
    └────────────────────────────────────────┘
                     │
              PolicyEngine
                     │
         resolve / trace / lint
```

1. **World file** is parsed into a `WorldFile` with `DeclaredEntity` instances
2. **Entities** are inserted into the `entities` table (with classes and attributes as JSON)
3. **Stylesheet** is parsed into a `View` AST
4. **Each selector** is compiled against the entities table, producing `cascade_candidates` — every (entity, property, value, specificity, rule_index) combination
5. **Resolution views** resolve the cascade: `_resolved_exact` (highest specificity), `_resolved_cap` (MIN for `<=` comparison), `_resolved_pattern` (set union for `pattern-in`)
6. **`resolved_properties`** is the UNION of the three resolution strategies — the final answer
7. **Projection views** pivot `resolved_properties` into one-row-per-entity views for convenience
8. **PolicyEngine** wraps the connection and provides the query API

Everything in the compiled database is queryable via `engine.execute()` if the high-level API doesn't cover your case.

## Multi-plugin coexistence

When multiple plugins register entities in the same taxon, the world file population path handles this naturally — each plugin's entities go through `load_world()` into the compiled database, and the PolicyEngine resolves them together. No matcher conflicts arise because compilation doesn't use matchers.

For live evaluation (runtime selector matching against state that isn't pre-compiled), the one-matcher-per-taxon constraint can be a problem. If blq and kibitzer both need to provide entities in the `state` taxon, they can't independently register matchers.

The recommended pattern is a composite matcher that delegates by entity type:

```python
class CompositeMatcher:
    """Delegate to per-type matchers within a single taxon."""

    def __init__(self):
        self._delegates: dict[str, MatcherProtocol] = {}

    def add(self, entity_type: str, matcher: MatcherProtocol):
        self._delegates[entity_type] = matcher

    def match_type(self, type_name: str, context=None) -> list:
        delegate = self._delegates.get(type_name)
        return delegate.match_type(type_name, context) if delegate else []

    def children(self, parent, child_type: str) -> list:
        delegate = self._delegates.get(child_type)
        return delegate.children(parent, child_type) if delegate else []

    def condition_met(self, selector, context=None) -> bool:
        return all(d.condition_met(selector, context) for d in self._delegates.values())

    def get_attribute(self, entity, name: str):
        for delegate in self._delegates.values():
            val = delegate.get_attribute(entity, name)
            if val is not None:
                return val
        return None

    def get_id(self, entity) -> str | None:
        for delegate in self._delegates.values():
            val = delegate.get_id(entity)
            if val is not None:
                return val
        return None
```

Register the composite once for the taxon; each plugin adds its delegate:

```python
composite = CompositeMatcher()
composite.add("hook", kibitzer_matcher)
composite.add("job", blq_matcher)
register_matcher(taxon="state", matcher=composite)
```

This preserves the 1:1 taxon→matcher mapping at the registry level while allowing multiple sources underneath. In practice, most plugins won't need this — world file population covers the common case.

## Cross-taxon policy invariants

Per-taxon validators can check structural constraints within a taxon, but some invariants span taxa — "if tool#Bash is allowed, resource#wall-time must have a limit." These are best expressed as custom lint rules rather than validators, because the linter already sees the full resolved database:

```python
def lint_bash_requires_wall_time(engine: PolicyEngine) -> list[LintWarning]:
    bash_allowed = engine.check(type="tool", id="Bash", allow="true")
    wall_time = engine.resolve(type="resource", id="wall-time", property="limit")
    if bash_allowed and wall_time is None:
        return [LintWarning(
            smell="missing_constraint",
            severity="warning",
            description="tool#Bash is allowed but resource#wall-time has no limit",
            entities=("tool#Bash", "resource#wall-time"),
            property=None,
        )]
    return []
```

Custom lint rules run after compilation and can query any entity type. This avoids adding a cross-taxon validator protocol — the PolicyEngine query API is already the cross-taxon interface.

## Plugin discovery (future)

Currently, plugins must be explicitly imported and their `register_*()` functions called. For systems where many plugins coexist, a future version will support `entry_points`-based autodiscovery:

```toml
# In a plugin's pyproject.toml
[project.entry-points."umwelt.plugins"]
blq = "blq.umwelt_plugin:register"
kibitzer = "kibitzer.umwelt_plugin:register"
```

Until then, the recommended pattern is a single orchestration function that imports and registers all plugins needed for a given deployment.

## Design principles for plugin authors

**Register at import time.** Call `register_*` functions when your module is imported, not lazily. This ensures the vocabulary is available before any parsing happens.

**Use comparison semantics.** If a property represents a cap or limit, register it with `comparison="<="`. The cascade will correctly resolve to the tightest bound. If it represents a set of patterns, use `comparison="pattern-in"` for set union.

**Keep consumers thin.** Your consumer should call `engine.resolve()` and interpret the string. Don't reimplement cascade resolution, specificity computation, or selector matching — that's what umwelt is for.

**Compile once, query many times.** Use `from_files()` or the programmatic builder during setup, then `save()` the result. Distribute the `.db` file to consumers, which load it with `from_db()` (fast — no parsing needed).

**Use extend() for specialization.** If your consumer needs to fork the policy for different contexts (per-request, per-mode, per-user), use `extend()` rather than rebuilding from scratch. The SQLite backup is fast and gives you true isolation.

**Test with the programmatic builder.** Create a `PolicyEngine()`, add entities and a stylesheet, and assert on `resolve()`. No files needed. The `registry_scope()` fixture keeps your tests isolated.

## Next steps

- [PolicyEngine](policy-engine.md) — the full API reference for consuming resolved policy
- [World Files](world-files.md) — declare the entities your policy matches
- [Writing Views](writing-views.md) — write the stylesheets that set policy
- [How It Works](how-it-works.md) — the architecture underneath
- [Entity Reference](entity-reference.md) — all registered entity types and properties
