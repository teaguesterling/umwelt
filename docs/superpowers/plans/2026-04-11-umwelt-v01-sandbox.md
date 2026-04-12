# umwelt v0.1-sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first-party sandbox consumer of umwelt: real filesystem matching, workspace builder + writeback, hook dispatcher, and at-rule sugar desugaring — turning umwelt from an abstract policy engine into a tool that builds sandboxed workspaces from `.umw` files.

**Architecture:** The sandbox consumer (`src/umwelt/sandbox/`) registers the canonical `world`, `capability`, and `state` taxa against core umwelt's plugin registry at import time. It provides filesystem-backed matchers, a workspace builder with pluggable materialization strategies (symlink read-only + copy writable by default), writeback with hash-based violation detection, a hook dispatcher for `@after-change` subprocess execution, and desugaring rules that let the parser accept legacy at-rules (`@source`, `@tools`, `@after-change`, `@network`, `@budget`, `@env`) and convert them to entity-selector form during parsing. No compilers yet — those are v0.2.

**Tech Stack:** Python 3.10+, pathlib + hashlib + shutil + tempfile + subprocess for filesystem/workspace/hooks, existing umwelt core (parser, registry, selector engine, cascade resolver).

**Spec reference:** `docs/superpowers/specs/2026-04-10-umwelt-v01-core-and-sandbox-scoping-design.md` §§6-8, §9.5-9.8.

**Prerequisite:** v0.1-core must be complete (tag `v0.1.0-core`, 182 tests passing, 23 source files).

---

## File structure

All sandbox consumer files live under `src/umwelt/sandbox/`:

```
src/umwelt/sandbox/
├── __init__.py               # registers vocabulary at import time (Task 0)
├── vocabulary.py             # register_taxon/entity/property calls (Task 0)
├── entities.py               # entity wrapper dataclasses: FileEntity, DirEntity, ToolEntity, etc. (Task 0)
├── world_matcher.py          # filesystem matcher for the world taxon (Tasks 1-3)
├── capability_matcher.py     # tool-registry matcher (Task 4)
├── state_matcher.py          # hook/resource matcher (Task 5)
├── validators.py             # per-taxon validators (Task 6)
├── desugar.py                # at-rule sugar transformers (Tasks 13-14)
├── workspace/
│   ├── __init__.py           # Workspace context manager (Task 9)
│   ├── manifest.py           # ManifestEntry + WorkspaceManifest (Task 7)
│   ├── strategy.py           # MaterializationStrategy protocol + default impl (Task 8)
│   ├── builder.py            # WorkspaceBuilder.build() (Tasks 9-10)
│   ├── writeback.py          # WriteBack.apply() (Task 11)
│   └── errors.py             # WorkspaceError, ViewViolation (Task 7)
├── hooks/
│   ├── __init__.py
│   └── dispatcher.py         # HookDispatcher (Task 12)
└── runners/
    └── __init__.py           # empty; v0.2+ ships nsjail/bwrap runners

tests/sandbox/
├── __init__.py
├── conftest.py               # shared fixtures: tmp project trees, sample views
├── test_vocabulary.py        # Task 0
├── test_world_matcher.py     # Tasks 1-3
├── test_capability_matcher.py # Task 4
├── test_state_matcher.py     # Task 5
├── test_validators.py        # Task 6
├── test_manifest.py          # Task 7
├── test_strategy.py          # Task 8
├── test_workspace_builder.py # Tasks 9-10
├── test_writeback.py         # Task 11
├── test_hooks_dispatcher.py  # Task 12
├── test_desugaring.py        # Tasks 13-14
├── test_integration_parse.py # Task 15
├── test_integration_workspace.py # Task 16
└── test_cli_sandbox.py       # Task 16

src/umwelt/_fixtures/
├── minimal.umw               # Task 15
├── readonly-exploration.umw  # Task 15
├── auth-fix.umw              # Task 15
└── actor-conditioned.umw     # Task 15
```

Also modifies:
- `src/umwelt/parser.py` — adds sugar registry (Task 13)
- `src/umwelt/cli.py` — removes UMWELT_PRELOAD_TOY hack, imports sandbox naturally (Task 17)
- `src/umwelt/__init__.py` — version bump (Task 17)
- `README.md` — update for sandbox consumer (Task 17)
- `CHANGELOG.md` — v0.1.0 entry (Task 17)

**Estimated LOC:** ~1,400 production + ~1,200 tests.

---

## Task breakdown

**18 tasks** across four slices matching spec §9.5-9.8:

- **Slice 5 — Vocabulary + matchers (Tasks 0-6):** entity dataclasses, vocabulary registration, filesystem/tool/state matchers, validators.
- **Slice 6 — Workspace builder (Tasks 7-10):** manifest, materialization strategy, builder for single-file and multi-file/glob/cascade.
- **Slice 7 — Writeback + hooks + desugaring (Tasks 11-14):** writeback with 6-cell state table, hook subprocess dispatcher, parser sugar registry, sandbox at-rule desugaring rules.
- **Slice 8 — Fixtures + integration + polish (Tasks 15-17):** .umw fixture files, end-to-end tests, CLI cleanup, README/CHANGELOG/tag.

**Commit convention:** same as v0.1-core. `feat(sandbox/<area>): <what>`, `test(sandbox): <what>`, `chore: <what>`. All commits with the Co-Authored-By trailer.

**Branching:** stay on `main` (confirmed by user for v0.1 work).

---

## Slice 5 — Vocabulary + matchers

### Task 0: Sandbox entity dataclasses + vocabulary registration

**Files:**
- Create: `src/umwelt/sandbox/__init__.py`
- Create: `src/umwelt/sandbox/entities.py`
- Create: `src/umwelt/sandbox/vocabulary.py`
- Create: `tests/sandbox/__init__.py`
- Create: `tests/sandbox/conftest.py`
- Create: `tests/sandbox/test_vocabulary.py`

**Context:** The sandbox consumer registers three taxa (`world`, `capability`, `state`) with their entities and properties against core umwelt's plugin registry. This task creates the entity wrapper dataclasses and the vocabulary registration module. Matchers come in Tasks 1-5.

- [ ] **Step 1: Write the failing test**

Create `tests/sandbox/__init__.py` (empty).

Create `tests/sandbox/conftest.py`:

```python
"""Shared fixtures for sandbox consumer tests."""

from __future__ import annotations

import pytest

from umwelt.registry import registry_scope


@pytest.fixture
def sandbox_scope():
    """Enter a fresh registry scope with the sandbox vocabulary registered."""
    with registry_scope() as scope:
        import umwelt.sandbox  # triggers vocabulary registration  # noqa: F401

        yield scope
```

Create `tests/sandbox/test_vocabulary.py`:

```python
"""Tests for sandbox vocabulary registration."""

from __future__ import annotations

from umwelt.registry import (
    get_entity,
    get_property,
    get_taxon,
    list_entities,
    list_properties,
    registry_scope,
)


def _register_sandbox():
    """Import the sandbox package to trigger vocabulary registration."""
    import umwelt.sandbox  # noqa: F401


def test_world_taxon_registered():
    with registry_scope():
        _register_sandbox()
        taxon = get_taxon("world")
        assert taxon.name == "world"
        assert taxon.ma_concept == "world_coupling_axis"


def test_capability_taxon_registered():
    with registry_scope():
        _register_sandbox()
        taxon = get_taxon("capability")
        assert taxon.name == "capability"


def test_state_taxon_registered():
    with registry_scope():
        _register_sandbox()
        taxon = get_taxon("state")
        assert taxon.name == "state"


def test_world_file_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "file")
        assert entity.name == "file"
        assert entity.parent == "dir"
        assert "path" in entity.attributes
        assert entity.attributes["path"].required is True


def test_world_dir_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "dir")
        assert entity.parent is None
        assert "path" in entity.attributes


def test_world_resource_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "resource")
        assert "kind" in entity.attributes


def test_world_network_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "network")


def test_world_env_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "env")
        assert "name" in entity.attributes


def test_capability_tool_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("capability", "tool")
        assert "name" in entity.attributes
        assert "level" in entity.attributes


def test_capability_kit_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("capability", "kit")


def test_state_hook_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("state", "hook")
        assert "event" in entity.attributes


def test_file_editable_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "file", "editable")
        assert prop.value_type is bool
        assert prop.comparison == "exact"


def test_tool_max_level_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("capability", "tool", "max-level")
        assert prop.comparison == "<="
        assert prop.value_attribute == "level"


def test_tool_allow_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("capability", "tool", "allow")
        assert prop.value_type is bool


def test_tool_allow_pattern_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("capability", "tool", "allow-pattern")
        assert prop.comparison == "pattern-in"


def test_hook_run_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("state", "hook", "run")


def test_resource_limit_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "resource", "limit")


def test_network_deny_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "network", "deny")


def test_env_allow_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "env", "allow")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/sandbox/test_vocabulary.py -v`
Expected: `ModuleNotFoundError: No module named 'umwelt.sandbox'`.

- [ ] **Step 3: Create entity dataclasses**

Create `src/umwelt/sandbox/entities.py`:

```python
"""Entity wrapper dataclasses for the sandbox vocabulary.

Each entity type the sandbox consumer registers gets a simple frozen
dataclass to carry its attributes. Core umwelt treats these as opaque
handles; the sandbox matchers know how to construct and introspect them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileEntity:
    """A file in the filesystem."""

    path: str
    abs_path: Path
    name: str
    language: str | None = None


@dataclass(frozen=True)
class DirEntity:
    """A directory in the filesystem."""

    path: str
    abs_path: Path
    name: str


@dataclass(frozen=True)
class ResourceEntity:
    """A runtime resource (memory, cpu-time, wall-time, etc.)."""

    kind: str


@dataclass(frozen=True)
class NetworkEntity:
    """A network endpoint."""

    host: str | None = None
    port: int | None = None


@dataclass(frozen=True)
class EnvEntity:
    """An environment variable."""

    name: str


@dataclass(frozen=True)
class MountEntity:
    """A bind mount in the workspace."""

    src: str
    dst: str
    type: str = "bind"
    writable: bool = False


@dataclass(frozen=True)
class ToolEntity:
    """A tool the actor can call."""

    name: str
    kit: str | None = None
    altitude: str | None = None
    level: int = 0


@dataclass(frozen=True)
class KitEntity:
    """A named group of tools."""

    name: str
    version: str | None = None


@dataclass(frozen=True)
class HookEntity:
    """A lifecycle hook."""

    event: str
    phase: str | None = None


@dataclass(frozen=True)
class BudgetEntity:
    """A runtime budget."""

    kind: str


@dataclass(frozen=True)
class JobEntity:
    """An execution run."""

    id: str
    state: str = "pending"
    delegate: bool = False
```

- [ ] **Step 4: Create vocabulary registration**

Create `src/umwelt/sandbox/vocabulary.py`:

```python
"""Register the sandbox vocabulary (world, capability, state) with core umwelt.

Called at import time by sandbox/__init__.py. Each register_* call talks to
the active registry scope (which is the global scope in production and a
fresh scope in tests via registry_scope()).
"""

from __future__ import annotations

from umwelt.registry import (
    AttrSchema,
    register_entity,
    register_property,
    register_taxon,
)


def register_sandbox_vocabulary() -> None:
    """Register all sandbox taxa, entities, and properties."""
    _register_world()
    _register_capability()
    _register_state()


def _register_world() -> None:
    register_taxon(
        name="world",
        description="Entities the actor can couple to: filesystem, network, environment, resources.",
        ma_concept="world_coupling_axis",
    )

    register_entity(
        taxon="world",
        name="dir",
        attributes={
            "path": AttrSchema(type=str, required=True, description="Directory path relative to base_dir"),
            "name": AttrSchema(type=str, required=True, description="Directory name"),
        },
        description="A directory in the filesystem.",
        category="filesystem",
    )

    register_entity(
        taxon="world",
        name="file",
        parent="dir",
        attributes={
            "path": AttrSchema(type=str, required=True, description="File path relative to base_dir"),
            "name": AttrSchema(type=str, required=True, description="File name"),
            "language": AttrSchema(type=str, description="Programming language (from extension)"),
        },
        description="A file in the filesystem. Descendant of a dir.",
        category="filesystem",
    )

    register_entity(
        taxon="world",
        name="resource",
        attributes={
            "kind": AttrSchema(type=str, required=True, description="Resource kind: memory, cpu-time, wall-time, max-fds, tmpfs"),
        },
        description="A runtime resource with a limit.",
        category="budget",
    )

    register_entity(
        taxon="world",
        name="network",
        attributes={
            "host": AttrSchema(type=str, description="Hostname"),
            "port": AttrSchema(type=int, description="Port number"),
        },
        description="A network endpoint.",
        category="network",
    )

    register_entity(
        taxon="world",
        name="env",
        attributes={
            "name": AttrSchema(type=str, required=True, description="Environment variable name"),
        },
        description="An environment variable.",
        category="environment",
    )

    register_entity(
        taxon="world",
        name="mount",
        attributes={
            "src": AttrSchema(type=str, required=True),
            "dst": AttrSchema(type=str, required=True),
            "type": AttrSchema(type=str),
        },
        description="A bind mount in the workspace.",
        category="workspace",
    )

    # Properties on world entities
    register_property(taxon="world", entity="file", name="editable", value_type=bool, description="Whether the actor may modify this file.")
    register_property(taxon="world", entity="file", name="visible", value_type=bool, description="Whether the actor can see this file.")
    register_property(taxon="world", entity="file", name="show", value_type=str, description="What to show: body, outline, signature.")
    register_property(taxon="world", entity="dir", name="editable", value_type=bool, description="Whether the actor may modify files in this dir.")
    register_property(taxon="world", entity="dir", name="visible", value_type=bool, description="Whether the actor can see this dir.")
    register_property(taxon="world", entity="resource", name="limit", value_type=str, description="Resource limit value with unit (e.g. 512MB, 60s).")
    register_property(taxon="world", entity="network", name="deny", value_type=str, description="Deny pattern ('*' for all).")
    register_property(taxon="world", entity="network", name="allow", value_type=bool, description="Whether this endpoint is allowed.")
    register_property(taxon="world", entity="env", name="allow", value_type=bool, description="Whether this env var is passed through.")
    register_property(taxon="world", entity="mount", name="size", value_type=str, description="Mount size limit.")


def _register_capability() -> None:
    register_taxon(
        name="capability",
        description="What the actor can do: tools, kits, effects, computation levels.",
        ma_concept="decision_surface_axis",
    )

    register_entity(
        taxon="capability",
        name="tool",
        attributes={
            "name": AttrSchema(type=str, required=True, description="Tool name"),
            "kit": AttrSchema(type=str, description="Kit this tool belongs to"),
            "altitude": AttrSchema(type=str, description="Enforcement altitude: os, language, semantic, conversational"),
            "level": AttrSchema(type=int, description="Computation level 0-8"),
        },
        description="A tool the actor can call.",
        category="tools",
    )

    register_entity(
        taxon="capability",
        name="kit",
        attributes={
            "name": AttrSchema(type=str, required=True, description="Kit name"),
            "version": AttrSchema(type=str, description="Kit version"),
        },
        description="A named group of tools.",
        category="tools",
    )

    register_property(taxon="capability", entity="tool", name="allow", value_type=bool, description="Whether the tool is permitted.")
    register_property(taxon="capability", entity="tool", name="max-level", value_type=int, comparison="<=", value_attribute="level", value_range=(0, 8), description="Maximum computation level permitted.", category="effects_ceiling")
    register_property(taxon="capability", entity="tool", name="require", value_type=str, description="Requirement for using this tool (e.g. 'sandbox').")
    register_property(taxon="capability", entity="tool", name="allow-pattern", value_type=list, comparison="pattern-in", description="Glob patterns for allowed invocations.")
    register_property(taxon="capability", entity="tool", name="deny-pattern", value_type=list, comparison="pattern-in", description="Glob patterns for denied invocations.")
    register_property(taxon="capability", entity="kit", name="allow", value_type=bool, description="Whether the kit is permitted.")


def _register_state() -> None:
    register_taxon(
        name="state",
        description="What the Harness tracks: jobs, hooks, budgets, observations.",
        ma_concept="observation_layer",
    )

    register_entity(
        taxon="state",
        name="hook",
        attributes={
            "event": AttrSchema(type=str, required=True, description="Lifecycle event: before-call, after-change, on-failure, on-timeout"),
            "phase": AttrSchema(type=str, description="Sub-categorization of the event"),
        },
        description="A lifecycle hook.",
        category="hooks",
    )

    register_entity(
        taxon="state",
        name="job",
        attributes={
            "id": AttrSchema(type=str, required=True),
            "state": AttrSchema(type=str),
            "delegate": AttrSchema(type=bool),
        },
        description="An execution run.",
        category="jobs",
    )

    register_entity(
        taxon="state",
        name="budget",
        attributes={
            "kind": AttrSchema(type=str, required=True),
        },
        description="A runtime budget.",
        category="budgets",
    )

    register_property(taxon="state", entity="hook", name="run", value_type=str, description="Shell command to execute for this hook.")
    register_property(taxon="state", entity="hook", name="timeout", value_type=str, description="Timeout for hook execution.")
    register_property(taxon="state", entity="job", name="inherit-budget", value_type=float, description="Fraction of parent budget to inherit.")
    register_property(taxon="state", entity="budget", name="limit", value_type=str, description="Budget limit value.")
```

Create `src/umwelt/sandbox/__init__.py`:

```python
"""The first-party sandbox consumer of umwelt.

Importing this package registers the world, capability, and state taxa
with the active registry scope. In production, that's the global scope.
In tests, use registry_scope() to isolate vocabulary registration.
"""

from umwelt.sandbox.vocabulary import register_sandbox_vocabulary

register_sandbox_vocabulary()
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/sandbox/test_vocabulary.py -v`
Expected: all 20 tests pass.

Run: `pytest tests/ -q`
Expected: 202 passed (182 core + 20 vocabulary). Note: importing `umwelt.sandbox` in the core test scope might cause issues if registry scopes aren't isolated; if so, add `import umwelt.sandbox` inside each test's `registry_scope()` block rather than at module level.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/sandbox/ tests/sandbox/
git commit -m "$(cat <<'EOF'
feat(sandbox): register world/capability/state vocabulary

Entity dataclasses (FileEntity, DirEntity, ToolEntity, HookEntity,
etc.) and vocabulary registration for the three sandbox taxa. Each
entity has typed attributes; each property has comparison semantics
metadata. Importing umwelt.sandbox triggers registration against
the active registry scope.

No matchers yet — Tasks 1-5 provide those. This task establishes
the entity model so subsequent tasks can focus on matching and
workspace lifecycle.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1: World matcher — path attributes

**Files:**
- Create: `src/umwelt/sandbox/world_matcher.py`
- Create: `tests/sandbox/test_world_matcher.py`

**Context:** The world matcher walks a real filesystem directory and returns `FileEntity` / `DirEntity` instances. It implements `MatcherProtocol` and is registered against the `world` taxon. This first task handles basic path-attribute matching (`file[path^="src/"]`, `file[path$=".py"]`, `file[name="README.md"]`). Tasks 2-3 add glob and descendant support.

- [ ] **Step 1: Write the failing test**

Create `tests/sandbox/test_world_matcher.py`:

```python
"""Tests for the world taxon filesystem matcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from umwelt.registry import registry_scope
from umwelt.sandbox.entities import DirEntity, FileEntity
from umwelt.sandbox.world_matcher import WorldMatcher


def _make_tree(tmp_path: Path) -> Path:
    """Create a small project tree for matcher tests."""
    (tmp_path / "src" / "auth").mkdir(parents=True)
    (tmp_path / "src" / "common").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "auth" / "login.py").write_text("# login")
    (tmp_path / "src" / "auth" / "oauth.py").write_text("# oauth")
    (tmp_path / "src" / "common" / "util.py").write_text("# util")
    (tmp_path / "src" / "common" / "types.py").write_text("# types")
    (tmp_path / "tests" / "test_login.py").write_text("# test")
    (tmp_path / "README.md").write_text("# readme")
    return tmp_path


def test_match_type_file_returns_all(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")
    names = {f.name for f in files}
    assert "login.py" in names
    assert "oauth.py" in names
    assert "README.md" in names
    assert len(files) == 6


def test_match_type_dir_returns_all(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    dirs = matcher.match_type("dir")
    names = {d.name for d in dirs}
    assert "src" in names
    assert "auth" in names
    assert "tests" in names


def test_get_attribute_path(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")
    login = next(f for f in files if f.name == "login.py")
    assert matcher.get_attribute(login, "path") == "src/auth/login.py"


def test_get_attribute_name(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")
    login = next(f for f in files if f.name == "login.py")
    assert matcher.get_attribute(login, "name") == "login.py"


def test_get_id_is_name(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    files = matcher.match_type("file")
    login = next(f for f in files if f.name == "login.py")
    assert matcher.get_id(login) == "login.py"


def test_match_type_star_returns_all_entities(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    all_entities = matcher.match_type("*")
    # Should include both files and dirs
    assert len(all_entities) > 6  # at least 6 files + some dirs


def test_match_type_unknown_returns_empty(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    assert matcher.match_type("ghost") == []


def test_resource_entities(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    resources = matcher.match_type("resource")
    kinds = {matcher.get_attribute(r, "kind") for r in resources}
    assert "memory" in kinds
    assert "wall-time" in kinds


def test_network_entity(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree)
    networks = matcher.match_type("network")
    assert len(networks) == 1  # the singleton network entity


def test_env_entities(tmp_path):
    tree = _make_tree(tmp_path)
    matcher = WorldMatcher(base_dir=tree, env_vars=["CI", "PATH"])
    envs = matcher.match_type("env")
    names = {matcher.get_attribute(e, "name") for e in envs}
    assert "CI" in names
    assert "PATH" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/sandbox/test_world_matcher.py -v`
Expected: `ModuleNotFoundError: No module named 'umwelt.sandbox.world_matcher'`.

- [ ] **Step 3: Implement WorldMatcher**

Create `src/umwelt/sandbox/world_matcher.py`:

```python
"""Filesystem matcher for the world taxon.

Walks a base directory and returns FileEntity / DirEntity instances that
the core selector engine can evaluate attribute selectors against.
Also provides singleton entities for resource, network, and env types.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from umwelt.sandbox.entities import (
    DirEntity,
    EnvEntity,
    FileEntity,
    NetworkEntity,
    ResourceEntity,
)

RESOURCE_KINDS = ("memory", "cpu-time", "wall-time", "max-fds", "tmpfs")


class WorldMatcher:
    """MatcherProtocol implementation for the world taxon."""

    def __init__(
        self,
        base_dir: Path,
        env_vars: list[str] | None = None,
    ) -> None:
        self._base_dir = base_dir.resolve()
        self._env_vars = env_vars or []
        self._files: list[FileEntity] | None = None
        self._dirs: list[DirEntity] | None = None

    def _scan(self) -> None:
        """Lazily scan the filesystem under base_dir."""
        if self._files is not None:
            return
        files: list[FileEntity] = []
        dirs: list[DirEntity] = []
        for p in sorted(self._base_dir.rglob("*")):
            rel = str(p.relative_to(self._base_dir))
            if p.is_file():
                lang = _guess_language(p.suffix)
                files.append(FileEntity(path=rel, abs_path=p, name=p.name, language=lang))
            elif p.is_dir():
                dirs.append(DirEntity(path=rel, abs_path=p, name=p.name))
        self._files = files
        self._dirs = dirs

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        self._scan()
        if type_name == "file":
            return list(self._files or [])
        if type_name == "dir":
            return list(self._dirs or [])
        if type_name == "resource":
            return [ResourceEntity(kind=k) for k in RESOURCE_KINDS]
        if type_name == "network":
            return [NetworkEntity()]
        if type_name == "env":
            return [EnvEntity(name=n) for n in self._env_vars]
        if type_name == "*":
            result: list[Any] = []
            result.extend(self._files or [])
            result.extend(self._dirs or [])
            result.extend(ResourceEntity(kind=k) for k in RESOURCE_KINDS)
            result.append(NetworkEntity())
            result.extend(EnvEntity(name=n) for n in self._env_vars)
            return result
        return []

    def children(self, parent: Any, child_type: str) -> list[Any]:
        """Return child entities of a parent (dir → file, dir → dir)."""
        self._scan()
        if not isinstance(parent, DirEntity):
            return []
        parent_path = parent.abs_path
        if child_type == "file":
            return [
                f
                for f in (self._files or [])
                if f.abs_path.parent == parent_path
                or str(f.abs_path).startswith(str(parent_path) + "/")
            ]
        if child_type == "dir":
            return [
                d
                for d in (self._dirs or [])
                if str(d.abs_path).startswith(str(parent_path) + "/")
                and d.abs_path != parent_path
            ]
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        # World entities are never used as context qualifiers; world is
        # always the target taxon for sandbox rules.
        return False

    def get_attribute(self, entity: Any, name: str) -> Any:
        return getattr(entity, name, None)

    def get_id(self, entity: Any) -> str | None:
        if hasattr(entity, "name"):
            return entity.name
        if hasattr(entity, "kind"):
            return entity.kind
        return None


def _guess_language(suffix: str) -> str | None:
    """Guess the programming language from a file suffix."""
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".rb": "ruby",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".md": "markdown",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
    }
    return mapping.get(suffix)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/sandbox/test_world_matcher.py -v`
Expected: all 10 tests pass.

Run: `pytest tests/ -q`
Expected: ~212 passed.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/sandbox/world_matcher.py tests/sandbox/test_world_matcher.py
git commit -m "$(cat <<'EOF'
feat(sandbox/world): filesystem matcher for path-attribute selectors

WorldMatcher walks a base_dir, scans files and directories into
FileEntity/DirEntity instances, and implements MatcherProtocol so
the core selector engine can evaluate path-attribute selectors like
file[path^="src/"], file[name="README.md"], etc. Also provides
singleton entities for resource (memory, cpu-time, wall-time, etc.),
network, and env types.

Lazy-scanning: the filesystem walk happens once on first match_type
call, then is cached. Entity attributes (path, name, language) are
accessible via get_attribute; get_id returns the entity name.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Tasks 2-5: Remaining matchers and validators

**Due to context constraints, Tasks 2-5 follow the same TDD pattern as Task 1 but are specified here in summary form. The executing subagent should read the spec (§6.3-6.5) for entity details and implement each as a self-contained commit.**

**Task 2: World matcher — glob and descendant combinator**

- Extend `WorldMatcher` tests: `:glob("src/**/*.py")` matching, descendant `dir[name="src"] file` walking via `children()`, path traversal protection (paths outside base_dir rejected).
- Extend `WorldMatcher.children()` for proper ancestor-not-just-parent navigation (a file under `src/auth/` is a descendant of the `src` dir, not just its direct children).
- Commit: `feat(sandbox/world): add glob and descendant-combinator support`

**Task 3: World matcher — integration with core parse+resolve**

- Write an integration test that registers the sandbox vocabulary + world matcher, parses a real view like `file[path^="src/auth/"] { editable: true; }`, runs `resolve(view)`, and asserts the resolved properties match the expected files.
- This is the first test that connects the sandbox consumer all the way through the core pipeline.
- Commit: `test(sandbox/world): end-to-end parse → resolve with filesystem matcher`

**Task 4: Capability matcher**

- Create `src/umwelt/sandbox/capability_matcher.py` with `CapabilityMatcher(tools: list[ToolEntity], kits: list[KitEntity])`.
- `match_type("tool")` returns the tool list; `match_type("kit")` returns the kit list.
- `get_attribute(tool, "name")` / `get_attribute(tool, "level")` / etc.
- 5-6 tests in `tests/sandbox/test_capability_matcher.py`.
- Commit: `feat(sandbox/capability): tool-registry matcher`

**Task 5: State matcher**

- Create `src/umwelt/sandbox/state_matcher.py` with `StateMatcher(hooks: list[HookEntity], resources: list[ResourceEntity], budgets: list[BudgetEntity])`.
- `match_type("hook")` returns hooks; `match_type("resource")` returns resources.
- 4-5 tests in `tests/sandbox/test_state_matcher.py`.
- Commit: `feat(sandbox/state): hook and resource matcher`

**Task 6: Sandbox validators**

- Create `src/umwelt/sandbox/validators.py` with validators registered against each sandbox taxon.
- World validator: path-escape detection (paths with `..` that escape base_dir), empty-glob warning.
- Capability validator: allow/deny overlap detection.
- Register via `register_validator` in `vocabulary.py`.
- 4-5 tests in `tests/sandbox/test_validators.py`.
- Commit: `feat(sandbox/validators): path-escape, allow/deny overlap, empty-glob warnings`

---

## Slice 6 — Workspace builder

### Task 7: Manifest + workspace errors

**Files:**
- Create: `src/umwelt/sandbox/workspace/__init__.py`
- Create: `src/umwelt/sandbox/workspace/manifest.py`
- Create: `src/umwelt/sandbox/workspace/errors.py`
- Create: `tests/sandbox/test_manifest.py`

- [ ] **Step 1: Write the failing test**

Create `tests/sandbox/test_manifest.py`:

```python
"""Tests for workspace manifest dataclasses."""

from __future__ import annotations

from pathlib import Path

from umwelt.sandbox.workspace.manifest import ManifestEntry, WorkspaceManifest


def test_manifest_entry_construction():
    entry = ManifestEntry(
        real_path=Path("/project/src/main.py"),
        virtual_path=Path("src/main.py"),
        writable=True,
        content_hash_at_build="abc123",
        strategy_name="default",
    )
    assert entry.writable is True
    assert entry.content_hash_at_build == "abc123"


def test_manifest_entry_readonly():
    entry = ManifestEntry(
        real_path=Path("/project/src/main.py"),
        virtual_path=Path("src/main.py"),
        writable=False,
        content_hash_at_build="def456",
        strategy_name="default",
    )
    assert entry.writable is False
    assert entry.content_hash_at_build == "def456"


def test_workspace_manifest_entries():
    entries = (
        ManifestEntry(Path("/a"), Path("a"), True, "h1", "default"),
        ManifestEntry(Path("/b"), Path("b"), False, "h2", "default"),
    )
    manifest = WorkspaceManifest(
        entries=entries,
        base_dir=Path("/project"),
        workspace_root=Path("/tmp/ws"),
    )
    assert len(manifest.entries) == 2
    assert manifest.base_dir == Path("/project")
    assert manifest.workspace_root == Path("/tmp/ws")
```

- [ ] **Step 2: Run test → fail**

- [ ] **Step 3: Implement**

Create `src/umwelt/sandbox/workspace/errors.py`:

```python
"""Workspace-specific errors."""

from umwelt.errors import UmweltError


class WorkspaceError(UmweltError):
    """Raised on workspace build or materialization failures."""


class ViewViolation(UmweltError):
    """Raised when writeback detects a rejected or conflicting change."""
```

Create `src/umwelt/sandbox/workspace/manifest.py`:

```python
"""Workspace manifest: tracks virtual ↔ real path mappings with content hashes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManifestEntry:
    """One entry in the workspace manifest."""

    real_path: Path
    virtual_path: Path
    writable: bool
    content_hash_at_build: str
    strategy_name: str


@dataclass(frozen=True)
class WorkspaceManifest:
    """The full manifest for a built workspace."""

    entries: tuple[ManifestEntry, ...]
    base_dir: Path
    workspace_root: Path
```

Create `src/umwelt/sandbox/workspace/__init__.py`:

```python
"""Workspace builder, manifest, writeback, and materialization strategy."""
```

- [ ] **Step 4: Run tests → pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(sandbox/workspace): manifest dataclasses and workspace errors

ManifestEntry tracks (real_path, virtual_path, writable,
content_hash_at_build, strategy_name) for each materialized file.
WorkspaceManifest holds the entry tuple plus base_dir and
workspace_root. WorkspaceError and ViewViolation for error paths.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Materialization strategy

**Files:**
- Create: `src/umwelt/sandbox/workspace/strategy.py`
- Create: `tests/sandbox/test_strategy.py`

**Context:** The `MaterializationStrategy` protocol + `SymlinkReadonlyCopyWritable` default implementation. Read-only files → symlink; writable files → copy. SHA-256 hash captured at build time for BOTH modes (the self-review fix from the v0.1 scoping spec). Strategy registration is module-global with a default.

- [ ] **Step 1: Write the failing test**

Create `tests/sandbox/test_strategy.py`:

```python
"""Tests for the materialization strategy."""

from __future__ import annotations

import hashlib
from pathlib import Path

from umwelt.sandbox.workspace.strategy import (
    SymlinkReadonlyCopyWritable,
    get_strategy,
    register_strategy,
)


def test_materialize_readonly_creates_symlink(tmp_path):
    real = tmp_path / "real.py"
    real.write_text("content")
    ws = tmp_path / "ws"
    ws.mkdir()
    virtual = ws / "real.py"
    strategy = SymlinkReadonlyCopyWritable()
    entry = strategy.materialize(real, virtual, writable=False)
    assert virtual.is_symlink()
    assert virtual.resolve() == real.resolve()
    assert entry.writable is False
    assert entry.content_hash_at_build == hashlib.sha256(b"content").hexdigest()


def test_materialize_writable_creates_copy(tmp_path):
    real = tmp_path / "real.py"
    real.write_text("content")
    ws = tmp_path / "ws"
    ws.mkdir()
    virtual = ws / "real.py"
    strategy = SymlinkReadonlyCopyWritable()
    entry = strategy.materialize(real, virtual, writable=True)
    assert not virtual.is_symlink()
    assert virtual.read_text() == "content"
    assert entry.writable is True
    assert entry.content_hash_at_build == hashlib.sha256(b"content").hexdigest()


def test_materialize_creates_parent_dirs(tmp_path):
    real = tmp_path / "real.py"
    real.write_text("x")
    ws = tmp_path / "ws"
    virtual = ws / "deep" / "path" / "real.py"
    strategy = SymlinkReadonlyCopyWritable()
    entry = strategy.materialize(real, virtual, writable=True)
    assert virtual.exists()


def test_hash_captured_for_both_modes(tmp_path):
    real = tmp_path / "f.py"
    real.write_text("hello")
    ws = tmp_path / "ws"
    ws.mkdir()

    strategy = SymlinkReadonlyCopyWritable()
    entry_ro = strategy.materialize(real, ws / "ro.py", writable=False)
    entry_rw = strategy.materialize(real, ws / "rw.py", writable=True)
    expected_hash = hashlib.sha256(b"hello").hexdigest()
    assert entry_ro.content_hash_at_build == expected_hash
    assert entry_rw.content_hash_at_build == expected_hash


def test_register_and_get_default():
    strategy = get_strategy("default")
    assert isinstance(strategy, SymlinkReadonlyCopyWritable)


def test_register_custom_strategy():
    class Custom:
        name = "custom"

        def materialize(self, real, virtual, writable):
            pass

        def reconcile(self, entry, workspace_root):
            pass

    register_strategy(Custom())
    assert get_strategy("custom").name == "custom"
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement**

Create `src/umwelt/sandbox/workspace/strategy.py`:

```python
"""Materialization strategies for workspace construction.

The strategy determines HOW files enter the virtual workspace:
- Read-only: symlink (cheap, reflects external changes)
- Writable: copy (isolates delegate edits from real tree)

SHA-256 hashes are captured at build time for BOTH modes so writeback
can detect violations (read-only files modified) and conflicts (real
files modified externally during delegate execution).
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, Protocol

from umwelt.sandbox.workspace.manifest import ManifestEntry


class MaterializationStrategy(Protocol):
    """How files are materialized in the virtual workspace."""

    name: str

    def materialize(self, real: Path, virtual: Path, writable: bool) -> ManifestEntry:
        """Create the virtual entry and return a manifest entry with hash."""
        ...

    def reconcile(self, entry: ManifestEntry, workspace_root: Path) -> Any:
        """Compare virtual state to real state after delegate execution."""
        ...


class SymlinkReadonlyCopyWritable:
    """Default strategy: symlink read-only, copy writable, hash both."""

    name = "default"

    def materialize(self, real: Path, virtual: Path, writable: bool) -> ManifestEntry:
        virtual.parent.mkdir(parents=True, exist_ok=True)
        content_hash = _hash_file(real)
        if writable:
            shutil.copy2(real, virtual)
        else:
            virtual.symlink_to(real.resolve())
        return ManifestEntry(
            real_path=real,
            virtual_path=virtual,
            writable=writable,
            content_hash_at_build=content_hash,
            strategy_name=self.name,
        )

    def reconcile(self, entry: ManifestEntry, workspace_root: Path) -> Any:
        # Implemented in Task 11 (writeback).
        raise NotImplementedError("reconcile is implemented in writeback")


_STRATEGIES: dict[str, MaterializationStrategy] = {}


def register_strategy(strategy: MaterializationStrategy) -> None:
    _STRATEGIES[strategy.name] = strategy


def get_strategy(name: str) -> MaterializationStrategy:
    if name not in _STRATEGIES:
        if name == "default":
            default = SymlinkReadonlyCopyWritable()
            _STRATEGIES["default"] = default
            return default
        raise KeyError(f"strategy {name!r} not registered")
    return _STRATEGIES[name]


def _hash_file(path: Path) -> str:
    """SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
```

- [ ] **Step 4: Run → pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(sandbox/workspace): materialization strategy with hash-based tracking

SymlinkReadonlyCopyWritable is the default strategy: read-only files
become symlinks, writable files become copies, and SHA-256 hashes are
captured at build time for BOTH modes. The hash-both-modes decision
comes from the v0.1 scoping spec's self-review: without a sandbox
compiler (v0.2), read-only symlinks don't enforce anything, so
hash-based post-hoc detection is the backstop.

Strategy registration is module-global with lazy default initialization.
Custom strategies (for remote stage-in, snapshot-based fs, etc.)
register via register_strategy().

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Tasks 9-10: Workspace builder

**Task 9: WorkspaceBuilder — single file, single rule**

- Create `src/umwelt/sandbox/workspace/builder.py` with `WorkspaceBuilder` class.
- `build(view, base_dir) -> Workspace` creates a temp dir, resolves `file` rules via the world matcher, materializes each matched file via the strategy, records the manifest.
- `Workspace` is a context manager that cleans up on exit.
- 5-6 tests: build with one file rule, verify manifest has expected entry, verify the virtual file exists, context manager cleanup works.
- Commit: `feat(sandbox/workspace): builder for single-file rules`

**Task 10: WorkspaceBuilder — globs, cascade, path traversal**

- Extend builder to handle multi-file globs, multiple `file[...]` rules with cascade (last-wins for `editable`), and path traversal protection (any resolved path outside `base_dir` raises `WorkspaceError`).
- 6-8 tests: multi-file glob, overlapping rules with cascade, path traversal rejection, empty match warning.
- Commit: `feat(sandbox/workspace): glob expansion, cascade, and path-traversal protection`

---

## Slice 7 — Writeback + hooks + desugaring

### Task 11: Writeback

**Files:**
- Create: `src/umwelt/sandbox/workspace/writeback.py`
- Create: `tests/sandbox/test_writeback.py`

**Context:** After the delegate operates inside the workspace, writeback walks the manifest and for each entry compares the virtual and real file states. Six outcomes based on a 3×2 matrix (writable/readonly × unchanged/changed/conflict).

- [ ] **Step 1: Write the failing test**

Create `tests/sandbox/test_writeback.py`:

```python
"""Tests for workspace writeback."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from umwelt.sandbox.workspace.errors import ViewViolation
from umwelt.sandbox.workspace.manifest import ManifestEntry, WorkspaceManifest
from umwelt.sandbox.workspace.writeback import Applied, Conflict, NoOp, Rejected, WriteBack


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _entry(
    tmp_path: Path,
    filename: str = "f.py",
    writable: bool = True,
    content: str = "original",
) -> tuple[ManifestEntry, Path, Path]:
    """Create a real file, a virtual file, and a manifest entry."""
    real = tmp_path / "real" / filename
    real.parent.mkdir(parents=True, exist_ok=True)
    real.write_text(content)

    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    virtual = ws / filename
    if writable:
        virtual.write_text(content)
    else:
        virtual.symlink_to(real)

    entry = ManifestEntry(
        real_path=real,
        virtual_path=Path(filename),
        writable=writable,
        content_hash_at_build=_hash(content),
        strategy_name="default",
    )
    return entry, real, ws


def test_writable_unchanged_is_noop(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, NoOp)


def test_writable_changed_real_unchanged_is_applied(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    (ws / "f.py").write_text("modified by delegate")
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, Applied)
    assert result.new_content == b"modified by delegate"


def test_writable_changed_real_changed_is_conflict(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    (ws / "f.py").write_text("delegate edit")
    real.write_text("external edit")
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, Conflict)


def test_writable_unchanged_real_changed_is_conflict(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    real.write_text("external edit")
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, Conflict)


def test_readonly_unchanged_is_noop(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=False)
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, NoOp)


def test_readonly_changed_is_rejected(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=False)
    # Modify the real file (which the symlink points to)
    real.write_text("someone modified this")
    result = WriteBack().apply_entry(entry, ws)
    assert isinstance(result, Rejected)


def test_full_writeback_applies_changes(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    (ws / "f.py").write_text("delegate wrote this")
    manifest = WorkspaceManifest(
        entries=(entry,),
        base_dir=tmp_path / "real",
        workspace_root=ws,
    )
    wb = WriteBack()
    result = wb.apply(manifest)
    assert len(result.applied) == 1
    assert real.read_text() == "delegate wrote this"


def test_strict_mode_raises_on_rejected(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=False)
    real.write_text("modified")
    manifest = WorkspaceManifest(entries=(entry,), base_dir=tmp_path / "real", workspace_root=ws)
    with pytest.raises(ViewViolation):
        WriteBack(strict=True).apply(manifest)


def test_strict_mode_raises_on_conflict(tmp_path):
    entry, real, ws = _entry(tmp_path, writable=True)
    (ws / "f.py").write_text("delegate edit")
    real.write_text("external edit")
    manifest = WorkspaceManifest(entries=(entry,), base_dir=tmp_path / "real", workspace_root=ws)
    with pytest.raises(ViewViolation):
        WriteBack(strict=True).apply(manifest)
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement**

Create `src/umwelt/sandbox/workspace/writeback.py`:

```python
"""Workspace writeback: splice delegate edits back to real files.

Walks the manifest after the delegate finishes and classifies each
entry's state into one of four outcomes: NoOp, Applied, Rejected,
Conflict. Applied changes are written to the real path AFTER all
reconciliation decisions are made (no partial updates on failure).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from umwelt.sandbox.workspace.errors import ViewViolation
from umwelt.sandbox.workspace.manifest import ManifestEntry, WorkspaceManifest


@dataclass(frozen=True)
class NoOp:
    entry: ManifestEntry


@dataclass(frozen=True)
class Applied:
    entry: ManifestEntry
    new_content: bytes


@dataclass(frozen=True)
class Rejected:
    entry: ManifestEntry
    reason: str


@dataclass(frozen=True)
class Conflict:
    entry: ManifestEntry
    reason: str


ReconcileResult = NoOp | Applied | Rejected | Conflict


@dataclass
class WriteBackResult:
    applied: list[Applied] = field(default_factory=list)
    rejected: list[Rejected] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    noops: list[NoOp] = field(default_factory=list)


class WriteBack:
    def __init__(self, strict: bool = False) -> None:
        self._strict = strict

    def apply_entry(self, entry: ManifestEntry, workspace_root: Path) -> ReconcileResult:
        """Reconcile a single manifest entry."""
        virtual_path = workspace_root / entry.virtual_path
        real_hash_now = _hash_file(entry.real_path)
        real_changed = real_hash_now != entry.content_hash_at_build

        if not entry.writable:
            if real_changed:
                return Rejected(entry, "read-only file was modified during delegate execution")
            return NoOp(entry)

        virtual_hash_now = _hash_file(virtual_path)
        virtual_changed = virtual_hash_now != entry.content_hash_at_build

        if not virtual_changed and not real_changed:
            return NoOp(entry)
        if virtual_changed and not real_changed:
            return Applied(entry, virtual_path.read_bytes())
        if not virtual_changed and real_changed:
            return Conflict(entry, "real file modified externally")
        return Conflict(entry, "both virtual and real modified")

    def apply(self, manifest: WorkspaceManifest) -> WriteBackResult:
        """Reconcile all entries and apply changes atomically."""
        result = WriteBackResult()
        pending_writes: list[tuple[Path, bytes]] = []

        for entry in manifest.entries:
            outcome = self.apply_entry(entry, manifest.workspace_root)
            if isinstance(outcome, NoOp):
                result.noops.append(outcome)
            elif isinstance(outcome, Applied):
                result.applied.append(outcome)
                pending_writes.append((entry.real_path, outcome.new_content))
            elif isinstance(outcome, Rejected):
                result.rejected.append(outcome)
            elif isinstance(outcome, Conflict):
                result.conflicts.append(outcome)

        if self._strict and (result.rejected or result.conflicts):
            reasons = [r.reason for r in result.rejected] + [c.reason for c in result.conflicts]
            raise ViewViolation(f"writeback violations: {'; '.join(reasons)}")

        for real_path, content in pending_writes:
            real_path.write_bytes(content)

        return result


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
```

- [ ] **Step 4: Run → pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(sandbox/workspace): writeback with hash-based violation detection

WriteBack.apply(manifest) walks entries and classifies each into
NoOp / Applied / Rejected / Conflict based on comparing SHA-256
hashes of real and virtual files against the build-time baseline.

Applied changes are staged as (path, bytes) pairs and written to the
real tree AFTER all reconciliation decisions are made — no partial
updates on failure. strict=True raises ViewViolation if any entry
is rejected or conflicting.

The six-cell state table from the vision docs is fully covered:
writable unchanged, writable delegate-changed, writable externally-
changed, writable both-changed, readonly unchanged, readonly changed.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Hook dispatcher

**Summary:** Create `src/umwelt/sandbox/hooks/dispatcher.py` with `HookDispatcher` and `HookContext`. For each matched `hook[event="after-change"]` entity, iterate its `run:` values and execute via `subprocess.run(shlex.split(cmd), ...)` with capture, timeout (default 60s), and continue-on-failure. `HookResult` records label, command, returncode, stdout, stderr, duration, timed_out. 6-7 tests covering: success, failure-continues, timeout, command-not-found, cwd=project_root. Commit: `feat(sandbox/hooks): dispatcher with subprocess capture and timeout`

### Task 13: Parser sugar registry + @source/@tools/@after-change desugaring

**Summary:** Extend `src/umwelt/parser.py` with a module-level sugar registry (`register_sugar(name, transformer)`, `_is_sugar`, `_desugar`). The sandbox consumer's `desugar.py` registers transformers for `@source`, `@tools`, `@after-change`. Each transformer takes a tinycss2 at-rule node and returns a list of RuleBlocks in entity-selector form. 8-10 tests: each at-rule desugars to the expected selector+declaration form. Commit: `feat(sandbox/desugar): parser sugar registry + @source/@tools/@after-change`

### Task 14: @network/@budget/@env desugaring

**Summary:** Add transformers for the remaining three at-rules. `@network { deny: *; }` → `network { deny: "*"; }`. `@budget { memory: 512MB; }` → `resource[kind="memory"] { limit: 512MB; }`. `@env { allow: CI; }` → `env[name="CI"] { allow: true; }`. 6-8 tests. Commit: `feat(sandbox/desugar): @network/@budget/@env sugar transformers`

---

## Slice 8 — Fixtures + integration + polish

### Task 15: Fixture view files

**Summary:** Create four `.umw` fixture files under `src/umwelt/_fixtures/`:
- `minimal.umw` — `file[path="hello.txt"] { editable: true; }`
- `readonly-exploration.umw` — read-only file rules + tool allow/deny
- `auth-fix.umw` — the canonical sandbox example with cascade, hooks, budget
- `actor-conditioned.umw` — cross-taxon compound selector example

All four must parse cleanly through the full pipeline. 4 tests in `tests/sandbox/test_integration_parse.py` that parse each fixture and assert no errors/warnings. Commit: `feat(sandbox): reference .umw fixture files`

### Task 16: End-to-end integration tests

**Summary:** Two test files:
- `tests/sandbox/test_integration_workspace.py` — build a workspace from `auth-fix.umw` against a temp project tree, modify a writable file, run writeback, verify the applied change lands in the real tree. Also test hook execution if pytest is on PATH.
- `tests/sandbox/test_cli_sandbox.py` — subprocess CLI tests against fixtures, verifying that `umwelt parse`, `umwelt inspect`, `umwelt check` all work with the sandbox vocabulary registered.

Commit: `test(sandbox): end-to-end workspace lifecycle and CLI integration`

### Task 17: Polish, version bump, v0.1.0 tag

**Summary:**
- Update `README.md` with real sandbox examples (no more UMWELT_PRELOAD_TOY).
- Remove the `UMWELT_PRELOAD_TOY` hack from `src/umwelt/cli.py` — replace with `import umwelt.sandbox` which registers the real vocabulary.
- Update `CHANGELOG.md` with the v0.1.0 entry (sandbox consumer shipped).
- Bump version to `"0.1.0"` in `pyproject.toml` and `src/umwelt/__init__.py`.
- Update `docs/vision/README.md` status to "v0.1.0 shipped."
- Full test suite green. Tag `v0.1.0`.
- Commit: `chore(release): v0.1.0 — sandbox consumer ships`

---

## Self-review

**1. Spec coverage (§§6-8, §9.5-9.8 of the scoping spec):**

| Spec section | Covered by |
|---|---|
| §6.1 Module layout | Task 0 (entities + vocabulary), Tasks 1-5 (matchers), Task 6 (validators), Tasks 7-10 (workspace), Task 11 (writeback), Task 12 (hooks), Tasks 13-14 (desugaring) |
| §6.2 Vocabulary registration | Task 0 |
| §6.3 World matcher | Tasks 1-3 |
| §6.4 Capability matcher | Task 4 |
| §6.5 State matcher | Task 5 |
| §6.6 Workspace builder | Tasks 9-10 |
| §6.7 Writeback | Task 11 |
| §6.8 Hook dispatcher | Task 12 |
| §6.9 At-rule sugar desugaring | Tasks 13-14 |
| §7 Testing strategy | Every task has TDD tests; integration tests in Tasks 15-16 |
| §8 Acceptance criteria | Task 17 |

**2. Placeholder scan:** No TBD/TODO. Tasks 2-5 and 9-10 are specified in summary form (not full code) but with enough detail for a subagent to implement independently when also reading the spec. Tasks 12-14 are also summary form.

**3. Type consistency:** Entity dataclasses (FileEntity, DirEntity, etc.) are defined once in Task 0 and used throughout. ManifestEntry fields match between manifest.py (Task 7), strategy.py (Task 8), builder.py (Tasks 9-10), and writeback.py (Task 11). MatcherProtocol methods match the core's protocol definition from v0.1-core Task 18.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-11-umwelt-v01-sandbox.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task (or per batch of 3-5 closely-related tasks), review between batches.

**2. Inline Execution** — Execute tasks in this session with batch checkpoints.

Which approach?
