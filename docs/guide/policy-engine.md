# PolicyEngine

The PolicyEngine is the consumer-facing Python API for querying resolved policy. It compiles a world file and a stylesheet into an in-memory SQLite database, resolves the CSS cascade, and answers questions about the result.

**umwelt declares, consumers enforce.** The PolicyEngine tells you what the policy says. Your tool — Kibitzer, Lackpy, a custom hook, an agent framework — decides what to do about it.

## Quick start

```python
from umwelt.policy import PolicyEngine

engine = PolicyEngine.from_files(
    world="delegate.world.yml",
    stylesheet="policy.umw",
)

# What's the resolved value of a property?
engine.resolve(type="tool", id="Bash", property="visible")  # → "true"

# Get all resolved properties for an entity
engine.resolve(type="tool", id="Bash")  # → {"visible": "true", "max-level": "3", ...}

# Does the policy match what we expect?
engine.check(type="tool", id="Bash", visible="true")  # → True

# Enforce it — raises PolicyDenied on mismatch
engine.require(type="tool", id="Bash", visible="true")
```

## Three constructors

PolicyEngine has three ways to create an instance, corresponding to three points in the lifecycle:

### Author time: `from_files()`

Compile from source files. Parses the world YAML, parses the stylesheet, builds the full compiled database.

```python
engine = PolicyEngine.from_files(
    world="delegate.world.yml",
    stylesheet="policy.umw",
)
```

Use this when you have the original source files and want the full compilation pipeline — parsing, vocabulary registration, cascade resolution, projection views.

### Consumer time: `from_db()`

Load a pre-compiled database. No parsing, no compilation. The database is copied into memory (copy-on-write semantics — the original file is never modified).

```python
engine = PolicyEngine.from_db("compiled.duckdb")
```

Use this in consumers that receive a compiled policy database. Kibitzer loads its policy this way — the compilation happened at authoring time, and Kibitzer just queries the result.

### Runtime: programmatic builder

Build an engine incrementally from Python data structures. Useful for testing, runtime composition, and consumers that construct policy dynamically.

```python
engine = PolicyEngine()
engine.add_entities([
    {"type": "tool", "id": "Read", "classes": ["safe"]},
    {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
    {"type": "mode", "id": "implement"},
])
engine.add_stylesheet("""
    tool { visible: true; allow: true; }
    tool.dangerous { max-level: 3; }
""")
```

Compilation is lazy — the engine compiles on first query, not on construction. You can call `add_entities()` and `add_stylesheet()` multiple times before querying.

## Query modes

### resolve — what does the policy say?

```python
# Single property
value = engine.resolve(type="tool", id="Bash", property="max-level")
# → "3" or None if no rule matches

# All properties for an entity
props = engine.resolve(type="tool", id="Bash")
# → {"visible": "true", "allow": "true", "max-level": "3"}

# All entities of a type with their properties
all_tools = engine.resolve_all(type="tool")
# → [{"entity_id": "Read", "type_name": "tool", "classes": [...], "properties": {...}}, ...]
```

All values are strings. The cascade resolves to string values; your consumer interprets them. `"true"` is the string `"true"`, not the Python boolean `True`. This is intentional — umwelt is a specification engine, not a runtime.

### trace — why does the policy say that?

```python
from umwelt.policy import TraceResult, Candidate

result: TraceResult = engine.trace(
    type="tool", id="Bash", property="max-level",
)

print(f"Winner: {result.value}")  # → "3"

for c in result.candidates:
    marker = "✓" if c.won else " "
    print(f"  [{marker}] {c.value}  spec={c.specificity}  "
          f"rule={c.rule_index}  {c.source_file}:{c.source_line}")
```

Output:

```
Winner: 3
  [✓] 3  spec=[0,1,1]  rule=2  policy.umw:3
  [ ] 5  spec=[0,0,1]  rule=1  policy.umw:1
```

Trace shows every cascade candidate that competed for a property, ordered by specificity (highest first). The winner is marked with `won=True`. This is how you debug "why did my tool get max-level 3 instead of 5?" — you can see which rule won and why.

### lint — are there policy smells?

```python
from umwelt.policy import LintWarning

warnings: list[LintWarning] = engine.lint()

for w in warnings:
    print(f"[{w.severity}] {w.smell}: {w.description}")
```

Five smell detectors:

| Smell | Severity | What it catches |
|---|---|---|
| `narrow_win` | warning | Winner beat runner-up by specificity margin of 1 — fragile |
| `shadowed_rule` | info | A rule that never wins for any entity — dead code |
| `conflicting_intent` | warning | Same specificity, opposite values — winner decided by source order alone |
| `uncovered_entity` | info | An entity with no resolved properties — nothing matches it |
| `specificity_escalation` | warning | 3+ specificity levels for one property — possible escalation war |

Lint is useful for policy authors debugging their stylesheets. Consumers can also use it to report warnings to users.

### check and require — enforce constraints

```python
# Soft check: returns True/False
if not engine.check(type="tool", id="Bash", visible="true", allow="true"):
    print("Policy violation")

# Hard check: raises PolicyDenied
try:
    engine.require(type="tool", id="Bash", visible="true")
except PolicyDenied as e:
    print(f"Denied: {e.entity} {e.property}={e.actual} (expected {e.expected})")
```

`check()` tests multiple properties at once — all must match for it to return `True`. `require()` raises `PolicyDenied` on the first mismatch.

## COW extend — fork and specialize

`extend()` produces a new engine with additional entities and/or stylesheet rules. The original engine is never modified.

```python
base = PolicyEngine.from_files(world="base.world.yml", stylesheet="base.umw")

# Fork with additional rules
strict = base.extend(stylesheet="tool.dangerous { allow: false; }")

# Fork with additional entities
expanded = base.extend(entities=[
    {"type": "tool", "id": "NewTool", "classes": ["experimental"]},
])

# Fork with both
custom = base.extend(
    entities=[{"type": "mode", "id": "review"}],
    stylesheet="mode#review tool { max-level: 2; }",
)

# The original is untouched
base.resolve(type="tool", id="Bash", property="allow")     # → "true"
strict.resolve(type="tool", id="Bash", property="allow")   # → "false"
```

This is implemented via SQLite `backup()` — the entire compiled database is copied into a new in-memory connection, then the new entities/rules are compiled on top. The cost is proportional to database size (typically <1ms for reasonable policy sizes).

Use cases:

- **Mode switching**: fork with a mode-specific stylesheet overlay
- **Per-request specialization**: add context-specific entities before querying
- **Testing**: create a base engine in a fixture, extend per test

## Persistence

### Save to file

```python
engine.save("compiled.duckdb")
```

Writes the compiled SQLite database to a file. Another consumer can load it with `from_db()`. The database contains everything: entities, cascade candidates, resolved properties, projection views, compilation metadata.

### Round-trip export

```python
engine.to_files(world="exported.world.yml", stylesheet="exported.umw")
```

Best-effort export back to source files. The world YAML is reconstructed from the entities table. The stylesheet is copied from the original source (if tracked in compilation metadata) or reconstructed as a comment block.

## Raw SQL escape hatch

The compiled database is a SQLite database with a well-defined schema. If the query API doesn't cover your use case, you can run SQL directly:

```python
rows = engine.execute(
    "SELECT entity_id, type_name FROM entities WHERE type_name = ?",
    ("tool",),
)
```

### Database schema

| Table | Purpose |
|---|---|
| `entities` | All declared entities (type, id, classes, attributes as JSON) |
| `selectors` | Compiled selector rules |
| `cascade_candidates` | Every (entity, property, value) candidate before resolution |
| `property_types` | Registered property schemas (type, comparison semantics) |
| `resolved_properties` | **The resolution result** — winning value per (entity, property) |
| `compilation_meta` | Provenance: source files, timestamps, counts |

### Projection views

The compiled database also contains vocabulary-driven SQL views:

| View | What it provides |
|---|---|
| `resolved_entities` | All entities with their resolved properties as a JSON object |
| `tools` | Pivot view: one row per tool, one column per tool property |
| `modes` | Pivot view for modes |
| (per entity type) | One pivot view per registered entity type with properties |

These views are generated from the vocabulary registry — whatever entity types and properties are registered get their own pivot view. A consumer can query `SELECT * FROM tools WHERE visible = 'true'` directly.

## Observability

PolicyEngine logs to `umwelt.policy` via Python's standard `logging`:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

| Level | What's logged |
|---|---|
| `INFO` | `compile` (source files, entity count), `resolve` (entity, property, value), `resolve_all`, `extend` |
| `WARNING` | `require_denied` (entity, property, expected vs actual), lint warnings |
| `DEBUG` | `trace` (entity, property, candidate count), vocabulary/projection skip reasons |

All log entries include structured `extra` fields for machine consumption.

## Error handling

```python
from umwelt.errors import PolicyDenied, PolicyError, UmweltError

# PolicyDenied — raised by require()
# PolicyError — base class for all policy errors
# UmweltError — base class for all umwelt errors
```

`PolicyDenied` has structured fields:

```python
try:
    engine.require(type="tool", id="Bash", visible="false")
except PolicyDenied as e:
    e.entity    # "tool#Bash"
    e.property  # "visible"
    e.expected  # "false"
    e.actual    # "true"
```

## Worked example: a Kibitzer-style consumer

Kibitzer is a semantic-altitude tool that observes and coaches an AI agent during a session. It needs to know which tools are visible, what their max computation level is, and whether specific modes are active. Here's how it integrates:

```python
from umwelt.policy import PolicyEngine, PolicyDenied

class KibitzerSession:
    def __init__(self, policy_db: str):
        self.engine = PolicyEngine.from_db(policy_db)

    def is_tool_allowed(self, tool_name: str) -> bool:
        return self.engine.check(type="tool", id=tool_name, allow="true")

    def get_tool_config(self, tool_name: str) -> dict:
        props = self.engine.resolve(type="tool", id=tool_name)
        if props is None:
            return {"visible": False, "allowed": False}
        return {
            "visible": props.get("visible") == "true",
            "allowed": props.get("allow") == "true",
            "max_level": int(props.get("max-level", "8")),
            "patterns": props.get("allow-pattern", "").split(","),
        }

    def get_visible_tools(self) -> list[str]:
        all_tools = self.engine.resolve_all(type="tool")
        return [
            t["entity_id"]
            for t in all_tools
            if t["properties"].get("visible") == "true"
        ]

    def enforce_tool_call(self, tool_name: str):
        """Raise if tool is not allowed by policy."""
        self.engine.require(type="tool", id=tool_name, allow="true")

    def switch_mode(self, mode_name: str) -> "KibitzerSession":
        """Fork the engine with a mode-specific overlay."""
        child_engine = self.engine.extend(
            entities=[{"type": "mode", "id": mode_name}],
        )
        session = KibitzerSession.__new__(KibitzerSession)
        session.engine = child_engine
        return session
```

The key pattern: Kibitzer never interprets CSS selectors or cascade rules. It asks the PolicyEngine "what does the resolved policy say about tool X?" and acts on the answer. umwelt handles the compilation; Kibitzer handles the enforcement.

## Worked example: a Lackpy-style namespace builder

Lackpy restricts which tools an AI agent can call at the language level. It builds a Python namespace from resolved policy:

```python
from umwelt.policy import PolicyEngine

def build_tool_namespace(engine: PolicyEngine) -> dict:
    """Build a tool restriction namespace from resolved policy."""
    all_tools = engine.resolve_all(type="tool")
    namespace = {}

    for tool in all_tools:
        name = tool["entity_id"]
        props = tool["properties"]

        if props.get("allow") != "true":
            continue

        entry = {"name": name}

        if "max-level" in props:
            entry["max_level"] = int(props["max-level"])

        if "allow-pattern" in props:
            entry["patterns"] = [
                p.strip() for p in props["allow-pattern"].split(",")
            ]

        namespace[name] = entry

    return namespace

# Usage
engine = PolicyEngine.from_db("compiled.duckdb")
ns = build_tool_namespace(engine)
# → {"Read": {"name": "Read"}, "Bash": {"name": "Bash", "max_level": 3, "patterns": ["git *"]}}
```

## Worked example: policy-aware test fixture

Use PolicyEngine in tests to verify that your policy produces the expected results:

```python
import pytest
from umwelt.policy import PolicyEngine

@pytest.fixture
def engine():
    e = PolicyEngine()
    e.add_entities([
        {"type": "tool", "id": "Read", "classes": ["safe"]},
        {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
    ])
    e.add_stylesheet("""
        tool { visible: true; allow: true; }
        tool.dangerous { max-level: 3; }
        tool.safe { max-level: 8; }
    """)
    return e

def test_dangerous_tools_are_capped(engine):
    assert engine.resolve(type="tool", id="Bash", property="max-level") == "3"

def test_safe_tools_are_uncapped(engine):
    assert engine.resolve(type="tool", id="Read", property="max-level") == "8"

def test_all_tools_visible(engine):
    for tool in engine.resolve_all(type="tool"):
        assert tool["properties"].get("visible") == "true"

def test_policy_has_no_smells(engine):
    warnings = engine.lint()
    errors = [w for w in warnings if w.severity == "warning"]
    assert errors == [], f"Policy smells: {[w.description for w in errors]}"
```

## Next steps

- [World Files](world-files.md) — declare the entities your policy matches against
- [Writing Views](writing-views.md) — write the stylesheets
- [Plugins](plugins.md) — extend the vocabulary with custom entity types and properties
- [How It Works](how-it-works.md) — understand the architecture
