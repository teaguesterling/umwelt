# umwelt

**Define what an AI agent can see, edit, call, and trigger — in a file that reads like CSS.**

```css
world#auth-fix {
  file[path^="src/auth/"] { editable: true; }
  file[path^="src/"]      { editable: false; }
  tool[name="Read"]        { allow: true; }
  tool[name="Edit"]        { allow: true; }
  tool[name="Bash"]        { allow: false; }
  network                  { deny: "*"; }
  resource                 { memory: 512MB; wall-time: 5m; }
  hook[event="after-change"] {
    run: "pytest tests/auth/ -x";
    run: "ruff check src/auth/";
  }
}
```

This view says: the agent can edit auth files (everything else is read-only), use Read and Edit but not Bash, has no network, 512MB of memory, 5 minutes, and must pass tests after every change.

umwelt parses this, builds a virtual workspace from it, and — with enforcement compilers — translates it into whatever config format your sandbox tool already accepts (nsjail textproto, bwrap argv, lackpy namespace, kibitzer hooks).

## Why

Every tool in the AI agent stack has its own way to say "the agent can do X but not Y": nsjail has protobuf textproto, bwrap has argv flags, lackpy has namespace dicts, kibitzer has hook rules, Claude Code has settings.json. They're all describing the same thing in different languages.

umwelt is the **common language**. Write one view file. Every enforcement tool reads the parts it can enforce.

## Install

```bash
pip install -e ".[dev]"    # from source
```

Requires Python 3.10+.

## Quick start

```bash
# Parse a view and print the AST
umwelt parse src/umwelt/_fixtures/auth-fix.umw

# Structural summary grouped by taxon
umwelt inspect src/umwelt/_fixtures/auth-fix.umw

# Check: parse + validate + report compiler coverage
umwelt check src/umwelt/_fixtures/auth-fix.umw

# Dry-run: resolve cascade and show per-entity properties
umwelt dry-run src/umwelt/_fixtures/auth-fix.umw
```

## Write a view

A view is a `.umw` file. It looks like CSS because it IS CSS — selectors match entities, declarations attach policy, the cascade resolves conflicts.

```css
/* The simplest view: one file, editable */
file[path="src/main.py"] { editable: true; }
```

Build up from there:

```css
/* Multiple files with cascade — later rules override earlier ones */
file[path^="src/"]      { editable: false; }   /* everything read-only */
file[path^="src/auth/"] { editable: true; }    /* except auth */

/* Tool restrictions */
tool[name="Read"] { allow: true; }
tool[name="Bash"] { allow: false; }

/* Run tests after any change */
hook[event="after-change"] { run: "pytest tests/auth/ -x"; }

/* Resource limits */
resource { memory: 512MB; wall-time: 5m; }
network { deny: "*"; }
```

Or use the shorthand @ syntax if you prefer:

```css
@source("src/auth/**/*.py") { * { editable: true; } }
@tools { allow: Read, Edit; deny: Bash; }
@after-change { test: pytest tests/auth/ -x; }
@budget { memory: 512MB; wall-time: 5m; }
@network { deny: *; }
```

Both forms compile to the same thing. Use whichever is clearer. See the [Writing Views Guide](docs/guide/writing-views.md) for the full tutorial.

## Multiple environments in one file

Name your environments with `world#name`:

```css
/* Shared defaults */
network { deny: "*"; }

/* Development */
world#dev file { editable: true; }
world#dev tool[name="Bash"] { allow: true; max-level: 4; }

/* CI */
world#ci file { editable: false; }
world#ci tool[name="Bash"] { max-level: 2; }
world#ci resource { memory: 512MB; }
```

Resolve against a specific environment: `umwelt dry-run --world dev project.umw`.

## How it works

umwelt has a plugin architecture. The core knows nothing about files, tools, or networks — it knows about **selectors** and **cascade**. Consumers register their own entity types:

- **world** taxon: files, directories, mounts, resources, network, env vars
- **capability** taxon: tools, kits, computation levels
- **state** taxon: hooks, jobs, budgets

Each taxon provides a matcher (how to evaluate selectors against its world) and can provide compilers (how to translate resolved policy into enforcement configs).

When the selector descends from one domain into another — filesystem into AST, for example — that's a **pivot**:

```css
file[path="src/auth/login.py"] node.function#authenticate { show: body; }
```

The `file → node` boundary is where the filesystem matcher hands off to the AST matcher (sitting_duck / pluckit). Same grammar, different world model.

See [How umwelt Works](docs/guide/how-it-works.md) for the full architectural picture.

## Status

**v0.6.0** — current release. What's new since v0.5:

- **Resource block model** — single `resource` entity with properties replaces per-resource singletons
- **World state layer** (`umwelt.world`) — YAML world files with shorthand expansion, vocabulary validation, three-level materialization. `umwelt materialize` CLI command
- **PolicyEngine** (`umwelt.policy`) — consumer-facing Python API over compiled SQLite. `from_files`, `from_db`, programmatic builder. Resolve, trace, lint, select, check, require. COW `extend()` for fork-and-specialize
- **Mode filtering** — `mode#review tool { allow: false }` gates rules by active mode. Both in-memory cascade and SQL backends
- **Fixed constraints** — post-cascade clamping for safety-critical properties
- **CompositeMatcher** — multiple matchers per taxon
- **Plugin autodiscovery** — entry point registration for third-party plugins
- **832 tests**, mypy strict, ruff clean

## The ecosystem

umwelt is the common language connecting these tools:

| Tool | What it does | How it connects to umwelt |
|---|---|---|
| [lackpy](https://github.com/teaguesterling/lackpy) | Delegate orchestration | Consumes views as runtime config |
| [blq](https://github.com/teaguesterling/lq) | Build log query | Provides observations for the ratchet |
| [pluckit](https://github.com/teaguesterling/pluckit) | CSS selectors for code | Evaluates `node` selectors inside files |
| [kibitzer](https://github.com/teaguesterling/kibitzer) | In-session coaching | Enforces tool restrictions at semantic altitude |
| [agent-riggs](https://github.com/teaguesterling/agent-riggs) | Cross-session auditor | Consumes views as data for pattern discovery |
| [sitting_duck](https://github.com/teaguesterling/sitting_duck) | DuckDB AST extension | Provides the AST matcher for source-code pivots |
| [jetsam](https://github.com/teaguesterling/jetsam) | Git state management | Git-state entities in a future taxon |
| [fledgling](https://github.com/teaguesterling/fledgling) | Code navigation MCP | Tool entities in the capability taxon |

The theoretical foundation is in [The Ma of Multi-Agent Systems](https://judgementalmonad.com/blog/ma/00-intro). The practitioner companion is [Ratchet Fuel](https://judgementalmonad.com/blog/fuel/). umwelt is the concrete tool that implements the policy layer those series describe.

## Development

```bash
pip install -e ".[dev]"
pytest -q              # 832 tests
ruff check src/ tests/ # lint
mypy src/              # type check (strict)
```

## License

MIT — see [LICENSE](LICENSE).
