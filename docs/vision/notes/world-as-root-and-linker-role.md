# Note: world-as-root entity, the pivot model, and umwelt as linker

*Captured during a post-v0.1.0 design discussion on 2026-04-11. Records decisions that should feed into the user-facing docs and the entity-model.md revision.*

---

## Decision: `world` is a root entity, not just a taxon name

`world` is simultaneously a taxon name AND the root entity type in that taxon. `world#auth-fix` selects a named environment. Multiple environments in one file = multiple `world#name` trees.

```css
world#dev mount[path="/workspace"] { source: "."; }
world#dev file { editable: true; }
world#dev tool[name="Bash"] { allow: true; max-level: 4; }

world#ci mount[path="/workspace"] { source: "."; readonly: true; }
world#ci file { editable: false; }
world#ci tool[name="Bash"] { max-level: 2; }
```

Rules outside any `world#X` scope are global defaults that apply to all environments.

The hierarchy: `world → mount → dir → file → node`. This is the DOM. Navigable with descendant selectors, same as HTML/CSS.

**Implementation:** `register_entity(taxon="world", name="world", ...)` makes `world` both the taxon and its root. The parser resolves `world` as an entity type in the `world` taxon. `@world { ... }` remains valid as a taxon-scoping at-rule (checked separately from entity resolution). No conflict.

**Resolving against a named environment:** `umwelt compile --target nsjail --world auth-fix project.umw` — the resolver filters to rules matching `world#auth-fix` plus unscoped global rules.

---

## Decision: mounts are structural entities with host-mapping declarations

Mounts declare the workspace topology — what parts of the host filesystem appear inside the environment:

```css
world#auth-fix mount[path="/workspace/src"]   { source: "./src"; }
world#auth-fix mount[path="/workspace/tests"] { source: "./tests"; readonly: true; }
world#auth-fix mount[path="/tmp"]             { type: "tmpfs"; size: 64MB; }
```

The mount entity carries the mapping information the compilers need: `source` (host path), `readonly`, `type`, `size`. The nsjail compiler translates each mount to a `mount { src: ... dst: ... rw: ... }` stanza. The bwrap compiler translates to `--bind` / `--ro-bind` flags.

File editability rules then apply within mounted spaces:

```css
world#auth-fix mount[path="/workspace/src"] file[path^="auth/"] { editable: true; }
```

**Mount path as id:** `mount#/workspace/src` doesn't work because `/` breaks CSS's id grammar (`[a-zA-Z0-9_.-]+`). Use `mount[path="/workspace/src"]` for path-based matching, or `mount#workspace-src` for short named mounts. The attribute-selector form is CSS-standard.

---

## Decision: @ sugar is first-class, not legacy

`@source("src/auth")` is not deprecated. It's a valid authoring surface alongside entity-selector form. The sugar is the **high-level dialect**; the entity-selector form is the **canonical form**. Both are first-class. Authors pick whichever is clearer.

The principle on @-rules: if it can be expressed as a selector + cascade, don't ADD a new @-rule for it. But the existing sugar stays because it's readable and familiar. The only @-rules the format should grow are ones for genuinely non-selector concerns: `@import` (view composition), `@version` (format versioning), maybe `@layer` (cascade-layer priority, per CSS Cascade Layers).

---

## Concept: pivots between world models

When a selector descends from one domain into another, that's a **pivot**. The entity type changes from one tool's world model to another's.

**Filesystem → AST (sitting_duck):**
```css
file[path="src/auth/login.py"] node.function#authenticate { show: body; editable: true; }
```
The `file → node` boundary is where the filesystem matcher hands off to the AST matcher. pluckit/sitting_duck evaluates the `node` selector via tree-sitter.

**Filesystem → data (DuckDB/blq):**
```css
table#test-results row[severity="error"] { flag: blocking; }
```
The `table → row` boundary is where blq's event store hands off to DuckDB's query engine.

**Context qualifiers (not pivots):**
```css
tool[name="Bash"] file[path^="src/"] { editable: false; }
```
This isn't a structural pivot — it's a context gate. The tool qualifier conditions the file rule; it doesn't contain files.

The distinction: pivots are structural (containment/descent within or between taxa); context qualifiers are conditional (gating).

---

## Concept: umwelt as the ecosystem linker

umwelt is not a sandbox tool. It's the **common selector + cascade surface** connecting every tool in the ecosystem. Each tool has its own world model; umwelt provides the grammar they all share.

| Taxon | World model | Matcher provided by | Consumers |
|---|---|---|---|
| world | filesystem, mounts, env, network, resources | umwelt.sandbox (built-in) | nsjail, bwrap, workspace builder |
| source | AST nodes (class, function, method, call...) | sitting_duck / pluckit | duck_hunt, pluckit, code-level policy |
| data | tables, rows, columns | DuckDB / blq | duck_tails, duckdb_mcp, blq |
| capability | tools, kits, effects | lackpy / fledgling / squawkit | MCP servers, tool registries |
| state | hooks, jobs, budgets, observations | kibitzer / agent-riggs | hook dispatch, audit |
| git | commits, branches, diffs | jetsam | git state management |
| actor | principal, inferencer, executor, harness | the Ma framework layer | multi-agent policy |

umwelt imports nothing from any of them. They all import umwelt's registry API. Leaf dependency.

---

## Future direction: extensible DOM schemas

Each tool that plugs into umwelt brings its own entity hierarchy — a "DOM" for its domain. Currently these are declared entity-by-entity via `register_entity(parent=..., ...)`. A future improvement: a formal DOM schema that a plugin can declare as a loadable unit.

```python
# Hypothetical schema declaration
DOMSchema(
    name="source",
    description="AST entity hierarchy for source code",
    entities=[
        EntityDef("module", children=["class", "function", "import"]),
        EntityDef("class", children=["method", "property"]),
        EntityDef("function", children=["parameter", "call"]),
        ...
    ],
    pivot_from=("world", "file"),  # this DOM attaches under file entities
)
```

This would make pivot points explicit, self-documenting, and discoverable. Think of it as Shadow DOM for policy surfaces — each plugin defines its own internal tree that snaps into the global hierarchy at a declared attachment point.

Critically, the schema should also declare **which properties apply to each entity type** and their descriptions — the same way CSS specs define which properties apply to which elements (`display` applies to all, `flex-direction` only to flex containers). This is already partially captured in `register_property(taxon=..., entity=..., name=..., description=...)` but a schema would present it as a self-documenting unit. The descriptions serve two consumers: (a) human-readable docs generated from the schema, and (b) the delegate-context compiler (v1.1) which renders the view into a prompt fragment for the Inferencer. One schema, two consumers — the DOM spec IS the transparency layer.

Deferred. The entity-by-entity registration works for v1. Schema declarations are a v2 concern.

---

## What to update in the vision docs when these decisions land

1. `entity-model.md` §3.1: add `world` as a root entity in the world taxon; add mount as child of world; update the hierarchy to `world → mount → dir → file → node`.
2. `entity-model.md` §4: add examples with `world#env-name` compound selectors.
3. `view-format.md`: add examples showing multiple environments in one file via `world#dev` / `world#ci` patterns.
4. `policy-layer.md`: update the "What umwelt is" section to reflect the linker role.
5. `package-design.md`: note that the resolve step can filter to a named world.
6. New user docs: lead with environments as the primary pattern.

---

## Pointer to the conversation context

These decisions emerged from a post-v0.1.0 design conversation about:
- How to define multiple environments in one .umw file
- Whether @-rules were being overused
- The user's observation that `world#my-env mount[path=...]` gives a natural DOM root
- The connection between umwelt's entity model and sitting_duck's AST model and blq's data model
- umwelt's role as the "linker" between all ecosystem tools
