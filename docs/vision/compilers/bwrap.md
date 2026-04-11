# Compiler: bwrap

*How umwelt compiles a view into bwrap's argv list. This is the OS-altitude enforcement compiler for users who prefer bubblewrap (the container runtime used by Flatpak and friends) over nsjail. umwelt emits argv directly; it does not depend on any Python wrapper for bwrap.*

## Summary

The `umwelt.compilers.bwrap` module takes a parsed `View` and emits a list of strings — the argv flags to prepend to a command when invoking bwrap. Unlike nsjail (which takes a config file), bwrap is configured entirely via command-line flags, so the compiler output is a flat list ready to be concatenated with the delegate command.

```python
from umwelt import parse
from umwelt.compilers import bwrap

view = parse("views/auth-fix.umw")
argv: list[str] = bwrap.to_argv(view)

# Concatenate with the command and run
cmd = ["bwrap"] + argv + ["--", "python", "delegate.py"]
subprocess.run(cmd)
```

Or use the convenience runner:

```python
from umwelt.runners import run_in_bwrap

result = run_in_bwrap(view, command=["python", "delegate.py"])
```

Like the nsjail compiler, bwrap reads only the view constructs with OS-altitude enforcement meaning: `@source`, `@network`, `@budget`, `@env`. Everything else is silently dropped.

## Why bwrap in addition to nsjail?

bwrap and nsjail solve overlapping problems with different trade-offs:

- **bwrap** is simpler, ships in most Linux distros as a package (`bubblewrap`), and is the runtime Flatpak uses. Good default for desktop Linux environments.
- **nsjail** is more featureful (seccomp, uid mapping, cgroups v2, rich resource limits), but less commonly installed. Better for production sandboxing.

Offering both gives users a choice without privileging one. Both are covered because they're the two OS-altitude sandboxes we actively use in the rigged suite. Firejail, Docker, systemd-run, and others can be added as additional compilers later.

## Scope: what bwrap compiles

### `@source(path) { ... }`

Each `@source` block produces one or more bind-mount flags.

```
@source("src/auth") {
  * { editable: true; }
}
```

produces:

```
--bind src/auth /workspace/src/auth
```

- `editable: true` → `--bind src dst` (writable bind-mount)
- `editable: false` or omitted → `--ro-bind src dst` (read-only bind-mount)

### `@network { ... }`

| Declaration | bwrap flag |
|---|---|
| `deny: *;` | `--unshare-net` |
| `allow: hostname;` (v1.1 only) | **v1: ignored with warning** |

### `@budget { ... }`

bwrap itself doesn't have resource-limit flags — it runs processes with the inherited ulimits. To enforce `@budget` under bwrap, umwelt wraps the delegate command with `ulimit` and `timeout` calls:

```
@budget {
  memory:    512MB;
  wall-time: 60s;
  max-fds:   128;
}
```

produces (conceptually — actual emission below):

```
timeout 60 sh -c "ulimit -v 524288; ulimit -n 128; exec <original command>"
```

or, more idiomatically, the runner shells out via `prlimit` and `timeout` when they're available on the target system.

| Declaration | Enforcement mechanism |
|---|---|
| `memory: 512MB;` | `prlimit --as=524288000` wrapper (or `ulimit -v`) |
| `wall-time: 60s;` | `timeout 60` wrapper |
| `cpu-time: 30s;` | `prlimit --cpu=30` (or `ulimit -t`) |
| `max-fds: 128;` | `prlimit --nofile=128` (or `ulimit -n`) |
| `tmpfs: 64MB;` | `--tmpfs /tmp --size=64M` (bwrap flag) |

Note: the `@budget` declarations are not compiled into bwrap flags directly (except for `tmpfs`). They're compiled into a wrapper command that the runner uses when invoking the delegate. The bwrap compiler output is:

```python
{
    "argv": [...bwrap flags...],
    "wrapper": [...prlimit/timeout flags...],
}
```

The runner concatenates: `bwrap` + `argv` + `--` + `wrapper` + `delegate_command`.

This two-piece output is slightly different from the nsjail compiler's single textproto string. The difference reflects the underlying tools' conventions: nsjail's config file holds everything; bwrap's argv covers bind-mounts and namespaces, and resource limits need a wrapper command.

### `@env { ... }`

bwrap has `--setenv VAR value` and `--unsetenv VAR` flags. The compilation maps `allow: VAR` to `--setenv` using the caller's current environment value:

```python
# At compile time:
@env { allow: CI, PYTHONPATH; }

# Produces (using os.environ.get at runner time):
--setenv CI "$CI_value" --setenv PYTHONPATH "$PYTHONPATH_value"
```

`deny: *` (default) means no `--setenv` flags are emitted, and bwrap starts the process with the parent environment blanked via `--unsetenv`-all (or `--clearenv` if the bwrap version supports it).

## Full mapping table

| View construct | bwrap output |
|---|---|
| `@source("path") { * { editable: true } }` | `--bind path /workspace/path` |
| `@source("path") { * { editable: false } }` | `--ro-bind path /workspace/path` |
| `@source("path") { }` (default) | `--ro-bind path /workspace/path` |
| `@source("/abs/path") { ... }` | `--bind /abs/path /abs/path` (mirrors path) |
| `@network { deny: *; }` | `--unshare-net` |
| `@network { allow: host; }` | *v1 ignored with warning* |
| `@budget { memory: 512MB; }` | wrapper: `prlimit --as=524288000` |
| `@budget { wall-time: 60s; }` | wrapper: `timeout 60` |
| `@budget { cpu-time: 30s; }` | wrapper: `prlimit --cpu=30` |
| `@budget { max-fds: 128; }` | wrapper: `prlimit --nofile=128` |
| `@budget { tmpfs: 64MB; }` | bwrap flag: `--tmpfs /tmp --size=64M` |
| `@env { allow: VAR; }` | `--setenv VAR <current-value>` |
| `@env { deny: *; }` | `--clearenv` (or repeated `--unsetenv`) |

## Constructs the bwrap compiler ignores

Same as nsjail:

- `@tools` — semantic altitude
- `@after-change` — semantic altitude, dispatched by umwelt runtime
- `@namespace` — language altitude
- Unknown at-rules — forward compatibility
- Nested selector rules inside `@source` blocks — workspace-builder concern

## Worked example

Input view (same as nsjail example for side-by-side comparison):

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

Compiler output (as a Python dict for clarity):

```python
{
    "argv": [
        "--bind",     "src/auth",    "/workspace/src/auth",
        "--ro-bind",  "src/common",  "/workspace/src/common",
        "--bind",     "/tmp/work",   "/tmp/work",
        "--unshare-net",
        "--tmpfs",    "/tmp",  "--size=64M",
        "--setenv",   "CI",   "<value of $CI at runner time>",
        "--clearenv",    # (placed before --setenv actually; see ordering note)
    ],
    "wrapper": [
        "timeout", "60",
        "prlimit", "--as=524288000",
    ],
}
```

The runner then invokes:

```bash
bwrap \
  --bind src/auth /workspace/src/auth \
  --ro-bind src/common /workspace/src/common \
  --bind /tmp/work /tmp/work \
  --unshare-net \
  --tmpfs /tmp --size=64M \
  --setenv CI <value> \
  -- \
  timeout 60 prlimit --as=524288000 python delegate.py
```

This achieves the same enforcement as the equivalent nsjail invocation, using bwrap's conventions.

## Ordering notes

bwrap processes flags in order, and some flags depend on others being evaluated first. The compiler's emitter follows this ordering:

1. `--clearenv` (if `@env { deny: *; }`) — must come before `--setenv` flags
2. `--setenv` flags — after clearenv
3. Bind-mount flags (`--bind`, `--ro-bind`) — order doesn't matter relative to each other, but all come after env setup
4. `--tmpfs` flags — typically after bind-mounts so /tmp replaces any inherited bind
5. Namespace-unshare flags (`--unshare-net`, `--unshare-pid`, etc.) — near the end
6. `--` separator
7. Wrapper command (`timeout`, `prlimit`) — outside bwrap's argument scope
8. Delegate command

The compiler's emitter handles this ordering automatically. Callers should not reorder the argv list.

## Implementation shape

~150 lines of Python, hand-rolled. Similar structure to the nsjail compiler but producing argv lists instead of textproto:

```python
# umwelt/compilers/bwrap.py

from dataclasses import dataclass, field
from umwelt.ast import View, SourceBlock, NetworkBlock, BudgetBlock, EnvBlock

@dataclass
class Compilation:
    argv: list[str] = field(default_factory=list)
    wrapper: list[str] = field(default_factory=list)

def to_argv(view: View, workspace_root: str = "/workspace") -> list[str]:
    """Compile a view into a bwrap argv list (flags only, no command).
    
    For @budget enforcement that requires a wrapper command, use
    to_compilation() instead to get both pieces.
    """
    result = to_compilation(view, workspace_root)
    return result.argv

def to_compilation(view: View, workspace_root: str = "/workspace") -> Compilation:
    """Compile a view into both bwrap argv and wrapper command pieces."""
    result = Compilation()
    
    # Order matters for bwrap
    if view.env_block and view.env_block.is_deny_all:
        result.argv.append("--clearenv")
    
    if view.env_block:
        for var in view.env_block.allow:
            result.argv.extend(["--setenv", var, _current_env_value(var)])
    
    for source in view.source_blocks:
        _compile_source(result, source, workspace_root)
    
    if view.budget_block and view.budget_block.tmpfs:
        result.argv.extend(["--tmpfs", "/tmp", "--size=" + view.budget_block.tmpfs])
    
    if view.network_block and view.network_block.is_deny_all:
        result.argv.append("--unshare-net")
    
    if view.budget_block:
        _compile_budget_wrapper(result, view.budget_block)
    
    return result

def _compile_source(result: Compilation, source: SourceBlock, root: str) -> None: ...
def _compile_budget_wrapper(result: Compilation, budget: BudgetBlock) -> None: ...
def _current_env_value(var: str) -> str: ...
```

The `_current_env_value` helper reads from `os.environ` at compile time — which means the compiler is no longer strictly pure. This is a small exception to the "compilers are pure transformations" rule, and it's only necessary because bwrap's `--setenv` requires explicit values. Users who want fully deterministic compilation can pass an explicit `env_source: dict[str, str]` kwarg to override `os.environ`.

## Testing strategy

Same three-layer approach as the nsjail compiler:

1. **Unit tests** for each mapping row
2. **Snapshot tests** comparing emitted argv against reference fixtures
3. **Integration tests** (skipped if `bwrap` not on PATH) that run the actual bwrap binary with the emitted argv and assert exit codes

One extra test category for bwrap: **wrapper composition tests**. Since `@budget` produces a wrapper command that gets concatenated outside the bwrap argv, the tests need to verify that `run_in_bwrap(view, command=[...])` correctly assembles: `bwrap ARGV -- WRAPPER COMMAND`. Fixtures include budget-only views to exercise the wrapper path.

## Differences from nsjail

Summary for users choosing between the two compilers:

| Feature | nsjail | bwrap |
|---|---|---|
| Config format | textproto file | command-line argv |
| Resource limits | native (rlimits) | wrapper (prlimit/timeout) |
| Network isolation | native | native (unshare-net) |
| Bind mounts | native | native |
| tmpfs | native | native |
| Seccomp | native | not in v1 |
| uid/gid mapping | rich | basic (via `--unshare-user-try`) |
| Installation | less common | ships with most distros |
| umwelt output | `str` (textproto) | `list[str]` + optional wrapper |

For most delegate sandboxing use cases, bwrap is sufficient and easier to install. For production-grade isolation with seccomp and uid remapping, nsjail is the stronger choice. umwelt supports both so the user can pick based on their environment.

## Open questions

1. **Wrapper command availability.** The bwrap runner depends on `timeout` and `prlimit` being on PATH inside the sandbox. `timeout` ships with GNU coreutils (ubiquitous on Linux). `prlimit` ships with util-linux (also ubiquitous). But if the view's bind-mounts exclude `/usr/bin`, the wrapper commands may not be reachable from inside the jail. Mitigation: the runner can statically resolve the wrapper binaries at compile time and either bind-mount them explicitly or report an error. v1 assumes they're reachable and produces an error at runtime if not.

2. **`--clearenv` vs `--unsetenv *`.** Some older bwrap versions don't have `--clearenv`. The compiler should detect bwrap version and fall back to iterating `os.environ` with `--unsetenv` per variable. v1: assume modern bwrap; fall back is v1.1 work.

3. **Absolute path destinations.** When an `@source("src/auth")` block uses a relative path, the destination is `/workspace/src/auth`. When the path is absolute (`/etc/secrets`), umwelt currently mirrors it verbatim. Is that the right default, or should absolute paths get remapped under the workspace root too? v1: mirror verbatim; the runner can override via a `workspace_root` kwarg.

4. **User namespaces.** bwrap's `--unshare-user-try` enables user namespace isolation when available. This is generally desirable. Should it be on by default? v1: yes, on by default; an explicit `@identity { share-user: true; }` at-rule (v1.1) can opt out.

5. **Read-only rootfs.** A common bwrap pattern is `--ro-bind / /` to bind the host root as read-only, then overlay writable workspace bind-mounts. umwelt doesn't emit this by default — it only mounts the paths in `@source`. If the delegate needs access to `/usr/bin` etc., those must be in a `@source` block. Alternative: an implicit "mount the standard system paths read-only" default behavior. v1: no implicit mounts; explicit wins for clarity. v1.1 may add a `@system { include: standard-paths; }` convenience at-rule.

## What this doc doesn't cover

- **bwrap's own documentation.** See `man bwrap` or https://github.com/containers/bubblewrap.
- **The view format itself.** See [`../view-format.md`](../view-format.md).
- **Other compilers.** See [`nsjail.md`](./nsjail.md) for the alternative OS-altitude compiler and future compilers for lackpy namespace and kibitzer hooks.
