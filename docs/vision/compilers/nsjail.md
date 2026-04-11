# Compiler: nsjail

*How umwelt compiles a view into nsjail's protobuf textproto configuration format. This is the OS-altitude enforcement compiler for filesystem, network, and resource bounds. umwelt emits textproto directly; it does not depend on `nsjail-python` or any other Python wrapper.*

## Summary

The `umwelt.compilers.nsjail` module takes a parsed `View` and emits a string of nsjail's protobuf textproto config — the format nsjail accepts via its `--config` flag. The output is a text document suitable for writing to a tempfile and passing to the `nsjail` binary as-is.

```python
from umwelt import parse
from umwelt.compilers import nsjail

view = parse("views/auth-fix.umw")
textproto: str = nsjail.to_textproto(view)

# Write to tempfile and run
with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg") as f:
    f.write(textproto)
    f.flush()
    subprocess.run(["nsjail", "--config", f.name, "--", "python", "delegate.py"])
```

Or use the convenience runner:

```python
from umwelt.runners import run_in_nsjail

result = run_in_nsjail(view, command=["python", "delegate.py"])
```

The compiler reads only the view constructs that have OS-altitude enforcement meaning: `@source` (for filesystem bind-mounts), `@network` (for network namespace control), `@budget` (for rlimits and timeouts), and `@env` (for environment variable passthrough). Every other at-rule (`@tools`, `@after-change`, `@namespace`, anything unknown) is silently dropped because nsjail cannot enforce at those altitudes.

## Scope: what nsjail compiles

The four at-rules nsjail understands, and the declarations inside them that map to nsjail config fields:

### `@source(path) { ... }`

Each `@source` block produces one or more `mount` entries in the nsjail config. The path from the block's argument becomes the source (real) path; the virtual workspace path becomes the destination (jail) path.

```
@source("src/auth") {
  * { editable: true; }
}
```

produces:

```
mount {
  src: "src/auth"
  dst: "/workspace/src/auth"
  is_bind: true
  rw: true
}
```

- `editable: true` → `rw: true` (writable bind-mount)
- `editable: false` or omitted → `rw: false` (read-only bind-mount)

When a block's path is absolute (`/tmp/scratch`), the destination path mirrors it. When relative (`src/auth`), the destination is relative to a configured workspace root (default: `/workspace`).

### `@network { ... }`

Maps to nsjail's network namespace flag.

| Declaration | nsjail textproto |
|---|---|
| `deny: *;` | `clone_newnet: true` (default behavior) |
| `allow: hostname;` (v1.1 only) | **v1: ignored with warning**; v1.1: requires DNS + proxy logic, not yet designed |

v1 supports only `deny: *`. Explicit allowlists for hostnames require either name resolution inside the jail (hard) or a proxy layer (out of scope). Defer.

If `@network` is absent from the view, nsjail's default is applied (network on). This is the opposite of the view language's intent; users should explicitly say `@network { deny: *; }` when they want isolation. The runner may warn when no `@network` block is present.

### `@budget { ... }`

Maps directly to nsjail's rlimit fields and the `time_limit` field.

| Declaration | nsjail textproto |
|---|---|
| `memory: 512MB;` | `rlimit_as: 512`, `rlimit_as_type: SOFT` |
| `wall-time: 60s;` | `time_limit: 60` |
| `cpu-time: 30s;` | `rlimit_cpu: 30` |
| `max-fds: 128;` | `rlimit_nofile: 128` |
| `tmpfs: 64MB;` | `mount { dst: "/tmp", fstype: "tmpfs", is_bind: false, options: "size=64M" }` |

Unit conversions:
- Memory: `KB` → 1/1024 MB, `MB` → 1, `GB` → 1024 (nsjail's `rlimit_as` is in MB)
- Time: `ms` → rounded to nearest second (nsjail is second-granular), `s` → 1, `m` → 60, `h` → 3600

Declarations missing from `@budget` mean "no limit on this dimension" — the corresponding nsjail field is omitted.

### `@env { ... }`

Maps to nsjail's `envar` passthrough.

```
@env { allow: CI, PYTHONPATH; }
```

produces:

```
envar: "CI"
envar: "PYTHONPATH"
```

`deny: *` (the default) means no `envar` entries are emitted, and nsjail starts the jailed process with a clean environment except for what's explicitly allowed.

Explicit assignments (`VAR = value`) are v1.1. v1 only supports passthrough.

## Full mapping table

For reference, every view construct the nsjail compiler acts on:

| View construct | nsjail textproto |
|---|---|
| `@source("path") { * { editable: true } }` | `mount { src: "path" dst: "/workspace/path" is_bind: true rw: true }` |
| `@source("path") { * { editable: false } }` | `mount { src: "path" dst: "/workspace/path" is_bind: true rw: false }` |
| `@source("path") { }` (default) | `mount { src: "path" dst: "/workspace/path" is_bind: true rw: false }` |
| `@source("/abs/path") { ... }` | `mount { src: "/abs/path" dst: "/abs/path" ... }` |
| `@network { deny: *; }` | `clone_newnet: true` |
| `@network { allow: host; }` | *v1 ignored with warning* |
| `@budget { memory: 512MB; }` | `rlimit_as: 512 rlimit_as_type: SOFT` |
| `@budget { wall-time: 60s; }` | `time_limit: 60` |
| `@budget { cpu-time: 30s; }` | `rlimit_cpu: 30` |
| `@budget { max-fds: 128; }` | `rlimit_nofile: 128` |
| `@budget { tmpfs: 64MB; }` | `mount { dst: "/tmp" fstype: "tmpfs" options: "size=64M" }` |
| `@env { allow: VAR; }` | `envar: "VAR"` |
| `@env { deny: *; }` | *no envar entries* |

## Constructs the nsjail compiler ignores

Silently dropped (not an error, but may emit a debug log):

- `@tools` — semantic altitude, enforced by hook layer or language validator
- `@after-change` — semantic altitude, dispatched by the umwelt runtime
- `@namespace` — language altitude, enforced by lackpy's validator
- Any unknown at-rule — forward compatibility
- Nested selector rules inside `@source` blocks (`.fn#main { ... }`) — these are workspace-builder concerns, not enforcement-layer concerns. The nsjail compiler only sees the `@source` block's path and the block's default editability. Selector-level extraction happens at the workspace builder, not at the nsjail compiler.

## Worked example

Input view:

```
@source("src/auth") {
  * { editable: true; }
}

@source("src/common") {
  * { editable: false; }
}

@source("/tmp/work") {
  * { editable: true; }
}

@network { deny: *; }

@budget {
  memory:    512MB;
  wall-time: 60s;
  tmpfs:     64MB;
}

@env { allow: CI; }

@tools { allow: Read, Edit; deny: Bash; }    # ignored
@after-change { test: pytest; }                # ignored
```

Emitted nsjail textproto:

```
name: "umwelt-sandbox"
hostname: "umwelt"

time_limit: 60

clone_newnet: true

rlimit_as: 512
rlimit_as_type: SOFT

mount {
  src: "src/auth"
  dst: "/workspace/src/auth"
  is_bind: true
  rw: true
}

mount {
  src: "src/common"
  dst: "/workspace/src/common"
  is_bind: true
  rw: false
}

mount {
  src: "/tmp/work"
  dst: "/tmp/work"
  is_bind: true
  rw: true
}

mount {
  dst: "/tmp"
  fstype: "tmpfs"
  is_bind: false
  options: "size=64M"
}

envar: "CI"
```

The `@tools` and `@after-change` blocks leave no trace in the nsjail config — they're handled by other layers. Running `nsjail --config <this> -- python delegate.py` produces a jailed process that can read `src/common`, edit `src/auth` and `/tmp/work`, has no network, has a 512MB memory limit and 60s wall-clock limit, and sees only the `CI` environment variable.

## Implementation shape

The compiler is ~200 lines of Python, hand-rolled. No protobuf library dependency. The structure:

```python
# umwelt/compilers/nsjail.py

from dataclasses import dataclass
from umwelt.ast import View, SourceBlock, NetworkBlock, BudgetBlock, EnvBlock

@dataclass
class Config:
    """An in-memory representation of the nsjail textproto we're building."""
    name: str = "umwelt-sandbox"
    hostname: str = "umwelt"
    time_limit: int | None = None
    clone_newnet: bool = False
    rlimit_as: int | None = None
    rlimit_cpu: int | None = None
    rlimit_nofile: int | None = None
    mounts: list[dict] = field(default_factory=list)
    envars: list[str] = field(default_factory=list)

def to_textproto(view: View, workspace_root: str = "/workspace") -> str:
    """Compile a view into nsjail protobuf textproto."""
    cfg = Config()
    
    for source in view.source_blocks:
        _compile_source(cfg, source, workspace_root)
    
    if view.network_block:
        _compile_network(cfg, view.network_block)
    
    if view.budget_block:
        _compile_budget(cfg, view.budget_block)
    
    if view.env_block:
        _compile_env(cfg, view.env_block)
    
    return _emit_textproto(cfg)

def _compile_source(cfg: Config, source: SourceBlock, root: str) -> None: ...
def _compile_network(cfg: Config, network: NetworkBlock) -> None: ...
def _compile_budget(cfg: Config, budget: BudgetBlock) -> None: ...
def _compile_env(cfg: Config, env: EnvBlock) -> None: ...
def _emit_textproto(cfg: Config) -> str: ...
```

The `_emit_textproto` function hand-rolls the textproto output. Textproto is simpler than wire-format protobuf: it's a line-oriented key-value format with `{ }` for nested messages and basic escaping for string values. The subset umwelt emits (strings, integers, booleans, nested messages) needs maybe 30 lines of emitter code.

## Testing strategy

Three layers:

1. **Unit tests**: each `_compile_*` function, then `to_textproto` end-to-end. Fixtures include every mapping-table row plus edge cases (missing blocks, unit conversion, absolute vs relative paths).

2. **Snapshot tests**: reference view files in `_fixtures/` with expected textproto output in `_fixtures/expected/nsjail/`. Regression-safe; any change to the compiler that produces different textproto triggers a snapshot mismatch.

3. **Integration tests** (skipped if `nsjail` binary not on PATH): run the emitted textproto through an actual nsjail invocation with a trivial command (`echo hello`), assert the command runs successfully. This is the end-to-end correctness check — does the textproto we emit actually work?

Optional: if `nsjail-python` is installed, parse the emitted textproto through its serializer as an extra validation step. This catches textproto escaping bugs without requiring a real nsjail binary.

## Textproto output format reference

For readers unfamiliar with protobuf textproto, the format umwelt emits is a narrow subset:

```
key: value              # scalar field (string, int, bool)
key: "quoted string"    # string field
key {                   # nested message
  nested_key: value
}
repeated_key: "item1"   # repeated field (one line per entry)
repeated_key: "item2"
```

That's the entire grammar umwelt needs. No imports, no options, no reserved ranges, no packed encoding. Hand-rolling is appropriate.

## Open questions

1. **Workspace root convention.** Currently `/workspace` is the default mount target for relative source paths. Is that the right default, or should it be `/srv/view` or `/umwelt` or something else? Bikeshed. `/workspace` is simple and unambiguous.

2. **How does nsjail learn the command to run?** The view doesn't specify the delegate command — that's a runtime concern. The nsjail compiler emits only the config; the caller (usually the umwelt runner or lackpy) provides the command via `nsjail --config X -- command args`. This split matches nsjail's usage convention and keeps umwelt out of the command-orchestration business.

3. **Should the compiler validate against nsjail's schema?** v1: no, hand-rolled output with snapshot tests. v1.1 may add optional schema validation if `nsjail-python` is importable.

4. **User identity and uid mapping.** nsjail has rich uid/gid mapping features (`uidmap`, `gidmap`). v1 doesn't use them — the delegate runs as the invoking user. v1.1 may add a `@identity` or `@user` at-rule if there's demand for uid remapping.

5. **Seccomp profiles.** nsjail supports seccomp filtering. v1 doesn't emit any — the delegate gets the default syscall set. v1.1 may add a `@syscalls` at-rule if seccomp becomes valuable for specific delegate scenarios.

6. **Non-standard nsjail features.** nsjail has many features umwelt doesn't expose (cgroups v2, capability dropping, PID limits, per-process resource limits). These can be added as new at-rules or as extensions to existing ones. v1 covers the common case; specialized users can still hand-write nsjail configs and combine them with umwelt-generated fragments.

## What this doc doesn't cover

- **nsjail's own documentation.** For the meaning of individual textproto fields, refer to the nsjail project: https://github.com/google/nsjail
- **The view format itself.** See [`../view-format.md`](../view-format.md).
- **Other compilers.** See [`bwrap.md`](./bwrap.md) and future `lackpy-namespace.md`, `kibitzer-hooks.md`.
- **Security analysis.** Threat model for the nsjail compiler in particular lives in the eventual `security.md`.
