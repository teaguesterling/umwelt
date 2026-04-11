# umwelt v0.1 Scoping Design — Core + Sandbox Split

*Pre-implementation design doc for the first umwelt milestone, reflecting the policy-layer reframe and the selector-semantics decisions. Splits v0.1 into two sequenced sub-milestones: **v0.1-core** (vocabulary-agnostic) and **v0.1-sandbox** (first-party consumer). Supersedes [`2026-04-10-umwelt-v01-scoping-design.md`](./2026-04-10-umwelt-v01-scoping-design.md), which remains committed as the pre-reframe historical artifact.*

**Status:** approved, pre-implementation.
**Date:** 2026-04-10.
**Supersedes:** `2026-04-10-umwelt-v01-scoping-design.md` (same date, pre-reframe).
**Depends on:** `docs/vision/policy-layer.md`, `docs/vision/entity-model.md`, `docs/vision/view-format.md`, `docs/vision/package-design.md`, `docs/vision/notes/selector-semantics.md`.
**Next step after approval:** invoke `writing-plans` to produce a concrete implementation plan sequenced by the vertical slices below, starting with v0.1-core.

---

## 1. Scope and deliverables

This document produces four things:

1. **The core/sandbox split** (§2) — states the v0.1 division explicitly: core umwelt is vocabulary-agnostic and ships no hardcoded vocabulary; the sandbox consumer registers the first-party `world` / `capability` / `state` taxa and provides workspace/writeback/hooks as its runtime. Both ship in the same repo and PyPI package, but they are separately testable and separately milestoned.

2. **v0.1-core specification** (§§3–5) — a buildable spec for the vocabulary-agnostic walking skeleton: parser + AST + registry + selector engine + cascade resolver + compiler protocol + minimal CLI. **No hardcoded entities, no workspace, no compilers, no sandbox semantics.** Demo: parse a view against a toy taxonomy registered in-test, match selectors, resolve cascade, print the result.

3. **v0.1-sandbox specification** (§§6–8) — a buildable spec for the first-party consumer: sandbox vocabulary registration, filesystem / capability / state matchers, workspace builder (with the hash-based detection for both readable and writable entries per the self-review of the prior spec), writeback with all six reconciliation outcomes, hook dispatcher, at-rule sugar desugaring, fixtures. **No compilers** — those start at v0.2 per the `package-design.md` roadmap.

4. **Open-question resolutions** (§11) — every open question from the vision docs, with a v0.1 answer, unchanged-or-changed markers against the prior spec, and explicit deferrals.

This spec is the contract between brainstorming and implementation. After approval, `writing-plans` produces the concrete implementation plan sequenced against the vertical slices in §9.

### Explicit non-goals for v0.1

- **Any concrete compiler.** `compilers/protocol.py` ships in core (just the protocol + registry, no implementations). The sandbox consumer registers zero compilers in v0.1; nsjail and bwrap land in v0.2.
- **Runners** — empty `sandbox/runners/__init__.py` slot only.
- **Selector-level workspace extraction via pluckit.** v1.1 concern. Nested node selectors inside `file` are parsed and preserved but not evaluated.
- **The view bank.** v2 concern. Empty `bank/` slot.
- **Security / threat model.** Future `docs/vision/security.md`.
- **Remote compilers.** slurm, kubernetes — out of scope entirely for v0.1.
- **Cross-platform support.** v0.1 is Linux-only in CI.
- **The `delegate-context` compiler** (SELinux coda). Committed to v1.1 per the vision docs; not in v0.1.
- **Cross-taxon structural pseudo-classes** (`hook:triggered-by(...)`, etc.). v1.1+.
- **The `source` / `project` entity.** v1.1+.
- **Full `actor` taxon.** v0.1 ships only the minimal entities (`inferencer`, `executor`) per `entity-model.md` §3.4.
- **The `policy` meta-taxon.** v2.
- **Full actor-conditioned cascade** evaluation (context qualifiers require a runtime-state matcher that v0.1 doesn't have). v0.1 parses compound selectors and tags their mode, but actor-conditioned *evaluation* requires v0.2+ compilers to realize.

### What v0.1 does include that the prior spec didn't

- **Plugin registry API** — `register_taxon`, `register_entity`, `register_property`, `register_matcher`, `register_validator`, `register_compiler`.
- **Taxon resolution via registry lookup** — parser tags each simple selector with its owning taxon.
- **Compound selector AST** — `CompoundPart(simple_selector, combinator, mode)` with `mode` classified at parse time as `structural` or `context`.
- **Cascade scoped to target taxon** — rightmost entity's taxon, specificity accumulates across the compound.
- **Comparison-property cascade** — `max-`, `min-`, `only-`, `any-of-` prefixes.
- **Pattern-valued declarations** — `allow-pattern`, `deny-pattern`, `only-match` as registered properties (parsed; no runtime enforcement in v0.1 because no compiler is shipped).
- **CSS namespace syntax (`world|file`) and at-rule scoping (`@world { ... }`)** as disambiguation forms.
- **Altitude declaration on compilers** — not exercised in v0.1 (no compilers) but the protocol requires it for v0.2+.

---

## 2. The core / sandbox split

Core umwelt is vocabulary-agnostic. It knows about parsers, ASTs, selectors, cascade, and compilers. It does not know about files, tools, networks, jobs, or hooks. Any concrete vocabulary comes from a **consumer** — the first-party sandbox consumer, blq's integration, lackpy's integration, a third-party access-control consumer, anything that calls `register_*` at import time.

The **sandbox consumer** ships in the same repository under `src/umwelt/sandbox/` as a first-party example. It's a regular consumer of core umwelt using the same plugin registration API that third-party consumers use. Shipping in the same package is a convenience for distribution — it means `pip install umwelt` gives you both core and the sandbox vocabulary — not an architectural coupling.

**Why the split is load-bearing for v0.1:**

- **Core is testable in isolation.** v0.1-core's test suite registers a toy taxonomy inside the tests themselves. No filesystem, no subprocess, no external dependencies. Fast, deterministic, hermetic. A consumer that doesn't use the sandbox (e.g., a future policy-only consumer) can depend on core and never pay for sandbox runtime.
- **Sandbox is replaceable.** A consumer that wants different entity attributes, different cascade semantics, or different compilers can register alternative taxa under a different namespace without forking core. The split makes `umwelt.sandbox` concrete but not privileged.
- **The two milestones sequence cleanly.** v0.1-core lands first and is demoable as "parse, resolve, inspect a view against a toy taxonomy." v0.1-sandbox lands on top and is demoable as "build a workspace from a real view, edit files, apply writeback." Neither milestone is vacuous; both have honest demos.

v0.2 then adds the first real compiler (nsjail) in the sandbox consumer without touching core.

---

## 3. v0.1-core: architecture

Core umwelt is parser, AST, registry, selector engine, cascade resolver, compiler protocol, validator framework, utilities, CLI. **~1,600 LOC estimated.**

### 3.1 Module layout (core)

```
src/umwelt/
├── __init__.py               # public API re-exports: parse, View, ViewParseError, ...
├── py.typed
├── ast.py                    # View, RuleBlock, SimpleSelector, ComplexSelector,
│                             # CompoundPart, Declaration, PatternDeclaration, UnknownAtRule, etc.
├── parser.py                 # tinycss2-backed parser; parse(text) -> View
├── errors.py                 # UmweltError, ViewError, ViewParseError, ViewValidationError
├── validate.py               # dispatches registered per-taxon validators
├── cli.py                    # umwelt parse | inspect | check
├── registry/
│   ├── __init__.py           # register_taxon, register_entity, register_property,
│   │                         # register_matcher, register_validator, register_compiler
│   ├── taxa.py
│   ├── entities.py           # EntitySchema, AttrSchema
│   ├── properties.py         # PropertySchema with comparison semantics
│   ├── matchers.py           # MatcherProtocol
│   └── validators.py         # ValidatorProtocol
├── selector/
│   ├── __init__.py
│   ├── parse.py              # selector text -> SimpleSelector / ComplexSelector AST
│   ├── specificity.py        # CSS3 specificity; accumulation for compound selectors
│   └── match.py              # evaluate ComplexSelector against a matcher
├── cascade/
│   ├── __init__.py
│   └── resolver.py           # per-taxon cascade; target-taxon scoping; property-level cascade
├── compilers/
│   ├── __init__.py           # Compiler protocol, register(), get(), available()
│   └── protocol.py           # Compiler Protocol with target_name, target_format, altitude
├── inspect_util.py           # umwelt inspect implementation
├── dry_run.py                # umwelt dry-run implementation (scaffold; matchers supply the world)
├── check_util.py             # umwelt check implementation
└── _fixtures/                # reference fixtures (populated by v0.1-sandbox)
```

Core defines **zero concrete entities**. The fixtures directory is empty for v0.1-core and populated by v0.1-sandbox.

### 3.2 Parser

**`parser.parse(source: str | Path, *, validate: bool = True) -> View`** is the single public entry point. It:

1. Accepts `str` (view text) or `Path` (view file). Auto-detects.
2. Tokenizes via `tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True)`.
3. Walks the token stream, recognizing:
   - Top-level rule blocks with selectors (the canonical form).
   - Top-level at-rules. At-rules with known sandbox-vocabulary names (`@source`, `@tools`, `@network`, `@budget`, `@env`, `@after-change`) are desugared into entity-selector form during parsing (v0.1-sandbox ships the desugaring rules; in v0.1-core tests, the toy taxonomy uses its own sugar if it has any). At-rules that are taxon scopes (`@world { ... }`, `@capability { ... }`) are unwrapped; the enclosing taxon is recorded as a resolution hint for bare entity types inside the block.
   - Anything else as an `UnknownAtRule` with a warning flag.
4. For each rule block, parses the selector list via `selector/parse.py`, then the declaration list via tinycss2's declaration parser.
5. **Resolves each simple selector's entity type against the registry.** For each bare entity type name, the parser looks up the type across all registered taxa. If exactly one taxon owns it, that's the match. If multiple, the parser checks the enclosing at-rule scope (if any), then the explicit `taxon|type` namespace prefix (if any), and raises `ViewParseError("ambiguous entity type: 'file' registered by [world, audit]")` if still unresolved.
6. **Classifies each combinator in a compound selector.** For each combinator, compare the resolved taxa on either side. Same taxon → `mode="structural"`. Different taxa → `mode="context"`.
7. **Tags each rule with its target taxon** — the taxon of the rightmost simple selector. This is the cascade scope.
8. If `validate=True` (default), runs `validate.validate(view)` which dispatches to each registered per-taxon validator. Hard failures raise `ViewValidationError`. Soft warnings accumulate on `View.warnings`.
9. Raises `ViewParseError(message, line, col, source_path)` on syntactic errors.

### 3.3 AST

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass(frozen=True)
class SourceSpan:
    line: int
    col: int

@dataclass(frozen=True)
class AttrFilter:
    name: str
    op: Literal["exists", "=", "^=", "$=", "*=", "~=", "|="] | None
    value: str | None

@dataclass(frozen=True)
class PseudoClass:
    name: str
    argument: str | None          # :glob("src/**/*.py") or :not(...) etc.

@dataclass(frozen=True)
class SimpleSelector:
    type_name: str | None         # "file", "tool", "*", or None
    taxon: str                    # resolved at parse time
    id_value: str | None
    classes: tuple[str, ...]
    attributes: tuple[AttrFilter, ...]
    pseudo_classes: tuple[PseudoClass, ...]
    span: SourceSpan

@dataclass(frozen=True)
class CompoundPart:
    selector: SimpleSelector
    combinator: Literal["root", "descendant", "child", "sibling", "adjacent"]
    mode: Literal["structural", "context", "root"]

@dataclass(frozen=True)
class ComplexSelector:
    parts: tuple[CompoundPart, ...]
    target_taxon: str              # taxon of the rightmost simple selector
    specificity: tuple[int, int, int]   # accumulated across all parts

@dataclass(frozen=True)
class Declaration:
    property_name: str
    values: tuple[str, ...]
    span: SourceSpan

@dataclass(frozen=True)
class RuleBlock:
    selectors: tuple[ComplexSelector, ...]      # comma-separated union
    declarations: tuple[Declaration, ...]
    nested_blocks: tuple["RuleBlock", ...]       # for future @-scoped nesting; empty in v0.1
    span: SourceSpan

@dataclass(frozen=True)
class UnknownAtRule:
    name: str
    prelude_text: str
    block_text: str
    span: SourceSpan

@dataclass(frozen=True)
class ParseWarning:
    message: str
    span: SourceSpan

@dataclass(frozen=True)
class View:
    rules: tuple[RuleBlock, ...]
    unknown_at_rules: tuple[UnknownAtRule, ...]
    warnings: tuple[ParseWarning, ...]
    source_text: str
    source_path: Path | None
```

All frozen, tuple-typed, hashable. The AST is pure data — no methods beyond default equality.

### 3.4 Registry

```python
# registry/__init__.py public API

def register_taxon(
    name: str,
    description: str,
    ma_concept: str | None = None,
) -> None: ...

@dataclass(frozen=True)
class AttrSchema:
    type: type
    required: bool = False
    unit: str | None = None
    description: str | None = None

def register_entity(
    taxon: str,
    name: str,
    *,
    parent: str | None = None,
    attributes: dict[str, AttrSchema],
    description: str,
    category: str | None = None,
) -> None: ...

def register_property(
    taxon: str,
    entity: str,
    name: str,
    *,
    value_type: type,
    comparison: Literal["exact", "<=", ">=", "in", "overlap", "pattern-in"] = "exact",
    value_attribute: str | None = None,    # which entity attribute the value constrains
    value_unit: str | None = None,
    value_range: tuple | None = None,
    description: str,
    category: str | None = None,
) -> None: ...

def register_matcher(taxon: str, matcher: MatcherProtocol) -> None: ...
def register_validator(taxon: str, validator: ValidatorProtocol) -> None: ...
def register_compiler(name: str, compiler: CompilerProtocol) -> None: ...
```

The registry is module-global for v0.1. A `@contextmanager`-based scope override is provided for tests so per-test taxa don't leak. All registration is fail-fast on collision: duplicate taxa / entity types / property names raise `RegistryError` at import time.

### 3.5 Selector engine

`selector/parse.py` parses selector text into `ComplexSelector` using tinycss2's selector tokenization as a starting point (if available) or a small hand-rolled parser (if tinycss2's selector support is insufficient — decide during implementation).

`selector/specificity.py` computes CSS3 specificity `(ids, classes+attrs+pseudos, types)` per simple selector and sums component-wise across a compound.

`selector/match.py` evaluates a `ComplexSelector` against a registered matcher. For each `CompoundPart`:

- If `mode == "structural"`: navigate the matcher's parent/child hierarchy (matcher owns the walk).
- If `mode == "context"`: consult the qualifier's taxon's matcher for a condition-met query.
- If `mode == "root"`: match against the world root.

The match engine returns a set of target-taxon entities that satisfy the selector. Context qualifiers that no matcher can evaluate at the current altitude are treated as "condition unknown, rule dropped" — the matcher returns no matches rather than an error. This is the same behavior compilers use when dropping out-of-altitude rules; it centralizes the unrealized-rule handling in the match engine rather than duplicating it per compiler.

### 3.6 Cascade resolver

`cascade/resolver.py` takes a `View` and a registered matcher set and returns a `ResolvedView`:

1. For each rule, evaluate its selector against the target taxon's matcher → set of matched entities.
2. Group rules by target taxon.
3. For each taxon, for each entity in its matcher's world, compute the set of matching rules and their specificities.
4. Apply property-level cascade: for each property declared on an entity, the winning rule is the one with highest specificity; ties broken by document order.
5. Produce `ResolvedView = {taxon: {entity_id: {property_name: value}}}`.

Compilers read the `ResolvedView`, not the raw `View`. Cascade never reruns — one pass, fully resolved.

### 3.7 Compiler protocol

```python
# compilers/protocol.py

from typing import Protocol, Literal

Altitude = Literal["os", "language", "semantic", "conversational"]

class Compiler(Protocol):
    target_name: str
    target_format: str
    altitude: Altitude
    
    def compile(self, view: ResolvedView) -> str | list[str] | dict:
        """Translate a resolved view to the target's native format."""
        ...

_REGISTRY: dict[str, Compiler] = {}

def register(name: str, compiler: Compiler) -> None: ...
def get(name: str) -> Compiler: ...
def available() -> list[str]: ...
```

Core ships the protocol and the registry. Zero concrete compilers.

### 3.8 Validator framework

`validate.py` dispatches to each registered `(taxon, ValidatorProtocol)` pair. Each validator receives the parsed rules for its taxon and returns a list of warnings / errors. v0.1-core provides the dispatch machinery; the sandbox consumer registers concrete validators.

### 3.9 CLI (core)

```bash
umwelt parse file.umw              # parses + validates, prints the AST
umwelt inspect file.umw            # structural summary (taxa, rule counts, property coverage)
umwelt check file.umw              # parse + validate + every registered compiler, report per-target
```

`umwelt dry-run` is a scaffold — accepts a `--world <path>` argument but is only meaningful when a matcher knows how to evaluate against a path. The sandbox consumer's world matcher makes it concrete in v0.1-sandbox.

---

## 4. v0.1-core: testing strategy

**v0.1-core tests run against a toy taxonomy defined inside the test suite.** No filesystem, no subprocess, no external dependencies.

```python
# tests/conftest.py

@pytest.fixture
def toy_registry(registry_scope):
    register_taxon("test", description="toy taxonomy for core tests")
    register_entity("test", "thing", attributes={...}, description="a thing")
    register_entity("test", "widget", parent="thing", attributes={...}, description="a widget")
    register_property("test", "thing", "color", value_type=str, description="a color")
    register_property("test", "thing", "max-size", value_type=int, comparison="<=", description="cap")
    register_matcher("test", InMemoryTestMatcher({
        "thing/a": {"color": "red"},
        "thing/b": {"color": "blue"},
        "widget/w1": {"color": "green", "parent": "thing/a"},
    }))
    yield
```

Tests exercise:

- Parser: every at-rule type, every selector form, compound selectors (within and cross-taxon with a second toy taxon), pattern properties, unknown-construct preservation, malformed inputs with line/col assertions.
- Registry: registration, lookup, collision errors, scope-override for tests.
- Selector engine: structural descent, context qualifier, specificity computation including accumulation across compounds.
- Cascade: per-taxon scoping, target-taxon resolution for compound selectors, specificity ordering, document-order tiebreaking, property-level cascade.
- Validator framework: dispatch, warnings, errors.
- CLI: `umwelt parse` / `inspect` / `check` via subprocess, assert exit codes and output structure.

No integration tests against real enforcement tools in v0.1-core; those come with v0.2+ compilers.

---

## 5. v0.1-core: acceptance criteria

v0.1-core is "done" when all of the following are true:

1. `pip install -e ".[dev]"` succeeds on Python 3.10+.
2. `ruff check src/umwelt/ tests/` exits 0.
3. `mypy src/umwelt/` exits 0 under strict mode.
4. `pytest tests/core/` exits 0; every unit test and integration test passes.
5. CI is green on Python 3.10, 3.11, 3.12, 3.13.
6. `umwelt parse` and `umwelt inspect` work on a test fixture that registers a toy taxonomy and parses a sample view against it.
7. The `Compiler` protocol is defined and has zero concrete implementations.
8. No dependencies on `umwelt.sandbox` from anywhere in `src/umwelt/` outside the `sandbox/` subpackage.

v0.1-core is **not** required to build a real workspace, run a real delegate, or produce any enforcement config. It is required to prove the core infrastructure works against a toy taxonomy.

---

## 6. v0.1-sandbox: architecture

The sandbox consumer registers the first-party `world` / `capability` / `state` taxa, provides their matchers, and ships the workspace runtime. **~1,400 LOC estimated.**

### 6.1 Module layout (sandbox)

```
src/umwelt/sandbox/
├── __init__.py               # triggers vocabulary registration at import
├── vocabulary.py             # register_taxon / register_entity / register_property calls
├── world_matcher.py          # filesystem matcher for world taxon
├── capability_matcher.py     # tool-registry matcher for capability taxon (minimal)
├── state_matcher.py          # hook / resource / budget matchers
├── desugar.py                # @source / @tools / @after-change / @network / @budget / @env desugaring rules
├── validators.py             # per-taxon validators registered with core
├── workspace/
│   ├── __init__.py           # Workspace, WorkspaceBuilder, WriteBack
│   ├── builder.py
│   ├── writeback.py
│   ├── manifest.py
│   ├── strategy.py           # MaterializationStrategy protocol + SymlinkReadonlyCopyWritable default
│   └── errors.py
├── hooks/
│   ├── __init__.py
│   └── dispatcher.py         # after-change hook runner
└── runners/
    └── __init__.py           # empty in v0.1; v0.2+ ships nsjail and bwrap runners
```

### 6.2 Sandbox vocabulary registration

`sandbox/vocabulary.py` is imported at package init and calls `register_*` for each taxon, entity, property, matcher, and validator it owns. See [`../../vision/entity-model.md`](../../vision/entity-model.md) §3.1-3.3 for the complete entity and property lists:

- **`world` taxon**: `dir`, `file`, `node` (opaque in v0.1), `mount`, `env`, `network`, `resource`. Properties: `editable`, `visible`, `limit`, `allow`, `deny`, `max-limit`, `max-memory`, `max-wall-time`, `max-cpu-time`, `max-fds`, etc.
- **`capability` taxon**: `tool`, `kit`. Properties: `allow`, `deny`, `max-level`, `allow-pattern`, `deny-pattern`, `only-kits`.
- **`state` taxon**: `hook`, `job`, `budget`, `manifest`. Properties: `run`, `timeout`, `inherit-budget`, etc.

### 6.3 World matcher

Matches `world` taxon entities against a local filesystem. v0.1 supports:

- `file[path="..."]` exact match
- `file[path^="..."]`, `file[path$="..."]`, `file[path*="..."]` attribute operators
- `file:glob("...")` via `pathlib.Path.glob`
- `dir[name="..."] file[...]` descendant combinator via the declared `dir → file` parent-child relationship
- `resource[kind="..."]` — the matcher returns a fixed set of resource entities (`memory`, `cpu-time`, `wall-time`, `max-fds`, `tmpfs`) when asked; rules set their properties.
- `network` — a single-entity match; `deny: "*"` is the v0.1 form.
- `env[name="..."]` — matches environment variable entities by name.
- Path traversal protection: resolved paths that escape `base_dir` raise `WorkspaceError`.

v0.1 does **not** support node-level selectors inside files (the `file ... node` form parses but the matcher returns empty for node queries — deferred to v1.1 via pluckit).

### 6.4 Capability matcher

Matches `capability` taxon entities against a supplied tool registry. v0.1 takes a declared list of `(name, kit, altitude, level)` tuples at construction time and evaluates selectors against them. It does not introspect MCP servers, lackpy kits, or claude-plugins registries — those integrations come with v0.2+. The matcher is sufficient for sandbox-consumer tests that need to match tools by name, kit, and altitude.

### 6.5 State matcher

Matches `state` taxon entities (`hook`, `resource`, `budget`) against a supplied runtime state (jobs running, hooks scheduled, budgets configured). In v0.1, the only live state is `hook` — the matcher returns hook entities for whatever events the view declares. Jobs and budgets are placeholder entities that match by kind but don't have live values until a runner populates them.

### 6.6 Workspace builder

For each `world file[...]` rule in the resolved view:

1. Resolve the selector via the world matcher → set of real file paths.
2. For each matched file, look up the cascaded `editable` property.
3. Call the registered `MaterializationStrategy` with `(real_path, virtual_path, writable)`.
4. Record the `ManifestEntry` with a SHA-256 hash of the file at build time.

**Per the self-review fix from the prior spec**, the hash is captured for *both* read-only and writable entries. Read-only symlinks in v0.1 are advisory — without a sandbox compiler, the symlink does not prevent writes through it. Hash-based detection catches violations post-hoc and reports them as `Rejected`. v0.2 nsjail/bwrap compilers provide actual enforcement.

Default strategy: `SymlinkReadonlyCopyWritable`. Symlinks for read-only, copies for writable, SHA-256 hashes captured on build for both.

### 6.7 Writeback

```python
class WriteBack:
    def __init__(self, strict: bool = False): ...
    def apply(self, workspace: Workspace) -> WriteBackResult: ...
```

For each manifest entry, call `strategy.reconcile(entry, workspace_root)`. Reconcile returns one of:

| Entry state | Real-file state | Virtual-file state | Outcome |
|---|---|---|---|
| writable | unchanged | unchanged | `NoOp` |
| writable | unchanged | changed | `Applied(new_content)` |
| writable | changed externally | unchanged | `Conflict("real modified externally")` |
| writable | changed externally | changed | `Conflict("both modified")` |
| read-only | unchanged | — (symlink) | `NoOp` |
| read-only | changed (via symlink or externally) | — | `Rejected("read-only modified during execution")` |

Applied content is written to the real path *after* all reconciliation decisions are made, so partial failure doesn't leave a half-updated tree. If `strict=True` and `rejected` or `conflicts` is non-empty, raise `ViewViolation`.

### 6.8 Hook dispatcher

`state hook[event="after-change"] { run: "..."; }` rules produce a hook dispatch. The dispatcher:

1. For each matched hook entity, iterate its `run:` values in document order.
2. Execute each via `subprocess.run(shlex.split(cmd), cwd=context.project_root, env=context.env, capture_output=True, timeout=context.timeout_seconds)`.
3. Collect `HookResult(label, command, returncode, stdout, stderr, duration_seconds, timed_out)`.
4. On timeout, record `timed_out=True` with partial output.
5. On `FileNotFoundError`, record `returncode=-1` with "command not found: <cmd>".
6. Failing commands do not abort subsequent commands in v0.1.
7. Return the list.

`HookContext.project_root` is passed explicitly by the caller; the dispatcher does not know about the workspace.

### 6.9 At-rule sugar desugaring

`sandbox/desugar.py` is imported alongside `vocabulary.py` and registers the sugar rules with the core parser. Each sandbox at-rule maps to one or more entity-selector rules per the desugaring table in [`entity-model.md`](../../vision/entity-model.md) §7.1. The parser invokes the desugaring during parsing; by the time the AST is built, all rules are in entity-selector form and the sugar has been forgotten.

---

## 7. v0.1-sandbox: testing strategy

Unit tests:

- **Vocabulary registration**: every `register_*` call succeeds, every entity and property is accessible via the registry.
- **World matcher**: path-exact, prefix, suffix, substring, glob, descendant combinator, multi-file glob, empty glob warning, path traversal rejection.
- **Capability matcher**: tool by name, tool by kit, tool by altitude, tool by max-level (comparison property).
- **State matcher**: hook by event, resource by kind, budget by kind.
- **Workspace builder**: single file, multi-file glob, cascade (last-block-wins), overlapping sources, strategy override.
- **Materialization strategy**: materialize + reconcile for all six cells of the state table.
- **Writeback**: mixed applied/rejected/conflict, `strict=True` raises, default returns result.
- **Hook dispatcher**: success, failure-continues, timeout, command-not-found, cwd respected, env captured.
- **Desugaring**: every sandbox at-rule desugars to the expected entity-selector form. Round-trip tests show the same view written in sugar and canonical forms produces identical ASTs.

Integration tests:

- **End-to-end parse + resolve + inspect**: every fixture in `_fixtures/` parses, validates, and round-trips through cascade resolution without error.
- **End-to-end workspace lifecycle**: build a workspace from `auth-fix.umw` against a temp project tree, simulate edits to writable files, run writeback, assert applied/rejected/conflicts match expectations.
- **CLI**: subprocess invocation of `umwelt parse`, `umwelt inspect`, `umwelt check` on fixture files; assert exit codes and output contents.

Fixtures (`src/umwelt/_fixtures/`):

- `minimal.umw` — one `file[path="hello.txt"]` rule. Smallest valid view.
- `readonly-exploration.umw` — read-only file rules, `capability tool[name="Read"] { allow: true; }`, no hooks.
- `auth-fix.umw` — the canonical example from the vision docs: two file rules with cascade, tool allow/deny, `state hook[event="after-change"] { run: "pytest"; }`, resource limits, `env[name="CI"] { allow: true; }`.
- `actor-conditioned.umw` — one cross-taxon compound selector (`tool[name="Bash"] file[path^="src/auth/"] { editable: false; }`), demonstrating compound parsing and cascade target resolution even though no compiler realizes it in v0.1. The test asserts the rule parses, the compound selector is tagged `mode="context"`, and the cascade target is `file` in the `world` taxon.

---

## 8. v0.1-sandbox: acceptance criteria

v0.1-sandbox is "done" when all of the following are true (in addition to the v0.1-core criteria being met):

1. `pytest tests/sandbox/` exits 0.
2. The three sandbox taxa (`world`, `capability`, `state`) register without errors on `import umwelt.sandbox`.
3. `umwelt inspect src/umwelt/_fixtures/auth-fix.umw` prints the rule set grouped by taxon with no warnings.
4. `umwelt check src/umwelt/_fixtures/auth-fix.umw` reports "0 rules realized by any compiler" (expected — no compilers in v0.1) and validates without errors.
5. An end-to-end test in `tests/sandbox/test_workspace_lifecycle.py` builds a workspace from `auth-fix.umw`, modifies a writable virtual file, runs writeback, and asserts the applied change appears in the real file tree.
6. `README.md` in the repo root includes an install + usage example that actually works when run against `_fixtures/minimal.umw`.
7. `CHANGELOG.md` has a v0.1.0 entry listing both milestones (core + sandbox).
8. Git tag `v0.1.0`.

---

## 9. Vertical slice plan

Eight slices total. Slices 1–4 are v0.1-core; slices 5–8 are v0.1-sandbox. Each slice is intended to be PR-sized (< 1000 LOC). Each ends with a demoable green test run.

### 9.1 Slice 1 — Core parser, AST, and simple selector matching (v0.1-core)

**Goal:** Parse a view against a toy taxonomy registered in-test, match simple selectors, return a set of entities.

**Landed:**
- `ast.py`: all dataclasses
- `parser.py`: tinycss2-backed parser for top-level rule blocks with simple selectors (type, id, classes, attribute selectors)
- `registry/`: `register_taxon`, `register_entity`, `register_property`, `register_matcher` + scope-override context manager for tests
- `selector/parse.py`: simple selector parsing; attribute operators (`=`, `^=`, `$=`, `*=`, `~=`, `|=`); `:not(...)` and `:glob(...)` pseudo-classes
- `selector/specificity.py`: CSS3 specificity for simple selectors
- `selector/match.py`: evaluate `SimpleSelector` against a matcher
- `errors.py`: core error hierarchy
- `tests/core/test_parser.py`, `test_registry.py`, `test_selector_simple.py`

**Demo:** A test that registers a toy taxonomy with one entity type `thing` and one property `color`, parses `thing[name="red"] { color: red; }`, and asserts the matched entity set is `{thing/red}`.

### 9.2 Slice 2 — Compound selectors, combinators, cross-taxon mode classification (v0.1-core)

**Goal:** Parse and evaluate compound selectors in both within-taxon (structural) and cross-taxon (context) modes.

**Landed:**
- `selector/parse.py` extended: descendant (whitespace) and child (`>`) combinators; `ComplexSelector` with `parts` tuple
- Taxon resolution in the parser: each simple selector tagged with its resolved taxon; each combinator tagged `structural` or `context` based on taxon comparison
- `selector/specificity.py` extended: accumulation across compound selectors
- `selector/match.py` extended: within-taxon structural walk via matcher's parent/child API; cross-taxon context qualifier evaluation via consulting the qualifier's taxon's matcher
- `tests/core/test_selector_compound.py`: within-taxon descent, cross-taxon context, three-level compounds, ambiguous-type-raises-error, mode classification correct

**Demo:** A test registers two toy taxa, writes a compound selector crossing them, and asserts the parser tags the combinator as `mode="context"` and the rule's `target_taxon` is the rightmost entity's taxon.

### 9.3 Slice 3 — Cascade resolver with target-taxon scoping + comparison properties (v0.1-core)

**Goal:** Resolve a view to a `{taxon: {entity: {property: value}}}` map with correct cascade semantics, including compound-selector specificity accumulation and comparison-property prefixes.

**Landed:**
- `cascade/resolver.py`: group rules by target taxon; per-taxon specificity resolution; document-order tiebreaking; property-level cascade
- `registry/properties.py` extended: comparison-property metadata (`max-`, `min-`, `only-`, `any-of-`, `pattern-in`) registered with each property; no runtime evaluation of comparison semantics yet (that's the compiler/matcher concern)
- `parser.py` extended: pattern properties (`allow-pattern`, `deny-pattern`, `only-match`) parsed into AST; stored in declaration values as comma-separated lists
- `tests/core/test_cascade.py`: specificity ordering, doc-order ties, compound-selector specificity accumulation, per-taxon scoping, comparison-prefix cascade, pattern-property round-trip

**Demo:** A test writes a view with three rules cascading on the same entity (plain, prefix-matched, and compound-qualified), runs cascade, and asserts the winning rule is the compound one with accumulated specificity.

### 9.4 Slice 4 — CLI, utilities, compiler protocol, core acceptance (v0.1-core)

**Goal:** v0.1-core ships with a working CLI, the compiler protocol is defined (no implementations), core acceptance criteria met.

**Landed:**
- `compilers/protocol.py`: `Compiler` protocol, `register`, `get`, `available`; no concrete compilers
- `validate.py`: dispatcher for registered per-taxon validators
- `cli.py`: `umwelt parse`, `umwelt inspect`, `umwelt check` — all three work against the toy taxonomy fixture
- `inspect_util.py`, `dry_run.py` (scaffold), `check_util.py`
- `pyproject.toml`: hatchling backend, script entry point `umwelt = "umwelt.cli:main"`, `tinycss2>=1.2` dep
- `.github/workflows/ci.yml`: Python 3.10-3.13 matrix; `pip install -e ".[dev]"`, `ruff check`, `mypy src/`, `pytest tests/core/`
- `LICENSE` (MIT), `.gitignore`, `README.md` stub, `CHANGELOG.md`
- `tests/core/test_cli.py`: subprocess tests for `umwelt parse`, `umwelt inspect`, `umwelt check`

**Demo:** CI is green on all four Python versions. `pip install -e . && umwelt parse tests/core/fixtures/toy.umw` runs from a clean clone and produces the expected AST dump.

### 9.5 Slice 5 — Sandbox vocabulary registration, world + capability + state matchers (v0.1-sandbox)

**Goal:** The sandbox vocabulary registers cleanly, matchers for all three taxa work against concrete worlds.

**Landed:**
- `sandbox/__init__.py`: imports `vocabulary` at package init
- `sandbox/vocabulary.py`: every `register_*` call for `world`/`capability`/`state`
- `sandbox/world_matcher.py`: filesystem matcher (path attributes, globs, descendant combinator, traversal rejection)
- `sandbox/capability_matcher.py`: minimal tool-registry matcher taking a declared tool list
- `sandbox/state_matcher.py`: hook / resource / budget matcher
- `sandbox/validators.py`: per-taxon semantic validators (path-escape rejection, allow/deny conflict detection, etc.)
- `tests/sandbox/test_vocabulary.py`, `test_world_matcher.py`, `test_capability_matcher.py`, `test_state_matcher.py`

**Demo:** A test parses a real-looking view (`file[path^="src/"] { editable: true; }`) against a temp directory populated with source files, runs the world matcher, and asserts the correct set of files is matched.

### 9.6 Slice 6 — Workspace builder, manifest, materialization strategy (v0.1-sandbox)

**Goal:** Building a workspace from a view produces a manifest with correct hash-based entries for both read-only and writable files.

**Landed:**
- `sandbox/workspace/manifest.py`: `ManifestEntry`, `WorkspaceManifest`
- `sandbox/workspace/strategy.py`: `MaterializationStrategy` protocol; `SymlinkReadonlyCopyWritable` default with SHA-256 hashing at build time for both modes; `register_strategy`, `get_strategy`
- `sandbox/workspace/builder.py`: `WorkspaceBuilder.build(view, base_dir)` — iterates world-taxon rules, resolves via world matcher, materializes via strategy
- `sandbox/workspace/__init__.py`: `Workspace` context manager
- `sandbox/workspace/errors.py`: `WorkspaceError`, `ViewViolation`
- `tests/sandbox/test_workspace_builder.py`, `test_manifest.py`, `test_strategy.py`

**Demo:** Build a workspace from `auth-fix.umw`, inspect the manifest, verify read-only entries are symlinks with hashes recorded and writable entries are copies with hashes recorded.

### 9.7 Slice 7 — Writeback, hook dispatcher, at-rule sugar desugaring (v0.1-sandbox)

**Goal:** End-to-end workspace lifecycle works. After-change hooks run. Legacy at-rule sugar parses.

**Landed:**
- `sandbox/workspace/writeback.py`: `WriteBack.apply(workspace) -> WriteBackResult` with all six reconciliation outcomes; atomic write after decision phase; `strict=True` raises
- `sandbox/hooks/dispatcher.py`: `HookDispatcher.dispatch(blocks, context)` with subprocess + capture + timeout + continue-on-failure
- `sandbox/desugar.py`: desugaring rules for `@source`, `@tools`, `@after-change`, `@network`, `@budget`, `@env`; registered with the core parser at import time
- `tests/sandbox/test_writeback.py`, `test_hooks_dispatcher.py`, `test_desugaring.py`

**Demo:** Full workspace lifecycle test: parse `auth-fix.umw` (containing at-rule sugar), build a workspace, modify a writable file, run writeback, run the after-change hooks, assert the applied change appears in the real file and the pytest hook ran.

### 9.8 Slice 8 — Fixtures, integration tests, polish, v0.1.0 tag (v0.1-sandbox)

**Goal:** v0.1-sandbox is ready to tag.

**Landed:**
- `_fixtures/minimal.umw`, `readonly-exploration.umw`, `auth-fix.umw`, `actor-conditioned.umw`
- `tests/sandbox/test_integration_workspace.py`: end-to-end against `auth-fix.umw` on a temp project tree
- `tests/sandbox/test_integration_parse.py`: every fixture parses, validates, resolves without warning
- `tests/sandbox/test_cli_sandbox.py`: CLI subprocess tests against fixtures
- `README.md` updated with install + usage example that runs against `minimal.umw`
- `CHANGELOG.md` v0.1.0 entry
- Ruff + mypy clean across `src/` and `tests/`
- CI green on Python 3.10–3.13
- `py.typed` marker verified
- Git tag `v0.1.0`

**Demo:** `pip install -e . && umwelt parse src/umwelt/_fixtures/auth-fix.umw` works from a clean clone. `pytest` runs all unit and integration tests green.

### Slice dependency graph

```
Core:
  Slice 1 (parser + AST + simple selectors)
      ↓
  Slice 2 (compound selectors + combinator modes)
      ↓
  Slice 3 (cascade resolver + comparison + pattern properties)
      ↓
  Slice 4 (CLI + compiler protocol + core acceptance)

Sandbox (depends on core being green):
  Slice 5 (vocabulary + matchers) ──┐
                                    ↓
  Slice 6 (workspace + manifest + strategy)
                                    ↓
  Slice 7 (writeback + hooks + desugar)
                                    ↓
  Slice 8 (fixtures + integration + polish + tag)
```

Slices 5 and 6 could run in parallel if there's capacity, but sequential is simpler.

---

## 10. Port-ready decomposition

Per `implementation-language.md`, the architecture stays port-ready so a future Rust port (if needed) is scoped to the parser and compiler layers, not the whole package. v0.1 preserves this by construction:

- `parser.parse(text: str) -> View` is a pure function: no side effects, no I/O beyond reading the input file.
- Selector parsing, specificity computation, and cascade resolution are pure functions over the AST.
- The registry is module-global state, but registration is explicit at import time — no discovery, no side effects beyond the registry mutation.
- The compiler protocol is `compile(view: ResolvedView) -> str | list[str] | dict` — pure.
- Workspace operations are I/O-bound and not port candidates.
- Hook dispatch is subprocess orchestration and not a port candidate.

**Rust-port criteria (from `implementation-language.md`, unchanged):** any future Rust port requires at least one of:

- A measured performance problem in the parser, selector engine, or cascade resolver.
- A concrete non-Python consumer requesting bindings.
- A security audit finding that depends on memory safety of the parser.
- A distribution problem requiring a static binary.

None are true in 2026. Revisit only when one becomes true.

---

## 11. Open-question resolutions

Every open question from the vision docs, with a v0.1 answer. Changes from the prior spec are marked `[updated]`; new questions are marked `[new]`.

### From `package-design.md` §Open questions

| # | Question | Resolution | Status |
|---|---|---|---|
| P-1 | File extension for views | `.umw` | unchanged |
| P-2 | Symlink vs copy for read-only | Symlinks for read-only, copies for writable, **hashes captured for both** to detect violations; pluggable `MaterializationStrategy` | unchanged (fix from prior spec carried forward) |
| P-3 | How does the delegate learn the workspace layout? | Deferred to v1.1's `delegate-context` compiler (the SELinux-coda view-transparency compiler). v0.1 returns a `Workspace` with `.manifest`; the consumer decides how to expose it until v1.1 lands. | [updated] |
| P-4 | Compiler registry priority ordering | Last-write-wins with a warning | unchanged |
| P-5 | Textproto hand-rolling vs library dependency | Hand-rolled; `nsjail-python` as optional validator | unchanged (not v0.1-blocking) |
| P-6 | CLI framework | argparse | unchanged |
| P-7 | Cascade semantics for overlapping rules | Last-block-wins within a taxon; **target-taxon scoping for compound selectors; specificity accumulates across compound parts** | [updated] |
| P-8 | `@env { allow: VAR }` semantics | Pass-through only in v1; explicit assignment in v1.1 | unchanged |
| P-9 | Should umwelt ever author views? | No in v1; `View.to_string()` is v1.1+ | unchanged |
| P-10 | Keep "view" as user-facing terminology | Yes | unchanged |

### From `implementation-language.md`

| # | Question | Resolution | Status |
|---|---|---|---|
| L-1 | Is "stdlib only" a hard constraint? | Soft; tinycss2 is required | unchanged |
| L-2 | Known non-Python consumer? | None | unchanged |
| L-3 | Port-ready decomposition as explicit constraint? | Yes (see §10) | unchanged |
| L-4 | "Measure first, port second" for v2? | Yes | unchanged |

### From the policy-layer reframe

| # | Question | Resolution | Status |
|---|---|---|---|
| R-1 | Is core umwelt vocabulary-agnostic? | Yes. Core ships no hardcoded taxa; the sandbox consumer registers `world`/`capability`/`state` via the plugin API the same way any third-party consumer would. | [new] |
| R-2 | Are entity type names prefixed with their taxon? | No. Bare names are canonical (`file`, `tool`, `hook`). Prefix form is dropped. Disambiguation uses CSS namespace syntax (`world\|file`) or at-rule scoping (`@world { ... }`). | [new] |
| R-3 | How is cascade scoped across taxa? | Per-target-taxon, determined by registry lookup on the rightmost entity in the selector. Specificity accumulates across compound parts. | [new] |
| R-4 | Do selectors support cross-taxon composition? | Yes. The descendant combinator has two modes: within-taxon (structural) and cross-taxon (context qualifier). Parser classifies at parse time via registry lookup. | [new] |
| R-5 | How do compilers declare what they can realize? | Each compiler declares an `altitude` attribute (`os`/`language`/`semantic`/`conversational`) and silently drops rules whose context qualifiers are outside its altitude. `dry-run` and `check` utilities report per-target. | [new] |
| R-6 | Are pattern properties (runtime matchers) selector-level or declaration-level? | Declaration-level. `allow-pattern` / `deny-pattern` / `only-match` are properties, not selectors. Parsed in v0.1; runtime enforcement is a compiler concern in v0.2+. | [new] |
| R-7 | Is the delegate-context compiler (SELinux coda) in v0.1? | No. Committed to v1.1. Plugin description fields are load-bearing for it — every taxon / entity / property registered in v0.1 must carry a description. | [new] |

### Deferred (explicitly not resolved in v0.1)

- Kubernetes / slurm compiler output shapes (v2+)
- View bank schema and retrieval (v2)
- Security threat model and parser hardening (v0.5)
- Per-command hook timeouts (v1.1)
- Selector-level extraction via pluckit (v1.1)
- `@network { allow: host }` enforcement (v1.1)
- `source` / `project` entity for logical file groupings (v1.1+)
- Invocation-time selectors (v1.1+)
- Cross-taxon structural pseudo-classes (v1.1+)
- uid/gid mapping `@identity` at-rule (v1.1+)
- seccomp profiles via `@syscalls` at-rule (v1.1+)
- `file#name.py.bak` id-value edge case (open; see `entity-model.md` §15.9)

---

## 12. v0.1 acceptance criteria (whole milestone)

v0.1 as a whole is "done" when both sub-milestones are done (§5 and §8) and additionally:

- The three commits in git are structured as: core landing (slices 1–4), sandbox landing (slices 5–8), polish + tag.
- The PyPI-ready metadata is in place (classifiers, description, keywords, homepage) but the package is *not* published in v0.1 — PyPI publish is v0.4 per the roadmap.
- `docs/vision/README.md` status line updated to "v0.1 implemented, core and sandbox both shipping."

v0.1 is **not** required to:

- Publish to PyPI (v0.4)
- Pass on macOS or Windows (Linux only in v0.1)
- Run under nsjail, bwrap, or any real enforcement tool (v0.2+)
- Express or enforce any rule at a compiler altitude (v0.2+)
- Realize pattern properties at runtime (v0.2+)
- Evaluate cross-taxon context qualifiers against runtime state (v0.2+; v0.1 parses and tags them, but matchers can't enforce without a runtime)

---

## 13. What this document is not

- **Not a replacement for the vision docs.** Read `docs/vision/policy-layer.md`, `entity-model.md`, `view-format.md`, and `package-design.md` alongside this. The vision docs carry the architectural reasoning; this spec carries the v0.1 scoping.
- **Not an implementation plan.** After approval, `writing-plans` produces the slice-by-slice plan with concrete tasks.
- **Not the last word on deferred items.** Every `[v1.1+]` or `[v2]` tag here gets revisited when the corresponding milestone approaches.
- **Not a superseding of the prior spec in git terms.** The prior spec at `2026-04-10-umwelt-v01-scoping-design.md` remains in history as the pre-reframe artifact. This spec is the currently-authoritative v0.1 scope.
