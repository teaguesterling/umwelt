# umwelt: The Entity Model

*What views attach policy to, how selectors match, how cascade resolves, and how consumers plug in their own taxa. The structural reference that [`policy-layer.md`](./policy-layer.md) motivates and [`view-format.md`](./view-format.md) depends on.*

---

## 1. The world the view describes

A view is a stylesheet. Stylesheets are useless without a world to query. CSS's world is the DOM tree. umwelt's world is the **entity graph** — a typed, queryable model of what the Harness is regulating.

The entity graph is not a single fixed schema. Core umwelt defines no entities. Instead, **consumers register taxa**: collections of entity types with typed attributes, structural relationships, and selector-matcher implementations. A view is interpreted against whatever taxa the running environment has registered. The sandbox consumer registers its taxa. blq's command registry registers its taxa. lackpy's namespace registers its taxa. An access-control consumer would register its own. The view's grammar is the same; the taxa are the vocabulary.

This separation is what makes umwelt vocabulary-agnostic in its core. The parser, cascade resolver, compiler protocol, and ratchet utilities know nothing about files, tools, or networks. They know about selectors, rule blocks, declarations, and entity-matching protocols. The taxa are the contract between core umwelt and its consumers.

The five canonical taxa specified here are **first-party suggestions**, not hardcoded requirements:

- **`world/`** — entities the actor can couple to (the W axis of the Ma grade)
- **`capability/`** — what the actor can do (tools, kits, effects, computation levels)
- **`state/`** — what the Harness tracks (jobs, hooks, budgets, observations)
- **`actor/`** — who's in the room (the four Ma actors; minimal in v1, expanded in v1.1+)
- **`policy/`** — meta-taxon for view-about-views (deferred to v2)

Any third-party consumer can define its own taxa by following the same plugin-registration pattern and participate in the ratchet the same way first-party taxa do.

---

## 2. Why these taxa: the Ma mapping

The taxa aren't arbitrary. Each one corresponds to a load-bearing concept in the [Ma framework](https://judgementalmonad.com/blog/ma/00-intro) and maps to a specific part of the regulatory picture the policy layer implements.

| Taxon | Ma concept | What the Harness regulates |
|---|---|---|
| `world/` | **World coupling axis** (post 2) | What external state can enter the actor's computation at runtime — filesystem, network, environment, resources. The "pipe's diameter" of the sandbox tower. |
| `capability/` | **Decision surface axis + computation channels** (posts 2 & 7) | What effects the actor can produce — tool calls, effect signatures, and their computation levels. The delta-reachable per tool call. |
| `state/` | **Observation layer** (post 8, Layer 2) | What the Harness tracks across turns — jobs, budgets, hooks, observations. The substrate for Layer 2 specified observation. |
| `actor/` | **The four-actor taxonomy** (post 1) | The Principal/Inferencer/Executor/Harness themselves — their grades, interfaces, and co-domain funnels. Needed only when views describe multi-actor systems; minimal in v1. |
| `policy/` | **The ratchet** (Configuration Ratchet essay) | Views as artifacts — provenance, versioning, priority, composition. Meta-level, deferred. |

The grid is not a hierarchy. All taxa sit at the same level; a view can attach policy to entities from any taxon in the same file. The grouping exists because each taxon corresponds to a distinct regulatory concern, and separating them keeps cascade scoped (see §5). It's also how the Harness's regulatory model is shaped: `(world, capability, state, actor)` is the minimum viable model the Harness needs to describe *what* it's regulating, *who* it's regulating, *what they can do*, and *what happened*. Add one more for *how the rules themselves evolve* and you have the full reflective picture.

A consumer does not have to use all five. The sandbox vocabulary in v0.1-sandbox uses `world`, `capability`, and `state`. A blq-specific consumer might use only `world` + `capability`. A future orchestration consumer might primarily use `actor` + `state`. Taxa are load-by-need; the ones that aren't registered don't exist from the view's perspective.

---

## 3. The five taxa in detail

Each subsection lists the canonical entities a first-party consumer would register, their attributes, and example selectors. Third-party consumers can (and will) extend these with their own entities and attributes; the schemas below are the v1 baseline.

### 3.1 `world/` — what actors can couple to

The W-axis entities. Files, directories, code nodes, mounts, env vars, network endpoints, runtime resources. This is the taxon the current sandbox at-rules (`@source`, `@network`, `@budget`, `@env`) map onto.

#### Entities

| Entity | Parent | Attributes | Notes |
|---|---|---|---|
| `dir` | — | `name`, `path`, `mtime`, `size` | A directory. Root entity for filesystem traversal. |
| `file` | `dir` | `name`, `path`, `language`, `size`, `mtime` | A file. Descendant of a `dir`. |
| `node` | `file` | `kind`, `name`, `parent_name`, `span` | A code node inside a file (v1.1 via pluckit). `kind` is e.g. `function`, `class`, `method`. |
| `mount` | — | `src`, `dst`, `type`, `writable` | A bind mount in the workspace. |
| `env` | — | `name`, `value` (write-only — reading value from a view is disallowed for safety) | An environment variable. |
| `network` | — | `host`, `port`, `protocol` | A network endpoint. v1 supports `*` wildcard only; explicit hosts are v1.1+. |
| `resource` | — | `kind`, `unit`, `limit` | A runtime resource: memory, cpu, wall-time, cpu-time, tmpfs, max-fds. |

#### Structural relationships

The plugin declares `file` has parent `dir` and `node` has parent `file`. This enables the descendant combinator for filesystem-shaped selection: `dir[name="src"] file[name$=".py"]` means "files ending in .py inside directories named src". The selector matcher walks the structural hierarchy the plugin exposes.

#### Example selectors

```
file[path^="src/auth/"]                    { editable: true; }
file[path$=".py"]                          { editable: true; }
dir[name="src"] dir[name="test"] file      { editable: false; }
file:glob("src/**/*.py")                    { editable: true; }
file[path^="src/auth/"] node[kind="function"][name="authenticate"] { show: body; }

resource[kind="memory"]                    { limit: 512MB; }
resource[kind="wall-time"]                 { limit: 60s; }
network                                    { deny: "*"; }
env[name="CI"]                             { allow: true; }
env[name="PYTHONPATH"]                     { allow: true; }
```

The `file[path^="src/auth/"]` form is the canonical short form (prefix match on an attribute). The `dir ... file` descendant form is equivalent and preferred when the author wants to emphasize structural traversal. Both compile to the same set of matched files.

### 3.2 `capability/` — what actors can do

The D-axis entities: tools, kits (grouped tool sets), effects, and — critically — computation levels. This taxon is where the Ma framework's nine-level computation channel taxonomy becomes first-class metadata.

#### Entities

| Entity | Parent | Attributes | Notes |
|---|---|---|---|
| `tool` | — | `name`, `kit`, `altitude`, `level`, `effect` | A tool the actor can call. `level` is the computation level 0–8 (see §3.2.1). `altitude` is `os`, `language`, `semantic`, or `conversational`. |
| `kit` | — | `name`, `version` | A group of tools capability-published together (e.g., `python-dev`, `postgres-admin`). |
| `effect` | `tool` | `kind` | An effect signature declared by the tool: `read`, `write`, `exec`, `spawn`, `mutate`, `network`. v1.1+. |

#### 3.2.1 Computation levels as declared attributes

The computation level on a `tool` entity comes from the tool itself — the tool declares its level as part of its manifest, following capability publishing (post 8 of the Ma series). umwelt does not infer levels; the consumer registering the `capability` taxon provides the level declarations via whatever means the consumer uses to enumerate tools (lackpy kits, MCP tool definitions, blq command registry, etc.).

The nine-level taxonomy from [Computation Channels](https://judgementalmonad.com/blog/ma/07-computation-channels):

| Level | Name | Description |
|---|---|---|
| 0 | sealed | Pure computation, no IO |
| 1 | structured-query | SQL, GraphQL, schema-bounded queries |
| 2 | read-compute | Read access + arbitrary computation |
| 3 | mutation | Sandboxed writes |
| 4 | amplification | Agent-generated executable specification (`bash`, `python -c`) |
| 5 | env-modification | Package install, environment state change |
| 6 | capability-creation | New tools generated from within |
| 7 | subprocess-spawn | Persistent background processes (fold escape) |
| 8 | controller-modification | Modifying `CLAUDE.md`, settings files, the Harness itself |

The levels are a discussion-and-policy convention, not a hard technical invariant. Tool authors choose their level honestly; umwelt's role is to let policy select against the chosen level.

#### Example selectors

```
tool[name="Read"]        { allow: true; }
tool[name="Bash"]        { allow: false; }
kit[name="python-dev"]   { allow: true; }
tool[altitude="os"]      { require: sandbox; }
```

Selecting by level is handled through declarations with comparison semantics rather than selector operators — see §4.3.

### 3.3 `state/` — what the Harness tracks

Runtime state entities: jobs, hooks, budgets, observations. This is where `@after-change` lives, and where view rules interact with the specified observation layer.

#### Entities

| Entity | Parent | Attributes | Notes |
|---|---|---|---|
| `job` | — | `id`, `state`, `parent`, `delegate` | An execution run. `delegate=true` if a sub-delegate was spawned. |
| `hook` | — | `event`, `phase` | A lifecycle hook. `event` is `before-call`, `after-change`, `on-failure`, `on-timeout`, etc. `phase` is reserved for sub-categorization. |
| `budget` | — | `kind`, `used`, `limit` | A runtime budget. `kind` is `memory`, `cpu-time`, `wall-time`, `tokens`, `cost`. |
| `manifest` | — | `workspace_root` | The workspace manifest (sandbox-runtime concern). |
| `observation` | — | `kind`, `target` | Something a Layer-2 observer reported. v1.1+. |

#### Example selectors

```
hook[event="after-change"] {
  run: "pytest tests/auth/ -x";
  run: "ruff check src/auth/";
  timeout: 60s;
}

job[delegate="true"] {
  inherit-budget: 0.5;
}

budget[kind="wall-time"] {
  limit: 5m;
}
```

Note how `hook[event="after-change"]` takes multiple `run:` declarations. This is how the current `@after-change { test: pytest; lint: ruff; }` form desugars — the at-rule becomes a selector, and each labelled command becomes a repeat of the `run:` property. Labels (`test:`, `lint:`, `fmt:`) in v1.1 may be modeled as entity-level sub-properties.

### 3.4 `actor/` — minimal in v1

The four Ma actors as entities. Full first-class treatment is deferred because it introduces design pressure around multi-actor view composition that v1 isn't ready to commit to. The slot exists so the entity model has room to grow without restructuring.

#### v1 entities (minimal)

| Entity | Attributes | Notes |
|---|---|---|
| `inferencer` | `model`, `kit`, `temperature` | The Inferencer's configuration. v1 supports only declarative model/kit selection. |
| `executor` | `tool_name`, `altitude` | The Executor's own grade. v1.1+. |

Selectors like `inferencer { model: "claude-sonnet-4-6"; temperature: 0; }` work in v1 but are not load-bearing for any v0.1 or v0.2 functionality. Full actor-taxon design lands when we have a concrete consumer that needs multi-actor policy (planner/worker/reviewer pipelines, agent-riggs audit views).

### 3.5 `policy/` — deferred

Meta-taxon for views-about-views: priority, inheritance, composition, provenance. Deferred to v2 alongside the view bank. Listed here so the cascade can eventually reason about rule priority from `policy` entities, and so the ratchet can emit `policy` entities representing its own revisions.

---

## 4. The selector grammar

The grammar is CSS, with small extensions that keep it specified and decidable. A view's selector syntax is a *subset* of CSS3 selectors plus a few umwelt-specific additions; the subset is what the parser accepts and the engine evaluates.

### 4.1 Base grammar: CSS selectors

Everything CSS-selector-level that every code-trained LLM has seen:

```
type                    file
type#id                 file#config.py          (id = identity by `name` attribute when present)
type.class              tool.sandbox-required
type[attr]              file[path]
type[attr="val"]        file[path="README.md"]
type[attr^="val"]       file[path^="src/"]       (prefix)
type[attr$="val"]       file[path$=".py"]        (suffix)
type[attr*="val"]       file[path*="/auth/"]     (substring)
type[attr|="val"]       file[lang|="en"]         (dash-separated prefix, rare)
type[attr~="val"]       file[tags~="test"]       (whitespace-separated word match)

selector selector       dir[name="src"] file     (descendant)
selector > selector     dir > file               (direct child)
selector, selector      file[path^="src/"], file[path^="tests/"]   (union — multiple selectors share declarations)

:not(selector)          file:not([path$=".md"])
:has(selector)          dir:has(file[name="pyproject.toml"])       (containment; v1.1+)
```

The wildcard `*` is an implicit type — `*.editable` means "any entity that matches the `.editable` class."

The grammar deliberately omits CSS's layout-specific pseudo-classes (`:hover`, `:focus`, `:nth-child`, etc.) because they don't map to policy semantics. What remains is the structural subset: identify by type, attribute, ancestry, negation, containment.

### 4.2 Path patterns and globs

Filesystem paths are common enough to warrant a first-class selector shortcut. The baseline is CSS attribute selectors on the `path` attribute:

```
file[path="src/main.py"]              exact match
file[path^="src/"]                    prefix match
file[path$=".py"]                     suffix match
file[path*="/auth/"]                  substring match
```

These cover most cases. For glob patterns that aren't expressible as prefix/suffix/substring, there's a pseudo-class:

```
file:glob("src/**/*.py")              shell glob
file:glob("tests/**/test_*.py")
dir:glob("src/*/internal")
```

The glob semantics are shell-style `fnmatch` with `**` meaning "any path segments" — the same semantics Python's `pathlib.Path.glob` uses. The pseudo-class form is used because attribute-selector syntax doesn't have a natural place for glob metacharacters and CSS-extension operators like `%=` would drift from the standard. Pseudo-classes are CSS's established extension point.

For structural path construction, the descendant combinator works when the filesystem plugin exposes parent/child relationships:

```
dir[name="src"] dir[name="auth"] file[name$=".py"] { editable: true; }
```

This is identical in match semantics to `file[path^="src/auth/"][path$=".py"]`, but makes the structural walk explicit. Authors can choose either form; the engine resolves both to the same set.

### 4.3 Declarations with comparison semantics

This is where umwelt differs from CSS in an important way.

In CSS, a declaration `color: red` sets a property value on the matched elements. In umwelt, some declarations have built-in *comparison semantics* — the property name encodes how the value is interpreted as a policy constraint.

Example from the `capability` taxon:

```
tool { max-level: 2; }
```

This does not mean "set the tool's level to 2." It means: **for any matched tool, the policy cap on its permitted computation level is 2**. Tools with declared level ≤ 2 pass the policy check; tools with level > 2 do not. The `max-` prefix is a *property-level comparison operator*, encoded in the property name, not in the selector.

The pattern generalizes:

| Property prefix | Comparison | Example |
|---|---|---|
| (none) | exact / assignment | `editable: true` |
| `max-` | value ≤ declared | `max-level: 2`, `max-memory: 512MB` |
| `min-` | value ≥ declared | `min-budget: 256MB` |
| `only-` | value ∈ declared set | `only-kits: python-dev, rust-dev` |
| `any-of-` | value overlaps declared set | `any-of-effects: read, write` |

The taxon's plugin registration declares which properties have comparison semantics and how they interpret their values. A declaration is fully qualified by `(property name, property semantics)`, not just a key-value pair.

This is cleaner than introducing new selector operators like `[level<=2]` because:

1. It keeps the selector grammar CSS-native. Anyone who knows CSS can read the selectors; only the declaration vocabulary is umwelt-specific.
2. It keeps the selector evaluation decidable. Selector engines only need to evaluate structural and attribute-equality predicates; comparison predicates move to the declaration layer where they're property-typed and well-bounded.
3. It keeps the cascade simple. Cascade operates on property names; `max-level` is a single property, not a family parameterized by a comparison operator.
4. It lets the plugin describe property semantics as part of its capability-publishing declaration. The ratchet and the dry-run utilities can then report "this rule sets `max-level` to 2, which caps computation at level 2" without hard-coding the semantics.

Plugins register properties with explicit metadata:

```python
register_property(
    taxon="capability",
    entity="tool",
    name="max-level",
    value_attribute="level",        # which attribute the value constrains
    comparison="<=",
    value_type="int",
    value_range=(0, 8),
    description="Maximum computation level permitted for this tool. Tools whose declared level exceeds this value fail the policy check.",
    category="effects_ceiling",
)
```

The `category` field groups related properties for tooling (the `umwelt inspect` CLI can list "effects_ceiling" properties across all taxa). The `description` is what the governed actor sees in the view-projection compiler (see §8).

### 4.4 Default taxon resolution

Entity type names are resolved against the plugin registry at parse time. When you write `file { editable: true; }`, the parser looks up `file` across all registered taxa. If exactly one taxon owns an entity type named `file`, that's the match. No taxon prefix, no qualification, no boilerplate. The CSS principle applies: you write `button`, not `html body button`, and the scope is implicit.

Authors should **not** have to prefix with the taxon name under normal conditions. Bare entity types are the primary form. The format is verbose only when the author opts into verbosity for structural emphasis (via descendant combinators) or for disambiguation when multiple taxa own the same type name.

### 4.5 Disambiguation

Two disambiguation mechanisms exist for the rare case that the bare form is ambiguous.

**CSS namespace syntax (inline):** CSS3 Selectors Level 3 defines `ns|type` for namespace-qualified element selection (`svg|circle`, `html|a`). umwelt reuses the same syntax for taxon qualification:

```
world|file[path^="src/"]        { editable: true; }
audit|file[path^="src/secrets"] { flag: sensitive; }
```

Both selectors have `file` as the entity type, but they resolve to different taxa. This is used only when two registered taxa both define a `file` entity; by default the bare form works and the pipe syntax is unnecessary.

**At-rule scoping (block):** For views with many rules in a single taxon, or for authors who want explicit taxon boundaries as documentation, at-rule scoping groups rules under a taxon name:

```
@world {
  file[path^="src/"]       { editable: true; }
  file[path$=".md"]        { editable: false; }
  resource[kind="memory"]  { limit: 512MB; }
  network                  { deny: "*"; }
}

@capability {
  tool                    { max-level: 2; }
  tool[name="Bash"]       { allow: false; }
  kit[name="python-dev"]  { allow: true; }
}

@state {
  hook[event="after-change"] {
    run: "pytest";
    run: "ruff check src/";
  }
}
```

Inside an `@world { ... }` block, entity type names are resolved against the `world` taxon first before falling back to global resolution. This lets you disambiguate by grouping and also serves as documentation for the reader.

The flat form and the at-rule form are interchangeable. Mix them freely in the same file. The parser produces identical ASTs. Authors choose based on readability — at-rule scoping is cleaner when a view has many rules in one taxon; flat form is cleaner when rules span multiple taxa and no disambiguation is needed.

The legacy at-rules from the original sandbox vocabulary (`@source`, `@tools`, `@after-change`, `@network`, `@budget`, `@env`) remain as sugar that desugars to typed selectors. See §7 for the desugaring table.

---

## 5. Cascade semantics

When multiple rules match the same entity, the cascade picks the winner.

### 5.1 Per-taxon cascade

**Cascade is scoped to a single taxon.** A `world` rule and a `capability` rule never compete even if a conceptual overlap exists, because they apply to disjoint entity sets. Rules inside the same taxon cascade against each other using CSS's standard order-of-precedence.

This matters for plugin composition: consumers registering different taxa are guaranteed their rules don't silently override each other. The `world` consumer's `file { editable: false; }` cannot accidentally cascade with the `capability` consumer's `tool { allow: true; }`.

### 5.2 Specificity and order

Within a taxon, the standard CSS cascade rules apply:

1. **Specificity wins.** A more specific selector beats a less specific one. Specificity is computed as a tuple `(ids, classes + attributes + pseudo-classes, types)` — the CSS3 spec. Ties are broken by order.
2. **Document order wins ties.** Later rules override earlier rules with equal specificity.
3. **Union selectors distribute.** `file[path^="src/"], file[path^="lib/"] { editable: true; }` is equivalent to writing each selector separately; each has its own specificity.

Example:

```
file                             { editable: false; }      /* S(0,0,1) — all files read-only */
file[path^="src/"]               { editable: true; }       /* S(0,1,1) — src is editable */
file[path^="src/generated/"]     { editable: false; }      /* S(0,1,1) — generated inside src is read-only */
file[path="src/auth/login.py"]   { editable: true; }       /* S(0,1,1) — this specific file overrides */
```

For `src/auth/login.py`: three rules match (the first three all apply). The exact-path rule at the bottom has specificity `(0,1,1)` equal to the earlier rules, but it comes later in document order, so it wins. Result: editable.

For `src/generated/protobuf_pb2.py`: the first three rules match. Same specificity, later order wins → read-only.

For `tests/test_auth.py`: only the first rule matches → read-only.

### 5.3 Property-level cascade

Properties cascade independently. A rule can set some properties on an entity while another rule sets others:

```
tool[name="Bash"] {
  allow: true;        /* set by this rule */
  max-level: 2;        /* set by this rule */
}
tool {
  max-level: 8;        /* default, overridden above for Bash */
}
```

For `Bash`: `allow: true` (from the specific rule), `max-level: 2` (from the specific rule, which wins over the default). For all other tools: `max-level: 8` from the default.

### 5.4 Comparison-property cascade

Comparison-semantics properties (`max-level`, `max-memory`, etc.) cascade by *value*, not by the comparison itself. The winning rule's declared value is the one applied. If two rules at the same specificity declare different `max-level` values, document order wins. The comparison semantics (`<=`) is property-level and does not interact with the cascade — it's applied *after* cascade picks the final value.

Under this, `max-level: 4` in a later rule overrides `max-level: 2` in an earlier rule, even though a loosening. Cascade is about which rule wins, not about which rule is stricter. If you want tightening-only semantics (the ratchet), that's a separate layer applied in the ratchet utility, not in the cascade.

---

## 6. Plugin registration: how taxa come into existence

Consumers register taxa at import time. The registration is declarative and produces metadata the ratchet, the dry-run utility, the `umwelt inspect` CLI, and the delegate-context compiler can all enumerate.

### 6.1 The registration API

```python
from umwelt.registry import register_taxon, register_entity, register_property, register_matcher

register_taxon(
    name="world",
    description="Entities the actor can couple to: filesystem, network, environment, resources.",
    ma_concept="world_coupling_axis",
)

register_entity(
    taxon="world",
    name="file",
    parent="dir",
    attributes={
        "name": AttrSchema(type=str, required=True),
        "path": AttrSchema(type=str, required=True),
        "language": AttrSchema(type=str, required=False),
        "size": AttrSchema(type=int, required=False, unit="bytes"),
        "mtime": AttrSchema(type=datetime, required=False),
    },
    description="A file in the filesystem. Descendant of a dir.",
    category="filesystem",
)

register_property(
    taxon="world",
    entity="file",
    name="editable",
    value_type=bool,
    comparison=None,                # exact / assignment
    description="Whether the actor is permitted to modify this file.",
    category="access_mode",
)

register_property(
    taxon="world",
    entity="resource",
    name="max-memory",
    value_attribute="limit",
    comparison="<=",
    value_type=int,
    value_unit="bytes",
    description="Maximum memory the actor may consume. Exceeding this triggers OOM.",
    category="budget",
)

register_matcher(
    taxon="world",
    matcher=FilesystemMatcher(),    # implements the selector protocol against real files
)
```

Each `register_*` call is pure metadata plus (for `register_matcher`) an implementation. The registration does not evaluate anything — it just builds the registry the core parser and cascade resolver consult during view compilation.

### 6.2 What's in the registry

After all consumers have registered, the registry contains:

- The set of known taxa, each with a description and Ma concept
- Per taxon: the entity types, their parent relationships, their attribute schemas
- Per entity type: the declared properties, their value types, their comparison semantics, their descriptions, their categories
- Per taxon: the matcher implementation

This is enough for:

- **Parsing**: the parser can accept arbitrary at-rules and declarations, and validation checks them against the registry. Unknown constructs become warnings (forward compatibility); known constructs are typed and range-checked.
- **Inspection**: `umwelt inspect --taxa` lists all registered taxa, entities, and properties with descriptions. `umwelt inspect tool` shows the full schema for a specific entity type.
- **Ratchet**: the ratchet utility enumerates the property vocabulary to propose view revisions in a form consumers understand.
- **Dry-run**: `umwelt dry-run view.umw --world <snapshot>` reports which entities each rule matches and which properties are set on each match.
- **Delegate-context compiler**: renders the view as prompt text by pulling entity and property descriptions from the registry.

### 6.3 Conflicts and namespacing

Taxa have unique names. A consumer that tries to register a taxon name another consumer already owns raises an error — this is fail-fast because silent namespace collisions would break cascade scoping.

Entity types within a taxon are also unique. `file` is owned by the world taxon; a consumer wanting to add "file" metadata from a different angle either extends the existing entity schema (adding attributes) or registers a different entity type (`world asset`, `world artifact`).

Properties on an entity are similarly unique per-entity. A consumer can extend an existing entity with new properties but cannot redefine an existing property's semantics.

Third-party taxa live in their own namespace. A consumer for the `bar` tool could register `bar/` as a top-level taxon, with its own entities and properties. The flat namespace is intentional — no `world.sandbox.file` style nesting — because cascade scoping is taxon-level and deeper nesting would either collapse cascade boundaries or require multi-level cascade rules that are not worth the complexity at v1.

---

## 7. Sandbox vocabulary: desugaring the current at-rules

The existing v1 sandbox at-rules (`@source`, `@tools`, `@after-change`, `@network`, `@budget`, `@env`) remain as **sugar** that the parser can accept, but they desugar to entity-selector form. The sandbox consumer of umwelt (shipped as `umwelt.sandbox` in the same package for v0.1-sandbox) registers the canonical taxa and the desugaring rules.

### 7.1 The desugaring table

| Current at-rule | Desugars to |
|---|---|
| `@source("src/auth/**/*.py") { * { editable: true; } }` | `file:glob("src/auth/**/*.py") { editable: true; }` |
| `@source("src/auth") { * { editable: true; } }` | `file[path^="src/auth/"] { editable: true; }` |
| `@source("src/auth") { .fn#authenticate { show: body; editable: true; } }` | `file[path^="src/auth/"] node[kind="function"][name="authenticate"] { show: body; editable: true; }` |
| `@tools { allow: Read, Edit; deny: Bash; kit: python-dev; }` | `tool[name="Read"] { allow: true; } tool[name="Edit"] { allow: true; } tool[name="Bash"] { allow: false; } kit[name="python-dev"] { allow: true; }` |
| `@network { deny: *; }` | `network { deny: "*"; }` |
| `@budget { memory: 512MB; wall-time: 60s; }` | `resource[kind="memory"] { limit: 512MB; } resource[kind="wall-time"] { limit: 60s; }` |
| `@env { allow: CI, PYTHONPATH; deny: *; }` | `env[name="CI"] { allow: true; } env[name="PYTHONPATH"] { allow: true; } env { allow: false; }` (with cascade: specific wins over `*`) |
| `@after-change { test: pytest tests/; lint: ruff check src/; }` | `hook[event="after-change"] { run: "pytest tests/"; run: "ruff check src/"; }` |

Both forms are valid input. The parser canonicalizes to entity-selector form internally; compilers operate on the canonical AST. Authors can write either style; the ratchet utility emits canonical form when proposing view revisions.

### 7.2 Why keep the sugar

Three reasons:

1. **Familiarity.** The at-rule form is what's in every current vision doc and in every example people have written by hand. Forcing a rewrite of every fixture would be hostile to early adopters.
2. **Brevity.** `@source("src/auth")` is shorter than `file[path^="src/auth/"]` and conveys the same thing when the author is writing a sandbox-specific view.
3. **Forward compatibility.** If the at-rules are kept as sugar, sandbox vocabulary changes can be made at the desugaring layer without requiring view-file rewrites. If the at-rules become primary and the entity form is secondary, future taxa can't use the same pattern.

The sugar is a convenience. The entity-selector form is the canonical representation in the AST, the ratchet's output format, and the format every new consumer should understand.

---

## 8. Mapping to blq's sandbox spec

A concrete exercise, because [blq](https://github.com/teaguesterling/lq)'s existing sandbox specs are the first real consumer's model and the test of whether this entity model holds up.

blq's `SandboxSpec` has eight dimensions. Here's how each one maps to the entity model:

| blq dimension | blq values | umwelt entity + property |
|---|---|---|
| `network` | `none`, `localhost`, `allowed_hosts`, `unrestricted` | `network { deny: "*" }` / `network[host="localhost"] { allow: true }` / etc. |
| `filesystem` | `readonly`, `workspace_only`, `scoped_write`, `unrestricted` | `file { editable: false }` (readonly) / `file:glob("workspace/**") { editable: true }` (workspace_only) / (unrestricted = omit) |
| `timeout` | duration | `resource[kind="wall-time"] { limit: <duration>; }` |
| `memory` | size | `resource[kind="memory"] { limit: <size>; }` |
| `cpu` | duration | `resource[kind="cpu-time"] { limit: <duration>; }` |
| `processes` | `isolated`, `visible` | `resource[kind="pids"] { isolation: <mode>; }` (or cleaner: `tool { max-level: 4; }` to block level 7 subprocess spawn) |
| `tmpfs` | size | `mount[dst="/tmp"] { type: "tmpfs"; size: <size>; }` |
| `paths_hidden` | list | `dir[path="/home"] { visible: false; } dir[path="/var"] { visible: false; } ...` |

blq's named presets (`readonly`, `test`, `build`, `integration`, `unrestricted`, `none`) become named views — each preset is a view file, and `blq commands register test --sandbox test` looks up the view by name and applies it.

blq's grade annotations (`grade_w`, `effects_ceiling`) are computed properties derived from the view, not authored properties. A post-processing step over the compiled view computes the W-axis grade by inspecting the network and filesystem rules, and the effects ceiling by inspecting the `tool { max-level: N }` rules. The Ma grade becomes a first-class queryable output of umwelt, not something blq has to compute independently — blq reads it from umwelt's view metadata.

blq's `sandbox suggest` and `sandbox tighten` workflows become instances of `umwelt ratchet`. `suggest` emits a new view given an observation set; `tighten` is `suggest` applied over an existing view, constrained to only narrow bounds. Both share the same underlying ratchet mechanics, generalized.

The mapping is not 1:1 in shape — umwelt expresses policy in a richer format with more structure — but it is 1:1 in *expressive power*. Every blq sandbox spec is representable as a view. The reverse is not true (views can express policy at altitudes blq does not reach), but the sandbox subset of views is exactly blq's current model in a different syntax.

---

## 9. Mapping to the computation level taxonomy

The nine-level taxonomy from the Ma framework's [Computation Channels post](https://judgementalmonad.com/blog/ma/07-computation-channels) maps directly into capability-tool attributes. The mapping is intentionally lossless — an umwelt policy can express any constraint the taxonomy describes.

### Level selection via declarations

Selecting by level uses the comparison-property pattern from §4.3:

```
tool { max-level: 2; }                   /* data channels only */
tool[altitude="os"] { max-level: 4; }    /* OS-altitude tools can amplify but not spawn */
tool[name="Bash"] { max-level: 2; }      /* Bash specifically capped to read+compute */
```

`max-level` is a comparison property with `<=` semantics. A tool with declared level > 2 does not pass the policy check; a tool with level ≤ 2 passes. The cascade picks the most specific matching rule's declared value.

### Level as a phase-transition boundary

The three phase transitions from post 7 (2→3 mutation, 3→4 amplification, 6→7 fold escape) are the boundaries where policy typically cares. Views can select on "does this cross a phase transition" via a derived pseudo-property:

```
tool:phase("amplification")   { require: sandbox; }    /* v1.1 */
tool:phase("fold-escape")     { allow: false; }        /* v1.1 */
```

v1 keeps this implicit in the numeric `max-level`; explicit phase selection is a v1.1 ergonomic addition.

### Effect signatures and capability publishing

A tool's level declaration is part of its capability publishing — the tool (or its kit, or its MCP server manifest, or blq's command registry) announces its computation level and umwelt reads it. umwelt does not infer levels. The sandbox is responsible for enforcement regardless of declaration honesty — this is the post-8 principle: capability publishing attenuates variety at the policy layer, while the sandbox bounds reality at the constraint layer.

---

## 10. Validation

Validation is per-taxon. Each taxon plugin provides a validator that checks rules inside that taxon for semantic correctness. Core umwelt runs validators in sequence after parsing:

```python
register_validator(
    taxon="world",
    validator=WorldValidator(),
)
```

The validator receives the parsed rules for its taxon and returns a list of warnings and errors. v1 validators check:

- Property values are in-range (`max-memory: -5MB` is rejected; `max-level: 12` is rejected).
- Comparison properties don't contradict each other on the same entity (`max-level: 2` and `min-level: 4` on the same selector).
- Paths don't escape the base directory (`file[path="../../../etc/passwd"]`).
- Globs are well-formed.
- Known entity types and property names are used correctly.

Cross-taxon invariants (e.g., "if `tool[name="Bash"] { allow: true }` then `resource[kind="wall-time"]` must set a limit") are not in v1. They would require a whole-view validator that sees multiple taxa at once; deferred.

Unknown at-rules, unknown entity types, and unknown declarations are always preserved with warnings, following the forward-compatibility principle from the policy-layer doc. A view can reference taxa that aren't currently registered; the view parses fine, and compilers that understand those taxa produce output for them while compilers that don't silently skip. This is how views written for a future vocabulary degrade on older umwelt installations.

---

## 11. Utilities (the CSS tooling)

This section is a brief preview; utility implementation details belong in `package-design.md`. Each utility is a thin wrapper over the parser + cascade + registry and implements a specific CSS-tooling-analog feature.

### `umwelt compile --target <name>`

Compile a view to a target's native format. Already core to the package; covered in `compilers/index.md`.

### `umwelt inspect`

Enumerate the registered taxa, entities, properties, and their descriptions. Given a view, list every rule, its selector, its properties, and what the validator thinks of it.

```
$ umwelt inspect my-view.umw
world (4 rules)
  file[path^="src/auth/"]            editable=true
  file                                editable=false
  network                             deny="*"
  resource[kind="memory"]             limit=512MB

capability (2 rules)
  tool                                max-level=2
  tool[name="Read"]                   allow=true

state (1 rule)
  hook[event="after-change"]          run=["pytest", "ruff check src/"]
```

### `umwelt dry-run --world <snapshot>`

Evaluate a view against a supplied world snapshot. For each rule in the view, report which entities it matched and what properties were set on each match. Similar to browser devtools' computed-style view for CSS.

```
$ umwelt dry-run my-view.umw --world .
file[path^="src/auth/"] { editable: true }
  → matches: src/auth/login.py, src/auth/oauth.py, src/auth/session.py
file { editable: false }
  → matches (after cascade): src/common/util.py, tests/test_util.py
...
```

This is the feature that makes views debuggable — an author can see exactly which files their selector is catching and which it's missing before deploying the view to any enforcement tool.

### `umwelt ratchet --observations <source>`

Given an observation source (blq database, ratchet-detect output, strace log, a JSON dump of an actor's tool calls), propose a view revision that is minimally consistent with the observations. The proposed view is written to stdout or to a file for human review. No auto-commit; the human decides whether the proposal is correct.

The observation source is plugin-supplied: each observation tool (blq, ratchet-detect, ...) can register a converter that normalizes its raw data into the umwelt vocabulary. The ratchet utility then runs a narrowing algorithm over the normalized observations to produce the proposed view.

This is the load-bearing automation step of the policy ratchet. Specified end-to-end: the conversion is specified transformation, the narrowing is specified analysis, the output is a specified view file. Human judgment applies at the commit point.

### `umwelt check`

Run the parser, the validators, and every registered compiler. Report any errors, warnings, or compiler complaints. The "does this view compile cleanly everywhere" sanity check.

### `umwelt diff view-a.umw view-b.umw`

Compare two views. Report which rules changed, which entities are matched differently, which properties drifted. Essential for reviewing ratchet-proposed revisions before committing.

---

## 12. View transparency: projecting the view into the actor's scope

The [SELinux coda](https://judgementalmonad.com/blog/ma/08-the-specified-band#the-selinux-coda) from the Ma series is a design requirement, not an optional add-on. Views should be projectable into the governed actor's scope so the Inferencer can model its own constraints without empirical probing.

The entity model supports this via the plugin registration's description fields. Every taxon, entity, and property carries a description string suitable for inclusion in a prompt. A future `compilers/delegate_context.py` compiler walks a view, resolves the matched entities, and emits a prompt fragment like:

```
## Your operating environment (umwelt view)

### What you can access
- Files in src/auth/ — you may read and edit these
- Files in src/ (other than src/auth/) — read-only
- Files in tests/ — read-only
- Your memory limit is 512MB; exceeding it will terminate the run.
- Your wall-clock limit is 60 seconds.
- You have no network access.

### What you can do
- You may use the tools: Read, Edit, Grep, Glob.
- You may NOT use the tools: Bash, Write.
- Your tool computation level is capped at level 2 (read + compute only).

### What happens after you make changes
- The command `pytest tests/auth/ -x` will run after any file change.
- The command `ruff check src/auth/` will run after any file change.
- If either command fails, the result will be reported as part of the turn.
```

The descriptions come from the plugin's registered metadata. No free-text generation, no trained summarization — the text is assembled from registered descriptions and the view's evaluated rule set. Specified end-to-end.

This is a v1.1 compiler target, flagged here so that plugin authors know to write their description fields thoughtfully. A plugin whose descriptions are sparse produces unhelpful prompts; a plugin whose descriptions are well-written produces projections the actor can actually use. The description field is a soft contract between plugin authors and the transparency principle.

---

## 13. What's in v1 vs. what's deferred

### v1 (shipped with v0.1-core + v0.1-sandbox)

- Parser with unknown-construct preservation
- Base AST types: `View`, `RuleBlock`, `AtRule`, `Selector`, `Declaration`, `ParseWarning`
- Plugin registration API: `register_taxon`, `register_entity`, `register_property`, `register_matcher`, `register_validator`
- Core selector evaluation: type, attribute, descendant, direct-child, comma-union, `:not`, `:glob` pseudo-class
- Cascade resolver with CSS3 specificity
- Comparison-property semantics
- First-party taxa: `world`, `capability`, `state` (minimal; see below)
- At-rule sugar desugaring for the sandbox vocabulary
- `umwelt compile`, `umwelt inspect`, `umwelt check`, `umwelt dry-run` (basic)
- `umwelt ratchet` scaffold (accepts an observation source plugin, runs narrowing, emits proposed view)

### v1.1

- `actor` taxon fully specified (was minimal in v1)
- `:has(...)` pseudo-class
- `:phase(...)` pseudo-class on tools
- Selector-level evaluation via pluckit (code nodes beyond file granularity)
- `compilers/delegate_context.py` — the view-transparency compiler
- `umwelt diff`
- Cross-taxon validation invariants
- `observation` entity type in the `state` taxon

### v2

- `policy` taxon (views-about-views)
- View bank: storage, retrieval, git-history distillation
- Multi-view composition via `@import` or equivalent
- Priority overrides across views

---

## 14. Design decisions with their reasons

A few of the choices in this document warrant explicit justification because they're load-bearing and non-obvious:

**Pluggable taxa with no hardcoded vocabulary in core.** Core umwelt knows about parsers, ASTs, selectors, cascade, and compilers. It does not know about files, tools, or networks. This is what makes umwelt the *common language* — any component in the specified band can register its vocabulary and participate, without waiting for core umwelt to grow support for it. The sandbox vocabulary ships in `umwelt.sandbox` as a first-party example, but it's a consumer of core umwelt, not built into it.

**Properties carry their own comparison semantics.** `max-level: 2` means "cap at level 2," not a selector filter. This keeps the selector grammar CSS-native and the evaluation decidable. It also lets plugins describe policy semantics as data (name, value type, comparison, description) rather than as code, which the ratchet utility consumes to propose revisions.

**Cascade is per-taxon.** `world` rules and `capability` rules never compete. This makes plugin composition safe — a third-party taxon can't accidentally override a first-party taxon's rules. The cost is that a view cannot express "this `file` rule should override this `tool` rule," but that's a cross-cutting concern that the enforcement layer handles, not the policy layer.

**Structural relationships via parent links, not via a separate tree.** Each entity declares its parent type (`file` has parent `dir`). The selector engine uses these for descendant combinator resolution. This avoids introducing a separate "structure of the world" representation and lets each plugin own its own hierarchy without coordinating with others.

**Glob patterns via `:glob()` pseudo-class, not a new attribute operator.** Keeps the attribute selector syntax CSS-native. Pseudo-classes are CSS's established extension point. The cost is one extra character (`:glob("...")` vs. `[path~~"..."]`), but the benefit is that CSS tooling (syntax highlighters, LSPs, linters) can handle the selectors without special-casing.

**The at-rule sugar (`@source`, `@tools`, ...) is preserved.** Existing docs and fixtures use this form. The parser accepts it and desugars internally. New consumers that don't care about sandbox semantics never touch the sugar; they write `tool[...] { ... }` directly.

**Computation levels are consumer-declared, not core-validated.** umwelt doesn't know that a tool is at level 4; the tool (or its kit, or its MCP manifest) declares it. umwelt validates only that the declared level is an integer in [0, 8]. Honesty of level declarations is a capability-publishing concern; the sandbox backstops dishonesty.

**View transparency is a first-party concern.** The plugin's description fields exist specifically so the view-projection compiler can build delegate-readable prompts. This is not optional ergonomics — the SELinux coda from the Ma framework says opaque specified policy wastes the Inferencer's decision surface, and projection is how we avoid that. Plugin authors who write sparse descriptions produce views that cost more to operate under; good descriptions are load-bearing.

---

## 15. Open questions

Recorded so they don't get lost. These are known-unknowns that don't block v1 but will need answers as real consumers exercise the model.

1. **How should properties with comparison semantics interact with inheritance?** CSS properties can be declared `inherit` — a child element inherits its parent's value. For umwelt, would `file { editable: inherit; }` mean "inherit from the parent `dir`"? v1: no inheritance; explicit only. v1.1+ may add it if a consumer needs it.

2. **What about selector-level quantifiers?** Some policies are most naturally expressed as "at least one file in this directory must be editable" or "at most three tools may have `max-level > 2`". CSS selectors can't express cardinality, and adding it would break decidability. v1: no quantifiers. If a use case appears, a separate constraint language can be added.

3. **Should the registry be module-global or session-scoped?** Plugin registration at import time is simplest but makes multi-tenant usage awkward (different views needing different vocabularies). v1: module-global with `@contextmanager`-based scope override for tests. v2 may revisit.

4. **Is there a need for "virtual" entities — entities computed from other entities?** E.g., a `world path-bundle` entity that groups files matching a glob so policy can be attached once. Could be added later as a consumer's own entity type; doesn't need core support.

5. **How does the ratchet utility handle observation sources that disagree?** If blq says the actor needs `max-level: 4` and ratchet-detect says `max-level: 2`, which wins? v1: merge by union (loosest wins) with a warning. v1.1: policy-driven merge strategies.

6. **Can two different taxa declare the same entity type name in different namespaces?** `file` and `audit file` could both exist. v1: yes, namespaced by taxon. Cascade is per-taxon so no conflict.

7. **Should at-rule sugar support arguments that aren't in the canonical form?** `@source("src/**/*.py" editable=true)` is compact but drifts from CSS. v1: no — sugar must correspond 1:1 to canonical form.

---

## 16. What this document is not

- **Not the format grammar.** See [`view-format.md`](./view-format.md) for the BNF of the view file syntax.
- **Not the implementation plan.** See [`package-design.md`](./package-design.md) for the module layout, API, and v0.1 scoping.
- **Not a CSS tutorial.** The selector syntax here is a subset of CSS3 with umwelt-specific additions; readers unfamiliar with CSS selectors should consult the CSS3 spec.
- **Not the complete taxonomy.** The five first-party taxa are a starting point; third-party consumers will add more, and the `actor` and `policy` taxa are intentionally underspecified in v1.
- **Not a runtime spec.** How the sandbox consumer actually builds a workspace from a view, what the hook dispatcher does, how the nsjail compiler emits textproto — those are each in their own docs.

The entity model is the contract between core umwelt and its consumers. Everything above the contract (view authors writing views, plugin authors registering vocabularies, compilers translating to native formats) uses the contract. Everything below the contract (parser internals, cascade resolution algorithms) implements the contract. The contract itself is what this document specifies.
