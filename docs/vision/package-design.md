# umwelt: Package Design

*Module layout, public API, runtime components, compiler interface, and roadmap. This document describes the shape of the package; it does not duplicate the policy-layer framing (see [`policy-layer.md`](./policy-layer.md)), the entity model (see [`entity-model.md`](./entity-model.md)), the format specification (see [`view-format.md`](./view-format.md)), or the individual compiler mappings (see [`compilers/`](./compilers)).*

## Goals

- **Be the common language of the specified band.** Parse, represent, validate, and compile views into whatever enforcement tool's native format each altitude accepts, without committing to any specific enforcement tool.
- **Stay vocabulary-agnostic in the core.** Core umwelt knows nothing about files, tools, or networks. It knows about selectors, cascade, and compilers. Consumers register their taxa; the core composes them.
- **Stay a leaf dependency.** No runtime imports of nsjail-python, bwrap, lackpy, pluckit, or any enforcement tool's Python wrapper.
- **Target native text formats.** Compilers emit whatever config format the underlying enforcement binary already accepts — nsjail protobuf textproto, bwrap argv, lackpy namespace dict, etc. Enforcement tools do not change to accommodate umwelt.
- **Be embeddable and scriptable.** Library API for Python consumers (lackpy primarily), CLI for shell users, text configs for direct pipe-and-redirect workflows.
- **Be extensible.** New taxa, new entities, new properties, new compilers can all be added without modifying the core. Plugin registration is the extension surface.

## Non-goals for v1

- **Selector-level workspace extraction.** v1 treats `file[...]` at file granularity — the entire matching file set enters the virtual workspace. Selector filters down to node level inside source files are parsed, stored in the AST, but only evaluated via pluckit at v1.1+.
- **The view bank.** Storage, retrieval, git-history distillation of views is a phase-2 concern. The module slot (`umwelt/bank/`) exists, but it's empty in v1.
- **Interactive / multi-turn workspace lifecycle.** v1 workspaces (in the sandbox consumer) are one-shot: build, run delegate, apply or reject changes, tear down. Long-lived workspaces come later.
- **Write-back conflict resolution.** v1 fails loudly if a real file has been modified since the virtual workspace was built. No three-way merge; the caller inspects and retries.
- **Enforcement itself.** umwelt emits configs; it does not run delegates or gate tool calls. Runners are a thin convenience layer over subprocess invocation, not a core feature.
- **Authoring tools.** v1 is read-only for the format. Programmatic view construction (AST → text) comes in v1.1 alongside the ratchet utility and view bank.
- **Full `actor` and `policy` taxa.** v1 ships minimal `actor` entities (just `inferencer` and `executor`) and an empty `policy` taxon slot; full treatment is v1.1+.
- **Cross-taxon validation invariants.** v1 validators run per-taxon. Rules like "if `tool[name='Bash']` is allowed then `resource[kind='wall-time']` must set a limit" are v1.1+.
- **LLM-based anything.** No trained judgment anywhere in the package. The ratchet is specified end-to-end.

## The core / sandbox split

Core umwelt is vocabulary-agnostic. It provides the parser, AST, selector engine, cascade resolver, compiler protocol, plugin registry, and CLI — but no hardcoded vocabulary and no runtime behavior beyond what's needed to evaluate views.

The **sandbox consumer** (`umwelt.sandbox`) is a first-party package ship-alongside that registers the canonical sandbox taxa (`world`, `capability`, `state`), provides the workspace builder + writeback + hook dispatcher, and registers the first compilers (nsjail, bwrap, lackpy-namespace, kibitzer-hooks). It is a regular consumer of core umwelt — it uses the same registration API any third-party consumer would use — but it ships in the same repository and PyPI package for convenience.

Other consumers (blq integration, agent-riggs integration, future policy domains) register their own taxa and compilers against core umwelt the same way. None are privileged; all are regular consumers of the common-language contract.

This split is load-bearing for v1:

- **Core is reusable.** A consumer that doesn't care about filesystems can still use core umwelt for policy layering (e.g., a rate-limiting-policy consumer, an access-control consumer).
- **Sandbox is replaceable.** A consumer that disagrees with how `umwelt.sandbox` models things (different entity attributes, different cascade semantics, different compilers) can register an alternative under a different taxon namespace without forking the core.
- **Testing is tractable.** Core tests use a toy taxonomy registered in-test; sandbox tests use the real sandbox taxa. The test suites don't cross-contaminate.

## Package layout

```
umwelt/                                      # repository / PyPI package root
├── pyproject.toml                           # hatchling backend; deps=[tinycss2]
├── README.md
├── LICENSE                                  # MIT
├── CHANGELOG.md
├── .gitignore
├── .github/workflows/ci.yml
├── docs/                                    # pre-existing; vision + specs + future user docs
└── src/
    └── umwelt/                              # the package
        ├── __init__.py                      # public API re-exports
        ├── py.typed
        │
        # ─── core umwelt (vocabulary-agnostic) ───────────────────────
        ├── ast.py                           # View, RuleBlock, Selector, Declaration, etc.
        ├── parser.py                        # tinycss2-backed parser
        ├── errors.py                        # ViewParseError, ViewValidationError, ...
        │
        ├── registry/                        # the plugin registration surface
        │   ├── __init__.py                  # register_taxon, register_entity, register_property, ...
        │   ├── taxa.py                      # taxon registry
        │   ├── entities.py                  # entity schema registry
        │   ├── properties.py                # property + comparison semantics registry
        │   ├── matchers.py                  # matcher protocol + registration
        │   └── validators.py                # per-taxon validator registry
        │
        ├── selector/                        # selector evaluation engine
        │   ├── __init__.py
        │   ├── parse.py                     # selector parsing (subset of CSS3 + umwelt extensions)
        │   ├── specificity.py               # CSS3 specificity computation
        │   └── match.py                     # evaluation against a matcher
        │
        ├── cascade/                         # cascade resolver
        │   ├── __init__.py
        │   └── resolver.py                  # per-taxon cascade with specificity + document order
        │
        ├── compilers/                       # compiler protocol + registry
        │   ├── __init__.py
        │   └── protocol.py                  # Compiler protocol, registry, altitude declaration
        │
        ├── validate.py                      # runs registered validators over a parsed View
        ├── cli.py                           # umwelt parse | inspect | compile | dry-run | ratchet | check | diff
        │
        # ─── utilities ─────────────────────────────────────────────
        ├── inspect_util.py                  # umwelt inspect implementation
        ├── dry_run.py                       # umwelt dry-run implementation
        ├── ratchet.py                       # umwelt ratchet scaffold
        ├── diff_util.py                     # umwelt diff implementation
        │
        # ─── sandbox consumer (first-party; regular consumer of core) ─
        ├── sandbox/
        │   ├── __init__.py                  # registers taxa at import time
        │   ├── vocabulary.py                # world / capability / state taxon registration
        │   ├── world_matcher.py             # filesystem matcher for the world taxon
        │   ├── capability_matcher.py        # tool-registry matcher for the capability taxon
        │   ├── state_matcher.py             # state matcher (jobs, hooks, budgets)
        │   ├── workspace/
        │   │   ├── __init__.py              # Workspace, WorkspaceBuilder, WriteBack
        │   │   ├── builder.py
        │   │   ├── writeback.py
        │   │   ├── manifest.py
        │   │   └── strategy.py              # pluggable MaterializationStrategy
        │   ├── hooks/
        │   │   ├── __init__.py
        │   │   └── dispatcher.py            # @after-change / hook[event="after-change"] runner
        │   ├── compilers/                   # sandbox-consumer compilers
        │   │   ├── __init__.py              # registers compilers at import time
        │   │   ├── nsjail.py                # view → nsjail textproto
        │   │   ├── bwrap.py                 # view → bwrap argv
        │   │   ├── lackpy_namespace.py      # view → lackpy namespace dict
        │   │   └── kibitzer_hooks.py        # view → kibitzer hook rules
        │   └── runners/
        │       ├── __init__.py
        │       ├── nsjail.py                # convenience: compile view → write temp config → invoke nsjail
        │       └── bwrap.py                 # convenience: compile view → build argv → invoke bwrap
        │
        ├── bank/                            # v2 placeholder
        │   └── __init__.py                  # empty in v1
        │
        └── _fixtures/                       # reference view files for tests and examples
            ├── minimal.umw
            ├── readonly-exploration.umw
            ├── auth-fix.umw
            └── test-runner.umw
```

### Size estimates (v1)

| Module | Lines of code (est) |
|---|---|
| **Core umwelt** | |
| `parser.py` + `ast.py` | ~300 |
| `registry/` | ~250 |
| `selector/` | ~250 |
| `cascade/` | ~100 |
| `compilers/protocol.py` | ~60 |
| `validate.py` + `errors.py` | ~120 |
| `cli.py` | ~200 |
| `inspect_util.py` + `dry_run.py` + `diff_util.py` + `ratchet.py` (scaffold) | ~300 |
| **Core total** | **~1,580 lines** |
| **Sandbox consumer** | |
| `sandbox/vocabulary.py` + matchers | ~300 |
| `sandbox/workspace/` | ~300 |
| `sandbox/hooks/` | ~100 |
| `sandbox/compilers/nsjail.py` | ~200 |
| `sandbox/compilers/bwrap.py` | ~150 |
| `sandbox/compilers/lackpy_namespace.py` | ~100 |
| `sandbox/compilers/kibitzer_hooks.py` | ~100 |
| `sandbox/runners/` | ~150 |
| **Sandbox total** | **~1,400 lines** |
| | |
| **Total implementation** | **~3,000 lines** |
| Tests (unit + integration + fixtures) | ~2,500 lines |
| **Total package** | **~5,500 lines** |

Core umwelt (~1,600 lines) is now smaller than the original monolithic plan suggested and is meaningfully reusable without the sandbox consumer. The sandbox consumer (~1,400 lines) is concentrated in the modules that care about enforcement specifically.

### Dependencies

**Runtime (required):**

- Python 3.10+
- `tinycss2` — CSS-3 tokenizer. Used for view file parsing. See [`implementation-language.md`](./implementation-language.md) for the rationale.

**Runtime (optional):**

- `nsjail-python` — if installed, `sandbox.runners.nsjail` can use its serializer as a validator for the hand-rolled textproto output. Not required; the compiler emits textproto without it.
- `pluckit` — if installed, the v1.1 `sandbox.workspace.builder` can perform selector-level extraction inside `file node[...]` blocks. Not required in v1.

**Development:**

- `pytest` for tests
- `ruff` for linting
- `mypy` for type checking

No tree-sitter, no protobuf library, no nsjail-python, no bwrap wrapper at runtime. The only required non-stdlib dependency is tinycss2 for CSS tokenization.

## Public API

### Core parsing and representation

```python
from umwelt import parse, View, ViewParseError

view: View = parse("views/auth-fix.umw")          # file path
view: View = parse("file[path^='src/']{editable:true;}")   # or raw string
view: View = parse(Path("..."))                    # or Path
```

`parse()` is the single entry point for core umwelt. It auto-detects whether the input is a path or a view-text string. Returns a `View` AST dataclass. Raises `ViewParseError` with line/column on malformed input. Runs validators from the registry by default unless `parse(text, validate=False)` is passed.

### Plugin registration

```python
from umwelt.registry import (
    register_taxon, register_entity, register_property,
    register_matcher, register_validator,
    AttrSchema, EntitySchema,
)

register_taxon(
    name="world",
    description="Entities the actor can couple to.",
    ma_concept="world_coupling_axis",
)

register_entity(
    taxon="world",
    name="file",
    parent="dir",
    attributes={
        "path": AttrSchema(type=str, required=True),
        "language": AttrSchema(type=str, required=False),
    },
    description="A file in the filesystem.",
    category="filesystem",
)

register_property(
    taxon="world",
    entity="file",
    name="editable",
    value_type=bool,
    comparison=None,
    description="Whether the actor may modify this file.",
    category="access_mode",
)
```

This is what `umwelt.sandbox` calls at import time. Third-party consumers follow the same pattern. See [`entity-model.md`](./entity-model.md) §6 for the full API reference.

### Compiler protocol and registry

```python
from typing import Protocol
from umwelt.ast import View

class Compiler(Protocol):
    """A compiler translates a View to an enforcement target's native config."""
    target_name: str                       # e.g. "nsjail", "bwrap"
    target_format: str                     # e.g. "textproto", "argv", "dict"
    altitude: str                          # "os", "language", "semantic", "conversational"
    
    def compile(self, view: View) -> str | list[str] | dict:
        """Translate a view to the target's native format."""
        ...
```

Compilers register themselves at import time:

```python
from umwelt.compilers import register

register("nsjail", NsjailCompiler())
register("bwrap",  BwrapCompiler())
```

The registry allows `umwelt compile --target nsjail view.umw` to work uniformly across all registered compilers, including third-party ones. Each compiler declares its altitude so `umwelt dry-run` can report which rules are honestly enforced by the currently-registered compilers vs. which are declarative-only.

### Workspace lifecycle (sandbox consumer)

```python
from umwelt import parse
from umwelt.sandbox.workspace import WorkspaceBuilder, WriteBack

view = parse("views/auth-fix.umw")

# Build a workspace
workspace = WorkspaceBuilder().build(view, base_dir=Path.cwd())

# Inspect it
print(workspace.root)
for entry in workspace.manifest.entries:
    print(entry.real_path, entry.virtual_path, entry.writable)

# After a delegate has operated inside workspace.root ...
result = WriteBack().apply(workspace)
print(result.applied_changes)
print(result.rejected_changes)
print(result.conflicts)

workspace.cleanup()
```

Workspace building is a sandbox-consumer concern, not core. A consumer that doesn't need workspace materialization (e.g., a policy-only consumer that consumes views as data) never touches this API.

As a context manager:

```python
with WorkspaceBuilder().build(view, base_dir=Path.cwd()) as workspace:
    # delegate operates inside workspace.root
    result = WriteBack().apply(workspace)
    # cleanup on exit
```

### Utilities

```python
from umwelt import inspect, dry_run, ratchet, diff, check

inspect(view)                                      # structural summary
dry_run(view, world_snapshot=Path.cwd())           # which entities each rule matches
ratchet(view, observations="blq://...", output="proposed.umw")   # ratchet the view from observations
check(view)                                        # parser + validator + all compilers
diff(view_a, view_b)                               # compare two views
```

Each utility is a thin wrapper over the core parser, registry, and cascade resolver. See [`entity-model.md`](./entity-model.md) §11 for functional previews.

### CLI

```bash
# Parse and validate a view file
umwelt parse views/auth-fix.umw

# Structural summary
umwelt inspect views/auth-fix.umw

# Compile a view to a target's native format
umwelt compile --target nsjail  views/auth-fix.umw
umwelt compile --target bwrap   views/auth-fix.umw

# Compile and run directly (sandbox consumer runners)
umwelt run --target nsjail views/auth-fix.umw -- python delegate.py

# Check parser + validator + compilers
umwelt check views/auth-fix.umw

# Dry-run: which rules match which entities in the current working directory
umwelt dry-run views/auth-fix.umw

# Ratchet: propose a view revision from observations
umwelt ratchet views/auth-fix.umw --observations blq:///tmp/blq.duckdb

# Diff two views
umwelt diff a.umw b.umw
```

The CLI is ~200 lines total, built on argparse (stdlib). It's a thin wrapper over the library API, dispatching to the utilities and the sandbox runners.

## Runtime components in detail

### Parser and AST

The parser is thin glue over `tinycss2`, which handles CSS-3 tokenization (strings, numbers with units, comments, at-rule prelude/block separation, nested blocks). umwelt's parser walks tinycss2's token stream and constructs the `View` AST. See [`implementation-language.md`](./implementation-language.md) for the decision rationale and [`view-format.md`](./view-format.md) for the grammar.

**Parser responsibilities:**

- Invoke `tinycss2.parse_stylesheet()` on the input text.
- Walk the token stream, recognizing at-rules and top-level rule blocks.
- For at-rules with umwelt sugar semantics (`@source`, `@tools`, `@after-change`, `@network`, `@budget`, `@env`), desugar to entity-selector form during parsing (the sugar is syntactic; the AST is canonical).
- For at-rules that are taxon scopes (`@world { ... }`, `@capability { ... }`), unwrap and prefix the inner selectors with the taxon name.
- Parse selectors into the internal selector AST (subset of CSS3 + umwelt extensions; see `selector/parse.py`).
- Parse declarations into `Declaration(property_name, values, span)` entries.
- Preserve unknown at-rules, unknown entity types, and unknown declarations with warning flags.
- Raise `ViewParseError` with line/column on syntactic errors.

**Port-ready decomposition**: the parser is a pure function — `parse(text: str) -> View`. No side effects, no dependencies on the runtime. If umwelt ever needs a Rust parser for performance reasons, it can be swapped in behind the same interface without touching downstream code. See [`implementation-language.md`](./implementation-language.md).

### Registry

The plugin registry holds the runtime metadata for all registered taxa, entities, properties, matchers, validators, and compilers. Registration happens at import time (when a consumer module is imported, it calls `register_*` to announce its contributions). The registry is global-but-explicit — no auto-discovery, no entry points, just module-level code that consumers invoke.

Registry responsibilities:

- Accept `register_taxon`, `register_entity`, `register_property`, `register_matcher`, `register_validator`, `register_compiler` calls.
- Reject duplicate names within a namespace (taxa, entity types per taxon, properties per entity).
- Provide lookup APIs for the parser (for validation), the selector engine (for matcher resolution), the cascade resolver (for property semantics), and the CLI (for `umwelt inspect`).

### Selector engine

`selector/` parses CSS-shaped selector text into an internal AST and evaluates it against a world snapshot via a registered matcher.

Selector AST:

```python
@dataclass(frozen=True)
class SimpleSelector:
    type_name: str | None       # "file", "tool", "*", or None
    id: str | None              # "#README.md"
    classes: tuple[str, ...]    # ".test"
    attributes: tuple[AttrFilter, ...]
    pseudo: tuple[PseudoClass, ...]

@dataclass(frozen=True)
class ComplexSelector:
    parts: tuple[tuple[SimpleSelector, Combinator], ...]
    taxon: str                  # "world", "capability", ...
```

The engine translates `ComplexSelector` into match predicates the registered matcher understands. Each taxon's matcher is responsible for walking its own world (filesystem, tool registry, hook schedule, etc.) and returning matched entities.

### Cascade resolver

Given a parsed View and a matcher, the cascade resolver:

1. Evaluates each rule's selector against the matcher, producing `{entity: rule}` pairs.
2. Groups rules by taxon (cascade is scoped per taxon).
3. For each taxon, for each entity, computes the set of matching rules and their specificity.
4. Applies property-level cascade: for each property, the winning rule is the one with highest specificity, ties broken by document order.
5. Produces a `ResolvedView` with `{taxon: {entity: {property: value}}}` — the final policy after cascade.

Compilers read the `ResolvedView`, not the raw `View`. This way compilers never reimplement cascade.

### Sandbox consumer runtime components

#### Virtual workspace builder

For each `file[...]` rule in the resolved view, the workspace builder:

1. Resolves the selector against the base directory via the filesystem matcher.
2. For each matched file, determines editability from the cascaded `editable` property.
3. Physically materializes the entry via the registered `MaterializationStrategy`:
   - **Read-only**: symlink `workspace_root/virtual_path` → `real_path`; hash at build time for violation detection.
   - **Writable**: copy the file to `workspace_root/virtual_path`; hash at build time for applied-change detection.
4. Records the entry in the manifest.

The workspace root is a temp directory under the system temp dir (or a user-specified location via `base_dir=`).

**Why v1 uses file-level matching, not selector-level extraction?** Simplicity. Walking file paths and materializing them is ~30 lines of code. Selector-level extraction inside files requires calling pluckit to find matching nodes, determining line ranges, and constructing virtual files that are slices of real files — an order of magnitude more work with its own write-back complications. Deferred to v1.1.

**The strategy is pluggable.** Consumers (or alternative sandbox implementations) can register a different `MaterializationStrategy` for e.g. remote stage-in, snapshot-based filesystems, or in-memory ephemeral workspaces. The v1 default is `SymlinkReadonlyCopyWritable`.

#### Write-back layer

After the delegate finishes, write-back walks the manifest and compares each virtual file to its original state. See [`entity-model.md`](./entity-model.md) §3.3 and the v0.1 scoping spec for the detailed state table.

The write-back returns a `WriteBackResult` with `applied_changes`, `rejected_changes`, and `conflicts`. The caller decides whether to raise on violations or return the structured result. Default CLI behavior is to raise with a summary; library consumers pick their own error policy.

#### Hook dispatcher

Straightforward subprocess runner for `hook[event="after-change"] { run: "..." }` rules:

1. For each resolved hook entity with its `run` commands, iterate the commands in document order.
2. Run each command via `subprocess.run(shlex.split(command), cwd=context.project_root, capture_output=True, timeout=...)`.
3. Collect `HookResult` objects with `command`, `stdout`, `stderr`, `returncode`, `duration_seconds`, `timed_out`.
4. Return the list. Hook failures do not abort subsequent hooks in v1 — the dispatcher runs all of them and reports.

### Core compilers (protocol only)

Core umwelt ships zero concrete compilers. The `compilers/protocol.py` module defines the `Compiler` protocol and the registry; concrete compilers ship in consumers (`umwelt.sandbox.compilers.*`, third-party packages, etc.). This keeps core umwelt free of any coupling to specific enforcement tools.

### Sandbox compilers

The sandbox consumer ships four compilers:

- **`nsjail`** — emits protobuf textproto. OS altitude. See [`compilers/nsjail.md`](./compilers/nsjail.md).
- **`bwrap`** — emits argv list + wrapper command. OS altitude. See [`compilers/bwrap.md`](./compilers/bwrap.md).
- **`lackpy-namespace`** — emits a Python dict representing a lackpy namespace restriction. Language altitude. Doc TBD.
- **`kibitzer-hooks`** — emits a kibitzer hook rules dict. Semantic altitude. Doc TBD.

Each is a pure function from `ResolvedView` to the target's native format, with a mapping table that's stable-ish (target binaries' config formats change slowly).

## Testing strategy

Three layers.

### Unit tests

**Core:**

- **Parser**: every at-rule, every declaration type, every unit, nested blocks, comments, unknown-construct preservation, malformed inputs with line/column assertions, selector parsing.
- **Registry**: register / lookup / duplicate-detection for every kind (taxa, entities, properties, matchers, validators, compilers).
- **Selector engine**: every selector form, every combinator, pseudo-classes, attribute operators, specificity computation.
- **Cascade resolver**: specificity ordering, document-order tiebreaking, per-taxon scoping, property-level cascade, comparison-property value handling.
- **Each utility**: `inspect`, `dry-run`, `diff`, `ratchet` (scaffold). Tests use a toy taxonomy registered in a fixture.

**Sandbox consumer:**

- **Vocabulary registration**: the sandbox taxa register without errors, all attributes and properties are accessible via the registry.
- **World matcher**: single source, multiple sources, overlapping sources (last-block-wins cascade), missing globs (empty match, warning), path traversal attempts (rejected).
- **Write-back**: all six cells of the state table (applied / rejected / conflict × writable / read-only), mixed applied/rejected/conflict case.
- **Hook dispatcher**: success, failure (one command fails, others continue), timeout, missing command.
- **Each compiler**: every mapping row in its table, plus at least one "view with constructs outside this compiler's altitude — output ignores them cleanly" test.

### Integration tests

- **End-to-end parse+validate+compile**: each fixture in `_fixtures/` parses, validates, and compiles to every registered compiler target.
- **End-to-end workspace lifecycle**: build a workspace from `auth-fix.umw` against a temp project tree, simulate edits, run writeback, assert outcomes.
- **End-to-end with nsjail runner** (skipped if `nsjail` binary not on PATH): small view, trivial delegate command, assert it executed inside the jail.
- **End-to-end with bwrap runner** (skipped if `bwrap` binary not on PATH): same pattern.
- **Cross-compiler consistency**: parse a view, compile it to all targets, assert each output is syntactically valid for its target.

### Example-based tests

- **Reference views under `_fixtures/`**: 5-10 hand-written view files covering the common patterns. Each fixture has a sibling `expected/` directory with the expected textproto, argv, dict, and `ResolvedView` JSON outputs for regression testing.
- **Mixed-form fixtures**: at least one fixture uses only at-rule sugar, one uses only entity-selector form, and one mixes both. All three must parse to the same `ResolvedView`.

## Roadmap

### v0.1-core — the vocabulary-agnostic walking skeleton (weekend one)

- Parser + AST for the core grammar (entity selectors + at-rule sugar for the sandbox vocabulary)
- Registry with `register_taxon`, `register_entity`, `register_property`, `register_matcher`, `register_validator`
- Selector parsing and specificity computation
- Cascade resolver
- `compilers/protocol.py` — Compiler protocol + registry (no concrete compilers)
- `validate.py` running registered validators
- `errors.py`
- Minimal CLI: `umwelt parse file.umw`, `umwelt inspect file.umw`
- Toy taxonomy fixture registered in tests
- Unit tests for parser, registry, selector engine, cascade

**Goal:** "I can parse a view against a toy taxonomy, match selectors, resolve cascade, and inspect the result." No sandbox specifics yet, no compilers, no workspace. The demo is against a fixture taxonomy built inside the test suite.

### v0.1-sandbox — the first consumer (weekend two)

- `umwelt.sandbox.vocabulary`: register `world` / `capability` / `state` taxa
- `umwelt.sandbox.world_matcher`: filesystem matcher with glob + path attribute selectors
- `umwelt.sandbox.capability_matcher`: tool registry matcher (minimal — takes a declared tool list)
- `umwelt.sandbox.state_matcher`: hooks + resources + budgets
- `umwelt.sandbox.workspace.*`: builder + writeback + manifest + strategy
- `umwelt.sandbox.hooks.dispatcher`
- At-rule sugar desugaring for `@source`, `@tools`, `@after-change`, `@network`, `@budget`, `@env`
- Fixtures: `minimal.umw`, `readonly-exploration.umw`, `auth-fix.umw`
- `umwelt dry-run` utility (matched entities per rule)
- Unit tests for each sandbox component
- Integration test: end-to-end workspace lifecycle with `auth-fix.umw`

**Goal:** "I can build a workspace from a sandbox view, modify files, apply write-back." Still no compilers — that's v0.2.

### v0.2 — the first compiler (weekend three)

- `umwelt.sandbox.compilers.nsjail` emitting textproto for the full mapping table
- `umwelt.sandbox.runners.nsjail` — temp file + subprocess
- Integration tests against a real `nsjail` binary
- Expanded `_fixtures/` with expected nsjail textproto outputs
- CLI: `umwelt compile --target nsjail` and `umwelt run --target nsjail`
- `umwelt check` utility

**Goal:** "I can run a subprocess inside an nsjail built from a view."

### v0.3 — second compiler and the ratchet scaffold (weekend four)

- `umwelt.sandbox.compilers.bwrap` emitting argv + wrapper command
- `umwelt.sandbox.runners.bwrap`
- Additional fixtures with expected bwrap outputs
- CLI: `umwelt compile --target bwrap`
- `umwelt ratchet` scaffold: accepts an observation source plugin, runs narrowing, emits proposed view
- First observation source plugin: blq database reader (reads resource metrics from `.bird/blq.duckdb`)
- Integration test: run a trivial delegate under bwrap; observe resources with blq; feed into ratchet; emit a tightened view

**Goal:** "Two enforcement targets work. The ratchet turns once, end-to-end, specified the whole way."

### v0.4 — lackpy integration and PyPI release

- `umwelt.sandbox.compilers.lackpy_namespace`
- Published as a pip package on PyPI
- lackpy updated to depend on umwelt for the view runtime
- Example view + lackpy delegate end-to-end
- `umwelt diff` utility

**Goal:** "lackpy's view executor is a ~200-line wrapper around umwelt, and it works."

### v0.5 — kibitzer, consolidation, API freeze

- `umwelt.sandbox.compilers.kibitzer_hooks`
- Security pass: threat model, parser hardening, fuzz tests
- Documentation polish
- Public API freeze for v1.0

**Goal:** "Four consumers work (lackpy, kibitzer, a CLI user, blq). Ready for v1.0."

### v1.0 — ship

- Release to PyPI
- Blog post

### v1.1 — selector-level extraction, delegate-context compiler, actor taxon

- Optional pluckit dependency for node-level selectors inside `file ... node[...]`
- `compilers/delegate_context.py` — the view-projection compiler (SELinux coda)
- `:has()` and `:phase()` pseudo-classes
- Full `actor` taxon treatment
- Cross-taxon validation invariants
- `View.to_string()` for the ratchet utility

### v2 — the view bank

- `bank/` module with SQLite or DuckDB storage
- `umwelt bank add` / `list` / `find` subcommands
- Git-history distillation: walk `git log`, extract views corresponding to commits/PRs/branches, populate the bank
- Similarity search for retrieval
- `policy/` meta-taxon for views-about-views

## Open questions

Resolved questions have been rolled into the specs in `docs/superpowers/specs/`. The open questions remaining at the package-design level:

1. **Symlink farm vs full copies for read-only files.** v1 plan is symlinks for read-only, copies for writable. Concern: some tools resolve symlinks before editing and may accidentally write to the real file. Mitigation: the default strategy is `SymlinkReadonlyCopyWritable`; environments where symlinks misbehave can register an alternative strategy.

2. **How does the delegate learn the workspace layout?** Options: (a) emit a `.umw-manifest.json` in the workspace root, (b) include the manifest in the delegate's prompt, (c) both, (d) the v1.1 delegate-context compiler handles this and obviates the need for a separate manifest file. Leaning toward (d).

3. **Compiler registry priority ordering.** If two compilers claim the same `target_name`, which wins? v1: registration is last-write-wins with a warning. v1.1 may add explicit priority.

4. **Textproto hand-rolling vs library dependency.** The nsjail compiler emits textproto by hand. When escaping gets tricky (strings with newlines, nested messages), the hand-rolled emitter may mishandle cases. Mitigation: `nsjail-python` as optional validator.

5. **CLI framework: argparse, click, or typer?** Minimizing additional dependencies beyond `tinycss2` is a goal — argparse (stdlib) wins. Revisit only if a compelling reason emerges.

6. **Registry scope: global vs session-scoped.** Plugin registration is module-global at import time in v1. For test isolation and multi-tenant scenarios, a context-manager-based scope override is provided. v2 may revisit if a real need for full session scoping appears.

7. **How should the ratchet utility merge conflicting observations from multiple sources?** If blq says `max-level: 4` is needed and ratchet-detect says `max-level: 2` is sufficient, which wins? v1: merge by union (loosest wins, warn). v1.1: policy-driven merge strategies.

8. **Observation source plugin API.** The `umwelt ratchet --observations <source>` utility delegates to a source-specific plugin that converts raw observations to the umwelt vocabulary. v1 ships exactly one source plugin (blq); the plugin API is minimal. v1.1+ expands.
