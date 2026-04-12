# umwelt v0.2 nsjail Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first enforcement compiler — translating resolved umwelt views into nsjail protobuf textproto configs that nsjail accepts via `--config`.

**Architecture:** The compiler is a pure function `compile(resolved_view, workspace_root="/workspace") -> str` that walks the world-taxon entries of a `ResolvedView` and emits textproto. It reads file editability → mount stanzas, resource limits → rlimits/time_limit, network deny → clone_newnet, env allow → envar lines. Everything outside the OS altitude (tools, hooks, actor qualifiers) is silently dropped. The runner is a thin convenience wrapper: compile → write temp file → `subprocess.run(["nsjail", "--config", tempfile, "--", *command])`.

**Tech Stack:** Python 3.10+, existing umwelt core + sandbox consumer. No protobuf library — textproto is hand-rolled (it's a narrow subset: scalars, strings, nested messages).

**Spec reference:** `docs/vision/compilers/nsjail.md` (the full mapping table and worked example).

**Prerequisite:** v0.1.0 tagged, 338 tests passing, sandbox vocabulary registered with world-as-root.

---

## File structure

```
src/umwelt/sandbox/compilers/
├── __init__.py               # registers nsjail compiler at import (Task 0)
├── nsjail.py                 # the compiler (Tasks 0-2)
└── _value_parser.py          # parse "512MB" → int, "60s" → int (Task 0)

src/umwelt/sandbox/runners/
├── __init__.py
└── nsjail.py                 # convenience runner (Task 4)

src/umwelt/_fixtures/expected/
└── nsjail/
    ├── minimal.textproto     # expected output for minimal.umw (Task 3)
    ├── auth-fix.textproto    # expected output for auth-fix.umw (Task 3)
    └── readonly-exploration.textproto (Task 3)

tests/sandbox/
├── test_value_parser.py      # Task 0
├── test_nsjail_compiler.py   # Tasks 1-2
├── test_nsjail_snapshots.py  # Task 3
├── test_nsjail_runner.py     # Task 4
└── test_cli_compile.py       # Task 5

Also modifies:
- src/umwelt/cli.py           # add `compile` and `run` subcommands (Task 5)
```

---

## Task breakdown

**6 tasks:**
- Task 0: Value parser + compiler skeleton with mount emission
- Task 1: Network, resource limits, env passthrough
- Task 2: Full textproto document emission
- Task 3: Snapshot tests against fixture expected outputs
- Task 4: Runner module
- Task 5: CLI compile + run subcommands + polish

---

### Task 0: Value parser + compiler skeleton with mount emission

**Files:**
- Create: `src/umwelt/sandbox/compilers/_value_parser.py`
- Create: `src/umwelt/sandbox/compilers/__init__.py`
- Create: `src/umwelt/sandbox/compilers/nsjail.py`
- Create: `tests/sandbox/test_value_parser.py`
- Create: `tests/sandbox/test_nsjail_compiler.py`

**Step 1:** Create the value parser — a utility that converts view declaration values into the units nsjail expects:

```python
# src/umwelt/sandbox/compilers/_value_parser.py
"""Parse view declaration values into nsjail-native units."""

import re

_SIZE_PATTERN = re.compile(r'^(\d+)\s*(KB|MB|GB|TB)?$', re.IGNORECASE)
_TIME_PATTERN = re.compile(r'^(\d+)\s*(ms|s|m|h)?$', re.IGNORECASE)


def parse_memory_mb(value: str) -> int:
    """Parse a memory value like '512MB' into megabytes (nsjail's rlimit_as unit)."""
    m = _SIZE_PATTERN.match(value.strip())
    if not m:
        raise ValueError(f"cannot parse memory value: {value!r}")
    num = int(m.group(1))
    unit = (m.group(2) or "MB").upper()
    if unit == "KB":
        return max(1, num // 1024)
    if unit == "MB":
        return num
    if unit == "GB":
        return num * 1024
    if unit == "TB":
        return num * 1024 * 1024
    return num


def parse_time_seconds(value: str) -> int:
    """Parse a time value like '60s' or '5m' into seconds."""
    m = _TIME_PATTERN.match(value.strip())
    if not m:
        raise ValueError(f"cannot parse time value: {value!r}")
    num = int(m.group(1))
    unit = (m.group(2) or "s").lower()
    if unit == "ms":
        return max(1, num // 1000)
    if unit == "s":
        return num
    if unit == "m":
        return num * 60
    if unit == "h":
        return num * 3600
    return num


def parse_size_for_tmpfs(value: str) -> str:
    """Parse a size value into the format nsjail's tmpfs options expect (e.g. '64M')."""
    m = _SIZE_PATTERN.match(value.strip())
    if not m:
        raise ValueError(f"cannot parse size value: {value!r}")
    num = int(m.group(1))
    unit = (m.group(2) or "MB").upper()
    if unit == "KB":
        return f"{num}K"
    if unit == "MB":
        return f"{num}M"
    if unit == "GB":
        return f"{num}G"
    return f"{num}M"
```

**Step 2:** Write value parser tests:

```python
# tests/sandbox/test_value_parser.py
from umwelt.sandbox.compilers._value_parser import (
    parse_memory_mb, parse_time_seconds, parse_size_for_tmpfs,
)

def test_memory_mb():
    assert parse_memory_mb("512MB") == 512
    assert parse_memory_mb("1GB") == 1024
    assert parse_memory_mb("256") == 256  # default MB
    assert parse_memory_mb("512mb") == 512  # case insensitive

def test_time_seconds():
    assert parse_time_seconds("60s") == 60
    assert parse_time_seconds("5m") == 300
    assert parse_time_seconds("1h") == 3600
    assert parse_time_seconds("60") == 60  # default seconds

def test_tmpfs_size():
    assert parse_size_for_tmpfs("64MB") == "64M"
    assert parse_size_for_tmpfs("1GB") == "1G"
```

**Step 3:** Create the compiler skeleton with mount emission from file entities:

```python
# src/umwelt/sandbox/compilers/nsjail.py
"""Compile a resolved umwelt view into nsjail protobuf textproto.

The compiler reads OS-altitude constructs from the resolved view:
- file entities → mount stanzas (bind mounts with rw based on editable)
- mount entities → mount stanzas (direct source/dest mapping)
- resource entities → rlimits and time_limit
- network entities → clone_newnet
- env entities → envar passthrough

Everything else (tools, hooks, actors, state) is silently dropped —
those are enforced at other altitudes.

See docs/vision/compilers/nsjail.md for the full mapping table.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers._value_parser import (
    parse_memory_mb, parse_time_seconds, parse_size_for_tmpfs,
)


@dataclass
class NsjailConfig:
    """In-memory representation of the nsjail textproto being built."""
    name: str = "umwelt-sandbox"
    hostname: str = "umwelt"
    time_limit: int | None = None
    clone_newnet: bool = False
    rlimit_as: int | None = None
    rlimit_cpu: int | None = None
    rlimit_nofile: int | None = None
    mounts: list[dict[str, Any]] = field(default_factory=list)
    envars: list[str] = field(default_factory=list)


class NsjailCompiler:
    """Compiler protocol implementation for nsjail."""
    target_name = "nsjail"
    target_format = "textproto"
    altitude = "os"

    def compile(self, view: ResolvedView, workspace_root: str = "/workspace") -> str:
        cfg = NsjailConfig()
        self._compile_world(cfg, view, workspace_root)
        return _emit_textproto(cfg)

    def _compile_world(self, cfg: NsjailConfig, view: ResolvedView, root: str) -> None:
        # Walk world-taxon entries
        for entity, props in view.entries("world"):
            entity_type = type(entity).__name__
            if entity_type == "FileEntity":
                self._compile_file(cfg, entity, props, root)
            elif entity_type == "MountEntity":
                self._compile_mount(cfg, entity, props)
            elif entity_type == "ResourceEntity":
                self._compile_resource(cfg, entity, props)
            elif entity_type == "NetworkEntity":
                self._compile_network(cfg, entity, props)
            elif entity_type == "EnvEntity":
                self._compile_env(cfg, entity, props)

    def _compile_file(self, cfg, entity, props, root):
        path = getattr(entity, "path", "")
        editable = props.get("editable", "false").lower() == "true"
        if path.startswith("/"):
            dst = path
        else:
            dst = f"{root}/{path}"
        src = str(getattr(entity, "abs_path", path))
        cfg.mounts.append({
            "src": src, "dst": dst, "is_bind": True, "rw": editable,
        })

    def _compile_mount(self, cfg, entity, props):
        path = getattr(entity, "path", "")
        source = props.get("source", path)
        readonly = props.get("readonly", "false").lower() == "true"
        mount_type = props.get("type", "bind")
        if mount_type == "tmpfs":
            size = props.get("size", "64M")
            cfg.mounts.append({
                "dst": path, "fstype": "tmpfs", "is_bind": False,
                "options": f"size={parse_size_for_tmpfs(size)}",
            })
        else:
            cfg.mounts.append({
                "src": source, "dst": path, "is_bind": True, "rw": not readonly,
            })

    def _compile_resource(self, cfg, entity, props):
        kind = getattr(entity, "kind", "")
        limit = props.get("limit", "")
        if not limit:
            return
        if kind == "memory":
            cfg.rlimit_as = parse_memory_mb(limit)
        elif kind == "wall-time":
            cfg.time_limit = parse_time_seconds(limit)
        elif kind == "cpu-time":
            cfg.rlimit_cpu = parse_time_seconds(limit)
        elif kind == "max-fds":
            cfg.rlimit_nofile = int(limit)
        elif kind == "tmpfs":
            cfg.mounts.append({
                "dst": "/tmp", "fstype": "tmpfs", "is_bind": False,
                "options": f"size={parse_size_for_tmpfs(limit)}",
            })

    def _compile_network(self, cfg, entity, props):
        if props.get("deny", "") == "*":
            cfg.clone_newnet = True

    def _compile_env(self, cfg, entity, props):
        if props.get("allow", "false").lower() == "true":
            name = getattr(entity, "name", "")
            if name:
                cfg.envars.append(name)


def _emit_textproto(cfg: NsjailConfig) -> str:
    """Hand-roll the textproto output."""
    lines: list[str] = []
    lines.append(f'name: "{cfg.name}"')
    lines.append(f'hostname: "{cfg.hostname}"')
    lines.append("")
    if cfg.time_limit is not None:
        lines.append(f"time_limit: {cfg.time_limit}")
        lines.append("")
    if cfg.clone_newnet:
        lines.append("clone_newnet: true")
        lines.append("")
    if cfg.rlimit_as is not None:
        lines.append(f"rlimit_as: {cfg.rlimit_as}")
        lines.append("rlimit_as_type: SOFT")
        lines.append("")
    if cfg.rlimit_cpu is not None:
        lines.append(f"rlimit_cpu: {cfg.rlimit_cpu}")
        lines.append("")
    if cfg.rlimit_nofile is not None:
        lines.append(f"rlimit_nofile: {cfg.rlimit_nofile}")
        lines.append("")
    for mount in cfg.mounts:
        lines.append("mount {")
        if "src" in mount:
            lines.append(f'  src: "{mount["src"]}"')
        lines.append(f'  dst: "{mount["dst"]}"')
        if "fstype" in mount:
            lines.append(f'  fstype: "{mount["fstype"]}"')
        lines.append(f'  is_bind: {"true" if mount.get("is_bind") else "false"}')
        if mount.get("rw") is not None:
            lines.append(f'  rw: {"true" if mount["rw"] else "false"}')
        if "options" in mount:
            lines.append(f'  options: "{mount["options"]}"')
        lines.append("}")
        lines.append("")
    for var in cfg.envars:
        lines.append(f'envar: "{var}"')
    return "\n".join(lines).strip() + "\n"
```

**Step 4:** Create `src/umwelt/sandbox/compilers/__init__.py`:

```python
"""Sandbox enforcement compilers.

Importing this module registers available compilers with the core registry.
"""
from umwelt.compilers import register as register_compiler
from umwelt.sandbox.compilers.nsjail import NsjailCompiler

def register_sandbox_compilers() -> None:
    register_compiler("nsjail", NsjailCompiler())
```

**Step 5:** Write initial compiler tests — mount emission from file entities:

```python
# tests/sandbox/test_nsjail_compiler.py (initial version — Tasks 1-2 expand)
"""Tests for the nsjail compiler."""
from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.nsjail import NsjailCompiler
from umwelt.sandbox.entities import FileEntity
from pathlib import Path


def test_file_editable_true_emits_rw_mount():
    rv = ResolvedView()
    rv.add("world", FileEntity(path="src/auth/login.py", abs_path=Path("/project/src/auth/login.py"), name="login.py"), {"editable": "true"})
    compiler = NsjailCompiler()
    output = compiler.compile(rv)
    assert 'src: "/project/src/auth/login.py"' in output
    assert 'dst: "/workspace/src/auth/login.py"' in output
    assert "rw: true" in output


def test_file_editable_false_emits_ro_mount():
    rv = ResolvedView()
    rv.add("world", FileEntity(path="src/common/util.py", abs_path=Path("/project/src/common/util.py"), name="util.py"), {"editable": "false"})
    compiler = NsjailCompiler()
    output = compiler.compile(rv)
    assert "rw: false" in output


def test_absolute_path_mirrors():
    rv = ResolvedView()
    rv.add("world", FileEntity(path="/tmp/work/data.txt", abs_path=Path("/tmp/work/data.txt"), name="data.txt"), {"editable": "true"})
    compiler = NsjailCompiler()
    output = compiler.compile(rv)
    assert 'dst: "/tmp/work/data.txt"' in output


def test_empty_view_emits_minimal_config():
    rv = ResolvedView()
    compiler = NsjailCompiler()
    output = compiler.compile(rv)
    assert 'name: "umwelt-sandbox"' in output
    assert 'hostname: "umwelt"' in output
```

**Step 6:** Run tests, verify, commit.

Commit: `feat(sandbox/compilers): nsjail compiler skeleton with mount emission and value parser`

---

### Task 1: Network, resource limits, env passthrough

Extend `test_nsjail_compiler.py` with tests for:

```python
def test_network_deny_all_emits_clone_newnet():
    rv = ResolvedView()
    rv.add("world", NetworkEntity(), {"deny": "*"})
    output = NsjailCompiler().compile(rv)
    assert "clone_newnet: true" in output

def test_memory_limit():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(kind="memory"), {"limit": "512MB"})
    output = NsjailCompiler().compile(rv)
    assert "rlimit_as: 512" in output

def test_wall_time_limit():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(kind="wall-time"), {"limit": "60s"})
    output = NsjailCompiler().compile(rv)
    assert "time_limit: 60" in output

def test_cpu_time_limit():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(kind="cpu-time"), {"limit": "30s"})
    output = NsjailCompiler().compile(rv)
    assert "rlimit_cpu: 30" in output

def test_max_fds_limit():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(kind="max-fds"), {"limit": "128"})
    output = NsjailCompiler().compile(rv)
    assert "rlimit_nofile: 128" in output

def test_tmpfs_resource():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(kind="tmpfs"), {"limit": "64MB"})
    output = NsjailCompiler().compile(rv)
    assert 'fstype: "tmpfs"' in output
    assert 'options: "size=64M"' in output

def test_env_allow():
    rv = ResolvedView()
    rv.add("world", EnvEntity(name="CI"), {"allow": "true"})
    rv.add("world", EnvEntity(name="PYTHONPATH"), {"allow": "true"})
    output = NsjailCompiler().compile(rv)
    assert 'envar: "CI"' in output
    assert 'envar: "PYTHONPATH"' in output

def test_env_deny_emits_nothing():
    rv = ResolvedView()
    rv.add("world", EnvEntity(name="SECRET"), {"allow": "false"})
    output = NsjailCompiler().compile(rv)
    assert "SECRET" not in output

def test_tools_silently_dropped():
    rv = ResolvedView()
    from umwelt.sandbox.entities import ToolEntity
    rv.add("capability", ToolEntity(name="Bash"), {"allow": "false"})
    output = NsjailCompiler().compile(rv)
    assert "Bash" not in output

def test_hooks_silently_dropped():
    rv = ResolvedView()
    from umwelt.sandbox.entities import HookEntity
    rv.add("state", HookEntity(event="after-change"), {"run": "pytest"})
    output = NsjailCompiler().compile(rv)
    assert "pytest" not in output
```

Commit: `feat(sandbox/compilers): nsjail network, rlimits, env, and altitude filtering`

---

### Task 2: Full textproto document — the worked example

Test that the compiler produces the full textproto from the `nsjail.md` worked example:

```python
def test_full_worked_example():
    """The worked example from docs/vision/compilers/nsjail.md."""
    rv = ResolvedView()
    rv.add("world", FileEntity(path="src/auth", abs_path=Path("src/auth"), name="auth"), {"editable": "true"})
    rv.add("world", FileEntity(path="src/common", abs_path=Path("src/common"), name="common"), {"editable": "false"})
    rv.add("world", FileEntity(path="/tmp/work", abs_path=Path("/tmp/work"), name="work"), {"editable": "true"})
    rv.add("world", NetworkEntity(), {"deny": "*"})
    rv.add("world", ResourceEntity(kind="memory"), {"limit": "512MB"})
    rv.add("world", ResourceEntity(kind="wall-time"), {"limit": "60s"})
    rv.add("world", ResourceEntity(kind="tmpfs"), {"limit": "64MB"})
    rv.add("world", EnvEntity(name="CI"), {"allow": "true"})
    # These should be silently dropped:
    rv.add("capability", ToolEntity(name="Read"), {"allow": "true"})
    rv.add("state", HookEntity(event="after-change"), {"run": "pytest"})

    output = NsjailCompiler().compile(rv)

    # Verify key sections present
    assert 'name: "umwelt-sandbox"' in output
    assert "time_limit: 60" in output
    assert "clone_newnet: true" in output
    assert "rlimit_as: 512" in output
    # Three mounts: src/auth (rw), src/common (ro), /tmp/work (rw), plus tmpfs /tmp
    assert output.count("mount {") == 4
    assert 'envar: "CI"' in output
    # Tools and hooks NOT in output
    assert "Read" not in output
    assert "pytest" not in output
```

Commit: `test(sandbox/compilers): nsjail full worked-example textproto verification`

---

### Task 3: Snapshot tests against fixture expected outputs

Create expected textproto files for each fixture view:

- `src/umwelt/_fixtures/expected/nsjail/minimal.textproto`
- `src/umwelt/_fixtures/expected/nsjail/auth-fix.textproto`
- `src/umwelt/_fixtures/expected/nsjail/readonly-exploration.textproto`

Write a test that:
1. Registers sandbox vocabulary + sugar + compilers
2. Parses each fixture .umw file
3. Resolves the view
4. Compiles to nsjail
5. Compares output to the expected .textproto file

This is a regression test: any change to the compiler's output triggers a snapshot mismatch.

Note: the fixture views use file selectors like `file[path^="src/auth/"]`. These won't match any real files when resolved (no filesystem to match against). The snapshot test should use a synthetic ResolvedView that represents what the view WOULD resolve to against a known project tree, or test with a temp directory. The simpler approach: build a ResolvedView by hand for each fixture and test the compiler directly. This tests the compiler, not the full pipeline (which is tested in integration).

Commit: `test(sandbox/compilers): nsjail snapshot tests against expected textproto`

---

### Task 4: Runner module

Create `src/umwelt/sandbox/runners/nsjail.py`:

```python
"""Convenience runner: compile a view → write temp config → invoke nsjail."""
import os
import tempfile
import subprocess
from dataclasses import dataclass
from pathlib import Path
from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.nsjail import NsjailCompiler


@dataclass
class NsjailResult:
    returncode: int
    stdout: str
    stderr: str
    config_path: str  # the temp config file path (for debugging)


def run_in_nsjail(
    resolved_view: ResolvedView,
    command: list[str],
    workspace_root: str = "/workspace",
    timeout: float | None = None,
) -> NsjailResult:
    compiler = NsjailCompiler()
    textproto = compiler.compile(resolved_view, workspace_root=workspace_root)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".cfg", prefix="umwelt-nsjail-", delete=False
    ) as f:
        f.write(textproto)
        config_path = f.name

    try:
        result = subprocess.run(
            ["nsjail", "--config", config_path, "--"] + command,
            capture_output=True, text=True,
            timeout=timeout,
        )
        return NsjailResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            config_path=config_path,
        )
    except FileNotFoundError:
        return NsjailResult(
            returncode=-1, stdout="",
            stderr="nsjail binary not found on PATH",
            config_path=config_path,
        )
    except subprocess.TimeoutExpired:
        return NsjailResult(
            returncode=-2, stdout="",
            stderr="nsjail timed out",
            config_path=config_path,
        )
    finally:
        try:
            os.unlink(config_path)
        except OSError:
            pass
```

Tests: mock-based (don't require real nsjail). Plus a skip-if-not-installed integration test.

Commit: `feat(sandbox/runners): nsjail convenience runner`

---

### Task 5: CLI compile + run subcommands + polish

Extend `src/umwelt/cli.py`:

**`umwelt compile --target nsjail view.umw`** — parse, resolve, compile, print to stdout.

**`umwelt run --target nsjail view.umw -- python script.py`** — parse, resolve, compile, write temp, invoke nsjail.

Register the nsjail compiler in `_load_default_vocabulary()`:

```python
def _load_default_vocabulary() -> None:
    try:
        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        from umwelt.sandbox.desugar import register_sandbox_sugar
        from umwelt.sandbox.compilers import register_sandbox_compilers
        register_sandbox_vocabulary()
        register_sandbox_sugar()
        register_sandbox_compilers()
    except ImportError:
        pass
```

Tests:
- `umwelt compile --target nsjail _fixtures/auth-fix.umw` exits 0 and outputs textproto
- `umwelt compile --target nsjail --help` shows usage
- `umwelt check _fixtures/auth-fix.umw` now reports "1 compiler registered: nsjail (os)"
- `umwelt compile --target nonexistent view.umw` exits 1 with error

CHANGELOG: add v0.2 entry. Version bump to `"0.2.0.dev0"`.

Commit: `feat(cli): add umwelt compile + run subcommands for nsjail`

---

## Self-review

**Spec coverage (docs/vision/compilers/nsjail.md):**

| Spec section | Covered by |
|---|---|
| Mount emission from @source | Task 0 (file entities → mounts) |
| Mount from mount entities | Task 0 (_compile_mount) |
| @network → clone_newnet | Task 1 |
| @budget → rlimits + time_limit | Task 1 |
| @env → envar | Task 1 |
| Constructs ignored (tools, hooks) | Task 1 (silently-dropped tests) |
| Worked example | Task 2 |
| Snapshot regression | Task 3 |
| Runner | Task 4 |
| CLI | Task 5 |

**Placeholder scan:** No TBD/TODO. All code blocks are complete.

**Type consistency:** `NsjailCompiler.compile(view: ResolvedView, workspace_root: str)` is consistent across all tasks. `NsjailConfig` fields match the textproto emission. Value parser functions match their call sites.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-12-umwelt-v02-nsjail.md`. Subagent-driven execution — dispatch as a single batch since there are only 6 tasks.
