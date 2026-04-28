# World Assembly: Generator Protocol + Provenance-Aware Materialization

*How the world tree gains runtime children through generators, and how materialization renders the result with provenance awareness.*

---

## 1. Problem

umwelt's world tree is currently static. Every entity must be explicitly declared in a `.world.yml` file or expanded from a shorthand. But many entity types have children that aren't known until runtime:

- A **mount** contains directories and files on the host filesystem
- A **kit** contains tools exposed by an MCP server
- A **file** contains AST nodes (functions, classes) that require parsing
- A **network** endpoint may expose sub-resources discoverable only by probing

Today, the `discover:` block in world files is stashed as `discover_raw` with a "not yet implemented" warning. The `WorldMatcher` in the sandbox does a hardcoded filesystem walk with an implicit `base_dir`. There's no protocol for entity types to declare "I can enumerate my children at runtime."

Additionally, `umwelt materialize` renders all entities uniformly. There's no way to distinguish hand-declared entities from runtime-discovered ones, and no way to collapse bulk discovery (10,000 files under a mount) into a manageable summary.

---

## 2. Design principles

1. **The generator is the DOM navigation API.** Entity types that can have runtime children register a generator. The generator answers "what's under me?" — the same question the DOM's `childNodes` answers. It doesn't trigger batch enumeration; it makes the entity *navigable*.

2. **Entity types own their discovery.** The generator is registered on the entity type, not as a separate plugin. When you register `mount`, you can say "mounts are enumerable via this generator." Any entity type can be enumerable — mounts, kits, files, anything.

3. **Navigation bounds are policy.** `include-patterns` and `exclude-patterns` are CSS properties resolved by the cascade. Different modes or contexts can scope the same entity differently. The generator reads resolved bounds, not hardcoded config.

4. **Provenance is metadata, not policy.** Every entity carries a `provenance` tag (explicit, discovered, projected, included). Provenance tells auditors *how* the entity entered the world. It informs trust decisions without encoding them.

5. **Materialization depth is caller-controlled.** The detail level (summary, outline, full) controls how deep the pipeline navigates into enumerable entities. Summary probes; outline lists immediate children; full recurses.

---

## 3. Generator protocol

### 3.1 AnchorPoint

The result of a successful probe. An anchor point is an entity in the world tree that a generator can navigate into.

```python
@dataclass(frozen=True)
class AnchorPoint:
    entity: DeclaredEntity       # the entity being navigated into
    metadata: dict               # what the probe learned without enumerating
```

The `metadata` dict carries probe results — generator-defined, but conventionally:

| Key | Type | Meaning |
|---|---|---|
| `is_enumerable` | bool | Can children be listed? |
| `has_descendants` | bool | Are there any children? |
| `estimated_count` | int \| None | Approximate child count, if cheap to determine |
| `max_depth` | int \| None | Deepest nesting level, if known |
| `reachable` | bool | Is the source accessible right now? |

### 3.2 GeneratorProtocol

```python
class GeneratorProtocol(Protocol):
    name: str

    def attach(self, entity: DeclaredEntity) -> AnchorPoint | None:
        """Tier 1: Probe whether this entity's source exists.

        Reads location from entity.attributes (path, source, server, etc.).
        Returns an AnchorPoint with metadata if the source exists,
        None if it doesn't (the world file declared it, but it's not there).
        """
        ...

    def children(
        self,
        point: AnchorPoint,
        *,
        depth: int = 1,
        include: str | None = None,
        exclude: str | None = None,
    ) -> Iterator[DeclaredEntity]:
        """Tier 5: Enumerate children within navigation bounds.

        depth=1 is immediate children. depth=-1 is unlimited recursion
        within this generator's domain. Children are returned with
        parent set to the anchor entity's id and provenance=DISCOVERED.

        include/exclude are generator-interpreted pattern strings,
        typically from resolved CSS properties on the anchor entity.
        """
        ...

    def exists(
        self,
        point: AnchorPoint,
        entity_type: str,
        entity_id: str,
    ) -> DeclaredEntity | None:
        """Tier 3: Targeted existence check.

        Does a specific entity exist under this anchor point?
        More efficient than full enumeration when you only need one answer.

        Default implementation: iterate children() and filter.
        Generators may override for efficiency (e.g., stat() instead of readdir()).
        """
        ...
```

The tiers referenced in docstrings map to the progressive discovery model:

| Tier | Method | Question |
|---|---|---|
| 1 | `attach()` | Does this source exist? What can I learn without traversing? |
| 3 | `exists()` | Does a specific entity exist under this point? |
| 5 | `children()` | What entities are under this point? |

Tiers 2 (richer metadata) and 4 (reachability/access checks) are expressed through `attach()` metadata and future protocol extensions. They are not separate methods in this design.

### 3.3 Registration

The generator is an optional field on entity type registration:

```python
register_entity(
    taxon="world",
    name="mount",
    attributes={
        "path": AttrSchema(type=str, required=True),
        "source": AttrSchema(type=str),
        "type": AttrSchema(type=str),
    },
    generator=FilesystemGenerator(),
    description="A bind mount or tmpfs in the workspace.",
    category="workspace",
)
```

The generator is stored on the entity schema in the registry. Looked up via:

```python
from umwelt.registry.entities import get_entity_type

schema = get_entity_type("mount")
if schema and schema.generator:
    point = schema.generator.attach(entity)
```

Not every entity type has a generator. Entity types without generators are leaf nodes or nodes whose children are always explicitly declared.

### 3.4 What generators are NOT

- **Not matchers.** Matchers evaluate selectors against entities (`match_type`, `get_attribute`, `children` in the selector sense). Generators enumerate entities from external sources. Different protocols, different jobs.
- **Not batch jobs.** Generators don't "run" during assembly. They're called when someone navigates into an enumerable entity. Materialization controls when and how deep.
- **Not restricted to files.** Any entity type can have a generator. The protocol is entity-type-agnostic.

---

## 4. Navigation properties

### 4.1 `include-patterns` and `exclude-patterns`

CSS properties registered on any enumerable entity type. Resolved by the cascade, consumed by the generator as navigation bounds.

```css
/* Scope a mount to Python sources */
mount#source {
    include-patterns: "**/*.py";
    exclude-patterns: "__pycache__/, *.pyc";
}

/* In review mode, narrow further */
mode#review mount#source {
    include-patterns: "**/*.test.py";
}
```

Registration:

```python
register_property(
    taxon="world",
    entity="mount",
    name="include-patterns",
    value_type=str,
    description="Generator navigation inclusion patterns (generator-interpreted).",
)

register_property(
    taxon="world",
    entity="mount",
    name="exclude-patterns",
    value_type=str,
    description="Generator navigation exclusion patterns (generator-interpreted).",
)
```

The pattern values are **generator-interpreted strings**. A filesystem generator treats them as globs. A future MCP generator might treat them as name patterns. The cascade resolves which value wins; the generator decides what the value means.

### 4.2 Restrictive direction

For this round: `include-patterns` and `exclude-patterns` use standard last-wins-by-specificity cascade semantics (same as any string property). A more specific rule replaces the value entirely.

Future work: set-valued property types with intersection semantics for `include-patterns` (narrowing) and union semantics for `exclude-patterns` (widening). This requires the set-valued comparison type described in the entity model spec.

### 4.3 Resolution flow

The assembly pipeline resolves navigation properties on enumerable entities *before* calling the generator. This creates a two-phase compilation:

1. Compile policy against explicit entities only
2. Resolve `include-patterns`/`exclude-patterns` on enumerable entities
3. Pass resolved values to the generator during navigation
4. Discovered entities added; policy re-resolved against the full set

---

## 5. Assembly and materialization

### 5.1 Two-stage model: assemble then materialize

Assembly and materialization are distinct operations with different responsibilities and consumers:

| Stage | Input | Output | What it does | Consumers |
|---|---|---|---|---|
| `load_world()` | `.world.yml` | `WorldFile` | Parse YAML | Assembly |
| `assemble()` | `WorldFile` + stylesheet | `AssembledWorld` | Attach generators (Tier 1 probes), resolve navigation bounds | PolicyEngine, compilers, materialization |
| `materialize()` | `AssembledWorld` + detail level | `MaterializedWorld` | Walk the tree at requested depth (Tiers 3-5), merge, snapshot | Humans, audit tools, snapshots |

**Assembly** makes the tree **navigable** — generators are attached, anchor points are live, navigation bounds are resolved from policy. But nothing is enumerated. The `AssembledWorld` is a lazy object: you can call `exists()` or `children()` on its anchor points at any time.

**Materialization** **walks** the tree eagerly at the requested detail level. It's one consumer of assembly, not the only one. PolicyEngine can work against an assembled world directly — explicit entities are known, and discovered entities are resolvable on demand via anchor points (predicate mode).

### 5.2 `assemble()` function

```python
from umwelt.world import assemble

assembled = assemble(
    world_path="delegate.world.yml",
    stylesheet_path="policy.umw",     # optional: needed for navigation property resolution
)
```

### 5.3 Assembly pipeline

```
load_world()          Parse YAML → WorldFile (explicit entities, projections)
        ↓
phase_1_compile()     Compile policy against explicit entities only
        ↓
resolve_bounds()      Resolve include-patterns/exclude-patterns on enumerable entities
        ↓
attach()              For each enumerable entity:
                        generator.attach(entity) → AnchorPoint | None
                        Store successful anchor points (live, navigable)
                        Warnings for failed attaches
        ↓
validate()            Run vocabulary validation
        ↓
AssembledWorld        Explicit entities + live anchor points, ready to navigate
```

Assembly does NOT call `children()` or `exists()`. It probes (Tier 1) only. The tree is navigable after assembly; materialization or direct API calls navigate it.

### 5.4 Materialization pipeline

```python
from umwelt.world import materialize

snapshot = materialize(assembled, detail=DetailLevel.FULL)
```

```
AssembledWorld        Explicit entities + live anchor points
        ↓
navigate()            For each anchor point at requested depth:
                        generator.children(point, depth, include, exclude)
                        Tag results with provenance=DISCOVERED
        ↓
merge()               Combine explicit + discovered. Explicit wins on (type, id) collision.
        ↓
phase_2_compile()     Re-resolve policy against full entity set (via engine.extend())
        ↓
MaterializedWorld     All entities, provenance tagged, concrete snapshot
```

### 5.5 `AssembledWorld` type

```python
@dataclass(frozen=True)
class AssembledWorld:
    world_file: WorldFile                   # the original parse result
    entities: tuple[DeclaredEntity, ...]    # explicit entities only
    anchor_points: tuple[AnchorPoint, ...]  # live — generators attached, ready to navigate
    projections: tuple[Projection, ...]     # from world file
    warnings: tuple[WorldWarning, ...]      # parse + validation + attach failures
    engine: PolicyEngine | None             # phase 1 engine (explicit entities + resolved bounds)
```

`AssembledWorld` wraps `WorldFile` and adds:
- `anchor_points` — live handles for on-demand navigation (`exists()`, `children()`)
- `engine` — the phase 1 PolicyEngine with resolved navigation properties, available for direct queries against explicit entities
- `entities` — explicit entities only (discovered entities come from materialization or direct navigation)

### 5.6 Navigation depth by detail level

| Detail level | Generator calls (during materialization) | Result |
|---|---|---|
| SUMMARY | None (attach already done during assembly) | AnchorPoint metadata (counts, reachability). No children enumerated. |
| OUTLINE | `children(depth=1)` | Immediate children with type + id + classes. No attributes. |
| FULL | `children(depth=-1)` | Full recursive tree with all attributes. |

### 5.7 Merge semantics (during materialization)

When explicit and discovered entities share the same `(type, id)`:

- **Explicit wins.** The explicit entity is kept; the discovered entity is discarded.
- **Provenance preserved.** The winning entity retains its original provenance (`EXPLICIT`).
- **No merge of attributes.** The explicit declaration is the complete truth. Discovery doesn't supplement it.

This matches the existing merge pattern in `parser.py` where explicit entities override shorthands.

### 5.8 Error handling

| Condition | Stage | Behavior |
|---|---|---|
| Entity type has no generator | Assembly | Skip silently (not enumerable) |
| `attach()` returns None | Assembly | Warning: "source not found for mount#source" |
| `attach()` raises | Assembly | Warning: "generator error for mount#source: {message}" |
| `children()` raises | Materialization | Warning: "enumeration failed for mount#source: {message}" |
| Unknown entity type in results | Materialization | Warning via `validate_world()` (soft) |

Generator failures are always soft — they produce warnings, never errors. A world with a broken mount is still a valid world; it just has fewer entities than expected. This matches the forward-compatibility pattern throughout umwelt.

---

## 6. FilesystemGenerator

The first generator shipped with umwelt. Registered on the `mount` entity type in the sandbox vocabulary.

### 6.1 Behavior

```python
class FilesystemGenerator:
    name = "filesystem"

    def attach(self, entity: DeclaredEntity) -> AnchorPoint | None:
        source = entity.attributes.get("source") or entity.attributes.get("path")
        if not source:
            return None
        path = Path(source)
        if not path.exists():
            return None
        return AnchorPoint(
            entity=entity,
            metadata={
                "is_enumerable": path.is_dir(),
                "has_descendants": any(path.iterdir()) if path.is_dir() else False,
                "reachable": os.access(path, os.R_OK),
            },
        )

    def children(self, point, *, depth=1, include=None, exclude=None):
        # Walk filesystem under point.entity's source path
        # Apply include/exclude as glob patterns during traversal
        # Yield DeclaredEntity(type="dir"|"file", provenance=DISCOVERED)
        # Respect depth limit
        ...

    def exists(self, point, entity_type, entity_id):
        # stat() the specific path instead of walking
        ...
```

### 6.2 Entity production

The filesystem generator produces two entity types:

| Discovered type | Attributes | Parent |
|---|---|---|
| `dir` | `name`, `path` (relative to mount) | parent dir's id, or mount id for top-level |
| `file` | `name`, `path` (relative to mount), `language` (from extension) | containing dir's id |

All discovered entities get `provenance=DISCOVERED` and `parent` set to their containing directory (or the mount entity for top-level entries).

### 6.3 Pattern interpretation

The filesystem generator interprets `include-patterns` and `exclude-patterns` as glob patterns (using `fnmatch` semantics):

- `**/*.py` — any Python file at any depth
- `__pycache__/` — any directory named \_\_pycache\_\_
- `*.pyc` — any .pyc file

Patterns are applied during traversal, not as a post-filter. Excluded directories are not descended into.

---

## 7. Provenance-aware materialization

### 7.1 Rendering model

Materialization output groups entities by provenance and collapses discovered entities by default:

```yaml
meta:
  source: delegate.world.yml
  materialized_at: "2026-04-27T14:00:00Z"
  detail_level: full
  entity_count: 352
  type_counts:
    mount: 1
    dir: 47
    file: 298
    tool: 5
    mode: 1

# Explicit entities — shown in full
entities:
  - type: tool
    id: Read
    attributes:
      description: "Read file contents"
    provenance: explicit

  - type: tool
    id: Edit
    attributes:
      description: "Edit file contents"
    provenance: explicit

  - type: mode
    id: implement
    provenance: explicit

# Enumerable entities — mount points with discovery summary
  - type: mount
    id: source
    attributes:
      path: "/workspace"
      source: "/home/teague/Projects/foo/src"
    provenance: explicit
    enumerable: true
    discovered_children: 345     # count of children found
    discovered_types:            # breakdown by type
      dir: 47
      file: 298

# Discovered entities (collapsed by default)
# Use --expand to include individual discovered entities

projections:
  - type: mount
    id: node_modules
    attributes:
      path: "/workspace/node_modules"
    # Not enumerated — projection boundary
```

### 7.2 `--expand` flag

`umwelt materialize world.yml --expand` includes all discovered entities in the output:

```yaml
# ... explicit entities as above ...

discovered:
  - type: dir
    id: auth
    parent: source
    provenance: discovered
  - type: file
    id: auth/login.py
    parent: auth
    attributes:
      name: login.py
      path: auth/login.py
      language: python
    provenance: discovered
  # ... 343 more ...
```

### 7.3 `--provenance` filter

`umwelt materialize world.yml --provenance explicit` shows only explicit entities. Useful for auditing what was hand-declared vs. discovered.

Options: `all`, `explicit`, `discovered`, `projected`. Default: `all` (with discovered collapsed unless `--expand`).

---

## 8. Changes to existing code

### 8.1 Registry changes

**`src/umwelt/registry/entities.py`:**
- `EntitySchema` gains optional `generator: GeneratorProtocol | None` field
- `register_entity()` gains optional `generator` parameter
- `get_entity_type()` return value exposes `generator`

**`src/umwelt/registry/taxa.py`:**
- No changes. Generators are stored on entity schemas, not on `RegistryState` directly.

### 8.2 World layer changes

**`src/umwelt/world/model.py`:**
- Add `AnchorPoint` dataclass
- Add `AssembledWorld` dataclass

**`src/umwelt/world/assemble.py`** (new):
- `assemble()` — main entry point
- `_navigate()` — enumerate children of enumerable entities
- `_merge()` — combine explicit + discovered with collision resolution

**`src/umwelt/world/materialize.py`:**
- `materialize()` accepts `AssembledWorld` in addition to `WorldFile`
- Provenance-aware rendering: group by provenance, collapse discovered
- `render_yaml()` supports `expand` and `provenance` options

### 8.3 Sandbox vocabulary changes

**`src/umwelt/sandbox/vocabulary.py`:**
- Register `FilesystemGenerator()` on the `mount` entity type
- Register `include-patterns` and `exclude-patterns` properties on `mount`

### 8.4 CLI changes

**`src/umwelt/cli.py`:**
- `umwelt materialize` gains `--expand` and `--provenance` flags
- `umwelt materialize` calls `assemble()` instead of `load_world()` when a stylesheet is provided (needed for navigation property resolution)
- `umwelt assemble` as an alias or separate subcommand (TBD during planning)

### 8.5 What does NOT change

- The `.umw` view format
- The cascade resolver
- The selector engine
- The compiler protocol
- The `MatcherProtocol`
- Existing `load_world()` (still works for parse-only, no discovery)
- Existing `PolicyEngine` API (assembly feeds into it, doesn't replace it)

---

## 9. Scope

### This round (A + B)

- Generator protocol: `GeneratorProtocol`, `AnchorPoint`
- `generator` field on `register_entity()`
- `include-patterns`/`exclude-patterns` as CSS properties
- Two-phase assembly pipeline
- `FilesystemGenerator` for `mount` entity type
- Provenance-aware materialization with `--expand` and `--provenance`
- CLI integration

### Deferred (round C and beyond)

- **Overrides + fixed constraints** — post-discovery attribute modification, immutable world-level constraints
- **Pattern-based parent selectors** — `discover` recipes that match classes of entities, not specific IDs (e.g., discover AST nodes for all Python files)
- **Fixed-point iteration** — cascading discovery where one generator's output feeds another's input
- **Additional generators** — MCP, AST, git, HTTP
- **Caching/audit** — track what was actually enumerated at runtime, not just what could be
- **Set-valued restrictive direction** — intersection semantics for `include-patterns`, union for `exclude-patterns`
- **`vars:` substitution** — template variables in world files for environment-specific bindings

---

## 10. Relationship to existing specs

- **World State Layer** (`docs/vision/world-state.md`): This design implements Phase 3's "configurable discovery recipes" from section 9, but via generators on entity types rather than a separate `discover:` block. The `discover:` block is superseded by navigation properties + enumerable entity types.
- **Entity Model** (`docs/vision/entity-model.md`): Generators extend the entity model with runtime navigation. The `GeneratorProtocol` is a new capability on `EntitySchema`.
- **Policy Engine** (`docs/guide/policy-engine.md`): The two-phase compilation (resolve bounds → enumerate → re-resolve) uses `engine.extend()` for phase 2. No changes to the engine itself.
- **Resolution Modes** (`docs/guide/how-it-works.md`): Generators bridge the table/predicate gap — discovered entities start as predicate-mode (navigated on demand) and become table-mode after materialization.
