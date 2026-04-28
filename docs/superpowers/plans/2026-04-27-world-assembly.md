# World Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add generator protocol to entity types, implement filesystem generator for mounts, build assembly pipeline (attach-only), and enhance materialization with provenance-aware rendering.

**Architecture:** Generators are optional capabilities on entity type registrations. Assembly probes generators (Tier 1 attach) to create live AnchorPoints. Materialization walks AnchorPoints at requested depth, merges discovered entities with explicit ones, and renders with provenance grouping. Navigation bounds (`include-patterns`/`exclude-patterns`) are CSS properties resolved by the cascade.

**Tech Stack:** Python dataclasses, `pathlib` for filesystem traversal, `fnmatch` for glob patterns, existing PolicyEngine for two-phase compilation.

**Spec:** `docs/superpowers/specs/2026-04-27-world-assembly-design.md`

---

## Design Decisions

**D1: Generator protocol lives in `src/umwelt/world/generators.py`.** The protocol and AnchorPoint are world-layer concepts. `FilesystemGenerator` lives in `src/umwelt/sandbox/generators.py` because it's a sandbox-specific implementation (like `WorldMatcher`).

**D2: `AssembledWorld` is NOT frozen.** It holds a `PolicyEngine` reference which is mutable. We use a regular `@dataclass` instead of `@dataclass(frozen=True)` — this is a departure from the model.py pattern but necessary since the engine is a live object.

**D3: `materialize()` gains overloaded input.** It accepts either `WorldFile` (existing behavior, no discovery) or `AssembledWorld` (new behavior, with navigation). This preserves backward compatibility — all existing callers pass `WorldFile` and continue to work.

**D4: `render_yaml()` gains keyword args.** `expand: bool = False` and `provenance: str = "all"` control output. Defaults match current behavior (show everything, no provenance grouping) so existing callers are unaffected.

**D5: `_guess_language()` is shared.** The filesystem generator needs the same suffix→language mapping as `WorldMatcher`. We extract it to `src/umwelt/sandbox/entities.py` (where entity types already live) rather than duplicating it.

---

## Files

### New files
| File | Purpose |
|---|---|
| `src/umwelt/world/generators.py` | `GeneratorProtocol`, `AnchorPoint` dataclass |
| `src/umwelt/world/assemble.py` | `assemble()` pipeline — parse, phase-1 compile, resolve bounds, attach |
| `src/umwelt/sandbox/generators.py` | `FilesystemGenerator` implementation |
| `tests/world/test_generators_protocol.py` | Protocol and AnchorPoint tests |
| `tests/world/test_assemble.py` | Assembly pipeline tests |
| `tests/sandbox/test_filesystem_generator.py` | FilesystemGenerator tests |
| `tests/world/test_materialize_provenance.py` | Provenance-aware rendering tests |
| `tests/world/test_cli_assembly.py` | CLI --expand and --provenance flag tests |

### Modified files
| File | Change |
|---|---|
| `src/umwelt/registry/entities.py` | Add `generator` field to `EntitySchema`, param to `register_entity()` |
| `src/umwelt/world/model.py` | Add `AssembledWorld` dataclass |
| `src/umwelt/world/materialize.py` | Accept `AssembledWorld`, provenance-aware rendering |
| `src/umwelt/world/__init__.py` | Export new types and `assemble` |
| `src/umwelt/sandbox/vocabulary.py` | Register generator on mount, add navigation properties |
| `src/umwelt/sandbox/world_matcher.py` | Extract `_guess_language` to shared location |
| `src/umwelt/sandbox/entities.py` | Receive `guess_language()` function |
| `src/umwelt/cli.py` | Add `--expand`, `--provenance`, optional `--stylesheet` to materialize |
| `src/umwelt/errors.py` | Add `AssemblyWarning` (not an error — just a named warning type) |

---

## Tasks

### Task 1: Generator protocol and AnchorPoint

**Files:**
- Create: `src/umwelt/world/generators.py`
- Create: `tests/world/test_generators_protocol.py`

- [ ] **Step 1: Write tests for AnchorPoint construction and GeneratorProtocol shape**

```python
# tests/world/test_generators_protocol.py
import pytest
from umwelt.world.generators import AnchorPoint, GeneratorProtocol
from umwelt.world.model import DeclaredEntity, Provenance


class TestAnchorPoint:
    def test_construction(self):
        entity = DeclaredEntity(type="mount", id="src", attributes={"source": "/tmp"})
        point = AnchorPoint(entity=entity, metadata={"is_enumerable": True})
        assert point.entity.id == "src"
        assert point.metadata["is_enumerable"] is True

    def test_frozen(self):
        entity = DeclaredEntity(type="mount", id="src")
        point = AnchorPoint(entity=entity, metadata={})
        with pytest.raises(AttributeError):
            point.entity = DeclaredEntity(type="mount", id="other")

    def test_metadata_conventions(self):
        entity = DeclaredEntity(type="mount", id="src", attributes={"source": "/tmp"})
        point = AnchorPoint(
            entity=entity,
            metadata={
                "is_enumerable": True,
                "has_descendants": True,
                "estimated_count": 42,
                "max_depth": 3,
                "reachable": True,
            },
        )
        assert point.metadata["estimated_count"] == 42
        assert point.metadata["max_depth"] == 3


class TestGeneratorProtocol:
    def test_protocol_has_required_methods(self):
        """Verify GeneratorProtocol defines the expected interface."""
        assert hasattr(GeneratorProtocol, "attach")
        assert hasattr(GeneratorProtocol, "children")
        assert hasattr(GeneratorProtocol, "exists")

    def test_dummy_generator_satisfies_protocol(self):
        """A class implementing all methods satisfies the protocol."""
        class DummyGenerator:
            name = "dummy"

            def attach(self, entity):
                return AnchorPoint(entity=entity, metadata={})

            def children(self, point, *, depth=1, include=None, exclude=None):
                return iter([])

            def exists(self, point, entity_type, entity_id):
                return None

        gen = DummyGenerator()
        entity = DeclaredEntity(type="mount", id="test")
        point = gen.attach(entity)
        assert isinstance(point, AnchorPoint)
        assert list(gen.children(point)) == []
        assert gen.exists(point, "file", "test.py") is None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/world/test_generators_protocol.py -v
```

- [ ] **Step 3: Implement generators.py**

```python
# src/umwelt/world/generators.py
"""Generator protocol for entity types with runtime children.

A generator makes an entity type *navigable* — it answers "what's under me?"
without requiring children to be declared upfront. This is the DOM navigation
API for umwelt's world tree.

Assembly calls attach() (Tier 1 probe). Materialization calls children() and
exists() (Tiers 3-5). The protocol is entity-type-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator, Protocol, runtime_checkable

if TYPE_CHECKING:
    from umwelt.world.model import DeclaredEntity


@dataclass(frozen=True)
class AnchorPoint:
    """Result of a successful generator probe (Tier 1).

    An anchor point is an entity in the world tree that a generator
    can navigate into. The metadata dict carries probe results —
    generator-defined, but conventionally includes is_enumerable,
    has_descendants, estimated_count, max_depth, reachable.
    """

    entity: DeclaredEntity
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class GeneratorProtocol(Protocol):
    """Interface for entity types with runtime children."""

    name: str

    def attach(self, entity: DeclaredEntity) -> AnchorPoint | None:
        """Tier 1: Probe whether this entity's source exists."""
        ...

    def children(
        self,
        point: AnchorPoint,
        *,
        depth: int = 1,
        include: str | None = None,
        exclude: str | None = None,
    ) -> Iterator[DeclaredEntity]:
        """Tier 5: Enumerate children within navigation bounds."""
        ...

    def exists(
        self,
        point: AnchorPoint,
        entity_type: str,
        entity_id: str,
    ) -> DeclaredEntity | None:
        """Tier 3: Targeted existence check."""
        ...
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/world/test_generators_protocol.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/world/generators.py tests/world/test_generators_protocol.py
git commit -m "feat(world): add GeneratorProtocol and AnchorPoint"
```

---

### Task 2: Add generator field to entity registry

**Files:**
- Modify: `src/umwelt/registry/entities.py`
- Create: `tests/registry/test_entity_generator.py`

- [ ] **Step 1: Write tests for generator field on EntitySchema and register_entity**

```python
# tests/registry/test_entity_generator.py
from umwelt.registry import AttrSchema, register_entity, register_taxon
from umwelt.registry.entities import EntitySchema, get_entity, resolve_entity_type
from umwelt.registry.taxa import registry_scope
from umwelt.world.generators import AnchorPoint, GeneratorProtocol
from umwelt.world.model import DeclaredEntity


class _StubGenerator:
    name = "stub"

    def attach(self, entity):
        return AnchorPoint(entity=entity, metadata={})

    def children(self, point, *, depth=1, include=None, exclude=None):
        return iter([])

    def exists(self, point, entity_type, entity_id):
        return None


class TestEntityGeneratorField:
    def test_default_generator_is_none(self):
        with registry_scope():
            register_taxon(name="test", description="test")
            register_entity(
                taxon="test", name="thing",
                attributes={}, description="a thing",
            )
            schema = get_entity("test", "thing")
            assert schema.generator is None

    def test_register_with_generator(self):
        gen = _StubGenerator()
        with registry_scope():
            register_taxon(name="test", description="test")
            register_entity(
                taxon="test", name="thing",
                attributes={}, description="a thing",
                generator=gen,
            )
            schema = get_entity("test", "thing")
            assert schema.generator is gen
            assert schema.generator.name == "stub"

    def test_generator_preserved_on_lookup(self):
        gen = _StubGenerator()
        with registry_scope():
            register_taxon(name="test", description="test")
            register_entity(
                taxon="test", name="thing",
                attributes={}, description="a thing",
                generator=gen,
            )
            schema = get_entity("test", "thing")
            entity = DeclaredEntity(type="thing", id="x")
            point = schema.generator.attach(entity)
            assert point is not None
            assert point.entity.id == "x"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/registry/test_entity_generator.py -v
```

- [ ] **Step 3: Add generator field to EntitySchema and register_entity**

In `src/umwelt/registry/entities.py`, add the import at the top:

```python
from typing import Any
```

Modify `EntitySchema` to add the generator field:

```python
@dataclass(frozen=True)
class EntitySchema:
    """Metadata for a registered entity type."""

    name: str
    taxon: str
    parent: str | None
    attributes: dict[str, AttrSchema]
    description: str
    category: str | None = None
    generator: Any | None = None
```

Modify `register_entity()` to accept and pass through the generator:

```python
def register_entity(
    *,
    taxon: str,
    name: str,
    attributes: dict[str, AttrSchema],
    description: str,
    parent: str | None = None,
    category: str | None = None,
    generator: Any | None = None,
) -> None:
    """Register an entity type under a taxon."""
    get_taxon(taxon)
    canonical = resolve_taxon(taxon)
    state = _current_state()
    key = (canonical, name)
    if key in state.entities:
        raise RegistryError(
            f"entity {name!r} already registered in taxon {taxon!r}"
        )
    state.entities[key] = EntitySchema(
        name=name,
        taxon=canonical,
        parent=parent,
        attributes=dict(attributes),
        description=description,
        category=category,
        generator=generator,
    )
```

Note: We use `Any` for the generator type to avoid a circular import between `registry.entities` and `world.generators`. The protocol is checked at runtime by callers, not by the registry.

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/registry/test_entity_generator.py -v
```

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest tests/ -x -q
```

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/registry/entities.py tests/registry/test_entity_generator.py
git commit -m "feat(registry): add optional generator field to EntitySchema"
```

---

### Task 3: AssembledWorld data model

**Files:**
- Modify: `src/umwelt/world/model.py`
- Create: `tests/world/test_assembled_world.py`

- [ ] **Step 1: Write tests**

```python
# tests/world/test_assembled_world.py
from umwelt.world.generators import AnchorPoint
from umwelt.world.model import (
    AssembledWorld,
    DeclaredEntity,
    Projection,
    Provenance,
    WorldFile,
    WorldWarning,
)


class TestAssembledWorld:
    def test_construction_minimal(self):
        wf = WorldFile(entities=(), projections=(), warnings=())
        aw = AssembledWorld(
            world_file=wf,
            entities=(),
            anchor_points=(),
            projections=(),
            warnings=(),
            engine=None,
        )
        assert aw.engine is None
        assert len(aw.entities) == 0
        assert len(aw.anchor_points) == 0

    def test_with_entities_and_anchor_points(self):
        mount = DeclaredEntity(
            type="mount", id="src",
            attributes={"source": "/tmp/src"},
            provenance=Provenance.EXPLICIT,
        )
        wf = WorldFile(entities=(mount,), projections=(), warnings=())
        point = AnchorPoint(entity=mount, metadata={"is_enumerable": True})
        aw = AssembledWorld(
            world_file=wf,
            entities=(mount,),
            anchor_points=(point,),
            projections=(),
            warnings=(),
            engine=None,
        )
        assert len(aw.entities) == 1
        assert len(aw.anchor_points) == 1
        assert aw.anchor_points[0].metadata["is_enumerable"] is True

    def test_warnings_preserved(self):
        wf = WorldFile(entities=(), projections=(), warnings=())
        warn = WorldWarning(message="source not found for mount#missing")
        aw = AssembledWorld(
            world_file=wf,
            entities=(),
            anchor_points=(),
            projections=(),
            warnings=(warn,),
            engine=None,
        )
        assert len(aw.warnings) == 1
        assert "mount#missing" in aw.warnings[0].message

    def test_projections_carried_through(self):
        proj = Projection(type="dir", id="node_modules", attributes={"path": "node_modules/"})
        wf = WorldFile(entities=(), projections=(proj,), warnings=())
        aw = AssembledWorld(
            world_file=wf,
            entities=(),
            anchor_points=(),
            projections=(proj,),
            warnings=(),
            engine=None,
        )
        assert len(aw.projections) == 1
        assert aw.projections[0].id == "node_modules"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/world/test_assembled_world.py -v
```

- [ ] **Step 3: Add AssembledWorld to model.py**

Add at the end of `src/umwelt/world/model.py`:

```python
@dataclass
class AssembledWorld:
    """Output of the assembly pipeline.

    Holds explicit entities and live anchor points (generators attached,
    ready to navigate). Discovered entities come from materialization
    or direct navigation — assembly does not enumerate.
    """

    world_file: WorldFile
    entities: tuple[DeclaredEntity, ...]
    anchor_points: tuple[Any, ...]  # AnchorPoint — Any to avoid circular import
    projections: tuple[Projection, ...]
    warnings: tuple[WorldWarning, ...]
    engine: Any | None = None  # PolicyEngine — Any to avoid circular import
```

Note: `AssembledWorld` is NOT frozen (design decision D2). It uses `Any` for `anchor_points` and `engine` to avoid circular imports between model.py and generators.py/engine.py.

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/world/test_assembled_world.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/world/model.py tests/world/test_assembled_world.py
git commit -m "feat(world): add AssembledWorld dataclass"
```

---

### Task 4: FilesystemGenerator

**Files:**
- Modify: `src/umwelt/sandbox/entities.py` (extract `guess_language`)
- Modify: `src/umwelt/sandbox/world_matcher.py` (use shared `guess_language`)
- Create: `src/umwelt/sandbox/generators.py`
- Create: `tests/sandbox/test_filesystem_generator.py`

- [ ] **Step 1: Write tests for FilesystemGenerator**

```python
# tests/sandbox/test_filesystem_generator.py
import os
from pathlib import Path

import pytest

from umwelt.sandbox.generators import FilesystemGenerator
from umwelt.world.generators import AnchorPoint
from umwelt.world.model import DeclaredEntity, Provenance


@pytest.fixture
def source_tree(tmp_path):
    """Create a small filesystem tree for testing."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth").mkdir()
    (tmp_path / "src" / "auth" / "login.py").write_text("# login")
    (tmp_path / "src" / "auth" / "utils.py").write_text("# utils")
    (tmp_path / "src" / "core").mkdir()
    (tmp_path / "src" / "core" / "app.py").write_text("# app")
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "login.cpython-312.pyc").write_bytes(b"\x00")
    (tmp_path / "README.md").write_text("# readme")
    return tmp_path


def _mount_entity(source_path: str) -> DeclaredEntity:
    return DeclaredEntity(
        type="mount", id="test",
        attributes={"source": source_path, "path": "/workspace"},
    )


class TestAttach:
    def test_attach_existing_dir(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        assert point is not None
        assert point.metadata["is_enumerable"] is True
        assert point.metadata["has_descendants"] is True
        assert point.metadata["reachable"] is True

    def test_attach_nonexistent_returns_none(self):
        gen = FilesystemGenerator()
        entity = _mount_entity("/nonexistent/path/xyz")
        assert gen.attach(entity) is None

    def test_attach_no_source_attribute_returns_none(self):
        gen = FilesystemGenerator()
        entity = DeclaredEntity(type="mount", id="empty", attributes={})
        assert gen.attach(entity) is None

    def test_attach_file_not_enumerable(self, source_tree):
        gen = FilesystemGenerator()
        entity = DeclaredEntity(
            type="mount", id="file",
            attributes={"source": str(source_tree / "README.md")},
        )
        point = gen.attach(entity)
        assert point is not None
        assert point.metadata["is_enumerable"] is False


class TestChildren:
    def test_enumerate_depth_1(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        children = list(gen.children(point, depth=1))
        ids = {e.id for e in children}
        assert "src" in ids
        assert "README.md" in ids
        # depth=1: should NOT include nested files
        assert "src/auth/login.py" not in ids

    def test_enumerate_depth_unlimited(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        children = list(gen.children(point, depth=-1))
        ids = {e.id for e in children}
        assert "src/auth/login.py" in ids
        assert "src/core/app.py" in ids
        assert "README.md" in ids

    def test_all_discovered_provenance(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        children = list(gen.children(point, depth=-1))
        assert all(e.provenance == Provenance.DISCOVERED for e in children)

    def test_parent_set_correctly(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        children = list(gen.children(point, depth=-1))
        login = next(e for e in children if e.id == "src/auth/login.py")
        assert login.parent == "src/auth"
        src_dir = next(e for e in children if e.id == "src")
        assert src_dir.parent == "test"  # the mount entity's id

    def test_dirs_and_files_produced(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        children = list(gen.children(point, depth=-1))
        types = {e.type for e in children}
        assert "dir" in types
        assert "file" in types

    def test_file_attributes(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        children = list(gen.children(point, depth=-1))
        login = next(e for e in children if e.id == "src/auth/login.py")
        assert login.attributes["name"] == "login.py"
        assert login.attributes["path"] == "src/auth/login.py"
        assert login.attributes["language"] == "python"

    def test_include_patterns(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        children = list(gen.children(point, depth=-1, include="**/*.py"))
        ids = {e.id for e in children if e.type == "file"}
        assert "src/auth/login.py" in ids
        assert "README.md" not in ids

    def test_exclude_patterns(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        children = list(gen.children(point, depth=-1, exclude="__pycache__/"))
        ids = {e.id for e in children}
        assert not any("__pycache__" in eid for eid in ids)

    def test_include_and_exclude_combined(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        children = list(gen.children(
            point, depth=-1,
            include="**/*.py",
            exclude="__pycache__/",
        ))
        ids = {e.id for e in children if e.type == "file"}
        assert "src/auth/login.py" in ids
        assert not any("__pycache__" in eid for eid in ids)
        assert "README.md" not in ids


class TestExists:
    def test_existing_file(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        result = gen.exists(point, "file", "src/auth/login.py")
        assert result is not None
        assert result.type == "file"
        assert result.provenance == Provenance.DISCOVERED

    def test_nonexistent_file(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        assert gen.exists(point, "file", "src/nope.py") is None

    def test_existing_dir(self, source_tree):
        gen = FilesystemGenerator()
        entity = _mount_entity(str(source_tree))
        point = gen.attach(entity)
        result = gen.exists(point, "dir", "src/auth")
        assert result is not None
        assert result.type == "dir"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/sandbox/test_filesystem_generator.py -v
```

- [ ] **Step 3: Extract `guess_language` to shared location**

Add to the end of `src/umwelt/sandbox/entities.py`:

```python
def guess_language(suffix: str) -> str | None:
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

In `src/umwelt/sandbox/world_matcher.py`, replace the `_guess_language` function with an import:

```python
from umwelt.sandbox.entities import guess_language as _guess_language
```

Remove the old `_guess_language` function definition (lines 120-139).

- [ ] **Step 4: Implement FilesystemGenerator**

```python
# src/umwelt/sandbox/generators.py
"""Filesystem generator for mount entities.

Enumerates directories and files under a mount's source path,
producing DeclaredEntity instances with provenance=DISCOVERED.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterator

from umwelt.sandbox.entities import guess_language
from umwelt.world.generators import AnchorPoint
from umwelt.world.model import DeclaredEntity, Provenance


class FilesystemGenerator:
    """Generator for mount entities backed by a local filesystem."""

    name = "filesystem"

    def attach(self, entity: DeclaredEntity) -> AnchorPoint | None:
        source = entity.attributes.get("source") or entity.attributes.get("path")
        if not source:
            return None
        path = Path(source)
        if not path.exists():
            return None
        is_dir = path.is_dir()
        return AnchorPoint(
            entity=entity,
            metadata={
                "is_enumerable": is_dir,
                "has_descendants": is_dir and any(path.iterdir()),
                "reachable": os.access(path, os.R_OK),
            },
        )

    def children(
        self,
        point: AnchorPoint,
        *,
        depth: int = 1,
        include: str | None = None,
        exclude: str | None = None,
    ) -> Iterator[DeclaredEntity]:
        source = point.entity.attributes.get("source") or point.entity.attributes.get("path")
        if not source:
            return
        root = Path(source)
        if not root.is_dir():
            return

        include_patterns = _parse_patterns(include)
        exclude_patterns = _parse_patterns(exclude)
        mount_id = point.entity.id

        yield from _walk(root, root, mount_id, depth, include_patterns, exclude_patterns)

    def exists(
        self,
        point: AnchorPoint,
        entity_type: str,
        entity_id: str,
    ) -> DeclaredEntity | None:
        source = point.entity.attributes.get("source") or point.entity.attributes.get("path")
        if not source:
            return None
        target = Path(source) / entity_id
        if not target.exists():
            return None
        if entity_type == "file" and target.is_file():
            return _file_entity(target, entity_id, _parent_id(entity_id, point.entity.id))
        if entity_type == "dir" and target.is_dir():
            return _dir_entity(entity_id, _parent_id(entity_id, point.entity.id))
        return None


def _parse_patterns(patterns: str | None) -> list[str]:
    if not patterns:
        return []
    return [p.strip() for p in patterns.split(",") if p.strip()]


def _parent_id(rel_path: str, mount_id: str) -> str:
    parent = str(Path(rel_path).parent)
    if parent == ".":
        return mount_id
    return parent


def _file_entity(abs_path: Path, rel_path: str, parent: str) -> DeclaredEntity:
    return DeclaredEntity(
        type="file",
        id=rel_path,
        attributes={
            "name": abs_path.name,
            "path": rel_path,
            "language": guess_language(abs_path.suffix),
        },
        parent=parent,
        provenance=Provenance.DISCOVERED,
    )


def _dir_entity(rel_path: str, parent: str) -> DeclaredEntity:
    name = Path(rel_path).name
    return DeclaredEntity(
        type="dir",
        id=rel_path,
        attributes={"name": name, "path": rel_path},
        parent=parent,
        provenance=Provenance.DISCOVERED,
    )


def _should_exclude(rel_path: str, is_dir: bool, exclude_patterns: list[str]) -> bool:
    for pat in exclude_patterns:
        if pat.endswith("/"):
            if is_dir and fnmatch.fnmatch(Path(rel_path).name, pat.rstrip("/")):
                return True
        elif fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(Path(rel_path).name, pat):
            return True
    return False


def _matches_include(rel_path: str, include_patterns: list[str]) -> bool:
    if not include_patterns:
        return True
    for pat in include_patterns:
        if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(Path(rel_path).name, pat):
            return True
    return False


def _walk(
    root: Path,
    current: Path,
    mount_id: str,
    depth: int,
    include_patterns: list[str],
    exclude_patterns: list[str],
    _current_depth: int = 0,
) -> Iterator[DeclaredEntity]:
    if depth != -1 and _current_depth >= depth:
        return

    for entry in sorted(current.iterdir()):
        rel = str(entry.relative_to(root))
        is_dir = entry.is_dir()

        if _should_exclude(rel, is_dir, exclude_patterns):
            continue

        parent = _parent_id(rel, mount_id)

        if is_dir:
            yield _dir_entity(rel, parent)
            yield from _walk(
                root, entry, mount_id, depth,
                include_patterns, exclude_patterns,
                _current_depth + 1,
            )
        elif entry.is_file():
            if _matches_include(rel, include_patterns):
                yield _file_entity(entry, rel, parent)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/sandbox/test_filesystem_generator.py -v
```

- [ ] **Step 6: Run full suite to verify world_matcher refactor didn't break anything**

```bash
pytest tests/ -x -q
```

- [ ] **Step 7: Commit**

```bash
git add src/umwelt/sandbox/generators.py src/umwelt/sandbox/entities.py src/umwelt/sandbox/world_matcher.py tests/sandbox/test_filesystem_generator.py
git commit -m "feat(sandbox): add FilesystemGenerator for mount entities"
```

---

### Task 5: Assembly pipeline

**Files:**
- Create: `src/umwelt/world/assemble.py`
- Create: `tests/world/test_assemble.py`
- Modify: `tests/world/conftest.py` (add fixtures)

- [ ] **Step 1: Add fixtures to conftest.py**

Add to `tests/world/conftest.py`:

```python
from umwelt.sandbox.generators import FilesystemGenerator
from umwelt.world.generators import AnchorPoint


@pytest.fixture
def mount_world_yml(tmp_path):
    """World file with a mount entity pointing at a source tree."""
    src = tmp_path / "project" / "src"
    src.mkdir(parents=True)
    (src / "app.py").write_text("# app")
    (src / "utils.py").write_text("# utils")

    p = tmp_path / "test.world.yml"
    p.write_text(
        f"entities:\n"
        f'  - type: mount\n'
        f'    id: source\n'
        f'    attributes:\n'
        f'      source: "{src}"\n'
        f'      path: /workspace\n'
    )
    return p


@pytest.fixture
def world_vocab_with_generator():
    """Registry with mount entity type that has a FilesystemGenerator."""
    with registry_scope():
        register_taxon(name="world", description="test world")
        register_entity(
            taxon="world", name="mount",
            attributes={
                "path": AttrSchema(type=str),
                "source": AttrSchema(type=str),
            },
            description="a mount",
            generator=FilesystemGenerator(),
        )
        register_entity(
            taxon="world", name="dir",
            attributes={"name": AttrSchema(type=str), "path": AttrSchema(type=str)},
            description="a directory",
        )
        register_entity(
            taxon="world", name="file",
            attributes={
                "name": AttrSchema(type=str),
                "path": AttrSchema(type=str),
                "language": AttrSchema(type=str),
            },
            description="a file",
        )
        register_taxon(name="capability", description="test cap")
        register_entity(
            taxon="capability", name="tool",
            attributes={"description": AttrSchema(type=str)},
            description="a tool",
        )
        register_taxon(name="state", description="test state")
        register_entity(
            taxon="state", name="mode",
            attributes={}, description="a mode",
        )
        yield
```

- [ ] **Step 2: Write assembly tests**

```python
# tests/world/test_assemble.py
import pytest
from pathlib import Path

from umwelt.world.assemble import assemble
from umwelt.world.model import AssembledWorld, Provenance


class TestAssemble:
    def test_assemble_with_mount(self, mount_world_yml, world_vocab_with_generator):
        result = assemble(world_path=mount_world_yml)
        assert isinstance(result, AssembledWorld)
        assert len(result.entities) == 1  # just the mount (explicit)
        assert result.entities[0].type == "mount"
        assert len(result.anchor_points) == 1
        assert result.anchor_points[0].metadata["is_enumerable"] is True

    def test_assemble_no_generators(self, minimal_world_yml):
        result = assemble(world_path=minimal_world_yml)
        assert isinstance(result, AssembledWorld)
        assert len(result.anchor_points) == 0
        assert len(result.entities) == 1

    def test_assemble_nonexistent_source_warns(self, tmp_path):
        p = tmp_path / "test.world.yml"
        p.write_text(
            "entities:\n"
            "  - type: mount\n"
            "    id: missing\n"
            "    attributes:\n"
            "      source: /nonexistent/path/xyz\n"
            "      path: /workspace\n"
        )
        with pytest.importorskip("umwelt.registry.taxa").registry_scope():
            from umwelt.registry import AttrSchema, register_entity, register_taxon
            from umwelt.sandbox.generators import FilesystemGenerator
            register_taxon(name="world", description="test")
            register_entity(
                taxon="world", name="mount",
                attributes={"path": AttrSchema(type=str), "source": AttrSchema(type=str)},
                description="a mount",
                generator=FilesystemGenerator(),
            )
            result = assemble(world_path=p)
            assert len(result.anchor_points) == 0
            assert any("source not found" in w.message.lower() or "mount#missing" in w.message for w in result.warnings)

    def test_assemble_preserves_projections(self, tmp_path, world_vocab_with_generator):
        p = tmp_path / "test.world.yml"
        p.write_text(
            "projections:\n"
            "  - type: dir\n"
            "    id: node_modules\n"
            "    attributes:\n"
            "      path: node_modules/\n"
        )
        result = assemble(world_path=p)
        assert len(result.projections) == 1
        assert result.projections[0].id == "node_modules"

    def test_assemble_world_file_preserved(self, mount_world_yml, world_vocab_with_generator):
        result = assemble(world_path=mount_world_yml)
        assert result.world_file is not None
        assert result.world_file.source_path == str(mount_world_yml)
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
pytest tests/world/test_assemble.py -v
```

- [ ] **Step 4: Implement assemble.py**

```python
# src/umwelt/world/assemble.py
"""Assembly pipeline: parse world file, attach generators, produce AssembledWorld.

Assembly probes generators (Tier 1 attach) but does NOT enumerate children.
The resulting AssembledWorld is navigable — callers can probe anchor points
on demand, or pass it to materialize() for eager enumeration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from umwelt.registry.entities import get_entity, resolve_entity_type
from umwelt.world.generators import AnchorPoint
from umwelt.world.model import (
    AssembledWorld,
    DeclaredEntity,
    WorldFile,
    WorldWarning,
)
from umwelt.world.parser import load_world
from umwelt.world.validate import validate_world


def assemble(
    *,
    world_path: str | Path,
    stylesheet_path: str | Path | None = None,
) -> AssembledWorld:
    """Parse a world file and attach generators to enumerable entities.

    If stylesheet_path is provided, compiles a phase-1 PolicyEngine
    against explicit entities and resolves navigation properties
    (include-patterns, exclude-patterns) before attaching generators.
    """
    world = load_world(Path(world_path))
    world = validate_world(world)

    engine = None
    if stylesheet_path is not None:
        engine = _phase_1_compile(world, stylesheet_path)

    anchor_points, attach_warnings = _attach_generators(world.entities, engine)

    warnings = world.warnings + tuple(attach_warnings)

    return AssembledWorld(
        world_file=world,
        entities=world.entities,
        anchor_points=tuple(anchor_points),
        projections=world.projections,
        warnings=warnings,
        engine=engine,
    )


def _phase_1_compile(
    world: WorldFile, stylesheet_path: str | Path,
) -> Any:
    """Compile policy against explicit entities only."""
    from umwelt.policy import PolicyEngine

    entity_dicts = [
        {"type": e.type, "id": e.id, "classes": list(e.classes), "attributes": e.attributes}
        for e in world.entities
    ]
    engine = PolicyEngine()
    for ed in entity_dicts:
        engine.add_entities([ed])
    engine.add_stylesheet(Path(stylesheet_path).read_text())
    return engine


def _attach_generators(
    entities: tuple[DeclaredEntity, ...],
    engine: Any | None,
) -> tuple[list[AnchorPoint], list[WorldWarning]]:
    """Attach generators to enumerable entities (Tier 1 probe)."""
    anchor_points: list[AnchorPoint] = []
    warnings: list[WorldWarning] = []

    for entity in entities:
        taxa = resolve_entity_type(entity.type)
        if not taxa:
            continue

        for taxon in taxa:
            try:
                schema = get_entity(taxon, entity.type)
            except Exception:
                continue

            if schema.generator is None:
                continue

            try:
                point = schema.generator.attach(entity)
            except Exception as exc:
                warnings.append(WorldWarning(
                    message=f"generator error for {entity.type}#{entity.id}: {exc}",
                    key=entity.type,
                ))
                continue

            if point is None:
                warnings.append(WorldWarning(
                    message=f"source not found for {entity.type}#{entity.id}",
                    key=entity.type,
                ))
            else:
                anchor_points.append(point)
            break  # only first matching taxon

    return anchor_points, warnings
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/world/test_assemble.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/world/assemble.py tests/world/test_assemble.py tests/world/conftest.py
git commit -m "feat(world): assembly pipeline with generator attach"
```

---

### Task 6: Provenance-aware materialization

**Files:**
- Modify: `src/umwelt/world/materialize.py`
- Create: `tests/world/test_materialize_provenance.py`

- [ ] **Step 1: Write tests**

```python
# tests/world/test_materialize_provenance.py
import yaml
import pytest

from umwelt.world.generators import AnchorPoint
from umwelt.world.materialize import materialize, render_yaml
from umwelt.world.model import (
    AssembledWorld,
    DeclaredEntity,
    DetailLevel,
    Projection,
    Provenance,
    WorldFile,
)


def _assembled_world_with_mount(tmp_path):
    """Create an AssembledWorld with a mount that has a real source tree."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("# app")
    (src / "utils.py").write_text("# utils")

    mount = DeclaredEntity(
        type="mount", id="source",
        attributes={"source": str(src), "path": "/workspace"},
        provenance=Provenance.EXPLICIT,
    )
    tool = DeclaredEntity(
        type="tool", id="Read",
        attributes={"description": "read files"},
        provenance=Provenance.EXPLICIT,
    )
    from umwelt.sandbox.generators import FilesystemGenerator
    gen = FilesystemGenerator()
    point = gen.attach(mount)

    wf = WorldFile(entities=(mount, tool), projections=(), warnings=())
    return AssembledWorld(
        world_file=wf,
        entities=(mount, tool),
        anchor_points=(point,),
        projections=(),
        warnings=(),
        engine=None,
    )


class TestMaterializeAssembledWorld:
    def test_full_includes_discovered(self, tmp_path):
        aw = _assembled_world_with_mount(tmp_path)
        mw = materialize(aw, level=DetailLevel.FULL)
        assert mw.meta.entity_count > 2  # explicit + discovered
        discovered = [e for e in mw.entities if e.provenance == Provenance.DISCOVERED]
        assert len(discovered) > 0

    def test_summary_no_enumeration(self, tmp_path):
        aw = _assembled_world_with_mount(tmp_path)
        mw = materialize(aw, level=DetailLevel.SUMMARY)
        # Summary: only explicit entities counted, no discovered
        assert mw.meta.entity_count == 2  # mount + tool (explicit only)
        assert len(mw.entities) == 0  # summary never includes entities

    def test_outline_depth_1(self, tmp_path):
        aw = _assembled_world_with_mount(tmp_path)
        mw = materialize(aw, level=DetailLevel.OUTLINE)
        # Outline includes immediate children of mount
        discovered = [e for e in mw.entities if e.provenance == Provenance.DISCOVERED]
        assert len(discovered) > 0
        # Outline strips attributes
        for e in discovered:
            assert e.attributes == {}

    def test_explicit_wins_on_collision(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "special.py").write_text("# special")

        mount = DeclaredEntity(
            type="mount", id="source",
            attributes={"source": str(src), "path": "/workspace"},
            provenance=Provenance.EXPLICIT,
        )
        explicit_file = DeclaredEntity(
            type="file", id="special.py",
            attributes={"name": "special.py", "path": "special.py", "custom": "yes"},
            provenance=Provenance.EXPLICIT,
        )
        from umwelt.sandbox.generators import FilesystemGenerator
        gen = FilesystemGenerator()
        point = gen.attach(mount)
        wf = WorldFile(entities=(mount, explicit_file), projections=(), warnings=())
        aw = AssembledWorld(
            world_file=wf,
            entities=(mount, explicit_file),
            anchor_points=(point,),
            projections=(),
            warnings=(),
            engine=None,
        )
        mw = materialize(aw, level=DetailLevel.FULL)
        specials = [e for e in mw.entities if e.id == "special.py"]
        assert len(specials) == 1
        assert specials[0].provenance == Provenance.EXPLICIT
        assert specials[0].attributes.get("custom") == "yes"

    def test_worldfile_input_still_works(self):
        """Backward compat: materialize() still accepts WorldFile."""
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Read"),),
            projections=(),
            warnings=(),
        )
        mw = materialize(wf, level=DetailLevel.FULL)
        assert mw.meta.entity_count == 1


class TestRenderYamlProvenance:
    def test_default_collapses_discovered(self, tmp_path):
        aw = _assembled_world_with_mount(tmp_path)
        mw = materialize(aw, level=DetailLevel.FULL)
        text = render_yaml(mw)
        parsed = yaml.safe_load(text)
        # Default: discovered section is absent (collapsed)
        assert "discovered" not in parsed or parsed.get("discovered") is None

    def test_expand_includes_discovered(self, tmp_path):
        aw = _assembled_world_with_mount(tmp_path)
        mw = materialize(aw, level=DetailLevel.FULL)
        text = render_yaml(mw, expand=True)
        parsed = yaml.safe_load(text)
        assert "discovered" in parsed
        assert len(parsed["discovered"]) > 0

    def test_provenance_filter_explicit(self, tmp_path):
        aw = _assembled_world_with_mount(tmp_path)
        mw = materialize(aw, level=DetailLevel.FULL)
        text = render_yaml(mw, provenance="explicit")
        parsed = yaml.safe_load(text)
        if parsed.get("entities"):
            for e in parsed["entities"]:
                assert e["provenance"] == "explicit"

    def test_provenance_on_entities(self, tmp_path):
        aw = _assembled_world_with_mount(tmp_path)
        mw = materialize(aw, level=DetailLevel.FULL)
        text = render_yaml(mw, expand=True)
        parsed = yaml.safe_load(text)
        for e in parsed.get("entities", []):
            assert "provenance" in e
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/world/test_materialize_provenance.py -v
```

- [ ] **Step 3: Implement enhanced materialize() and render_yaml()**

Replace the entire contents of `src/umwelt/world/materialize.py` with:

```python
"""Materialization of world state into detail-level-specific snapshots.

Accepts either WorldFile (parse-only, no discovery) or AssembledWorld
(generators attached, navigation available). When given an AssembledWorld,
materialization walks anchor points at the requested depth to discover
entities, then merges with explicit entities.
"""

from __future__ import annotations

import datetime
from collections import Counter
from typing import Any

import yaml

from umwelt.world.model import (
    AssembledWorld,
    DeclaredEntity,
    DetailLevel,
    MaterializedMeta,
    MaterializedWorld,
    Provenance,
    WorldFile,
)


def materialize(
    world: WorldFile | AssembledWorld,
    level: DetailLevel = DetailLevel.FULL,
) -> MaterializedWorld:
    """Return a MaterializedWorld at the requested detail level.

    If *world* is an AssembledWorld, anchor points are navigated at
    depth determined by the detail level. If it's a WorldFile, no
    discovery occurs (backward compatible).
    """
    if isinstance(world, AssembledWorld):
        return _materialize_assembled(world, level)
    return _materialize_world_file(world, level)


def _materialize_world_file(
    world: WorldFile, level: DetailLevel,
) -> MaterializedWorld:
    """Original materialization path — no discovery."""
    type_counts: dict[str, int] = dict(Counter(e.type for e in world.entities))

    if level == DetailLevel.FULL:
        entities = world.entities
    elif level == DetailLevel.OUTLINE:
        entities = tuple(
            DeclaredEntity(
                type=e.type, id=e.id, classes=e.classes,
                attributes={}, parent=e.parent, provenance=e.provenance,
            )
            for e in world.entities
        )
    else:
        entities = ()

    meta = MaterializedMeta(
        source=world.source_path,
        materialized_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        detail_level=level.value,
        entity_count=len(world.entities),
        type_counts=type_counts,
    )

    return MaterializedWorld(
        meta=meta, entities=entities,
        projections=world.projections, warnings=world.warnings,
    )


def _materialize_assembled(
    world: AssembledWorld, level: DetailLevel,
) -> MaterializedWorld:
    """Materialization with generator navigation."""
    explicit = list(world.entities)
    discovered: list[DeclaredEntity] = []

    if level != DetailLevel.SUMMARY:
        depth = 1 if level == DetailLevel.OUTLINE else -1
        for point in world.anchor_points:
            schema = _get_generator_schema(point.entity.type)
            if schema is None or schema.generator is None:
                continue
            include = _resolve_nav_property(world, point.entity, "include-patterns")
            exclude = _resolve_nav_property(world, point.entity, "exclude-patterns")
            try:
                children = list(schema.generator.children(
                    point, depth=depth, include=include, exclude=exclude,
                ))
                discovered.extend(children)
            except Exception:
                pass

    all_entities = _merge(explicit, discovered)

    if level == DetailLevel.OUTLINE:
        all_entities = [
            DeclaredEntity(
                type=e.type, id=e.id, classes=e.classes,
                attributes={}, parent=e.parent, provenance=e.provenance,
            )
            for e in all_entities
        ]

    if level == DetailLevel.SUMMARY:
        type_counts = dict(Counter(e.type for e in explicit))
        final_entities: tuple[DeclaredEntity, ...] = ()
    else:
        type_counts = dict(Counter(e.type for e in all_entities))
        final_entities = tuple(all_entities)

    entity_count = len(explicit) if level == DetailLevel.SUMMARY else len(all_entities)

    meta = MaterializedMeta(
        source=world.world_file.source_path,
        materialized_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        detail_level=level.value,
        entity_count=entity_count,
        type_counts=type_counts,
    )

    return MaterializedWorld(
        meta=meta,
        entities=final_entities,
        projections=world.projections,
        warnings=world.warnings,
    )


def _merge(
    explicit: list[DeclaredEntity],
    discovered: list[DeclaredEntity],
) -> list[DeclaredEntity]:
    """Merge explicit + discovered. Explicit wins on (type, id) collision."""
    seen: set[tuple[str, str]] = {(e.type, e.id) for e in explicit}
    merged = list(explicit)
    for d in discovered:
        key = (d.type, d.id)
        if key not in seen:
            seen.add(key)
            merged.append(d)
    return merged


def _get_generator_schema(type_name: str) -> Any:
    """Look up the entity schema for a type that might have a generator."""
    from umwelt.registry.entities import resolve_entity_type, get_entity
    taxa = resolve_entity_type(type_name)
    for taxon in taxa:
        try:
            return get_entity(taxon, type_name)
        except Exception:
            continue
    return None


def _resolve_nav_property(
    world: AssembledWorld, entity: DeclaredEntity, prop_name: str,
) -> str | None:
    """Resolve a navigation property from the phase-1 engine if available."""
    if world.engine is None:
        return None
    try:
        return world.engine.resolve(type=entity.type, id=entity.id, property=prop_name)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# YAML rendering
# ---------------------------------------------------------------------------


def _entity_to_dict(entity: DeclaredEntity) -> dict[str, Any]:
    d: dict[str, Any] = {"type": entity.type, "id": entity.id}
    if entity.classes:
        d["classes"] = list(entity.classes)
    if entity.attributes:
        d["attributes"] = dict(entity.attributes)
    if entity.parent is not None:
        d["parent"] = entity.parent
    d["provenance"] = entity.provenance.value
    return d


def _projection_to_dict(proj: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"type": proj.type, "id": proj.id}
    if proj.attributes:
        d["attributes"] = dict(proj.attributes)
    return d


def render_yaml(
    materialized: MaterializedWorld,
    *,
    expand: bool = False,
    provenance: str = "all",
) -> str:
    """Serialize *materialized* to a YAML string.

    expand: if True, include individual discovered entities in output.
    provenance: filter entities by provenance ("all", "explicit", "discovered", "projected").
    """
    meta = materialized.meta
    meta_dict: dict[str, Any] = {
        "source": meta.source,
        "materialized_at": meta.materialized_at,
        "detail_level": meta.detail_level,
        "entity_count": meta.entity_count,
        "type_counts": dict(meta.type_counts),
    }

    data: dict[str, Any] = {"meta": meta_dict}

    explicit_entities = [
        e for e in materialized.entities
        if e.provenance != Provenance.DISCOVERED
    ]
    discovered_entities = [
        e for e in materialized.entities
        if e.provenance == Provenance.DISCOVERED
    ]

    if provenance == "all":
        show_explicit = explicit_entities
        show_discovered = discovered_entities
    elif provenance == "explicit":
        show_explicit = explicit_entities
        show_discovered = []
    elif provenance == "discovered":
        show_explicit = []
        show_discovered = discovered_entities
    elif provenance == "projected":
        show_explicit = [e for e in explicit_entities if e.provenance == Provenance.PROJECTED]
        show_discovered = []
    else:
        show_explicit = explicit_entities
        show_discovered = discovered_entities

    if show_explicit:
        data["entities"] = [_entity_to_dict(e) for e in show_explicit]

    if show_discovered and expand:
        data["discovered"] = [_entity_to_dict(e) for e in show_discovered]
    elif show_discovered:
        data.setdefault("meta", {})
        data["meta"]["discovered_count"] = len(show_discovered)
        disc_types = {}
        for e in show_discovered:
            disc_types[e.type] = disc_types.get(e.type, 0) + 1
        data["meta"]["discovered_types"] = disc_types

    if materialized.projections:
        data["projections"] = [_projection_to_dict(p) for p in materialized.projections]

    return yaml.dump(data, default_flow_style=False, sort_keys=False)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/world/test_materialize_provenance.py -v
```

- [ ] **Step 5: Run existing materialize tests to verify backward compat**

```bash
pytest tests/world/test_materialize.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/world/materialize.py tests/world/test_materialize_provenance.py
git commit -m "feat(world): provenance-aware materialization with AssembledWorld support"
```

---

### Task 7: Navigation properties on vocabulary

**Files:**
- Modify: `src/umwelt/sandbox/vocabulary.py`
- Create: `tests/sandbox/test_navigation_properties.py`

- [ ] **Step 1: Write tests**

```python
# tests/sandbox/test_navigation_properties.py
from umwelt.registry.taxa import registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.registry.entities import get_entity


class TestNavigationProperties:
    def test_mount_has_generator(self):
        with registry_scope():
            register_sandbox_vocabulary()
            schema = get_entity("world", "mount")
            assert schema.generator is not None
            assert schema.generator.name == "filesystem"

    def test_include_patterns_registered(self):
        with registry_scope():
            register_sandbox_vocabulary()
            from umwelt.registry.properties import get_property
            prop = get_property(taxon="world", entity="mount", name="include-patterns")
            assert prop is not None

    def test_exclude_patterns_registered(self):
        with registry_scope():
            register_sandbox_vocabulary()
            from umwelt.registry.properties import get_property
            prop = get_property(taxon="world", entity="mount", name="exclude-patterns")
            assert prop is not None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/sandbox/test_navigation_properties.py -v
```

- [ ] **Step 3: Add generator and navigation properties to vocabulary**

In `src/umwelt/sandbox/vocabulary.py`, add the import near the top of the file with the other imports:

```python
from umwelt.sandbox.generators import FilesystemGenerator
```

Modify the `mount` registration call (around line 257) to include the generator:

```python
    register_entity(
        taxon="world",
        name="mount",
        parent="world",
        attributes={
            "path": AttrSchema(type=str, required=True, description="Mount destination path inside the workspace"),
            "source": AttrSchema(type=str, description="Host path or URL this mount maps from"),
            "type": AttrSchema(type=str, description="Mount type: bind, tmpfs, overlay"),
        },
        description="A bind mount or tmpfs in the workspace.",
        category="workspace",
        generator=FilesystemGenerator(),
    )
```

Add after the existing mount property registrations (after line 287):

```python
    register_property(taxon="world", entity="mount", name="include-patterns", value_type=str, description="Generator navigation inclusion patterns (generator-interpreted).")
    register_property(taxon="world", entity="mount", name="exclude-patterns", value_type=str, description="Generator navigation exclusion patterns (generator-interpreted).")
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/sandbox/test_navigation_properties.py -v
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -x -q
```

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/sandbox/vocabulary.py tests/sandbox/test_navigation_properties.py
git commit -m "feat(sandbox): register FilesystemGenerator and navigation properties on mount"
```

---

### Task 8: CLI enhancements

**Files:**
- Modify: `src/umwelt/cli.py`
- Create: `tests/world/test_cli_assembly.py`

- [ ] **Step 1: Write tests**

```python
# tests/world/test_cli_assembly.py
import yaml
import pytest
from pathlib import Path
from umwelt.cli import build_parser, main


class TestMaterializeFlags:
    def test_expand_flag_accepted(self):
        parser = build_parser()
        args = parser.parse_args(["materialize", "test.world.yml", "--expand"])
        assert args.expand is True

    def test_expand_default_false(self):
        parser = build_parser()
        args = parser.parse_args(["materialize", "test.world.yml"])
        assert args.expand is False

    def test_provenance_flag_accepted(self):
        parser = build_parser()
        args = parser.parse_args(["materialize", "test.world.yml", "--provenance", "explicit"])
        assert args.provenance == "explicit"

    def test_provenance_default_all(self):
        parser = build_parser()
        args = parser.parse_args(["materialize", "test.world.yml"])
        assert args.provenance == "all"

    def test_stylesheet_flag_accepted(self):
        parser = build_parser()
        args = parser.parse_args(["materialize", "test.world.yml", "--stylesheet", "policy.umw"])
        assert args.stylesheet == "policy.umw"


class TestMaterializeWithMount:
    def test_materialize_mount_world(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("# app")

        p = tmp_path / "test.world.yml"
        p.write_text(
            f"entities:\n"
            f"  - type: mount\n"
            f"    id: source\n"
            f"    attributes:\n"
            f'      source: "{src}"\n'
            f"      path: /workspace\n"
        )
        rc = main(["materialize", str(p)])
        assert rc == 0

    def test_materialize_expand(self, tmp_path, capsys):
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("# app")

        p = tmp_path / "test.world.yml"
        p.write_text(
            f"entities:\n"
            f"  - type: mount\n"
            f"    id: source\n"
            f"    attributes:\n"
            f'      source: "{src}"\n'
            f"      path: /workspace\n"
        )
        rc = main(["materialize", str(p), "--expand"])
        assert rc == 0
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert "discovered" in parsed

    def test_materialize_provenance_explicit(self, tmp_path, capsys):
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("# app")

        p = tmp_path / "test.world.yml"
        p.write_text(
            f"entities:\n"
            f"  - type: mount\n"
            f"    id: source\n"
            f"    attributes:\n"
            f'      source: "{src}"\n'
            f"      path: /workspace\n"
        )
        rc = main(["materialize", str(p), "--provenance", "explicit"])
        assert rc == 0
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert "discovered" not in parsed
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/world/test_cli_assembly.py -v
```

- [ ] **Step 3: Update CLI**

In `src/umwelt/cli.py`, replace the `_cmd_materialize` function:

```python
def _cmd_materialize(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    from umwelt.errors import WorldParseError
    from umwelt.world.materialize import materialize, render_yaml
    from umwelt.world.model import DetailLevel

    level = DetailLevel(args.level)
    expand = getattr(args, "expand", False)
    provenance = getattr(args, "provenance", "all")
    stylesheet = getattr(args, "stylesheet", None)

    try:
        if stylesheet:
            from umwelt.world.assemble import assemble
            world = assemble(world_path=Path(args.file), stylesheet_path=stylesheet)
        else:
            from umwelt.world.assemble import assemble
            world = assemble(world_path=Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except WorldParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    result = materialize(world, level=level)
    output = render_yaml(result, expand=expand, provenance=provenance)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Materialized to {args.output}")
    else:
        print(output, end="")
    return 0
```

In the `build_parser()` function, update the materialize subparser (around line 424):

```python
    p_mat = subparsers.add_parser("materialize", help="materialize a .world.yml file")
    p_mat.add_argument("file", help="path to a .world.yml file")
    p_mat.add_argument("--level", choices=["summary", "outline", "full"], default="full",
                       help="detail level (default: full)")
    p_mat.add_argument("-o", "--output", default=None, help="output file path")
    p_mat.add_argument("--expand", action="store_true", help="include individual discovered entities in output")
    p_mat.add_argument("--provenance", choices=["all", "explicit", "discovered", "projected"],
                       default="all", help="filter entities by provenance (default: all)")
    p_mat.add_argument("--stylesheet", default=None, help="path to .umw stylesheet for navigation property resolution")
    p_mat.set_defaults(func=_cmd_materialize)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/world/test_cli_assembly.py -v
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -x -q
```

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/cli.py tests/world/test_cli_assembly.py
git commit -m "feat(cli): add --expand, --provenance, --stylesheet to materialize"
```

---

### Task 9: Update public API + integration test

**Files:**
- Modify: `src/umwelt/world/__init__.py`
- Create: `tests/world/test_assembly_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/world/test_assembly_integration.py
"""End-to-end test: world file with mount → assemble → materialize → render."""
import yaml
from pathlib import Path

from umwelt.registry.taxa import registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.world import assemble, materialize, render_yaml
from umwelt.world.model import DetailLevel, Provenance


def test_full_pipeline(tmp_path):
    src = tmp_path / "project" / "src"
    src.mkdir(parents=True)
    (src / "auth").mkdir()
    (src / "auth" / "login.py").write_text("# login")
    (src / "auth" / "utils.py").write_text("# utils")
    (src / "app.py").write_text("# app")

    p = tmp_path / "delegate.world.yml"
    p.write_text(
        f"tools: [Read, Edit]\n"
        f"modes: [implement]\n"
        f"entities:\n"
        f"  - type: mount\n"
        f"    id: source\n"
        f"    attributes:\n"
        f'      source: "{src}"\n'
        f"      path: /workspace\n"
    )

    with registry_scope():
        register_sandbox_vocabulary()

        # Assemble — attach generators
        assembled = assemble(world_path=p)
        assert len(assembled.anchor_points) == 1
        assert assembled.anchor_points[0].metadata["is_enumerable"] is True

        # Materialize at all three levels
        for level in DetailLevel:
            mw = materialize(assembled, level=level)
            text = render_yaml(mw)
            parsed = yaml.safe_load(text)
            assert "meta" in parsed

        # Full: has discovered entities
        mw_full = materialize(assembled, level=DetailLevel.FULL)
        discovered = [e for e in mw_full.entities if e.provenance == Provenance.DISCOVERED]
        assert len(discovered) >= 3  # auth/, auth/login.py, auth/utils.py, app.py

        # Explicit entities preserved
        explicit = [e for e in mw_full.entities if e.provenance == Provenance.EXPLICIT]
        explicit_types = {e.type for e in explicit}
        assert "tool" in explicit_types
        assert "mount" in explicit_types

        # Render with expand
        text = render_yaml(mw_full, expand=True)
        parsed = yaml.safe_load(text)
        assert "discovered" in parsed
        assert len(parsed["discovered"]) > 0

        # Render with provenance filter
        text = render_yaml(mw_full, provenance="explicit")
        parsed = yaml.safe_load(text)
        assert "discovered" not in parsed

        # Summary: no enumeration
        mw_summary = materialize(assembled, level=DetailLevel.SUMMARY)
        assert len(mw_summary.entities) == 0


def test_no_mount_no_discovery(tmp_path):
    p = tmp_path / "simple.world.yml"
    p.write_text("tools: [Read, Edit]\nmodes: [implement]\n")

    with registry_scope():
        register_sandbox_vocabulary()
        assembled = assemble(world_path=p)
        assert len(assembled.anchor_points) == 0
        mw = materialize(assembled, level=DetailLevel.FULL)
        assert all(e.provenance != Provenance.DISCOVERED for e in mw.entities)
```

- [ ] **Step 2: Update `__init__.py` exports**

```python
# src/umwelt/world/__init__.py
"""World state subpackage: parse, assemble, and materialize .world.yml files."""

from __future__ import annotations

from umwelt.world.assemble import assemble
from umwelt.world.generators import AnchorPoint, GeneratorProtocol
from umwelt.world.materialize import materialize, render_yaml
from umwelt.world.model import (
    AssembledWorld,
    DeclaredEntity,
    DetailLevel,
    MaterializedMeta,
    MaterializedWorld,
    Projection,
    Provenance,
    WorldFile,
    WorldWarning,
)
from umwelt.world.parser import load_world
from umwelt.world.validate import validate_world

__all__ = [
    "AnchorPoint",
    "AssembledWorld",
    "DeclaredEntity",
    "DetailLevel",
    "GeneratorProtocol",
    "MaterializedMeta",
    "MaterializedWorld",
    "Projection",
    "Provenance",
    "WorldFile",
    "WorldWarning",
    "assemble",
    "load_world",
    "materialize",
    "render_yaml",
    "validate_world",
]
```

- [ ] **Step 3: Run integration test**

```bash
pytest tests/world/test_assembly_integration.py -v
```

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v
```

- [ ] **Step 5: Run ruff**

```bash
ruff check src/umwelt/world/ src/umwelt/sandbox/generators.py src/umwelt/registry/entities.py tests/world/ tests/sandbox/test_filesystem_generator.py
```

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/world/__init__.py tests/world/test_assembly_integration.py
git commit -m "feat(world): public API + integration test for world assembly"
```

---

## Verification

After all tasks:

1. **Unit tests pass:** `pytest tests/world/ tests/sandbox/test_filesystem_generator.py tests/sandbox/test_navigation_properties.py tests/registry/test_entity_generator.py -v`
2. **Full suite passes:** `pytest tests/ -v` — no regressions
3. **Lint passes:** `ruff check src/umwelt/world/ src/umwelt/sandbox/ src/umwelt/registry/entities.py`
4. **CLI works end-to-end:**
   ```bash
   # Create a test world file
   cat > /tmp/test.world.yml << 'EOF'
   entities:
     - type: mount
       id: source
       attributes:
         source: "/tmp/test-src"
         path: /workspace
     - type: tool
       id: Read
       attributes:
         description: "Read files"
   EOF
   mkdir -p /tmp/test-src/auth
   echo "# login" > /tmp/test-src/auth/login.py
   echo "# readme" > /tmp/test-src/README.md

   umwelt materialize /tmp/test.world.yml
   umwelt materialize /tmp/test.world.yml --level summary
   umwelt materialize /tmp/test.world.yml --expand
   umwelt materialize /tmp/test.world.yml --provenance explicit
   umwelt materialize /tmp/test.world.yml --provenance discovered --expand
   umwelt materialize /tmp/test.world.yml -o /tmp/snapshot.yml
   ```
5. **Python API works:**
   ```python
   from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
   from umwelt.registry.taxa import registry_scope
   from umwelt.world import assemble, materialize, render_yaml
   from umwelt.world.model import DetailLevel

   with registry_scope():
       register_sandbox_vocabulary()
       assembled = assemble(world_path="/tmp/test.world.yml")
       print(f"Anchor points: {len(assembled.anchor_points)}")
       for ap in assembled.anchor_points:
           print(f"  {ap.entity.type}#{ap.entity.id}: {ap.metadata}")
       mw = materialize(assembled, level=DetailLevel.FULL)
       print(render_yaml(mw, expand=True))
   ```
