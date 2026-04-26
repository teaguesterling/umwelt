# Entity Reference

Every entity type, attribute, and property registered by the sandbox consumer. This is the comprehensive list — what you can select on and what you can declare in a view.

*Generated from the live registry. If this page disagrees with the code, the code wins.*

---

## VSM alias taxa (v0.5+)

v0.5 introduces a Viable System Model (VSM) aligned naming for taxa. The Beer names are **aliases** — existing names still work, and the VSM names resolve to the same matchers:

| VSM taxon | Legacy taxon | Beer's system |
|---|---|---|
| `principal` | *(new)* | S5 — Identity / commissioning authority |
| `world` | `world` | S0 — Environment |
| `audit` | *(new)* | S3\* — Audit bypass channel |
| `control` | `state` | S3 — Current-moment regulation |
| `coordination` | `state` | S2 — Anti-oscillation / harness |
| `intelligence` | `actor` | S4 — The inferencer |
| `operation` | `capability` | S1 — Tools and effects |

All seven taxa participate in cross-axis cascade specificity: selectors that name more axes win. See the design note at `docs/vision/notes/vsm-alignment.md` for the rationale.

---

## principal taxon

**What it models:** the commissioning authority — the human or outer agent who defined this view.
**VSM concept:** S5 (Identity / policy).

Minimal in v0.5. Richer principal modeling (cross-delegate lineage, grade lattice) is v1.1+.

### `principal` — the commissioning authority

| Attribute | Type | Required | Description |
|---|---|---|---|
| `name` | str | | Principal name (used as `#id` in selectors) |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `intent` | str | exact | Human-readable statement of purpose for this delegation |
| `grade` | str | exact | Trust grade: `personal`, `team`, `org` (v1.1+) |

**Selector examples:**
```css
principal#Teague { intent: "code review"; }
principal#Teague world#sandbox { /* rules for this principal's world */ }
```

---

## audit taxon

**What it models:** observations from outside the delegate's world — the S3\* bypass channel.
**VSM concept:** S3\* (Audit — direct observation without S2/S3 interference).

Audit sits *outside* the world hierarchy. Entries in `@audit { ... }` are never subject to world-scoped context qualifiers. No audit compiler ships in v0.5; these entities are the contract for v0.7's observation consumer.

### `observation` — an observation entry

Something a Layer-2 observer reported (e.g. from `blq`, `ratchet-detect`, `strace`).

| Attribute | Type | Required | Description |
|---|---|---|---|
| `id` | str | | Observation identifier (used as `#id` in selectors) |
| `source` | str | | Observer tool that produced this entry |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `enabled` | bool | exact | Whether this observation source is active |

**Selector examples:**
```css
@audit {
  observation#coach    { source: "kibitzer"; enabled: true; }
  observation#ratchet  { source: "ratchet-detect"; enabled: true; }
}
```

---

### `manifest` — the workspace manifest

| Attribute | Type | Required | Description |
|---|---|---|---|
| `id` | str | | Manifest identifier |
| `path` | str | | Path to the manifest file |

**Selector examples:**
```css
@audit {
  manifest#current { path: ".umwelt/manifest.json"; }
}
```

---

## world taxon

**What it models:** the actor's coupled world — filesystem, mounts, network, environment, resources.
**Ma concept:** world coupling axis.

**World-axis vs action-axis:** Properties like `editable`, `visible`, and `allow` on world entities (`file`, `dir`, `network`, `tool`) are **world-axis** — they express a property of the resource itself (e.g. a read-only mount, a denied network endpoint). These are distinct from the same-named properties on `use` entities, which are **action-axis** — they express what a specific delegate's access path permits. OS-altitude compilers (nsjail, bwrap) read world-axis properties; language-altitude compilers (lackpy, kibitzer) read action-axis properties. A full enforcement decision conjoins both. See the `use` entity (under the capability/operation taxon) and `docs/vision/notes/vsm-alignment.md`.

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

### `resource` — runtime resource block

A single entity declaring runtime limits. Each limit is a property — the cascade resolves them independently, and `restrictive_direction="min"` ensures the tightest bound wins.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `name` | str | no | Resource block name |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `memory` | str | <= (min) | Memory limit with unit (e.g. `512MB`, `1GB`) |
| `wall-time` | str | <= (min) | Wall-clock time limit (e.g. `10m`, `1h`) |
| `cpu-time` | str | <= (min) | CPU time limit (e.g. `30s`, `5m`) |
| `max-fds` | int | <= (min) | Maximum open file descriptors |
| `tmpfs` | str | <= (min) | Tmpfs size for /tmp (e.g. `64MB`, `256MB`) |

**Selector examples:**
```css
resource { memory: 512MB; wall-time: 5m; cpu-time: 30s; max-fds: 128; }
mode#implement resource { memory: 1GB; wall-time: 30m; }
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

### `exec` — executable binary (parent: `world`)

Declares an executable binary available inside the jail. When a `tool` entity
has an `exec` property referencing an exec entity's name, the hook command
resolution uses that binary's `path` (or `search-path`-augmented PATH) for
dispatch.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `name` | str | | Executable name (e.g. `bash`, `python3`) |
| `path` | str | | Absolute path to the binary inside the jail |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `path` | str | exact | Absolute path to the binary inside the jail |
| `search-path` | str | exact | Colon-separated PATH directories for the jail (default: `/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin`) |

**Bridge property on `tool`:**

| Property | Type | Description |
|---|---|---|
| `exec` | str | Name of the exec entity this tool delegates to (e.g. `"bash"`) |

**Selector examples:**
```css
exec[name="bash"]    { path: "/bin/bash"; }
exec[name="python3"] { path: "/usr/bin/python3"; }
exec                 { search-path: "/bin:/usr/bin:/usr/local/bin"; }

/* Bridge: link tool to executable entity */
tool[name="Bash"] { exec: "bash"; }
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
| `visible` | bool | exact | Whether the tool is displayed to the delegate (default: follows `allow`) |
| `max-level` | int | `<=` | Maximum computation level. Tools above this are denied. |
| `require` | str | exact | Requirement for using this tool (e.g. `sandbox`) |
| `allow-pattern` | list | `pattern-in` | Glob patterns for allowed invocations |
| `deny-pattern` | list | `pattern-in` | Glob patterns for denied invocations |

**Note on `visible`:** distinct from `allow`. `allow: false` keeps the tool from being invoked; `visible: false` hides it from the delegate's menu entirely. Default: `visible` follows `allow` (not-allowed → not-visible). Explicit `visible: true` with `allow: false` is valid (surfaces the tool so the delegate knows it exists but is gated).

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

/* Cross-axis: mode-gated tool surface (see also "Cross-axis idioms" below) */
mode#explore tool                   { allow: false; }          /* default-deny in explore */
mode#explore tool[name="Read"]      { allow: true; }
mode#explore tool[name="Grep"]      { allow: true; }

mode#test tool[name="Edit"]         { allow: true; max-level: 3; }
mode#test tool[name="Bash"]         { allow: true; allow-pattern: "pytest *"; }
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

### `use` — action-axis permission (v0.5+)

A permissioned projection of a world resource onto a specific delegate. `use[of=...]` is the **action-axis** counterpart to world-axis resource properties — it expresses what permissions a delegate holds on a resource through a particular access path.

The `of=` attribute takes a selector string pointing into the world axis. `use` entities do not appear in the world hierarchy; they cross-link operation-axis with world-axis.

| Attribute | Type | Required | Description |
|---|---|---|---|
| `of` | str | | Selector matching the target world entity (e.g. `"file#/src/auth.py"`) |
| `of-kind` | str | | Kind-scoped: matches all uses of resources of this type (e.g. `"file"`, `"network"`) |
| `of-like` | str | | Prefix-like match against a world entity selector |

| Property | Type | Comparison | Description |
|---|---|---|---|
| `editable` | bool | exact | Whether the delegate's access path grants edit rights |
| `visible` | bool | exact | Whether the delegate's access path reveals the resource |
| `show` | str | exact | What the delegate sees through this access: `body`, `outline`, `signature` |
| `allow` | bool | exact | Whether the delegate can invoke this capability through this access |
| `deny` | str | exact | Deny pattern for invocations through this access |
| `allow-pattern` | list | `pattern-in` | Glob patterns for invocations permitted through this access |
| `deny-pattern` | list | `pattern-in` | Glob patterns for invocations denied through this access |

**Selector examples:**
```css
/* default deny-edit on all uses */
use { editable: false; }

/* grant edit on all Python source files in implement mode */
mode#implement use[of-like="file#/src"] { editable: true; }

/* specific use in a specific context */
inferencer#opus tool[name="Edit"] use[of="file#/src/auth.py"] { editable: true; }

/* tool-level gating via use */
use[of-kind="network"] { allow: false; }
use[of="exec#bash"] { allow: true; allow-pattern: "git *", "pytest *"; }
```

**Relationship to world-axis properties:** `use.editable` and `file.editable` are independent. A write succeeds only when both allow it: the resource must be editable (world-axis) AND the delegate must hold an editable use (action-axis). This matches the OS-level distinction between a read-only mount (world-axis) and a user's file-permission bits (action-axis).

---

## Cross-axis idioms

The v0.5 cascade lets selectors join multiple axes. A rule that names more axes is more specific (`axis_count`-first ordering). A handful of patterns come up often enough to be worth documenting.

### Mode-gated tool surface

When the goal is "in this mode, these tools are on the menu; others are not," reach for a `mode#<id> tool[name=...]` cross-axis rule — **not** `use[of="tool#..."]`. Tool-level rules are shorter, and tool presence is the capability-level concept, not an invocation concept.

```css
/* Default-deny all tools in explore mode, then allow a narrow set. */
mode#explore tool                 { allow: false; }
mode#explore tool[name="Read"]    { allow: true; }
mode#explore tool[name="Grep"]    { allow: true; }
mode#explore tool[name="Glob"]    { allow: true; }

/* Implement mode: default-allow except for destructive tools. */
mode#implement tool[name="Bash"]  { allow: false; }

/* Test mode: narrow Bash to test runners. */
mode#test tool[name="Bash"]       { allow: true; allow-pattern: "pytest *", "blq run *"; }

/* Review mode: read-only posture. */
mode#review tool                  { allow: false; }
mode#review tool[name="Read"]     { allow: true; }
mode#review tool[name="Grep"]     { allow: true; }
mode#review tool[name="Glob"]     { allow: true; }
```

`visible` follows `allow` by default, so these rules also control what the delegate sees in the tool menu. The compiler can downgrade to visibility-only if the enforcement altitude doesn't support denial.

### When to reach for `use[of="tool#..."]`

Use `use[of=...]` when the rule is specifically about **an invocation of the tool**, not the tool's mere presence. Examples:

```css
/* Tighten this specific access path — not the tool's existence. */
use[of="tool#Bash"] { allow-pattern: "git commit *", "git push *"; }

/* Per-resource permission on a tool that can touch many resources. */
mode#implement use[of="file#/src/auth.py"] { editable: true; }

/* Three-way: inferencer × tool × specific file. */
inferencer#opus tool[name="Edit"] use[of="file#/src/auth.py"] { editable: true; }
```

Rule of thumb:
- About **the tool** (exists, allowed, level, patterns) → `tool[name=...]`.
- About **an invocation / access path** (which file, under which mode, via which inferencer) → `use[of=...]`.

### Three-axis narrowing

Once you have principal + mode + (tool or use), a rule can express very specific policy concisely:

```css
principal#Teague mode#implement tool[name="Bash"] {
  allow-pattern: "git *", "pytest *";
}

principal#Teague mode#test use[of-like="file#tests/"] {
  editable: true;
}
```

Three axes → `axis_count=3` → these rules beat any two-axis overlap.

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
| `effect` | operation | v1.1 | Effect signature declared by a tool: read, write, exec, spawn. |
| `source` | world (proposed) | v1.1+ | Logical file grouping for monorepos. See [design notes](../vision/notes/world-as-root-and-linker-role.md). |

*Note: `observation` and `manifest` moved from this table to the `audit` taxon section above — they are registered in v0.5.*

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
@audit {                               ← audit taxon (S3* — outside world)
  observation#coach                    ← observation entries
  manifest#current
}

principal#Teague                       ← principal taxon (S5)

world#env-name                        ← world taxon (S0 — root of environment)
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
├── resource                          ← runtime limits (memory, wall-time, cpu, max-fds)
├── network                           ← network access
├── env[name="CI"]                    ← env vars
└── exec[name="bash"]                 ← executable binaries

tool[name="Read"]                     ← operation taxon / capability (S1 — flat, not nested)
tool[name="Edit"]
tool[name="Bash"]
kit[name="python-dev"]
use[of="file#/src/auth.py"]           ← action-axis cross-link (operation taxon)

hook[event="after-change"]            ← coordination taxon / state (S2)

job[id="run-1"]                       ← control taxon / state (S3)
budget[kind="wall-time"]

inferencer[model="claude-sonnet-4-6"]  ← intelligence taxon / actor (S4)
```

Navigate with CSS descendant selectors. Cross-taxon compound selectors (e.g. `world#dev tool[name="Bash"]`) are context qualifiers, not structural descent. VSM alias names (`operation`, `coordination`, `control`, `intelligence`) are interchangeable with the legacy names (`capability`, `state`, `actor`).
