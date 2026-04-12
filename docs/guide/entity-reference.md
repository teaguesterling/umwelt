# Entity Reference

Every entity type, attribute, and property registered by the sandbox consumer. This is the comprehensive list — what you can select on and what you can declare in a view.

*Generated from the live registry. If this page disagrees with the code, the code wins.*

---

## world taxon

**What it models:** the actor's coupled world — filesystem, mounts, network, environment, resources.
**Ma concept:** world coupling axis.

### `world` — named environment (root)

The root of the hierarchy. Use `world#name` to define named environments.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `name` | str | | Environment name (used as `#id` in selectors) |

**Applicable properties:** none directly. `world` is a structural root; properties attach to its descendants.

**Selector examples:**
```css
world#dev { ... }                           /* named environment */
world#dev file { editable: true; }          /* all files in dev */
world#dev tool[name="Bash"] { allow: false; } /* cross-taxon: tools in dev context */
```

---

### `mount` — workspace mount (parent: `world`)

Declares how host paths map into the workspace. Compiles to nsjail `mount {}` stanzas or bwrap `--bind` flags.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `path` | str | yes | Mount destination path inside the workspace |
| `source` | str | | Host path or URL this mount maps from |
| `type` | str | | Mount type: `bind`, `tmpfs`, `overlay` |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `source` | str | exact | Host path or URL this mount maps from |
| `readonly` | bool | exact | Whether the mount is read-only |
| `type` | str | exact | Mount type: `bind`, `tmpfs`, `overlay` |
| `size` | str | exact | Size limit (for tmpfs mounts) |

**Selector examples:**
```css
world#dev mount[path="/workspace/src"] { source: "./src"; }
mount[path="/tmp"] { type: "tmpfs"; size: "64MB"; }
mount[path="/workspace"] { readonly: true; }
```

---

### `dir` — directory

A directory in the filesystem.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `path` | str | yes | Directory path relative to base_dir |
| `name` | str | yes | Directory name |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `editable` | bool | exact | Whether the actor may modify files in this dir |
| `visible` | bool | exact | Whether the actor can see this dir |

**Selector examples:**
```css
dir[name="src"] file { editable: true; }    /* structural descent */
dir[path^="src/auth"] { editable: true; }
```

---

### `file` — file (parent: `dir`)

A file in the filesystem. Descendant of `dir`.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `path` | str | yes | File path relative to base_dir |
| `name` | str | yes | File name |
| `language` | str | | Programming language (inferred from extension) |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `editable` | bool | exact | Whether the actor may modify this file |
| `visible` | bool | exact | Whether the actor can see this file |
| `show` | str | exact | What to show: `body`, `outline`, `signature` |

**Selector examples:**
```css
file[path^="src/auth/"]          { editable: true; }
file[path$=".py"]                { editable: false; }
file[name="README.md"]           { visible: true; }
file:glob("src/**/*.py")         { editable: true; }
file#README.md                   { editable: false; }
```

---

### `resource` — runtime resource

A runtime resource with a limit. The `kind` attribute selects which resource.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `kind` | str | yes | Resource kind: `memory`, `cpu-time`, `wall-time`, `max-fds`, `tmpfs` |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `limit` | str | exact | Resource limit value with unit (e.g. `512MB`, `60s`, `128`) |

**Selector examples:**
```css
resource[kind="memory"]    { limit: 512MB; }
resource[kind="wall-time"] { limit: 5m; }
resource[kind="cpu-time"]  { limit: 3m; }
resource[kind="max-fds"]   { limit: 128; }
resource[kind="tmpfs"]     { limit: 64MB; }
```

---

### `network` — network endpoint

Network access control. v1 supports only full denial; v1.1 adds hostname allowlists.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `host` | str | | Hostname (v1.1) |
| `port` | int | | Port number (v1.1) |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `deny` | str | exact | Deny pattern (`"*"` for all) |
| `allow` | bool | exact | Whether this endpoint is allowed |

**Selector examples:**
```css
network { deny: "*"; }                              /* deny all */
network[host="api.github.com"] { allow: true; }     /* v1.1: allowlist */
```

---

### `env` — environment variable

Controls which environment variables are passed through to the delegate.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `name` | str | yes | Environment variable name |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `allow` | bool | exact | Whether this env var is passed through |

**Selector examples:**
```css
env[name="CI"]         { allow: true; }
env[name="PYTHONPATH"] { allow: true; }
env                    { allow: false; }     /* deny all others (lower specificity) */
```

---

## capability taxon

**What it models:** what the actor can do — tools, kits, computation levels.
**Ma concept:** decision surface axis.

### `tool` — a callable tool

A tool the actor can call. Carries a computation level from the [nine-level taxonomy](https://judgementalmonad.com/blog/ma/07-computation-channels).

| Attribute | Type | Required | Description |
|---|---|---|---|
| `name` | str | yes | Tool name (e.g. `Read`, `Edit`, `Bash`) |
| `kit` | str | | Kit this tool belongs to |
| `altitude` | str | | Enforcement altitude: `os`, `language`, `semantic`, `conversational` |
| `level` | int | | Computation level 0–8 |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `allow` | bool | exact | Whether the tool is permitted |
| `max-level` | int | `<=` | Maximum computation level. Tools above this are denied. |
| `require` | str | exact | Requirement for using this tool (e.g. `sandbox`) |
| `allow-pattern` | list | `pattern-in` | Glob patterns for allowed invocations |
| `deny-pattern` | list | `pattern-in` | Glob patterns for denied invocations |

**Computation levels:**

| Level | Name | Description |
|---|---|---|
| 0 | sealed | Pure computation, no IO |
| 1 | structured-query | SQL, GraphQL, schema-bounded queries |
| 2 | read-compute | Read access + arbitrary computation |
| 3 | mutation | Sandboxed writes |
| 4 | amplification | Agent-generated executable specification |
| 5 | env-modification | Package install, environment change |
| 6 | capability-creation | New tools generated from within |
| 7 | subprocess-spawn | Persistent background processes |
| 8 | controller-modification | Modifying CLAUDE.md, the Harness itself |

**Selector examples:**
```css
tool[name="Read"]            { allow: true; }
tool[name="Bash"]            { allow: true; max-level: 2; }
tool[altitude="os"]          { require: sandbox; }
tool[name="Bash"] {
  allow-pattern: "git *", "pytest *";
  deny-pattern: "rm -rf *", "sudo *";
}
```

---

### `kit` — a tool group

A named collection of tools, capability-published together.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `name` | str | yes | Kit name (e.g. `python-dev`, `postgres-admin`) |
| `version` | str | | Kit version |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `allow` | bool | exact | Whether the kit is permitted |

**Selector examples:**
```css
kit[name="python-dev"] { allow: true; }
```

---

## state taxon

**What it models:** what the Harness tracks across turns — hooks, jobs, budgets.
**Ma concept:** observation layer.

### `hook` — lifecycle hook

A command that runs at a lifecycle event (e.g. after the delegate changes a file).

| Attribute | Type | Required | Description |
|---|---|---|---|
| `event` | str | yes | Lifecycle event: `before-call`, `after-change`, `on-failure`, `on-timeout` |
| `phase` | str | | Sub-categorization of the event |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `run` | str | exact | Shell command to execute. Repeat for multiple commands. |
| `timeout` | str | exact | Timeout for hook execution (e.g. `60s`) |

**Selector examples:**
```css
hook[event="after-change"] {
  run: "pytest tests/auth/ -x";
  run: "ruff check src/auth/";
  timeout: 60s;
}
```

---

### `job` — execution run

An execution run, possibly a sub-delegate.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `id` | str | yes | Job identifier |
| `state` | str | | Job state: `pending`, `running`, `completed`, `failed` |
| `delegate` | bool | | Whether this is a sub-delegate |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `inherit-budget` | float | exact | Fraction of parent budget to inherit (0.0–1.0) |

**Selector examples:**
```css
job[delegate=true] { inherit-budget: 0.5; }
```

---

### `budget` — runtime budget

A budget the job consumes.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `kind` | str | yes | Budget kind: `memory`, `cpu-time`, `wall-time`, `tokens`, `cost` |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `limit` | str | exact | Budget limit value |

**Selector examples:**
```css
budget[kind="wall-time"] { limit: 5m; }
budget[kind="tokens"]    { limit: 100000; }
```

---

## actor taxon

**What it models:** the four Ma actors — principal, inferencer, executor, harness.
**Ma concept:** four-actor taxonomy.

Minimal in v1. Full treatment (multi-actor view composition) is v1.1+.

### `inferencer` — the language model

| Attribute | Type | Required | Description |
|---|---|---|---|
| `model` | str | | Model identifier (e.g. `claude-sonnet-4-6`) |
| `kit` | str | | Kit this inferencer uses |
| `temperature` | float | | Sampling temperature |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `model` | str | exact | Model to use |
| `temperature` | float | exact | Sampling temperature |

**Selector examples:**
```css
inferencer { model: "claude-sonnet-4-6"; temperature: 0; }
```

---

### `executor` — a tool runner

| Attribute | Type | Required | Description |
|---|---|---|---|
| `tool_name` | str | | Tool this executor represents |
| `altitude` | str | | Enforcement altitude |

**Selector examples:**
```css
executor[tool_name="Bash"] { ... }     /* v1.1+ */
```

---

## Not yet registered (v1.1+)

These entity types are documented in the [entity model spec](../vision/entity-model.md) but not yet registered in code:

| Entity | Taxon | When | Description |
|---|---|---|---|
| `node` | world | v1.1 | Code construct inside a file (function, class, method). Evaluated via pluckit/sitting_duck. |
| `effect` | capability | v1.1 | Effect signature declared by a tool: read, write, exec, spawn. |
| `observation` | state | v1.1 | Something a Layer-2 observer reported. |
| `manifest` | state | v1.1 | The workspace manifest. |
| `source` | world (proposed) | v1.1+ | Logical file grouping for monorepos. See [design notes](../vision/notes/world-as-root-and-linker-role.md). |

---

## Property comparison operators

Properties with prefixed names carry built-in comparison semantics:

| Prefix | Comparison | Meaning | Example |
|---|---|---|---|
| *(none)* | exact | Set this property to this value | `editable: true` |
| `max-` | `≤` | Cap: permitted values ≤ declared | `max-level: 2` |
| `min-` | `≥` | Floor: permitted values ≥ declared | `min-budget: 256MB` |
| `only-` | `∈` | Set membership | `only-kits: python-dev, rust-dev` |
| `any-of-` | overlap | Set overlap | `any-of-effects: read, write` |
| `allow-pattern` | glob | Invocations matching any pattern allowed | `allow-pattern: "git *"` |
| `deny-pattern` | glob | Invocations matching any pattern denied | `deny-pattern: "rm -rf *"` |

---

## The hierarchy

```
world#env-name                        ← root (named environment)
├── mount[path="/workspace/src"]      ← workspace topology
│   ├── dir[name="src"]
│   │   ├── dir[name="auth"]
│   │   │   ├── file[name="login.py"]
│   │   │   │   └── node.function#authenticate    (v1.1)
│   │   │   └── file[name="oauth.py"]
│   │   └── dir[name="common"]
│   │       └── file[name="util.py"]
│   └── dir[name="tests"]
│       └── file[name="test_login.py"]
├── resource[kind="memory"]           ← runtime limits
├── resource[kind="wall-time"]
├── network                           ← network access
└── env[name="CI"]                    ← env vars

tool[name="Read"]                     ← capability taxon (flat, not nested)
tool[name="Edit"]
tool[name="Bash"]
kit[name="python-dev"]

hook[event="after-change"]            ← state taxon
job[id="run-1"]
budget[kind="wall-time"]

inferencer[model="claude-sonnet-4-6"]  ← actor taxon (minimal v1)
```

Navigate with CSS descendant selectors. Cross-taxon compound selectors (e.g. `world#dev tool[name="Bash"]`) are context qualifiers, not structural descent.
