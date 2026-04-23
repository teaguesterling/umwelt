# How umwelt Works

This is the architectural picture for people who want to build on umwelt — write plugins, add enforcement targets, integrate their own tools. If you just want to write views, start with [Writing Views](writing-views.md).

## The one-sentence version

umwelt is a CSS engine where the DOM is your agent's world and the stylesheet is the policy.

## The entity model: the DOM

In CSS, selectors match elements in the DOM — a tree of typed nodes (`html → body → div → p`). In umwelt, selectors match **entities** in a world model — a tree of typed nodes describing what the agent can interact with.

The sandbox consumer (which ships with umwelt) defines this tree:

```
world#env-name                    ← the root: a named environment
  mount[path="/workspace/src"]    ← where host files appear
    dir[name="src"]
      dir[name="auth"]
        file[name="login.py"]    ← a file the agent might edit
          node.function#auth     ← a code construct inside the file (v1.1)
  resource[kind="memory"]         ← a runtime budget
  network                         ← network access
  env[name="CI"]                  ← an environment variable
```

This is not unlike the HTML DOM. `html → body → div → p → span` is a tree of presentation entities. `world → mount → dir → file → node` is a tree of workspace entities. Both are navigated with CSS selectors.

## Selectors: the query language

umwelt selectors are a subset of CSS3:

```css
file                              /* type selector */
file#README.md                    /* id selector */
file.test                         /* class selector */
file[path^="src/"]                /* attribute selector */
file:glob("src/**/*.py")          /* pseudo-class */
dir[name="src"] file              /* descendant combinator */
dir > file                        /* child combinator */
file, tool                        /* union (comma) */
file:not([path$=".md"])           /* negation */
```

Every selector the model already knows about. No new grammar to learn.

## Cascade: conflict resolution

When multiple rules match the same entity, the **cascade** decides which value wins for each property:

1. **Specificity** — a more specific selector beats a less specific one. Specificity is the standard CSS3 tuple `(ids, classes+attributes+pseudos, types)`.
2. **Document order** — equal specificity → later rule wins.
3. **Per-property** — different rules can win for different properties on the same entity. One rule might set `editable`, another might set `visible`.
4. **Per-taxon** — rules in different taxa never compete. A `file` rule and a `tool` rule are in different scopes.

This is exactly how CSS works. The only addition is per-taxon scoping, which CSS doesn't need because CSS has only one DOM.

## Taxa: namespaces for the world model

The entity tree above lives in the **world** taxon. But agents interact with more than files — they also call tools, trigger hooks, and consume budgets. Each domain is a **taxon** (a namespace of entity types):

| Taxon | What it models | Entity types |
|---|---|---|
| **world** | What the agent can see and touch | world, mount, dir, file, node, resource, network, env |
| **capability** | What the agent can do | tool, kit |
| **state** | What the harness tracks | hook, job, budget |

Each taxon has its own matcher (how to evaluate selectors against its world) and its own cascade scope (rules in different taxa never interfere).

When a selector crosses from one taxon to another, the meaning changes:

```css
/* Within-taxon: structural descent (containment) */
dir[name="src"] file[name$=".py"]

/* Cross-taxon: context qualifier (gating) */
tool[name="Bash"] file[path^="src/"]
```

In the first, `dir → file` is containment — the file is inside the directory. In the second, `tool → file` is conditioning — "when the acting tool is Bash, this file rule applies." The parser classifies each combinator automatically by looking up the entity types in the registry.

## Pivots: crossing between world models

The tree `world → mount → dir → file` is the filesystem. But a file contains source code, and source code has its own structure — functions, classes, methods. When the selector descends from `file` into `node`, it **pivots** from one world model to another:

```css
file[path="src/auth/login.py"] node.function#authenticate { show: body; }
```

The filesystem matcher finds the file; the AST matcher (sitting_duck / pluckit) finds the function inside it. Same selector grammar, different matcher on each side of the pivot.

Pivots aren't limited to code. A `table → row` pivot crosses from blq's event store into DuckDB's query engine. A `job → budget` pivot crosses from execution state into resource tracking. Each pivot is a boundary where one tool's world model hands off to another's.

## The plugin architecture

Core umwelt is vocabulary-agnostic. It provides:

- **Parser** — CSS tokenization via tinycss2, selector parsing, declaration extraction, @-rule sugar desugaring.
- **Registry** — `register_taxon`, `register_entity`, `register_property`, `register_matcher`, `register_validator`, `register_compiler`. Consumers call these at import time.
- **Selector engine** — evaluates selectors against registered matchers. Handles structural descent (within-taxon), context qualification (cross-taxon), and specificity computation.
- **Cascade resolver** — per-taxon property-level cascade with CSS3 specificity + document order.
- **Compiler protocol** — pure `compile(resolved_view) → target_format` with altitude declaration.

Core knows nothing about files, tools, or networks. All entity types come from consumers via the registry. The sandbox consumer (shipped in the same package) registers the world/capability/state taxa. Third-party consumers register their own.

### Adding a new entity type

```python
from umwelt.registry import register_entity, AttrSchema

register_entity(
    taxon="world",
    name="secret",
    parent="dir",
    attributes={
        "path": AttrSchema(type=str, required=True),
        "name": AttrSchema(type=str, required=True),
        "sensitivity": AttrSchema(type=str, description="Classification level"),
    },
    description="A secret file that requires special access policy.",
    category="security",
)
```

Now `secret[sensitivity="high"] { visible: false; }` works in any view.

### Adding a new taxon

```python
from umwelt.registry import register_taxon, register_entity, register_matcher

register_taxon(name="data", description="Query results and data tables.")
register_entity(taxon="data", name="table", attributes={...}, description="A data table.")
register_entity(taxon="data", name="row", parent="table", attributes={...}, description="A row.")
register_matcher(taxon="data", matcher=DuckDBMatcher(connection))
```

Now `table#events row[severity="error"] { flag: blocking; }` works, with a DuckDB-backed matcher evaluating the selectors against real query results.

### Adding a compiler

```python
from umwelt.compilers import register, Compiler

class NsjailCompiler:
    target_name = "nsjail"
    target_format = "textproto"
    altitude = "os"

    def compile(self, view):
        # Walk the resolved view's world-taxon entries and emit
        # nsjail protobuf textproto for mounts, rlimits, etc.
        ...

register("nsjail", NsjailCompiler())
```

Now `umwelt compile --target nsjail view.umw` works.

## The linker role

umwelt connects every tool in the ecosystem through a shared grammar:

```
                          umwelt
                     (CSS selectors + cascade)
                            |
         ┌──────────┬───────┼───────┬──────────┐
         |          |       |       |          |
      world      source    data    cap      state
      (fs)       (AST)    (tables) (tools)  (hooks)
         |          |       |       |          |
     nsjail    sitting   DuckDB  lackpy    kibitzer
     bwrap     _duck     blq     fledgling agent-riggs
               pluckit          squawkit   jetsam
```

Each column is a taxon with its own entity types and matcher. The CSS grammar spans all of them. A single view file can express policy over files, tools, code constructs, and query results — each compiled to the appropriate enforcement target.

This is why umwelt uses CSS syntax: not because views are visual, but because CSS's selector + cascade model is the best existing grammar for "broadly or finely select entities in a structured world, attach policy to the matches, and let the cascade resolve conflicts." Every code-trained LLM has seen it. Every developer knows it. The grammar transfers even when the domain doesn't.

## The ratchet: views that improve with use

A view isn't static. It's a **crystallization artifact** — the current committed understanding of what the agent needs, derived from observing what the agent actually does.

The cycle:

1. **Explore**: run the agent with a loose view. Observation tools (blq, ratchet-detect, strace) capture what happened — files read, tools called, resources consumed, failures hit.
2. **Crystallize**: `umwelt ratchet` proposes a tightened view consistent with the observations. What `@source` patterns match the files actually read? What `max-level` accommodates the tools actually used?
3. **Review**: a human reviews the proposed view and commits it.
4. **Enforce**: the committed view is compiled to enforcement configs and applied.
5. **Repeat**: new observations drive new revisions.

Each cycle moves a piece of the agent's behavior from "requires judgment" to "handled by policy." The specified base grows. The inference frontier shrinks. The system gets more trustworthy with use — not because the model improved, but because the configuration accumulated evidence.

This is the [configuration ratchet](https://judgementalmonad.com/blog/ma/the-configuration-ratchet) from the Ma framework, applied to policy specification. The ratchet utility ships in v0.3.

## World files: declaring the DOM

The entity tree above can be declared in a `.world.yml` file — a YAML document that lists what exists in the agent's world:

```yaml
# env.world.yml
tools: [Read, Edit, Bash]
modes: [implement]
principal: Teague

entities:
  - type: tool
    id: Bash
    classes: [dangerous]
    attributes:
      description: "Execute shell commands"

projections:
  - type: dir
    id: node_modules
    attributes:
      path: "node_modules/"
```

Shorthand keys (`tools:`, `modes:`, `principal:`) expand via a vocabulary-driven registry — `tools: [Read, Edit]` becomes two `DeclaredEntity(type="tool", ...)` instances. Explicit `entities:` entries override shorthands on `(type, id)` collision.

World files are parsed by `umwelt.world.load_world()` and can be materialized at three detail levels (summary, outline, full) via `umwelt materialize`.

## PolicyEngine: querying resolved policy

The **PolicyEngine** is the consumer-facing API. It compiles a world file + stylesheet into an in-memory SQLite database, resolves cascade, and answers queries:

```python
from umwelt.policy import PolicyEngine

engine = PolicyEngine.from_files(world="env.world.yml", stylesheet="policy.umw")

# What's the resolved value?
engine.resolve(type="tool", id="Bash", property="visible")  # → "false"

# Why did that value win?
trace = engine.trace(type="tool", id="Bash", property="visible")

# Are there policy smells?
warnings = engine.lint()  # narrow_win, shadowed_rule, conflicting_intent, ...

# Enforce a constraint
engine.require(type="tool", id="Bash", visible="false")  # raises PolicyDenied on mismatch
```

Consumers like Kibitzer and Lackpy use PolicyEngine instead of raw SQL — umwelt declares, consumers enforce.

## Where to go from here

- **[Vision: Policy Layer](../vision/policy-layer.md)** — the full theoretical framing: why umwelt exists, how it fits the specified-band regulation strategy, the three-layer model.
- **[Vision: Entity Model](../vision/entity-model.md)** — the structural contract: taxa, selectors, cascade, comparison properties, plugin registration.
- **[Vision: View Format](../vision/view-format.md)** — the grammar reference: BNF, all selector forms, all declaration types.
- **[The Ma of Multi-Agent Systems](https://judgementalmonad.com/blog/ma/00-intro)** — the theory underneath: four actors, the grade lattice, the specified band, the ratchet.
- **[Ratchet Fuel](https://judgementalmonad.com/blog/fuel/)** — the practitioner companion: failure-driven development, tool crystallization, the two-stage turn.
