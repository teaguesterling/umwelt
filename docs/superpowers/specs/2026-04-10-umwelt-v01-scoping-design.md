# umwelt v0.1 Scoping Design

*Pre-implementation design doc: resolves open questions, specifies the v0.1 walking skeleton, defines the package skeleton for bootstrap. Companion to the vision docs in [`../../vision/`](../../vision/), which are load-bearing context and not duplicated here.*

**Status:** approved, pre-implementation.
**Date:** 2026-04-10.
**Supersedes:** none.
**Next step after approval:** invoke `writing-plans` to produce a concrete implementation plan sequenced by the vertical slices below.

---

## 1. Scope and deliverables

This document produces three things, in the order a reader should care about them:

1. **Open-question resolutions** (§7) — settles every open question from `package-design.md` and `implementation-language.md` so they do not re-surface during implementation. Questions that are deliberately deferred to later milestones are listed with their deferral reason.

2. **v0.1 specification** (§§3–4) — a precise, buildable spec for the v0.1 "walking skeleton" as defined by the `package-design.md` roadmap: parser + AST + validator for the `@source` / `@tools` / `@after-change` at-rules, workspace builder (file-level globs only), write-back with strict violation detection, hook dispatcher, unit tests, and a minimal `umwelt parse` CLI. **No compilers, no runners, no `@network`/`@budget`/`@env` grammar** — those arrive in v0.2 alongside the first compiler.

3. **Package skeleton** (§2) — the concrete `pyproject.toml`, directory layout, empty module files, test scaffold, CI config, and license that make the repository buildable from zero. "Ready to implement" means `git clone && pip install -e . && pytest` succeeds on an empty test suite before any v0.1 logic is written.

### Explicit non-goals for this design doc

- **Compiler internals.** nsjail textproto emission and bwrap argv ordering are already specified in `docs/vision/compilers/nsjail.md` and `bwrap.md`. No v0.1 compiler work.
- **The view bank.** v2 concern. No schema, no retrieval, no git-history distillation.
- **Selector-level extraction via pluckit.** v1.1. Selector rules inside `@source` blocks are parsed and preserved as opaque strings only.
- **Security / threat model.** Future `docs/vision/security.md`.
- **Remote compilers.** slurm, kubernetes, apptainer — none are in scope.
- **Cross-platform support.** v0.1 is Linux-only in CI. macOS/Windows concerns surface with compiler work.

### Terminology note

Throughout this document, **"the vision docs"** refers to the set of files under `docs/vision/`: `README.md`, `package-design.md`, `view-format.md`, `implementation-language.md`, and `compilers/{index,nsjail,bwrap}.md`. That set is authoritative for any topic not addressed here.

---

## 2. Package skeleton (deliverable C)

This is the directory layout and file set that bootstrap produces before any v0.1 logic exists. An implementation agent executing this section should finish with a repository that passes `pip install -e . && pytest -q` (on an empty test suite) and `ruff check src/` (on the empty modules).

### Directory tree

```
umwelt/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── vision/                         # pre-existing; unchanged
│   └── superpowers/specs/              # this file lives here
├── src/
│   └── umwelt/
│       ├── __init__.py
│       ├── py.typed
│       ├── ast.py
│       ├── parser.py
│       ├── validate.py
│       ├── errors.py
│       ├── cli.py
│       ├── workspace/
│       │   ├── __init__.py
│       │   ├── builder.py
│       │   ├── writeback.py
│       │   ├── manifest.py
│       │   └── strategy.py
│       ├── hooks/
│       │   ├── __init__.py
│       │   └── dispatcher.py
│       ├── compilers/
│       │   ├── __init__.py
│       │   └── protocol.py             # stub in v0.1: Compiler protocol only
│       ├── runners/
│       │   └── __init__.py             # empty in v0.1
│       ├── bank/
│       │   └── __init__.py             # empty placeholder for v2
│       └── _fixtures/
│           ├── minimal.umw
│           ├── readonly-exploration.umw
│           └── auth-fix.umw
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    │   ├── __init__.py
    │   ├── test_parser.py
    │   ├── test_ast.py
    │   ├── test_validate.py
    │   ├── test_workspace_builder.py
    │   ├── test_workspace_writeback.py
    │   ├── test_workspace_manifest.py
    │   ├── test_workspace_strategy.py
    │   └── test_hooks_dispatcher.py
    └── integration/
        ├── __init__.py
        ├── test_end_to_end_parse.py
        ├── test_end_to_end_workspace.py
        └── test_cli.py
```

### `pyproject.toml` shape

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "umwelt"
version = "0.1.0"
description = "A CSS-shaped declarative format and runtime for bounding the world a delegated actor operates inside."
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.10"
authors = [
  { name = "Teague Sterling" },
]
keywords = ["sandbox", "delegate", "agent", "sandboxing", "nsjail", "bwrap", "view"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: MIT License",
  "Operating System :: POSIX :: Linux",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Topic :: Software Development :: Libraries",
  "Topic :: System :: Systems Administration",
]
dependencies = [
  "tinycss2>=1.2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "ruff>=0.5",
  "mypy>=1.10",
]

[project.scripts]
umwelt = "umwelt.cli:main"

[project.urls]
Homepage = "https://github.com/teaguesterling/umwelt"
Source = "https://github.com/teaguesterling/umwelt"
Issues = "https://github.com/teaguesterling/umwelt/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/umwelt"]

[tool.hatch.build.targets.wheel.force-include]
"src/umwelt/_fixtures" = "umwelt/_fixtures"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
strict = true
python_version = "3.10"
files = ["src/umwelt"]
```

**Key choices, with rationale anchors in §7:**

- `src/` layout — standard modern convention, prevents shadow imports before install.
- `hatchling` as the build backend — minimal, PEP 517-compliant, no friction.
- `tinycss2` as the single required runtime dep — §7 item L-1.
- No lockfile tool — consumer installs however they want (§7 item I-packaging).
- `py.typed` marker ships in the package — consumers get typed imports.
- `_fixtures` force-included in the wheel so downstream consumers can use them for their own tests if useful.

### CI shape (`.github/workflows/ci.yml`)

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: ruff check src/ tests/
      - run: mypy src/
      - run: pytest -q
```

No macOS/Windows matrix. No coverage gate. No pre-commit hook config. See §5 for the reasoning.

### Bootstrap acceptance criteria

Before any v0.1 logic lands, the skeleton must satisfy:

1. `pip install -e ".[dev]"` succeeds on a clean Python 3.10+ environment.
2. `ruff check src/` exits 0 (empty modules pass).
3. `mypy src/` exits 0 (empty modules pass under strict mode).
4. `pytest -q` exits 0 with "no tests collected" (no tests exist yet).
5. `umwelt --help` exits 0 and prints usage (CLI entry point is wired up even if `parse` subcommand is a stub that raises `NotImplementedError`).
6. CI matrix is green on all four Python versions.

Only after these six pass does Slice 1 (§4.1) start landing real code.

---

## 3. Core architecture for v0.1

Data flow is linear and every arrow is a pure-function or explicit-object boundary:

```
view file  ──parse──▶  View AST  ──build──▶  Workspace  ──(delegate edits)──▶  WriteBack  ──dispatch──▶  Hooks
                           │                                                                              
                           └──validate──▶ warnings / ViewValidationError
```

Each node below corresponds to one or more files from §2.

### 3.1 Parser and AST (`parser.py`, `ast.py`, `errors.py`)

**`parser.parse(source: str | Path, *, validate: bool = True) -> View`** is the single public entry point.

**Behavior:**

1. Accepts `str` (view text) or `Path` (view file). Auto-detects by `isinstance`.
2. Reads file contents into memory if given a path; keeps the raw text on the resulting `View` for error-reporting fidelity.
3. Tokenizes via `tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True)`.
4. Walks the token stream, dispatching on at-rule names (`@source`, `@tools`, `@after-change`). Any other at-rule is preserved as an `UnknownAtRule` with a parse-time warning — this is the forward-compatibility property described in `view-format.md`.
5. For recognized at-rules, parses block contents via `tinycss2.parse_declaration_list()`. Declarations that the parser does not recognize within a known at-rule are preserved as `UnknownDeclaration` with a warning.
6. For `@source` blocks, also walks nested selector rules into opaque `SelectorRule(selector_text, declarations)` entries. v0.1 does not interpret the selector text beyond preserving it verbatim.
7. If `validate=True` (default), runs `validate.validate(view)` before returning. Hard validation failures raise `ViewValidationError`. Soft warnings accumulate on `View.warnings`.
8. Raises `ViewParseError(message, line, col, source_path)` on syntactic errors. Line and column come from tinycss2's token positions; the message includes the offending token's repr.

**AST dataclasses (`ast.py`):** all frozen, all hashable where possible, all use `tuple` for sequence fields so instances are safely shareable.

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class SourceSpan:
    line: int
    col: int

@dataclass(frozen=True)
class SelectorRule:
    selector_text: str
    declarations: tuple[tuple[str, str], ...]   # (key, value) pairs
    span: SourceSpan

@dataclass(frozen=True)
class SourceBlock:
    path: str                                   # pre-glob-expansion argument
    default_editable: bool                      # from `* { editable: ... }`; False if no wildcard
    selector_rules: tuple[SelectorRule, ...]    # opaque in v0.1
    span: SourceSpan

@dataclass(frozen=True)
class ToolsBlock:
    allow: tuple[str, ...]
    deny: tuple[str, ...]
    kit: str | None
    span: SourceSpan

@dataclass(frozen=True)
class HookBlock:
    event: str                                  # "after-change" in v0.1
    commands: tuple[tuple[str, str], ...]       # (label, command) pairs
    span: SourceSpan

@dataclass(frozen=True)
class UnknownAtRule:
    name: str
    prelude_text: str
    block_text: str
    span: SourceSpan

@dataclass(frozen=True)
class UnknownDeclaration:
    key: str
    value: str
    in_at_rule: str
    span: SourceSpan

@dataclass(frozen=True)
class ParseWarning:
    message: str
    span: SourceSpan

@dataclass(frozen=True)
class View:
    source_blocks: tuple[SourceBlock, ...]
    tools_block: ToolsBlock | None
    hook_blocks: tuple[HookBlock, ...]
    unknown_at_rules: tuple[UnknownAtRule, ...]
    unknown_declarations: tuple[UnknownDeclaration, ...]
    warnings: tuple[ParseWarning, ...]
    source_text: str
    source_path: Path | None
```

**Errors (`errors.py`):**

```python
class UmweltError(Exception): ...
class ViewError(UmweltError): ...
class ViewParseError(ViewError):
    def __init__(self, message: str, line: int, col: int, source_path: Path | None = None): ...
class ViewValidationError(ViewError): ...
class WorkspaceError(UmweltError): ...
class ViewViolation(UmweltError):
    """Raised by writeback when a rejected change is encountered and strict=True."""
```

### 3.2 Validator (`validate.py`)

**`validate.validate(view: View) -> View`** returns a new `View` with accumulated warnings attached; raises `ViewValidationError` on hard failures.

v0.1 rules:

| Kind | Rule | Severity |
|---|---|---|
| H-1 | `@source` path must not escape the base directory via `..` segments after resolution | hard (raises) |
| H-2 | `@tools.allow` and `@tools.deny` must not share any entry | hard (raises) |
| S-1 | Multiple `@tools` blocks: the last wins, but emit a warning | soft |
| S-2 | Empty `@source` blocks (no wildcard rule, no selector rules, no declarations) | soft |
| S-3 | Duplicate declaration keys inside a block (last-wins per CSS cascade) | soft |

Soft warnings become `ParseWarning` entries attached to `View.warnings`. Hard failures raise with a message containing the offending span.

Validation runs by default inside `parse()`. Callers who want to inspect an unvalidated AST (e.g., for tooling that works on malformed files) pass `parse(text, validate=False)` and call `validate()` themselves if and when they want to.

### 3.3 Workspace (`workspace/`)

Four files, each with a single clear purpose.

#### `manifest.py`

```python
@dataclass(frozen=True)
class ManifestEntry:
    real_path: Path
    virtual_path: Path              # relative to workspace root
    writable: bool
    content_hash_at_build: str      # SHA-256 hex of real file at build time; always set
    strategy_name: str

@dataclass(frozen=True)
class WorkspaceManifest:
    entries: tuple[ManifestEntry, ...]
    base_dir: Path
    workspace_root: Path
```

Pure data. Serialization to JSON is a v0.2 concern (runners will need it); v0.1 keeps it in-memory only.

#### `strategy.py`

The "delegate materialization to providers" extension point from Question 5.4.

```python
from typing import Protocol

class ReconcileResult(Protocol): ...        # sealed: Applied | Rejected | Conflict | NoOp

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

@dataclass(frozen=True)
class NoOp:
    entry: ManifestEntry

class MaterializationStrategy(Protocol):
    name: str
    def materialize(self, real: Path, virtual: Path, writable: bool) -> ManifestEntry: ...
    def reconcile(self, entry: ManifestEntry, workspace_root: Path) -> ReconcileResult: ...

# Registry
_STRATEGIES: dict[str, MaterializationStrategy] = {}

def register_strategy(strategy: MaterializationStrategy) -> None: ...
def get_strategy(name: str) -> MaterializationStrategy: ...
def default_strategy() -> MaterializationStrategy: ...
```

**Default impl:** `SymlinkReadonlyCopyWritable`.

- `materialize(real, virtual, writable)`:
  - For both read-only and writable, compute and record a SHA-256 hash of the real file's bytes at build time. The hash is always captured regardless of strategy, so reconcile can detect any modification.
  - For read-only, create `virtual` as a symlink to `real`.
  - For writable, copy `real`'s bytes to `virtual`.
- `reconcile(entry, workspace_root)`:
  - **Read-only entries:** hash the real file's current bytes; compare to `entry.content_hash_at_build`.
    - Unchanged → `NoOp`.
    - Changed → `Rejected("read-only file was modified during delegate execution")`. Note the v0.1 caveat: without a sandbox compiler (v0.2), "read-only" is advisory — a delegate determined to write through the symlink can do so. Hash-based detection catches the modification after the fact but cannot distinguish delegate writes from external writes. Conservative assumption: treat any change as a violation.
  - **Writable entries:** hash the virtual file's current bytes and the real file's current bytes; compare both to `entry.content_hash_at_build`.
    - Virtual unchanged, real unchanged → `NoOp`.
    - Virtual changed, real unchanged → `Applied(new_content=<virtual bytes>)`.
    - Virtual unchanged, real changed → `Conflict("real file modified externally")`.
    - Virtual changed, real changed → `Conflict("both virtual and real modified; would overwrite external change")`.

`register_strategy` is how providers (v0.2+ runners, remote compilers, custom consumers) register alternative materialization strategies. The registry is global-but-explicit — no auto-registration at import time; callers opt in.

#### `builder.py`

```python
class WorkspaceBuilder:
    def __init__(self, strategy: str | MaterializationStrategy | None = None):
        self._strategy = _resolve_strategy(strategy)  # defaults to default_strategy()

    def build(self, view: View, base_dir: Path) -> Workspace:
        ...
```

**Algorithm:**

1. Create a temp directory as `workspace_root` (via `tempfile.mkdtemp(prefix="umwelt-")`).
2. Initialize an empty list of entries and a map of `real_path -> latest ManifestEntry`.
3. For each `SourceBlock` in `view.source_blocks` (in document order):
   - Resolve the block's `path` against `base_dir` via `Path(base_dir).glob(block.path)`. Literal paths work because `glob` treats no-wildcard inputs as single-match globs.
   - For each matched file:
     - Compute `virtual_path` as `workspace_root / relative_path_under_base_dir`.
     - If the real path resolves outside `base_dir` (via `realpath` + `is_relative_to`), raise `WorkspaceError("path traversal rejected")`.
     - Determine `writable = block.default_editable`.
     - If an entry already exists for this real path from an earlier block, apply the cascade: the later block's `writable` wins. Remove the earlier entry, re-materialize with the new strategy call if needed.
     - Call `self._strategy.materialize(real_path, virtual_path, writable)`, store the returned entry.
4. If zero files were matched across all blocks, emit a warning on the returned `Workspace.warnings`.
5. Return `Workspace(root=workspace_root, manifest=WorkspaceManifest(entries, base_dir, workspace_root), view=view)`.

`Workspace` is a context manager: `__enter__` returns self, `__exit__` calls `cleanup()` which `shutil.rmtree`s the workspace root.

#### `writeback.py`

```python
class WriteBack:
    def __init__(self, strict: bool = False): ...

    def apply(self, workspace: Workspace) -> WriteBackResult:
        ...
```

**Algorithm:**

1. Walk `workspace.manifest.entries`.
2. For each entry, call `strategy.reconcile(entry, workspace.root)` — the strategy name on the entry is used to look up the right strategy for reconciliation, so custom strategies work.
3. Accumulate results into four lists: `applied`, `rejected`, `conflicts`, `noops`.
4. For each `Applied(entry, new_content)`, write `new_content` to `entry.real_path`.
5. If `strict=True` and either `rejected` or `conflicts` is non-empty after reconciliation, raise `ViewViolation` with a summary.
6. Return `WriteBackResult(applied, rejected, conflicts, noops)`.

**Important:** writes to `real_path` happen *after* all reconciliation decisions are made. This ensures a partial failure doesn't leave the real tree half-updated — either all applied changes land or none do (caveat: between "decided to apply" and "finished writing", arbitrary failures like disk full can still occur; we don't do atomic multi-file commits in v0.1).

### 3.4 Hooks (`hooks/dispatcher.py`)

```python
@dataclass(frozen=True)
class HookContext:
    project_root: Path
    env: Mapping[str, str] | None = None     # defaults to os.environ
    timeout_seconds: float = 60.0

@dataclass(frozen=True)
class HookResult:
    label: str
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool

class HookDispatcher:
    def dispatch(self, blocks: Sequence[HookBlock], context: HookContext) -> list[HookResult]:
        ...
```

**Behavior:**

1. For each `HookBlock`, iterate its `(label, command)` pairs in order.
2. Each command is split via `shlex.split(command)` and run via `subprocess.run(..., cwd=context.project_root, env=context.env, capture_output=True, text=True, timeout=context.timeout_seconds)`.
3. On timeout, record `timed_out=True` with the partial stdout/stderr captured before the timeout.
4. On `FileNotFoundError`, record `returncode=-1` with a synthetic stderr "command not found: <cmd>".
5. A failing command (`returncode != 0`) does **not** abort subsequent commands; the dispatcher runs every one and reports results. Hook failure policy is the caller's concern.
6. Return the list of `HookResult`s.

`HookContext.project_root` is **explicit** — the dispatcher does not know about the workspace; the caller passes the project root (usually the same `base_dir` they gave to the workspace builder). This keeps the hook dispatcher decoupled from the workspace module.

### 3.5 CLI (`cli.py`)

v0.1 exposes exactly one subcommand:

```bash
umwelt parse path/to/file.umw
```

Implementation: `argparse`, ~40 lines. Parses the file, validates, prints the `View` dataclass via `pprint.pformat` (or a small custom formatter — decide at implementation time). Exit code 0 on success, 1 on `ViewParseError`, 2 on `ViewValidationError`. Errors print a short message to stderr with line/col.

No `compile`, `run`, `check`, or `inspect` subcommands in v0.1 — those arrive in v0.2+ with compilers.

`umwelt --help` and `umwelt parse --help` must work cleanly.

### 3.6 Compiler protocol stub (`compilers/protocol.py`)

Even though v0.1 ships zero concrete compilers, the `Compiler` protocol exists in v0.1 so the import path `from umwelt.compilers import Compiler` is stable from day 1 and v0.2's nsjail compiler slots in without moving files.

```python
from typing import Protocol
from umwelt.ast import View

class Compiler(Protocol):
    target_name: str
    target_format: str
    def compile(self, view: View) -> str | list[str] | dict: ...

_REGISTRY: dict[str, Compiler] = {}

def register(name: str, compiler: Compiler) -> None: ...
def get(name: str) -> Compiler: ...
def available() -> list[str]: ...
```

No concrete compilers are registered. `available()` returns `[]` in v0.1.

### 3.7 What the architecture does not include in v0.1

- `@network`, `@budget`, `@env` grammar: parser preserves them as `UnknownAtRule` with a warning. Dataclass definitions for `NetworkBlock`, `BudgetBlock`, `EnvBlock` arrive with v0.2's nsjail compiler.
- Any concrete compiler.
- Runners.
- Selector evaluation (opaque strings only).
- Concurrent hook execution.
- JSON manifest emission (v0.2 runners will need it).
- PyPI publish (metadata is ready; publish is v0.4).

---

## 4. Vertical slice plan (deliverable A build sequence)

v0.1 grows outward from a trivial end-to-end path. Six increments, each ending with a demoable green test. Slices are intended to be PR-sized.

### 4.1 Slice 1 — The trivial path

**Goal:** Parse a single-block view with one literal-path file, build a workspace, clean up.

**View that must work:**
```
@source("hello.txt") { * { editable: true; } }
```

**Landed:**
- `ast.py`: `View`, `SourceBlock`, `SourceSpan`, `SelectorRule` (empty), `ParseWarning`
- `parser.py`: tinycss2 setup; `parse()` recognizing exactly `@source(path) { * { editable: bool; } }`
- `errors.py`: `ViewParseError` with line/col
- `workspace/manifest.py`: `WorkspaceManifest`, `ManifestEntry`
- `workspace/strategy.py`: protocol + `SymlinkReadonlyCopyWritable` default + registry + SHA-256 hash-at-build
- `workspace/builder.py`: `build()` for a single block, literal path only
- `workspace/__init__.py`: `Workspace` context manager
- `tests/unit/test_parser.py` (1 test), `test_workspace_builder.py` (1 test), `test_workspace_strategy.py` (materialize + reconcile happy path)
- `tests/integration/test_end_to_end_parse.py` (1 test)

**Demo:** `python -c "from umwelt import parse; from umwelt.workspace import WorkspaceBuilder; from pathlib import Path; v = parse('demo.umw'); w = WorkspaceBuilder().build(v, Path.cwd()); print(w.root); w.cleanup()"`

### 4.2 Slice 2 — Writeback

**Goal:** Writable edits splice back; read-only edits rejected; external modifications detected.

**Landed:**
- `workspace/writeback.py`: `WriteBack.apply()` with `Applied`/`Rejected`/`Conflict`/`NoOp` reconciliation
- SHA-256 hashing in `SymlinkReadonlyCopyWritable`
- `tests/unit/test_workspace_writeback.py`: the six-cell state table from the vision docs, plus the mixed-outcome case

**Demo:** Build a workspace, modify a writable file, call writeback, observe splice-back.

### 4.3 Slice 3 — Globs and cascade

**Goal:** Multi-file globs, multiple `@source` blocks, last-block-wins cascade.

**Landed:**
- Glob expansion via `Path.glob()` in `builder.py`
- Cascade logic for overlapping blocks
- Empty-glob warning on `Workspace.warnings`
- Path-traversal rejection test
- `_fixtures/readonly-exploration.umw`
- Expanded `test_workspace_builder.py`

### 4.4 Slice 4 — `@tools` and `@after-change`

**Goal:** Full v0.1 at-rule set.

**Landed:**
- `ast.py`: `ToolsBlock`, `HookBlock`, `UnknownAtRule`, `UnknownDeclaration`
- `parser.py`: at-rule dispatch table recognizing `@tools` and `@after-change`; preserving unknown at-rules with warning
- `validate.py`: the five validation rules from §3.2
- `hooks/dispatcher.py`: full `HookDispatcher` implementation
- `_fixtures/auth-fix.umw`
- `tests/unit/test_hooks_dispatcher.py`, `test_validate.py`

### 4.5 Slice 5 — CLI and fixtures

**Goal:** `umwelt parse file.umw` works end-to-end; all fixtures round-trip through the parser.

**Landed:**
- `cli.py`: argparse entry point, `parse` subcommand
- `pyproject.toml` script entry verified
- `tests/integration/test_end_to_end_parse.py`: every fixture parses clean
- `tests/integration/test_cli.py`: subprocess invocation test

### 4.6 Slice 6 — Polish and v0.1.0 tag

**Goal:** v0.1 is ready to install and use.

**Landed:**
- `README.md` with install + usage example
- `CHANGELOG.md` v0.1 entry
- Ruff + mypy clean across `src/` and `tests/`
- CI green on Python 3.10–3.13
- `py.typed` marker verified
- `docs/vision/README.md` "Status" line updated to "v0.1 implemented"
- Git tag `v0.1.0`

### Slice dependency graph

```
Slice 1  ─┬─▶  Slice 2  (writeback depends on manifest + strategy)
          │
          └─▶  Slice 3  (globs + cascade depend on builder)
                   │
                   ▼
               Slice 4  (at-rules + hooks can start after Slice 3; uses parser from Slice 1)
                   │
                   ▼
               Slice 5  (CLI + fixtures need parser, validate, workspace)
                   │
                   ▼
               Slice 6  (polish)
```

Slices 2 and 3 can run in parallel (different files) if useful; sequential is simpler.

---

## 5. Testing strategy

### Unit tests — `tests/unit/`

One test file per production module. Coverage targets:

| Module | Test focus |
|---|---|
| `test_parser.py` | Every at-rule; every declaration type; nested selector rules preserved as opaque; all three comment forms; malformed input raises `ViewParseError` with correct line/col; unknown at-rules preserved with warning; string escapes (`\\`, `\"`, `\n`, `\t`); case-insensitivity on identifiers; numeric unit suffixes parsed (even though v0.1 doesn't use them semantically) |
| `test_ast.py` | Dataclass equality, frozen-ness, tuple field immutability |
| `test_validate.py` | Each of the five validation rules; valid views pass clean; warning vs error distinction |
| `test_workspace_manifest.py` | Entry construction, hash stability |
| `test_workspace_strategy.py` | Default strategy materialize+reconcile for all four outcomes; registering a custom strategy; lookup by name; unknown-name error; `register_strategy` idempotency |
| `test_workspace_builder.py` | Single source single file; multi-file glob; multiple sources with cascade (last-block-wins); empty-glob warning; path-traversal rejection; strategy override via constructor |
| `test_workspace_writeback.py` | All four reconcile outcomes × writable/read-only; mixed-outcome case; `strict=True` raises; `strict=False` returns result |
| `test_hooks_dispatcher.py` | Success; failure-continues; timeout hit; command-not-found; cwd is `project_root`; env override; output capture |

### Integration tests — `tests/integration/`

- `test_end_to_end_parse.py` — every fixture in `_fixtures/` parses without error; validator produces expected warning set.
- `test_end_to_end_workspace.py` — build a workspace from `auth-fix.umw` against a temp project tree; simulate an edit by writing to a writable virtual file; run writeback; assert the applied/rejected/conflicts counts match expectations.
- `test_cli.py` — subprocess invocation of `umwelt parse _fixtures/auth-fix.umw`; assert exit 0; assert the pretty-printed AST contains the expected source-block paths.

### Fixtures — `src/umwelt/_fixtures/`

Three v0.1 fixtures:

- `minimal.umw` — single `@source` block, one file, writable. Smallest possible valid view.
- `readonly-exploration.umw` — two `@source` blocks, all read-only, `@tools` with `allow: Read, Grep, Glob`. No hooks.
- `auth-fix.umw` — trimmed-to-v0.1 version of the kitchen-sink example from `view-format.md`: two `@source` blocks with cascade, `@tools` allow+deny, `@after-change` with two commands. Drops `@network`/`@budget`/`@env` since those are v0.2.

### Deliberate omissions

- **No fuzz testing.** Malformed-input hardening is a v0.5 concern per the vision roadmap.
- **No property-based tests.** The grammar is narrow enough and the fixtures cover the space.
- **No benchmark suite.** v0.1 performance is not a concern; tinycss2 handles the hot path.
- **No coverage gates in CI.** Track locally; don't fail builds on percentage.
- **No macOS/Windows CI.** Linux-only; symlink behavior is Linux-shaped and cross-platform concerns arrive with compilers.
- **No real-sandbox integration tests.** nsjail/bwrap arrive with v0.2.
- **No pre-commit hooks.** CI is the authoritative check.

### Tooling

- **pytest** as test runner. Canonical command: `pytest -q`.
- **ruff** for lint + format. Config in `pyproject.toml`.
- **mypy** strict mode on `src/umwelt/`.
- **pytest-tmp-path** (stdlib fixture) for every workspace builder test.

---

## 6. Port-ready decomposition

Per `implementation-language.md`, the architecture must remain port-ready so a future Rust port (if ever needed) is scoped to the parser and compiler layers, not the whole package. v0.1 satisfies this by construction:

- `parser.parse(text: str) -> View` is a pure function: no side effects, no I/O beyond reading the input file.
- Compiler protocol (stub in v0.1, concrete from v0.2) is `compile(view: View) -> str | list[str] | dict` — pure.
- Workspace operations are I/O-bound and not port candidates.
- Hook dispatch is subprocess orchestration and not a port candidate.

**Rust-port criteria (from `implementation-language.md`, adopted here):** any future Rust port requires *at least one* of the following:

- A measured performance problem in the parser or compilers (not hypothesized).
- A concrete non-Python consumer requesting bindings.
- A security audit finding that depends on memory safety of the parser.
- A distribution problem requiring a static binary.

None are true in 2026. Revisit only when one becomes true.

---

## 7. Open-question resolutions (deliverable B)

Every open question from the vision docs, with a v0.1 resolution and reason.

### 7.1 From `package-design.md` §Open questions

| # | Question | Resolution | Reason |
|---|---|---|---|
| P-1 | File extension for views | **`.umw`** | Distinct, short, not overloaded. Decision made during brainstorming. |
| P-2 | Symlink vs copy for read-only | **Symlinks for read-only, copies for writable; pluggable via `MaterializationStrategy`** | Default matches vision. The pluggable strategy protocol in `workspace/strategy.py` is the extension point providers use when the defaults don't fit (e.g., remote stage-in, snapshot-based filesystems). Captured in §3.3. |
| P-3 | How does the delegate learn the workspace layout? | **Deferred to v0.2** | Not v0.1-blocking. v0.1 returns a `Workspace` with `.manifest`; the consumer decides how to expose it to its delegate. The `.umw-manifest.json` emission format gets pinned when v0.2 runners exist. |
| P-4 | Compiler registry priority ordering | **Last-write-wins with a warning** | Matches vision. Registry exists in v0.1 but has no concrete registrations, so the behavior is not exercised yet. |
| P-5 | Textproto hand-rolling vs library dependency | **Hand-rolled, optional `nsjail-python` validator** | Not v0.1-blocking — no compilers in v0.1. Decision stands for v0.2. |
| P-6 | CLI framework | **argparse** | Stdlib only, zero extra deps, v0.1 has one subcommand. |
| P-7 | Cascade semantics for overlapping `@source` blocks | **Last-block-wins (CSS cascade)** | Least surprising; matches vision. Implemented in Slice 3. |
| P-8 | `@env { allow: VAR }` semantics | **Pass-through only in v1; explicit assignment in v1.1** | Not v0.1-blocking — `@env` is an `UnknownAtRule` in v0.1. Resolution stands for v0.2. |
| P-9 | Should umwelt ever author views? | **No in v1; `View.to_string()` is v1.1+** | Keeps the v0.1 API surface tight. |
| P-10 | Keep "view" as user-facing terminology | **Yes** | Aligns with `.umw`, vision docs, naming. |

### 7.2 From `implementation-language.md` §Open follow-ups

| # | Question | Resolution | Reason |
|---|---|---|---|
| L-1 | Is "stdlib only" a hard constraint? | **Soft. tinycss2 is a required runtime dep.** | Decided in brainstorming. The leaf-dependency stance is preserved at the consumer-facing boundary (no nsjail-python, lackpy, pluckit at runtime). tinycss2 is a narrow, BSD-licensed, well-tested CSS tokenizer — a different category of dependency. |
| L-2 | Known non-Python consumer? | **None.** Rust port deferred. | All known consumers (lackpy, kibitzer, pluckit, claude-plugins) are Python. Revisit only on concrete demand. |
| L-3 | Port-ready decomposition as an explicit design constraint? | **Yes** — recorded in §6. | Parser and compilers are pure functions. v0.1's module boundaries enforce this. |
| L-4 | "Measure first, port second" rule for v2? | **Yes** — recorded in §6. | Prevents speculative rewrites; anchors any port decision in evidence. |

### 7.3 From the compiler vision docs

All open questions in `compilers/nsjail.md` and `compilers/bwrap.md` (workspace root convention, user identity, seccomp, wrapper command availability, absolute path remapping, user namespaces, read-only rootfs) are v0.2+ concerns. None block v0.1. They remain open and will be revisited when the corresponding compiler is implemented.

### 7.4 New questions surfaced during brainstorming

| # | Question | Resolution |
|---|---|---|
| N-1 | Does `@source("hello.txt")` (literal, not glob) need special handling? | No. `Path.glob()` handles literal paths as single-match "globs" correctly. |
| N-2 | What happens when a `@source` path matches zero files? | Warning attached to `Workspace.warnings`, not an error. |
| N-3 | Should `HookContext.project_root` default to `base_dir` of the workspace builder? | No — explicit. Keeps the hook dispatcher decoupled from the workspace module. |
| N-4 | Is there a v0.1 notion of "running a delegate inside the workspace"? | No. v0.1 builds a workspace and returns it; caller runs whatever they want inside `workspace.root`. |
| N-5 | Should `parse()` accept an open file object? | No in v0.1. `parse(Path(...))` and `parse(text)` cover every realistic case. Two-line addition if it ever matters. |
| N-6 | Packaging tooling | Plain `pyproject.toml` with `hatchling` build backend. No lockfile tool. Consumers install however they want. |

### 7.5 Explicitly still-open (intentionally unresolved)

Load-bearing for later work, zero v0.1 decision cost:

- Kubernetes/slurm compiler output shape (v2+)
- View bank schema and retrieval (v2)
- Security threat model and parser hardening (v0.5)
- Per-command hook timeouts (v1.1)
- Selector-level extraction semantics and pluckit integration (v1.1)
- `@network { allow: host }` enforcement mechanism (v1.1)
- `@after-change` scoped dispatch (v1.1)
- uid/gid mapping `@identity` at-rule (v1.1+)
- seccomp profiles via `@syscalls` at-rule (v1.1+)

---

## 8. v0.1 acceptance criteria

v0.1 is "done" when all of the following are true:

1. All six slices (§4) have landed on `main`.
2. CI is green on Python 3.10, 3.11, 3.12, 3.13.
3. `ruff check src/ tests/` exits 0.
4. `mypy src/` exits 0 under strict mode.
5. `pytest -q` exits 0; every unit test and integration test passes.
6. The three fixtures in `_fixtures/` round-trip through `parse()` without warnings other than those explicitly expected by their tests.
7. `pip install -e . && umwelt parse src/umwelt/_fixtures/minimal.umw` runs from a clean clone and produces non-empty output.
8. `README.md` includes the installation steps and a usage example that actually works when run.
9. `CHANGELOG.md` has a v0.1.0 entry listing what's included and what's deliberately deferred.
10. A git tag `v0.1.0` exists.

v0.1 is **not** required to publish to PyPI, pass on macOS, run under nsjail/bwrap, or handle any at-rule beyond `@source`/`@tools`/`@after-change`.

---

## 9. Glossary

- **View** — a `.umw` file declaring what an actor can see, edit, call, and trigger. CSS-shaped surface syntax.
- **At-rule** — a view construct starting with `@`, like `@source`, `@tools`, `@after-change`.
- **SourceBlock** — parsed representation of an `@source` at-rule; contains a path and default editability.
- **Manifest** — the list of `(real_path, virtual_path, writable, hash)` tuples recorded when the workspace is built; used to decide what to splice back.
- **Materialization strategy** — the pluggable policy for how virtual workspace entries are physically created (symlink, copy, snapshot, stage-in, etc.). v0.1 default is `SymlinkReadonlyCopyWritable`.
- **Writeback** — the post-delegate step that compares virtual files to real files and decides per-entry whether to splice, reject, or flag a conflict.
- **Altitude** — where in the sandbox tower an enforcement mechanism operates: OS (nsjail, bwrap), language (lackpy namespace), semantic (hooks, validators), conversational (retrieval, prompt composition).
- **Walking skeleton** — the v0.1 milestone: the minimal end-to-end slice of the package that works, without yet doing the full job.

---

## 10. What this document is not

- Not a replacement for the vision docs. Read `docs/vision/README.md` and `package-design.md` alongside this.
- Not an implementation plan. After approval, `writing-plans` produces the slice-by-slice plan with concrete tasks.
- Not the last word on any of the "explicitly still-open" items in §7.5. Those get revisited as their milestones approach.
