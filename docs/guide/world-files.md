# World Files

A world file (`.world.yml`) declares the entities that exist in an agent's environment — the tools it can call, the modes it operates in, the resources it has access to. It's the DOM that stylesheets match against.

## Your first world file

```yaml
# env.world.yml
entities:
  - type: tool
    id: Read
  - type: tool
    id: Edit
  - type: mode
    id: implement
```

Three entities. Two tools and a mode. A stylesheet can now match these:

```css
tool#Read { visible: true; }
tool#Edit { visible: true; allow: true; }
mode#implement tool { max-level: 5; }
```

Inspect it:

```bash
umwelt materialize env.world.yml
```

## Shorthand syntax

Writing `entities:` blocks for every tool gets tedious. Shorthand keys expand into entities via the vocabulary registry:

```yaml
# Same result, less typing
tools: [Read, Edit]
modes: [implement]
```

`tools: [Read, Edit]` expands to two `tool` entities. `modes: [implement]` expands to one `mode` entity. The shorthand registry knows which entity type each key maps to.

Available shorthands (from the sandbox vocabulary):

| Key | Entity type | Form | Example |
|---|---|---|---|
| `tools` | `tool` | list | `tools: [Read, Edit, Bash]` |
| `modes` | `mode` | list | `modes: [implement, review]` |
| `principal` | `principal` | scalar | `principal: Teague` |
| `inferencer` | `inferencer` | scalar | `inferencer: claude-sonnet` |
| `resources` | `resource` | map | `resources: {memory: 512MB, wall-time: 5m}` |

### Map shorthands

Map shorthands create entities with an attribute set from the value:

```yaml
resources:
  memory: 512MB
  wall-time: 5m
```

This creates two `resource` entities: `resource#memory` with `limit: 512MB` and `resource#wall-time` with `limit: 5m`. The `limit` attribute is configured by the shorthand's `attribute_key`.

## Explicit entities

For entities that need classes, attributes, or parent references, use the full `entities:` block:

```yaml
tools: [Read, Edit, Bash]

entities:
  - type: tool
    id: Bash
    classes: [dangerous, shell]
    attributes:
      description: "Execute shell commands"

  - type: tool
    id: Read
    attributes:
      description: "Read files from the filesystem"
```

### Merge semantics

When a shorthand and an explicit entry declare the same `(type, id)` pair, the explicit entry wins. In the example above, `Bash` appears in both `tools:` and `entities:` — the explicit entry with classes and attributes is kept; the shorthand version is discarded.

This lets you use shorthands for the common case and override specific entities when you need more detail.

## Classes

Classes work exactly like CSS classes. An entity can have zero or more:

```yaml
entities:
  - type: tool
    id: Bash
    classes: [dangerous, shell, system]
```

Stylesheets match classes with `.`:

```css
tool.dangerous { max-level: 3; }
tool.shell { allow-pattern: "echo *"; }
```

## Attributes

Attributes are key-value metadata on an entity:

```yaml
entities:
  - type: tool
    id: Read
    attributes:
      description: "Read files from the filesystem"
      kit: "filesystem"
```

Stylesheets match attributes with `[]`:

```css
tool[kit="filesystem"] { visible: true; }
```

## Projections

Projections declare entities that will be populated by external systems (filesystem discovery, runtime state, etc.):

```yaml
projections:
  - type: dir
    id: node_modules
    attributes:
      path: "node_modules/"

  - type: dir
    id: src
    attributes:
      path: "src/"
```

Projections are stored separately from entities — they represent what the environment *will* provide, not what the world file *declares*. In the compiled database, projections appear in the entities table with `provenance: projected`.

## Tools vs executables

A `tool` is a first-class capability provided to the inferencer — an MCP tool like Read, Edit, or Bash. An `exec` is an executable binary that exists in the environment — `bash`, `python3`, `git`. These are independent concepts: `tool#Bash` describes a capability the agent can invoke, but says nothing about how it's implemented. It might call `/bin/bash`, it might be a Python reimplementation, it might delegate to a WASM sandbox. The exec entities describe what binaries the environment provides, regardless of which tools use them.

```yaml
entities:
  # Tools — what the inferencer can call
  - type: tool
    id: Bash
    classes: [dangerous]

  # Executables — what runs in the environment
  - type: exec
    id: bash
    attributes:
      path: /bin/bash
  - type: exec
    id: git
    attributes:
      path: /usr/bin/git
  - type: exec
    id: python3
    attributes:
      path: /usr/bin/python3
```

These are independent entity types in different taxa — `tool` lives in `capability`, `exec` lives in `world`. They don't need to reference each other. A consumer like nsjail queries exec policy to build its sandbox configuration; a consumer like Kibitzer queries tool policy to decide what to show the agent. Each consumer reads the slice of policy it cares about.

```css
/* Tool-level: what the agent sees */
tool#Bash { allow: true; max-level: 3; }

/* Executable-level: what the sandbox restricts */
exec#bash    { path: "/bin/bash"; }
exec#git     { path: "/usr/bin/git"; }
exec#python3 { path: "/usr/bin/python3"; search-path: "/usr/bin:/usr/local/bin"; }
```

The relationship between `tool#Bash` and the executables it invokes is a consumer concern — umwelt doesn't model it. The tool entity describes what the inferencer can call; the exec entities describe what binaries exist in the environment. Different consumers enforce different parts of this policy independently.

## Directories and files

The world taxon includes `dir` and `file` entities for filesystem structure:

```yaml
entities:
  - type: dir
    id: src
    attributes:
      path: "src/"
      name: "src"
  - type: dir
    id: tests
    attributes:
      path: "tests/"
      name: "tests"
  - type: file
    id: auth.py
    attributes:
      path: "src/auth/auth.py"
      name: "auth.py"
      language: "python"
```

`file` is a child of `dir` in the world hierarchy, so descendant selectors work:

```css
dir[name="src"] file { editable: true; }       /* files under src/ */
dir[name="tests"] file { editable: false; }     /* tests are read-only */
file[path$=".py"] { visible: true; }            /* all Python files visible */
```

In practice, file and directory entities are often populated by projections or filesystem matchers rather than declared by hand in the world file.

## Combining everything

A realistic world file for a code editing session:

```yaml
# delegate.world.yml
principal: Teague
inferencer: claude-sonnet

tools: [Read, Edit, Bash, Grep, Glob, Write]
modes: [implement]

resources:
  memory: 1GB
  wall-time: 10m
  max-fds: 256

entities:
  - type: tool
    id: Bash
    classes: [dangerous]
    attributes:
      description: "Execute shell commands"

  - type: tool
    id: Write
    classes: [dangerous]
    attributes:
      description: "Overwrite entire files"

  - type: exec
    id: bash
    attributes:
      path: /bin/bash

  - type: exec
    id: git
    attributes:
      path: /usr/bin/git

projections:
  - type: dir
    id: src
    attributes:
      path: "src/"
```

Pair it with a stylesheet:

```css
/* policy.umw */
tool { visible: true; allow: true; }
tool.dangerous { max-level: 3; }
tool#Bash { allow-pattern: "git *"; allow-pattern: "pytest *"; }

mode#implement tool { max-level: 5; }

resource#memory { limit: 1GB; }
resource#wall-time { limit: 10m; }
```

Compile and query:

```bash
umwelt compile --target sqlite -o world.db policy.umw --world delegate.world.yml
```

Or use the Python API:

```python
from umwelt.policy import PolicyEngine

engine = PolicyEngine.from_files(
    world="delegate.world.yml",
    stylesheet="policy.umw",
)
engine.resolve(type="tool", id="Bash", property="max-level")  # → "3"
```

## Materialization

`umwelt materialize` renders a world file at three detail levels:

```bash
# Full: all entities with all attributes
umwelt materialize env.world.yml --level full

# Outline: entities with classes but no attributes
umwelt materialize env.world.yml --level outline

# Summary: just counts by type
umwelt materialize env.world.yml --level summary
```

Write to a file:

```bash
umwelt materialize env.world.yml -o snapshot.yml
```

This is useful for inspecting what the world file produces after shorthand expansion — the materialized output shows every entity that will enter the compiled database.

## Vocabulary validation

When the sandbox vocabulary is registered, the parser validates entity types against the registry:

```yaml
entities:
  - type: frobnitz    # ← unknown type
    id: X
```

This produces a warning (not an error): `unknown entity type 'frobnitz' (not in registered vocabulary)`. Unknown types are allowed for forward compatibility — you can declare entities for vocabulary that hasn't been registered yet.

## Future keys

Some keys are parsed and stored but produce warnings because they aren't implemented yet:

| Key | Status | Purpose |
|---|---|---|
| `discover:` | Phase 2 | Filesystem/runtime entity discovery |
| `overrides:` | Phase 2 | Per-environment overrides |
| `fixed:` | Phase 2 | Immutable constraints |
| `include:` | Phase 2 | Include other world files |
| `exclude:` | Phase 2 | Exclude entities from included files |
| `vars:` | Reserved | Template variables |
| `when:` | Reserved | Conditional blocks |
| `version:` | Reserved | Schema versioning |

These keys are stored on the `WorldFile` dataclass so future versions can process them without re-parsing.

## Next steps

- [PolicyEngine](policy-engine.md) — query resolved policy from Python
- [Writing Views](writing-views.md) — write stylesheets that match world entities
- [Plugins](plugins.md) — extend the vocabulary with your own entity types
