# umwelt v0.1-core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the vocabulary-agnostic core of umwelt — parser + AST + plugin registry + selector engine + cascade resolver + compiler protocol + CLI — tested end-to-end against a toy taxonomy registered in-test.

**Architecture:** Pure functions at the parse/resolve/compile boundaries. Plugin registry is module-global with test scope override. Selector engine classifies descendant combinators as structural (within a taxon) or context (across taxa) at parse time via registry lookup. Cascade is scoped to the rule's target taxon (rightmost entity), with specificity accumulating across compound parts.

**Tech Stack:** Python 3.10+, `tinycss2` for CSS tokenization, `pytest` for testing, `ruff` for lint, `mypy` strict for types, `hatchling` build backend. See `docs/vision/implementation-language.md` for the rationale.

**Spec reference:** `docs/superpowers/specs/2026-04-10-umwelt-v01-core-and-sandbox-scoping-design.md` §§2-5, §9.1-9.4. The spec is authoritative for any architecture question this plan leaves ambiguous.

---

## File structure

Core umwelt files created by this plan:

```
src/umwelt/
├── __init__.py                  # public API re-exports (Task 3)
├── py.typed                     # PEP 561 marker (Task 0)
├── errors.py                    # exception hierarchy (Task 1)
├── ast.py                       # View, RuleBlock, SimpleSelector, ... (Task 2)
├── parser.py                    # tinycss2-backed parse() entry (Tasks 8-16)
├── validate.py                  # validator dispatcher (Task 18)
├── cli.py                       # umwelt parse | inspect | check (Task 25)
├── inspect_util.py              # umwelt inspect implementation (Task 26)
├── check_util.py                # umwelt check implementation (Task 27)
├── dry_run.py                   # umwelt dry-run scaffold (Task 28)
├── registry/
│   ├── __init__.py              # public register_* API (Tasks 4-7)
│   ├── taxa.py                  # taxon registration + lookup (Task 4)
│   ├── entities.py              # entity registration + schemas (Task 5)
│   ├── properties.py            # property registration + comparison semantics (Task 6)
│   ├── matchers.py              # MatcherProtocol + register_matcher (Task 7)
│   └── validators.py            # ValidatorProtocol + register_validator (Task 18)
├── selector/
│   ├── __init__.py
│   ├── parse.py                 # selector text -> SimpleSelector / ComplexSelector (Tasks 8-14)
│   ├── specificity.py           # CSS3 specificity + compound accumulation (Tasks 15, 17)
│   └── match.py                 # evaluate selector against a matcher (Tasks 19-21)
├── cascade/
│   ├── __init__.py
│   └── resolver.py              # per-taxon cascade; target-taxon scoping (Tasks 22-24)
└── compilers/
    ├── __init__.py              # register/get/available (Task 23)
    └── protocol.py              # Compiler Protocol with altitude (Task 23)

tests/
├── conftest.py                  # shared fixtures incl. registry scope (Task 0)
├── core/
│   ├── __init__.py
│   ├── helpers/
│   │   ├── __init__.py
│   │   └── toy_taxonomy.py      # InMemoryTestMatcher + toy taxa for tests (Task 7)
│   ├── test_errors.py           # Task 1
│   ├── test_ast.py              # Task 2
│   ├── test_registry_taxa.py    # Task 4
│   ├── test_registry_entities.py # Task 5
│   ├── test_registry_properties.py # Task 6
│   ├── test_registry_matchers.py # Task 7
│   ├── test_parser_basic.py     # Tasks 8-11
│   ├── test_parser_selectors.py # Tasks 12-14
│   ├── test_parser_resolution.py # Tasks 15-16
│   ├── test_specificity.py      # Task 17
│   ├── test_validate.py         # Task 18
│   ├── test_selector_match.py   # Tasks 19-21
│   ├── test_cascade.py          # Tasks 22, 24
│   ├── test_compiler_protocol.py # Task 23
│   ├── test_cli.py              # Task 25
│   ├── test_inspect.py          # Task 26
│   └── test_check.py            # Task 27

pyproject.toml                   # Task 0
README.md                        # updated in Task 29
LICENSE                          # Task 0
CHANGELOG.md                     # Task 29
.gitignore                       # Task 0
.github/workflows/ci.yml         # Task 0
```

**Total files created:** ~35 source files + ~15 test files.
**Estimated LOC:** ~1,600 production + ~1,400 tests.

---

## Task breakdown

This plan has **29 tasks** across four slices matching the scoping spec §9.1-9.4:

- **Slice 1 — Core parser + AST + simple selectors (Tasks 0-11):** bootstrap, errors, AST, registry, parser for simple selectors.
- **Slice 2 — Compound selectors + combinator modes (Tasks 12-17):** descendant/child combinators, taxon resolution, mode classification, specificity accumulation.
- **Slice 3 — Cascade + comparison + pattern properties (Tasks 18-24):** validator framework, selector matching, cascade resolver, comparison-prefix and pattern-valued declarations.
- **Slice 4 — CLI + compiler protocol + acceptance (Tasks 25-29):** compiler protocol, CLI subcommands, inspect/check/dry-run utilities, README + CHANGELOG + v0.1-core acceptance.

Every task follows the pattern: (1) write the failing test, (2) run to verify it fails, (3) implement the minimal code to pass, (4) run to verify it passes, (5) commit. For tasks that also touch docs or configuration, an extra step runs `ruff check` and `mypy src/` before the commit.

**Commit message convention:** `feat(<area>): <what>` for new functionality, `test(<area>): <what>` for test-only additions, `chore: <what>` for bootstrap/tooling. Bodies explain why when non-obvious. All commits use the `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>` trailer.

**Branching:** stay on `main` for v0.1-core. We're pre-implementation with one contributor; main is additive and there's nothing to disrupt. Revisit branching once v0.1-core is tagged.

---

## Slice 1 — Core parser + AST + simple selectors

### Task 0: Project bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `LICENSE`
- Create: `.gitignore`
- Create: `.github/workflows/ci.yml`
- Create: `src/umwelt/__init__.py`
- Create: `src/umwelt/py.typed`
- Create: `tests/__init__.py`
- Create: `tests/core/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "umwelt"
version = "0.1.0.dev0"
description = "The common language of the specified band. A CSS-shaped declarative format for policy specification."
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.10"
authors = [
  { name = "Teague Sterling" },
]
keywords = ["sandbox", "delegate", "agent", "policy", "specified-band", "view"]
classifiers = [
  "Development Status :: 2 - Pre-Alpha",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: MIT License",
  "Operating System :: POSIX :: Linux",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Topic :: Software Development :: Libraries",
  "Topic :: System :: Systems Administration",
  "Typing :: Typed",
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

[tool.ruff]
line-length = 100
target-version = "py310"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]
ignore = ["E501"]  # line length handled by formatter

[tool.mypy]
strict = true
python_version = "3.10"
files = ["src/umwelt"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 Teague Sterling

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
*.egg

# Virtualenvs
.venv/
venv/
env/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Type checking
.mypy_cache/
.dmypy.json
dmypy.json

# Ruff
.ruff_cache/

# Editors
.vscode/
.idea/
*.swp
*~
.DS_Store
```

- [ ] **Step 4: Create `.github/workflows/ci.yml`**

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
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install
        run: pip install -e ".[dev]"
      - name: Ruff
        run: ruff check src/ tests/
      - name: Mypy
        run: mypy src/
      - name: Pytest
        run: pytest -q
```

- [ ] **Step 5: Create empty package files**

```bash
mkdir -p src/umwelt tests/core
touch src/umwelt/py.typed
```

Create `src/umwelt/__init__.py` with:

```python
"""umwelt: the common language of the specified band."""

__version__ = "0.1.0.dev0"
```

Create `tests/__init__.py` (empty file).

Create `tests/core/__init__.py` (empty file).

Create `tests/conftest.py` with:

```python
"""Shared pytest fixtures."""
```

- [ ] **Step 6: Install and run baseline**

Run: `pip install -e ".[dev]"`
Expected: successful install.

Run: `ruff check src/ tests/`
Expected: `All checks passed!` (no files to check but exit 0).

Run: `mypy src/`
Expected: `Success: no issues found in 1 source file` (just `__init__.py`).

Run: `pytest -q`
Expected: `no tests ran in X.XXs` (exit 5 is fine for "no tests collected"; add `--co -q` if pytest is configured to fail on no-tests; otherwise passthrough exits 0).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml LICENSE .gitignore .github/ src/ tests/
git commit -m "$(cat <<'EOF'
chore: bootstrap v0.1-core package skeleton

Initializes pyproject.toml with hatchling backend, tinycss2 runtime
dep, and pytest/ruff/mypy dev deps. MIT LICENSE, .gitignore, CI
matrix on Python 3.10-3.13. Empty src/umwelt/ and tests/core/
packages with py.typed marker.

pip install -e ".[dev]" works; ruff, mypy, pytest all exit clean
on the empty skeleton.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1: Error hierarchy

**Files:**
- Create: `src/umwelt/errors.py`
- Create: `tests/core/test_errors.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_errors.py`:

```python
"""Tests for the umwelt error hierarchy."""

import pytest

from umwelt.errors import (
    RegistryError,
    UmweltError,
    ViewError,
    ViewParseError,
    ViewValidationError,
)


def test_umwelt_error_is_exception():
    assert issubclass(UmweltError, Exception)


def test_view_error_is_umwelt_error():
    assert issubclass(ViewError, UmweltError)


def test_view_parse_error_is_view_error():
    assert issubclass(ViewParseError, ViewError)


def test_view_validation_error_is_view_error():
    assert issubclass(ViewValidationError, ViewError)


def test_registry_error_is_umwelt_error():
    assert issubclass(RegistryError, UmweltError)


def test_view_parse_error_captures_position():
    err = ViewParseError("unexpected token", line=5, col=12)
    assert err.line == 5
    assert err.col == 12
    assert "line 5" in str(err)
    assert "col 12" in str(err)


def test_view_parse_error_optional_source_path():
    from pathlib import Path

    err = ViewParseError(
        "unexpected token", line=5, col=12, source_path=Path("views/test.umw")
    )
    assert err.source_path == Path("views/test.umw")
    assert "views/test.umw" in str(err)


def test_view_parse_error_raises_cleanly():
    with pytest.raises(ViewParseError, match="unexpected token"):
        raise ViewParseError("unexpected token", line=1, col=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_errors.py -v`
Expected: `ModuleNotFoundError: No module named 'umwelt.errors'` — all tests error.

- [ ] **Step 3: Write minimal implementation**

Create `src/umwelt/errors.py`:

```python
"""Exception hierarchy for umwelt."""

from __future__ import annotations

from pathlib import Path


class UmweltError(Exception):
    """Base class for all umwelt errors."""


class ViewError(UmweltError):
    """Base class for errors raised while handling a view."""


class ViewParseError(ViewError):
    """Raised when a view file fails to parse."""

    def __init__(
        self,
        message: str,
        *,
        line: int,
        col: int,
        source_path: Path | None = None,
    ) -> None:
        self.message = message
        self.line = line
        self.col = col
        self.source_path = source_path
        location = f"line {line}, col {col}"
        if source_path is not None:
            location = f"{source_path} {location}"
        super().__init__(f"{message} ({location})")


class ViewValidationError(ViewError):
    """Raised when a parsed view fails semantic validation."""


class RegistryError(UmweltError):
    """Raised on plugin-registry collisions or lookup failures."""
```

- [ ] **Step 4: Run tests and type check**

Run: `pytest tests/core/test_errors.py -v`
Expected: all eight tests pass.

Run: `mypy src/`
Expected: `Success: no issues found in 2 source files`.

Run: `ruff check src/ tests/`
Expected: `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/errors.py tests/core/test_errors.py
git commit -m "$(cat <<'EOF'
feat(errors): add umwelt exception hierarchy

UmweltError / ViewError / ViewParseError / ViewValidationError /
RegistryError. ViewParseError captures line, col, and optional
source_path; its str() includes the location so error messages
are useful without unpacking.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: AST dataclasses

**Files:**
- Create: `src/umwelt/ast.py`
- Create: `tests/core/test_ast.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_ast.py`:

```python
"""Tests for the umwelt AST dataclasses."""

from __future__ import annotations

from pathlib import Path

import pytest

from umwelt.ast import (
    AttrFilter,
    CompoundPart,
    ComplexSelector,
    Declaration,
    ParseWarning,
    PseudoClass,
    RuleBlock,
    SimpleSelector,
    SourceSpan,
    UnknownAtRule,
    View,
)


def test_source_span_is_frozen():
    span = SourceSpan(line=1, col=1)
    with pytest.raises((AttributeError, Exception)):  # dataclass frozen
        span.line = 2  # type: ignore[misc]


def test_simple_selector_basic():
    sel = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(AttrFilter(name="path", op="^=", value="src/"),),
        pseudo_classes=(),
        span=SourceSpan(line=1, col=1),
    )
    assert sel.type_name == "file"
    assert sel.taxon == "world"
    assert sel.attributes[0].name == "path"


def test_simple_selector_is_hashable():
    sel1 = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(),
        pseudo_classes=(),
        span=SourceSpan(line=1, col=1),
    )
    sel2 = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(),
        pseudo_classes=(),
        span=SourceSpan(line=1, col=1),
    )
    # Equality on frozen dataclasses is structural
    assert sel1 == sel2
    assert hash(sel1) == hash(sel2)
    # Can live in a set
    assert {sel1, sel2} == {sel1}


def test_compound_part_modes():
    simple = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(),
        pseudo_classes=(),
        span=SourceSpan(line=1, col=1),
    )
    part = CompoundPart(selector=simple, combinator="root", mode="root")
    assert part.mode == "root"
    assert part.combinator == "root"


def test_complex_selector_target_taxon_and_specificity():
    simple = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(AttrFilter(name="path", op="^=", value="src/"),),
        pseudo_classes=(),
        span=SourceSpan(line=1, col=1),
    )
    compound = ComplexSelector(
        parts=(CompoundPart(selector=simple, combinator="root", mode="root"),),
        target_taxon="world",
        specificity=(0, 1, 1),
    )
    assert compound.target_taxon == "world"
    assert compound.specificity == (0, 1, 1)


def test_declaration_multi_value():
    decl = Declaration(
        property_name="run",
        values=("pytest", "ruff check"),
        span=SourceSpan(line=3, col=5),
    )
    assert decl.property_name == "run"
    assert decl.values == ("pytest", "ruff check")


def test_view_construction():
    view = View(
        rules=(),
        unknown_at_rules=(),
        warnings=(),
        source_text="",
        source_path=None,
    )
    assert view.rules == ()
    assert view.source_path is None


def test_view_with_source_path():
    view = View(
        rules=(),
        unknown_at_rules=(),
        warnings=(),
        source_text="",
        source_path=Path("test.umw"),
    )
    assert view.source_path == Path("test.umw")


def test_unknown_at_rule_preserved():
    at = UnknownAtRule(
        name="retrieval",
        prelude_text="",
        block_text="context: last-3;",
        span=SourceSpan(line=1, col=1),
    )
    assert at.name == "retrieval"


def test_parse_warning():
    warn = ParseWarning(
        message="duplicate declaration key",
        span=SourceSpan(line=5, col=3),
    )
    assert "duplicate" in warn.message


def test_pseudo_class_with_argument():
    ps = PseudoClass(name="glob", argument="src/**/*.py")
    assert ps.name == "glob"
    assert ps.argument == "src/**/*.py"


def test_attr_filter_exists_form():
    # [path] — existence check, no op or value
    af = AttrFilter(name="path", op=None, value=None)
    assert af.name == "path"
    assert af.op is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_ast.py -v`
Expected: `ModuleNotFoundError: No module named 'umwelt.ast'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/umwelt/ast.py`:

```python
"""AST dataclasses for parsed umwelt views.

Everything is a frozen dataclass with tuple-typed sequence fields so the
AST is safely shareable and hashable. No methods beyond dataclass defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Combinator = Literal["root", "descendant", "child", "sibling", "adjacent"]
CombinatorMode = Literal["structural", "context", "root"]
AttrOp = Literal["=", "^=", "$=", "*=", "~=", "|="]


@dataclass(frozen=True)
class SourceSpan:
    """Line and column of an AST node in the source text."""

    line: int
    col: int


@dataclass(frozen=True)
class AttrFilter:
    """An attribute selector filter: [name], [name=value], [name^=value], ..."""

    name: str
    op: AttrOp | None
    value: str | None


@dataclass(frozen=True)
class PseudoClass:
    """A pseudo-class selector: :not(...), :glob(...), :has(...)."""

    name: str
    argument: str | None


@dataclass(frozen=True)
class SimpleSelector:
    """A single element in a selector chain.

    `taxon` is resolved at parse time by looking up `type_name` in the
    plugin registry. Compound selectors use this to classify each combinator
    as structural (same taxon) or context (different taxa).
    """

    type_name: str | None
    taxon: str
    id_value: str | None
    classes: tuple[str, ...]
    attributes: tuple[AttrFilter, ...]
    pseudo_classes: tuple[PseudoClass, ...]
    span: SourceSpan


@dataclass(frozen=True)
class CompoundPart:
    """One part of a compound selector.

    `combinator` is the CSS-style relationship to the previous part
    ("root" for the first part, "descendant"/"child"/etc. for the rest).
    `mode` is set at parse time by comparing the taxa on either side of
    the combinator: "structural" when they match, "context" when they
    differ, "root" for the leading part.
    """

    selector: SimpleSelector
    combinator: Combinator
    mode: CombinatorMode


@dataclass(frozen=True)
class ComplexSelector:
    """A compound selector with taxon-resolved target and specificity."""

    parts: tuple[CompoundPart, ...]
    target_taxon: str
    specificity: tuple[int, int, int]


@dataclass(frozen=True)
class Declaration:
    """A property declaration: `name: value;` or `name: v1, v2, v3;`."""

    property_name: str
    values: tuple[str, ...]
    span: SourceSpan


@dataclass(frozen=True)
class RuleBlock:
    """A selector list + its declaration block.

    `nested_blocks` is reserved for future CSS-style nesting support and
    is always empty in v0.1.
    """

    selectors: tuple[ComplexSelector, ...]
    declarations: tuple[Declaration, ...]
    nested_blocks: tuple["RuleBlock", ...]
    span: SourceSpan


@dataclass(frozen=True)
class UnknownAtRule:
    """An @-rule the parser didn't recognize. Preserved for forward compat."""

    name: str
    prelude_text: str
    block_text: str
    span: SourceSpan


@dataclass(frozen=True)
class ParseWarning:
    """A soft parser warning, attached to the View rather than raised."""

    message: str
    span: SourceSpan


@dataclass(frozen=True)
class View:
    """A parsed view: top-level rule blocks plus preserved unknown at-rules."""

    rules: tuple[RuleBlock, ...]
    unknown_at_rules: tuple[UnknownAtRule, ...]
    warnings: tuple[ParseWarning, ...]
    source_text: str
    source_path: Path | None
```

- [ ] **Step 4: Run tests and checks**

Run: `pytest tests/core/test_ast.py -v`
Expected: all 12 tests pass.

Run: `mypy src/`
Expected: `Success: no issues found in 3 source files`.

Run: `ruff check src/ tests/`
Expected: `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/ast.py tests/core/test_ast.py
git commit -m "$(cat <<'EOF'
feat(ast): add frozen-dataclass AST for parsed views

View, RuleBlock, ComplexSelector, CompoundPart, SimpleSelector,
AttrFilter, PseudoClass, Declaration, UnknownAtRule, ParseWarning.
All frozen, all tuple-typed sequence fields, all hashable. SimpleSelector
carries its resolved taxon (populated at parse time by registry lookup);
ComplexSelector carries target_taxon and accumulated specificity for
cascade scoping.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Public API re-exports

**Files:**
- Modify: `src/umwelt/__init__.py`
- Create: `tests/core/test_public_api.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_public_api.py`:

```python
"""Tests for the public import surface."""


def test_top_level_imports():
    from umwelt import (  # noqa: F401
        ParseWarning,
        RegistryError,
        SourceSpan,
        UmweltError,
        View,
        ViewError,
        ViewParseError,
        ViewValidationError,
        __version__,
    )


def test_version_format():
    from umwelt import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_public_api.py -v`
Expected: `ImportError` on the first test — the names aren't exported yet.

- [ ] **Step 3: Update `src/umwelt/__init__.py`**

```python
"""umwelt: the common language of the specified band."""

from umwelt.ast import ParseWarning, SourceSpan, View
from umwelt.errors import (
    RegistryError,
    UmweltError,
    ViewError,
    ViewParseError,
    ViewValidationError,
)

__version__ = "0.1.0.dev0"

__all__ = [
    "ParseWarning",
    "RegistryError",
    "SourceSpan",
    "UmweltError",
    "View",
    "ViewError",
    "ViewParseError",
    "ViewValidationError",
    "__version__",
]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_public_api.py -v`
Expected: both tests pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/__init__.py tests/core/test_public_api.py
git commit -m "$(cat <<'EOF'
feat(init): expose AST and error types at the public import surface

`from umwelt import View, ViewParseError, ...` now works. The parse()
entry point lands with the parser in a later task.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Registry — taxa

**Files:**
- Create: `src/umwelt/registry/__init__.py`
- Create: `src/umwelt/registry/taxa.py`
- Create: `tests/core/test_registry_taxa.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_registry_taxa.py`:

```python
"""Tests for taxon registration."""

import pytest

from umwelt.errors import RegistryError
from umwelt.registry import (
    TaxonSchema,
    get_taxon,
    list_taxa,
    register_taxon,
    registry_scope,
)


def test_register_and_lookup():
    with registry_scope():
        register_taxon(name="world", description="the actor's world")
        taxon = get_taxon("world")
        assert taxon.name == "world"
        assert taxon.description == "the actor's world"


def test_register_with_ma_concept():
    with registry_scope():
        register_taxon(
            name="world",
            description="the actor's world",
            ma_concept="world_coupling_axis",
        )
        taxon = get_taxon("world")
        assert taxon.ma_concept == "world_coupling_axis"


def test_duplicate_raises():
    with registry_scope():
        register_taxon(name="world", description="first")
        with pytest.raises(RegistryError, match="already registered"):
            register_taxon(name="world", description="second")


def test_unknown_raises():
    with registry_scope():
        with pytest.raises(RegistryError, match="not registered"):
            get_taxon("ghost")


def test_list_taxa():
    with registry_scope():
        register_taxon(name="world", description="a")
        register_taxon(name="capability", description="b")
        names = {t.name for t in list_taxa()}
        assert names == {"world", "capability"}


def test_scope_isolation():
    with registry_scope():
        register_taxon(name="world", description="inside")
        assert get_taxon("world").description == "inside"
    # Outside the scope, the taxon is gone
    with pytest.raises(RegistryError):
        get_taxon("world")


def test_nested_scopes():
    with registry_scope():
        register_taxon(name="outer", description="o")
        with registry_scope():
            register_taxon(name="inner", description="i")
            assert get_taxon("inner").name == "inner"
            with pytest.raises(RegistryError):
                get_taxon("outer")
        # Inner scope done; outer is back
        assert get_taxon("outer").name == "outer"
        with pytest.raises(RegistryError):
            get_taxon("inner")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_registry_taxa.py -v`
Expected: `ModuleNotFoundError: No module named 'umwelt.registry'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/umwelt/registry/taxa.py`:

```python
"""Taxon registration for the umwelt plugin registry."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator

from umwelt.errors import RegistryError


@dataclass(frozen=True)
class TaxonSchema:
    """Metadata for a registered taxon."""

    name: str
    description: str
    ma_concept: str | None = None


@dataclass
class RegistryState:
    """The full contents of a registry scope.

    Other registry submodules (entities, properties, matchers, validators,
    compilers) attach their own dicts here as fields.
    """

    taxa: dict[str, TaxonSchema] = field(default_factory=dict)


_GLOBAL_STATE = RegistryState()
_ACTIVE_STATE: ContextVar[RegistryState] = ContextVar("umwelt_registry_state", default=_GLOBAL_STATE)


def _current_state() -> RegistryState:
    return _ACTIVE_STATE.get()


def register_taxon(
    *,
    name: str,
    description: str,
    ma_concept: str | None = None,
) -> None:
    """Register a taxon with the active registry scope."""
    state = _current_state()
    if name in state.taxa:
        raise RegistryError(f"taxon {name!r} already registered")
    state.taxa[name] = TaxonSchema(
        name=name,
        description=description,
        ma_concept=ma_concept,
    )


def get_taxon(name: str) -> TaxonSchema:
    """Look up a registered taxon by name."""
    state = _current_state()
    try:
        return state.taxa[name]
    except KeyError as exc:
        raise RegistryError(f"taxon {name!r} not registered") from exc


def list_taxa() -> list[TaxonSchema]:
    """Return all registered taxa in the active scope."""
    return list(_current_state().taxa.values())


@contextmanager
def registry_scope() -> Iterator[RegistryState]:
    """Enter a fresh registry scope. For tests and multi-tenant usage."""
    fresh = RegistryState()
    token = _ACTIVE_STATE.set(fresh)
    try:
        yield fresh
    finally:
        _ACTIVE_STATE.reset(token)
```

Create `src/umwelt/registry/__init__.py`:

```python
"""The umwelt plugin registry.

Consumers register taxa, entities, properties, matchers, validators, and
compilers at import time. Core umwelt reads the registry during parsing,
selector evaluation, and cascade resolution.
"""

from umwelt.registry.taxa import (
    RegistryState,
    TaxonSchema,
    get_taxon,
    list_taxa,
    register_taxon,
    registry_scope,
)

__all__ = [
    "RegistryState",
    "TaxonSchema",
    "get_taxon",
    "list_taxa",
    "register_taxon",
    "registry_scope",
]
```

- [ ] **Step 4: Run tests and checks**

Run: `pytest tests/core/test_registry_taxa.py -v`
Expected: all 7 tests pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/registry/ tests/core/test_registry_taxa.py
git commit -m "$(cat <<'EOF'
feat(registry): add taxon registration with scope override

TaxonSchema + register_taxon/get_taxon/list_taxa + a registry_scope
context manager that isolates registration for tests. The active
scope is held in a ContextVar so nested scopes work correctly.
Duplicate registration raises RegistryError; lookup of unknown
taxa raises RegistryError.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Registry — entities

**Files:**
- Create: `src/umwelt/registry/entities.py`
- Modify: `src/umwelt/registry/__init__.py`
- Modify: `src/umwelt/registry/taxa.py` (add `entities` field to `RegistryState`)
- Create: `tests/core/test_registry_entities.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_registry_entities.py`:

```python
"""Tests for entity registration."""

import pytest

from umwelt.errors import RegistryError
from umwelt.registry import (
    AttrSchema,
    EntitySchema,
    get_entity,
    list_entities,
    register_entity,
    register_taxon,
    registry_scope,
    resolve_entity_type,
)


def test_register_entity_minimal():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(
            taxon="world",
            name="file",
            attributes={"path": AttrSchema(type=str, required=True)},
            description="a file",
        )
        entity = get_entity("world", "file")
        assert entity.name == "file"
        assert entity.taxon == "world"
        assert entity.parent is None
        assert entity.attributes["path"].type is str
        assert entity.attributes["path"].required is True


def test_register_entity_with_parent():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(
            taxon="world",
            name="dir",
            attributes={"path": AttrSchema(type=str, required=True)},
            description="a dir",
        )
        register_entity(
            taxon="world",
            name="file",
            parent="dir",
            attributes={"path": AttrSchema(type=str, required=True)},
            description="a file",
        )
        assert get_entity("world", "file").parent == "dir"


def test_register_entity_with_category():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(
            taxon="world",
            name="file",
            attributes={},
            description="a file",
            category="filesystem",
        )
        assert get_entity("world", "file").category == "filesystem"


def test_duplicate_entity_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        with pytest.raises(RegistryError, match="already registered"):
            register_entity(taxon="world", name="file", attributes={}, description="b")


def test_register_entity_unknown_taxon_raises():
    with registry_scope():
        with pytest.raises(RegistryError, match="taxon 'ghost' not registered"):
            register_entity(taxon="ghost", name="file", attributes={}, description="a")


def test_get_entity_unknown_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        with pytest.raises(RegistryError, match="entity 'file' not registered"):
            get_entity("world", "file")


def test_resolve_entity_type_unique():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        taxa = resolve_entity_type("file")
        assert taxa == ["world"]


def test_resolve_entity_type_ambiguous():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_taxon(name="audit", description="a")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        register_entity(taxon="audit", name="file", attributes={}, description="b")
        taxa = resolve_entity_type("file")
        assert set(taxa) == {"world", "audit"}


def test_resolve_entity_type_unknown():
    with registry_scope():
        assert resolve_entity_type("ghost") == []


def test_list_entities_for_taxon():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        register_entity(taxon="world", name="dir", attributes={}, description="b")
        entities = list_entities("world")
        assert {e.name for e in entities} == {"file", "dir"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_registry_entities.py -v`
Expected: `ImportError` — the new symbols don't exist.

- [ ] **Step 3: Update `RegistryState` to hold entities**

Modify `src/umwelt/registry/taxa.py` — add an `entities` field to `RegistryState`:

```python
@dataclass
class RegistryState:
    """The full contents of a registry scope."""

    taxa: dict[str, TaxonSchema] = field(default_factory=dict)
    # Keyed by (taxon_name, entity_name)
    entities: dict[tuple[str, str], "EntitySchema"] = field(default_factory=dict)
```

Add a forward reference import comment at the top:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from umwelt.registry.entities import EntitySchema
```

- [ ] **Step 4: Write entity registration**

Create `src/umwelt/registry/entities.py`:

```python
"""Entity registration for the umwelt plugin registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from umwelt.errors import RegistryError
from umwelt.registry.taxa import _current_state, get_taxon


@dataclass(frozen=True)
class AttrSchema:
    """Schema for one entity attribute."""

    type: type
    required: bool = False
    unit: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class EntitySchema:
    """Metadata for a registered entity type."""

    name: str
    taxon: str
    parent: str | None
    attributes: dict[str, AttrSchema]
    description: str
    category: str | None = None


def register_entity(
    *,
    taxon: str,
    name: str,
    attributes: dict[str, AttrSchema],
    description: str,
    parent: str | None = None,
    category: str | None = None,
) -> None:
    """Register an entity type under a taxon."""
    # Verify the taxon exists first (raises RegistryError if not).
    get_taxon(taxon)
    state = _current_state()
    key = (taxon, name)
    if key in state.entities:
        raise RegistryError(
            f"entity {name!r} already registered in taxon {taxon!r}"
        )
    state.entities[key] = EntitySchema(
        name=name,
        taxon=taxon,
        parent=parent,
        attributes=dict(attributes),
        description=description,
        category=category,
    )


def get_entity(taxon: str, name: str) -> EntitySchema:
    """Look up a registered entity by (taxon, name)."""
    state = _current_state()
    try:
        return state.entities[(taxon, name)]
    except KeyError as exc:
        raise RegistryError(
            f"entity {name!r} not registered in taxon {taxon!r}"
        ) from exc


def list_entities(taxon: str) -> list[EntitySchema]:
    """Return all entities registered under a taxon."""
    state = _current_state()
    return [e for (t, _n), e in state.entities.items() if t == taxon]


def resolve_entity_type(name: str) -> list[str]:
    """Return the list of taxa that have an entity named `name`.

    - Empty list: the type is unknown.
    - Single entry: unambiguous, caller uses it directly.
    - Multiple entries: ambiguous, caller must disambiguate via
      explicit `taxon|type` prefix or `@taxon { ... }` scoping.
    """
    state = _current_state()
    return [t for (t, n) in state.entities if n == name]
```

- [ ] **Step 5: Re-export from `registry/__init__.py`**

Update `src/umwelt/registry/__init__.py`:

```python
"""The umwelt plugin registry."""

from umwelt.registry.entities import (
    AttrSchema,
    EntitySchema,
    get_entity,
    list_entities,
    register_entity,
    resolve_entity_type,
)
from umwelt.registry.taxa import (
    RegistryState,
    TaxonSchema,
    get_taxon,
    list_taxa,
    register_taxon,
    registry_scope,
)

__all__ = [
    "AttrSchema",
    "EntitySchema",
    "RegistryState",
    "TaxonSchema",
    "get_entity",
    "get_taxon",
    "list_entities",
    "list_taxa",
    "register_entity",
    "register_taxon",
    "registry_scope",
    "resolve_entity_type",
]
```

- [ ] **Step 6: Run tests and checks**

Run: `pytest tests/core/test_registry_taxa.py tests/core/test_registry_entities.py -v`
Expected: all tests pass (7 taxa tests + 10 entity tests).

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/umwelt/registry/ tests/core/test_registry_entities.py
git commit -m "$(cat <<'EOF'
feat(registry): add entity registration with parent relationships

EntitySchema + register_entity/get_entity/list_entities, plus
resolve_entity_type which returns the set of taxa that own a given
entity name. Single-taxon ownership is the default resolution; a
non-unique result is an ambiguity the parser must disambiguate.
Parent relationships are recorded for structural descendant-selector
evaluation.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Registry — properties

**Files:**
- Create: `src/umwelt/registry/properties.py`
- Modify: `src/umwelt/registry/taxa.py` (add `properties` field to `RegistryState`)
- Modify: `src/umwelt/registry/__init__.py`
- Create: `tests/core/test_registry_properties.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_registry_properties.py`:

```python
"""Tests for property registration."""

import pytest

from umwelt.errors import RegistryError
from umwelt.registry import (
    AttrSchema,
    PropertySchema,
    get_property,
    list_properties,
    register_entity,
    register_property,
    register_taxon,
    registry_scope,
)


def test_register_exact_property():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(
            taxon="world",
            name="file",
            attributes={"path": AttrSchema(type=str, required=True)},
            description="a file",
        )
        register_property(
            taxon="world",
            entity="file",
            name="editable",
            value_type=bool,
            description="whether the actor may modify this file",
        )
        prop = get_property("world", "file", "editable")
        assert prop.name == "editable"
        assert prop.value_type is bool
        assert prop.comparison == "exact"


def test_register_comparison_property():
    with registry_scope():
        register_taxon(name="capability", description="c")
        register_entity(taxon="capability", name="tool", attributes={}, description="t")
        register_property(
            taxon="capability",
            entity="tool",
            name="max-level",
            value_type=int,
            comparison="<=",
            value_attribute="level",
            value_range=(0, 8),
            description="maximum computation level",
            category="effects_ceiling",
        )
        prop = get_property("capability", "tool", "max-level")
        assert prop.comparison == "<="
        assert prop.value_attribute == "level"
        assert prop.value_range == (0, 8)
        assert prop.category == "effects_ceiling"


def test_register_pattern_property():
    with registry_scope():
        register_taxon(name="capability", description="c")
        register_entity(taxon="capability", name="tool", attributes={}, description="t")
        register_property(
            taxon="capability",
            entity="tool",
            name="allow-pattern",
            value_type=list,
            comparison="pattern-in",
            description="glob patterns that allow the invocation",
        )
        assert get_property("capability", "tool", "allow-pattern").comparison == "pattern-in"


def test_duplicate_property_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        register_property(
            taxon="world",
            entity="file",
            name="editable",
            value_type=bool,
            description="d1",
        )
        with pytest.raises(RegistryError, match="already registered"):
            register_property(
                taxon="world",
                entity="file",
                name="editable",
                value_type=bool,
                description="d2",
            )


def test_register_property_unknown_entity_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        with pytest.raises(RegistryError, match="entity 'file' not registered"):
            register_property(
                taxon="world",
                entity="file",
                name="editable",
                value_type=bool,
                description="d",
            )


def test_list_properties_for_entity():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file", attributes={}, description="a")
        register_property(
            taxon="world", entity="file", name="editable", value_type=bool, description="a"
        )
        register_property(
            taxon="world", entity="file", name="visible", value_type=bool, description="b"
        )
        names = {p.name for p in list_properties("world", "file")}
        assert names == {"editable", "visible"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_registry_properties.py -v`
Expected: `ImportError` on the first test.

- [ ] **Step 3: Update `RegistryState`**

Add to `src/umwelt/registry/taxa.py`:

```python
@dataclass
class RegistryState:
    """The full contents of a registry scope."""

    taxa: dict[str, TaxonSchema] = field(default_factory=dict)
    entities: dict[tuple[str, str], "EntitySchema"] = field(default_factory=dict)
    # Keyed by (taxon_name, entity_name, property_name)
    properties: dict[tuple[str, str, str], "PropertySchema"] = field(default_factory=dict)
```

And extend the `TYPE_CHECKING` block:

```python
if TYPE_CHECKING:
    from umwelt.registry.entities import EntitySchema
    from umwelt.registry.properties import PropertySchema
```

- [ ] **Step 4: Write property registration**

Create `src/umwelt/registry/properties.py`:

```python
"""Property registration for the umwelt plugin registry.

Properties are the declaration vocabulary for an entity type. A property
can be a simple assignment (`editable: true`) or carry comparison
semantics encoded in the property name prefix (`max-level: 2` means
"cap the tool's computation level at <= 2").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from umwelt.errors import RegistryError
from umwelt.registry.entities import get_entity
from umwelt.registry.taxa import _current_state

Comparison = Literal["exact", "<=", ">=", "in", "overlap", "pattern-in"]


@dataclass(frozen=True)
class PropertySchema:
    """Metadata for a registered declaration property."""

    name: str
    taxon: str
    entity: str
    value_type: type
    comparison: Comparison = "exact"
    value_attribute: str | None = None
    value_unit: str | None = None
    value_range: tuple[Any, Any] | None = None
    description: str = ""
    category: str | None = None


def register_property(
    *,
    taxon: str,
    entity: str,
    name: str,
    value_type: type,
    description: str,
    comparison: Comparison = "exact",
    value_attribute: str | None = None,
    value_unit: str | None = None,
    value_range: tuple[Any, Any] | None = None,
    category: str | None = None,
) -> None:
    """Register a property on a (taxon, entity) pair."""
    get_entity(taxon, entity)  # raises if unknown
    state = _current_state()
    key = (taxon, entity, name)
    if key in state.properties:
        raise RegistryError(
            f"property {name!r} already registered on {taxon}.{entity}"
        )
    state.properties[key] = PropertySchema(
        name=name,
        taxon=taxon,
        entity=entity,
        value_type=value_type,
        comparison=comparison,
        value_attribute=value_attribute,
        value_unit=value_unit,
        value_range=value_range,
        description=description,
        category=category,
    )


def get_property(taxon: str, entity: str, name: str) -> PropertySchema:
    """Look up a property by (taxon, entity, name)."""
    state = _current_state()
    try:
        return state.properties[(taxon, entity, name)]
    except KeyError as exc:
        raise RegistryError(
            f"property {name!r} not registered on {taxon}.{entity}"
        ) from exc


def list_properties(taxon: str, entity: str) -> list[PropertySchema]:
    """Return all properties registered on an entity."""
    state = _current_state()
    return [
        p
        for (t, e, _n), p in state.properties.items()
        if t == taxon and e == entity
    ]
```

- [ ] **Step 5: Re-export from `registry/__init__.py`**

Add `PropertySchema`, `get_property`, `list_properties`, `register_property` to the `__init__.py` imports and `__all__`.

- [ ] **Step 6: Run tests and checks**

Run: `pytest tests/core/test_registry_properties.py -v`
Expected: all 6 tests pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/umwelt/registry/ tests/core/test_registry_properties.py
git commit -m "$(cat <<'EOF'
feat(registry): add property registration with comparison semantics

PropertySchema + register_property/get_property/list_properties.
Properties carry a Comparison tag (exact/<=/>=/in/overlap/pattern-in)
that encodes how declarations are interpreted at cascade and compile
time. v0.1 stores the metadata; runtime evaluation of comparison
semantics is a consumer/compiler concern.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Registry — matchers + toy taxonomy test helper

**Files:**
- Create: `src/umwelt/registry/matchers.py`
- Modify: `src/umwelt/registry/taxa.py` (add `matchers` field to `RegistryState`)
- Modify: `src/umwelt/registry/__init__.py`
- Create: `tests/core/helpers/__init__.py`
- Create: `tests/core/helpers/toy_taxonomy.py`
- Create: `tests/core/test_registry_matchers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_registry_matchers.py`:

```python
"""Tests for matcher registration."""

from typing import Any

import pytest

from umwelt.errors import RegistryError
from umwelt.registry import (
    MatcherProtocol,
    get_matcher,
    register_matcher,
    register_taxon,
    registry_scope,
)


class NullMatcher:
    """A matcher that never matches anything. For testing registration only."""

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        return []

    def children(self, parent: Any, child_type: str) -> list[Any]:
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        return False


def test_register_and_lookup_matcher():
    with registry_scope():
        register_taxon(name="world", description="w")
        m = NullMatcher()
        register_matcher(taxon="world", matcher=m)
        assert get_matcher("world") is m


def test_matcher_for_unknown_taxon_raises():
    with registry_scope():
        with pytest.raises(RegistryError, match="taxon 'ghost' not registered"):
            register_matcher(taxon="ghost", matcher=NullMatcher())


def test_duplicate_matcher_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_matcher(taxon="world", matcher=NullMatcher())
        with pytest.raises(RegistryError, match="already registered"):
            register_matcher(taxon="world", matcher=NullMatcher())


def test_get_unknown_matcher_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        with pytest.raises(RegistryError, match="no matcher registered"):
            get_matcher("world")


def test_matcher_protocol_is_runtime_checkable():
    # A structural check: NullMatcher satisfies MatcherProtocol
    assert isinstance(NullMatcher(), MatcherProtocol)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_registry_matchers.py -v`
Expected: `ImportError` — `MatcherProtocol`, `register_matcher`, `get_matcher` missing.

- [ ] **Step 3: Update `RegistryState`**

Add to `src/umwelt/registry/taxa.py`:

```python
@dataclass
class RegistryState:
    """The full contents of a registry scope."""

    taxa: dict[str, TaxonSchema] = field(default_factory=dict)
    entities: dict[tuple[str, str], "EntitySchema"] = field(default_factory=dict)
    properties: dict[tuple[str, str, str], "PropertySchema"] = field(default_factory=dict)
    matchers: dict[str, "MatcherProtocol"] = field(default_factory=dict)
```

Extend the `TYPE_CHECKING` block:

```python
if TYPE_CHECKING:
    from umwelt.registry.entities import EntitySchema
    from umwelt.registry.matchers import MatcherProtocol
    from umwelt.registry.properties import PropertySchema
```

- [ ] **Step 4: Write matcher registration + protocol**

Create `src/umwelt/registry/matchers.py`:

```python
"""Matcher protocol and registration.

A matcher is the consumer-supplied bridge between a `ComplexSelector`
and the consumer's world. The parser, selector engine, and cascade
resolver are matcher-agnostic — they know how to call these methods
but not what the implementation does. A filesystem matcher walks
real paths; an in-memory test matcher walks a dict.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from umwelt.errors import RegistryError
from umwelt.registry.taxa import _current_state, get_taxon


@runtime_checkable
class MatcherProtocol(Protocol):
    """Consumer-supplied access to a world for selector evaluation.

    The protocol is deliberately thin. Each method takes selector-space
    inputs and returns opaque entity handles that only the matcher knows
    how to interpret — the core selector engine treats them as tokens.
    """

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        """Return all entities of this type in the matcher's world.

        For structural lookups where no parent entity is pre-selected,
        this returns every entity of the type.
        """
        ...

    def children(self, parent: Any, child_type: str) -> list[Any]:
        """Return `child_type` entities that are descendants of `parent`.

        Used for within-taxon structural descendant selectors (e.g.,
        `dir[name="src"] file[name$=".py"]` — the matcher walks the
        dir -> file parent-child relationship).
        """
        ...

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        """Return True if a cross-taxon context qualifier is satisfied.

        Called by the selector engine when a compound selector crosses
        taxa (`tool[name="Bash"] file[...]`). The qualifier taxon's
        matcher is consulted with the qualifier selector to determine
        whether the rule's context condition holds.
        """
        ...


def register_matcher(*, taxon: str, matcher: MatcherProtocol) -> None:
    """Register a matcher for a taxon."""
    get_taxon(taxon)  # raises if unknown
    state = _current_state()
    if taxon in state.matchers:
        raise RegistryError(f"matcher for taxon {taxon!r} already registered")
    state.matchers[taxon] = matcher


def get_matcher(taxon: str) -> MatcherProtocol:
    """Look up the matcher for a taxon."""
    state = _current_state()
    try:
        return state.matchers[taxon]
    except KeyError as exc:
        raise RegistryError(f"no matcher registered for taxon {taxon!r}") from exc
```

- [ ] **Step 5: Re-export from `registry/__init__.py`**

Add `MatcherProtocol`, `get_matcher`, `register_matcher` to imports and `__all__`.

- [ ] **Step 6: Write the toy-taxonomy test helper**

Create `tests/core/helpers/__init__.py` (empty).

Create `tests/core/helpers/toy_taxonomy.py`:

```python
"""A toy taxonomy for v0.1-core tests.

Provides an in-memory world that covers the surface area the parser,
selector engine, and cascade resolver need to exercise: multi-taxon
registration, parent-child relationships, exact and prefix matching,
cross-taxon context qualifiers. No filesystem, no subprocess.

Usage:

    with registry_scope():
        install_toy_taxonomy()
        ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from umwelt.registry import (
    AttrSchema,
    MatcherProtocol,
    register_entity,
    register_matcher,
    register_property,
    register_taxon,
)


@dataclass(frozen=True)
class ToyThing:
    """An entity in the `shapes` toy taxon."""

    type_name: str  # "thing" or "widget"
    id: str
    color: str
    parent_id: str | None = None


@dataclass(frozen=True)
class ToyActor:
    """An entity in the `actors` toy taxon (for cross-taxon tests)."""

    type_name: str  # "actor"
    id: str
    role: str


@dataclass
class ToyShapesMatcher:
    """In-memory matcher for the toy `shapes` taxon."""

    things: list[ToyThing] = field(default_factory=list)

    def match_type(self, type_name: str, context: Any = None) -> list[ToyThing]:
        return [t for t in self.things if t.type_name == type_name]

    def children(self, parent: ToyThing, child_type: str) -> list[ToyThing]:
        return [
            t for t in self.things if t.type_name == child_type and t.parent_id == parent.id
        ]

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        # Shapes aren't used as context qualifiers in v0.1-core tests.
        return False


@dataclass
class ToyActorsMatcher:
    """In-memory matcher for the toy `actors` taxon.

    Supports context-qualifier evaluation: a compound selector like
    `actor[role="admin"] thing[...]` asks this matcher whether any
    actor with role=admin is in the current context. Context is a
    frozenset of actor ids that are "active" for a given evaluation.
    """

    actors: list[ToyActor] = field(default_factory=list)
    active_ids: frozenset[str] = field(default_factory=frozenset)

    def match_type(self, type_name: str, context: Any = None) -> list[ToyActor]:
        return [a for a in self.actors if a.type_name == type_name]

    def children(self, parent: Any, child_type: str) -> list[Any]:
        return []  # actors have no children in the toy world

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        # For the v0.1-core tests, the selector is a SimpleSelector with
        # type_name="actor" and an attribute filter on "role". We walk
        # our active_ids set and check whether any matching actor is in
        # it. The selector engine passes the simple selector it's trying
        # to qualify with.
        from umwelt.ast import SimpleSelector

        if not isinstance(selector, SimpleSelector):
            return False
        if selector.type_name != "actor":
            return False
        wanted_roles: set[str] = set()
        for attr in selector.attributes:
            if attr.name == "role" and attr.op == "=" and attr.value is not None:
                wanted_roles.add(attr.value)
        for actor in self.actors:
            if actor.id in self.active_ids and (
                not wanted_roles or actor.role in wanted_roles
            ):
                return True
        return False


def install_toy_taxonomy(
    shapes_matcher: ToyShapesMatcher | None = None,
    actors_matcher: ToyActorsMatcher | None = None,
) -> tuple[ToyShapesMatcher, ToyActorsMatcher]:
    """Register the toy `shapes` and `actors` taxa in the active registry scope.

    Returns the installed matchers so tests can mutate their state.
    """
    # --- shapes taxon ---
    register_taxon(name="shapes", description="toy shapes taxon for core tests")
    register_entity(
        taxon="shapes",
        name="thing",
        attributes={
            "id": AttrSchema(type=str, required=True),
            "color": AttrSchema(type=str),
        },
        description="a toy thing",
    )
    register_entity(
        taxon="shapes",
        name="widget",
        parent="thing",
        attributes={
            "id": AttrSchema(type=str, required=True),
            "color": AttrSchema(type=str),
        },
        description="a toy widget; descendant of a thing",
    )
    register_property(
        taxon="shapes",
        entity="thing",
        name="paint",
        value_type=str,
        description="override the thing's paint color",
    )
    register_property(
        taxon="shapes",
        entity="thing",
        name="max-glow",
        value_type=int,
        comparison="<=",
        value_attribute="glow_level",
        description="cap on glow intensity",
    )
    register_property(
        taxon="shapes",
        entity="widget",
        name="paint",
        value_type=str,
        description="override the widget's paint color",
    )

    # --- actors taxon (for cross-taxon tests) ---
    register_taxon(name="actors", description="toy actors taxon for cross-taxon tests")
    register_entity(
        taxon="actors",
        name="actor",
        attributes={
            "id": AttrSchema(type=str, required=True),
            "role": AttrSchema(type=str),
        },
        description="a toy actor",
    )
    register_property(
        taxon="actors",
        entity="actor",
        name="allowed",
        value_type=bool,
        description="whether the actor is allowed to act",
    )

    shapes = shapes_matcher or ToyShapesMatcher()
    actors = actors_matcher or ToyActorsMatcher()
    register_matcher(taxon="shapes", matcher=shapes)
    register_matcher(taxon="actors", matcher=actors)
    return shapes, actors
```

- [ ] **Step 7: Run tests and checks**

Run: `pytest tests/core/test_registry_matchers.py -v`
Expected: all 5 tests pass.

Run: `pytest tests/core/ -v`
Expected: all prior tests still pass (errors, ast, public_api, registry_*).

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/umwelt/registry/ tests/core/test_registry_matchers.py tests/core/helpers/
git commit -m "$(cat <<'EOF'
feat(registry): add matcher protocol and toy-taxonomy test helper

MatcherProtocol is a runtime-checkable Protocol with three methods:
match_type (entities of a type), children (parent-child navigation for
structural descendants), and condition_met (cross-taxon context
qualifier evaluation). Consumers implement the protocol against their
own worlds (filesystem, tool registry, in-memory dict for tests).

The toy_taxonomy helper installs two small taxa (shapes and actors)
with entities, properties, parent relationships, and in-memory
matchers that the parser, selector engine, and cascade-resolver tests
will use to exercise the full infrastructure without a filesystem.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Parser — top-level rule blocks via tinycss2

**Files:**
- Create: `src/umwelt/parser.py`
- Create: `tests/core/test_parser_basic.py`

**Context for this task:** `tinycss2` is a CSS-3 tokenizer plus a thin structural parser. Key functions we use:
- `tinycss2.parse_stylesheet(source, skip_comments=True, skip_whitespace=True)` — returns a list of `QualifiedRule`, `AtRule`, or `ParseError` nodes.
- `QualifiedRule.prelude` and `.content` — token lists for the selector and the declarations.
- `tinycss2.parse_declaration_list(content, skip_comments=True, skip_whitespace=True)` — turns a content token list into `Declaration` / `AtRule` / `ParseError` nodes.
- Token types we care about: `IdentToken`, `LiteralToken`, `WhitespaceToken`, `StringToken`, `HashToken`, `NumberToken`, `SquareBracketsBlock`, `ParenthesesBlock`, `CurlyBracketsBlock`.

We build a thin wrapper that calls tinycss2, walks its output, and produces the umwelt AST. The actual selector-string parsing lives in `selector/parse.py` (Task 9+).

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_parser_basic.py`:

```python
"""Tests for the top-level parser structure."""

from __future__ import annotations

import pytest

from umwelt.errors import ViewParseError
from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import install_toy_taxonomy


def test_parse_empty_string():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("")
    assert view.rules == ()
    assert view.unknown_at_rules == ()
    assert view.warnings == ()


def test_parse_whitespace_only():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("   \n   \n")
    assert view.rules == ()


def test_parse_single_rule_block():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { }")
    assert len(view.rules) == 1
    rule = view.rules[0]
    assert len(rule.selectors) == 1
    assert rule.declarations == ()


def test_parse_source_text_preserved():
    source = "thing { }"
    with registry_scope():
        install_toy_taxonomy()
        view = parse(source)
    assert view.source_text == source


def test_parse_from_path(tmp_path):
    path = tmp_path / "a.umw"
    path.write_text("thing { }\n")
    with registry_scope():
        install_toy_taxonomy()
        view = parse(path)
    assert view.source_path == path
    assert view.source_text == "thing { }\n"


def test_parse_unknown_at_rule_preserved():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("@retrieval { context: last-3; }")
    assert len(view.unknown_at_rules) == 1
    at = view.unknown_at_rules[0]
    assert at.name == "retrieval"


def test_parse_syntax_error_raises():
    with registry_scope():
        install_toy_taxonomy()
        with pytest.raises(ViewParseError):
            # Missing closing brace — tinycss2 reports this as a parse error.
            parse("thing { color: red")


def test_parse_accepts_string_or_path(tmp_path):
    path = tmp_path / "b.umw"
    path.write_text("thing { }")
    with registry_scope():
        install_toy_taxonomy()
        view_from_str = parse("thing { }")
        view_from_path = parse(path)
    assert view_from_str.source_path is None
    assert view_from_path.source_path == path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_parser_basic.py -v`
Expected: `ModuleNotFoundError: No module named 'umwelt.parser'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/umwelt/parser.py`:

```python
"""Top-level view parser.

Uses `tinycss2` for CSS tokenization; walks its output into the umwelt AST.
Selector-string parsing lives in `umwelt.selector.parse`; this module is the
orchestrator that recognizes rule blocks vs. at-rules, extracts source
positions, and produces the final `View`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tinycss2

from umwelt.ast import (
    ParseWarning,
    RuleBlock,
    SourceSpan,
    UnknownAtRule,
    View,
)
from umwelt.errors import ViewParseError

# tinycss2's ParseError node doesn't expose a typed class we can isinstance-check
# cleanly across versions, so we sniff by attribute instead.


def parse(source: str | Path, *, validate: bool = True) -> View:
    """Parse a view from text or a file path into a `View` AST.

    Args:
        source: Either a string containing view text, or a `Path` to a view file.
        validate: Whether to run the registered validators after parsing. v0.1
            defers validator implementation to Task 18; the flag is plumbed now.

    Returns:
        A `View` with rules, preserved unknown at-rules, and warnings.

    Raises:
        ViewParseError: On any syntactic error, with line and column.
    """
    if isinstance(source, Path):
        text = source.read_text()
        source_path: Path | None = source
    else:
        text = source
        source_path = None

    nodes = tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True)

    rules: list[RuleBlock] = []
    unknown_at_rules: list[UnknownAtRule] = []
    warnings: list[ParseWarning] = []

    for node in nodes:
        if _is_parse_error(node):
            raise _parse_error_to_view_error(node, source_path)
        node_type = getattr(node, "type", None)
        if node_type == "qualified-rule":
            rule = _build_rule_block(node, warnings)
            if rule is not None:
                rules.append(rule)
        elif node_type == "at-rule":
            unknown_at_rules.append(_build_unknown_at_rule(node))
        # tinycss2 with skip_whitespace=True shouldn't yield bare whitespace here.

    return View(
        rules=tuple(rules),
        unknown_at_rules=tuple(unknown_at_rules),
        warnings=tuple(warnings),
        source_text=text,
        source_path=source_path,
    )


def _is_parse_error(node: Any) -> bool:
    return getattr(node, "type", None) == "error"


def _parse_error_to_view_error(
    node: Any, source_path: Path | None
) -> ViewParseError:
    message = getattr(node, "message", "parse error")
    line = int(getattr(node, "source_line", 1) or 1)
    col = int(getattr(node, "source_column", 1) or 1)
    return ViewParseError(
        message, line=line, col=col, source_path=source_path
    )


def _span(node: Any) -> SourceSpan:
    line = int(getattr(node, "source_line", 1) or 1)
    col = int(getattr(node, "source_column", 1) or 1)
    return SourceSpan(line=line, col=col)


def _build_rule_block(
    node: Any, warnings: list[ParseWarning]
) -> RuleBlock | None:
    """Turn a tinycss2 qualified-rule into a `RuleBlock`.

    Task 8 only produces an empty-selector, empty-declaration block. Later
    tasks (9-11) populate the selectors and declarations.
    """
    return RuleBlock(
        selectors=(),
        declarations=(),
        nested_blocks=(),
        span=_span(node),
    )


def _build_unknown_at_rule(node: Any) -> UnknownAtRule:
    name = getattr(node, "lower_at_keyword", None) or getattr(node, "at_keyword", "")
    prelude = tinycss2.serialize(getattr(node, "prelude", []) or [])
    block = ""
    content = getattr(node, "content", None)
    if content is not None:
        block = tinycss2.serialize(content)
    return UnknownAtRule(
        name=name,
        prelude_text=prelude,
        block_text=block,
        span=_span(node),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_parser_basic.py -v`
Expected: all 8 tests pass. The "single rule block" test passes because the rule is built with empty selectors for now — the test only asserts `len(view.rules) == 1` and `rule.declarations == ()`.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/parser.py tests/core/test_parser_basic.py
git commit -m "$(cat <<'EOF'
feat(parser): wire tinycss2-backed top-level parse()

parse() accepts str or Path, runs tinycss2.parse_stylesheet, and
walks the token stream into a View with (empty) RuleBlocks for
qualified rules, UnknownAtRule entries for any at-rule, and
ViewParseError with source line/col on tinycss2 parse errors.

This task intentionally produces empty selectors and empty
declarations — Tasks 9-11 populate them. The purpose here is to
land the wiring: source-text preservation, path handling, at-rule
preservation, error translation.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Selector parser — type, id, class, attributes

**Files:**
- Create: `src/umwelt/selector/__init__.py`
- Create: `src/umwelt/selector/parse.py`
- Modify: `src/umwelt/parser.py` (use `selector.parse.parse_selector_list` in `_build_rule_block`)
- Create: `tests/core/test_parser_selectors.py`

**Context:** Selectors in a qualified rule's prelude arrive as a tinycss2 token list. We walk that token list and produce a list of `ComplexSelector` (comma-separated union). Each `ComplexSelector` contains one or more `CompoundPart`s; Task 9 handles single-part (no combinators yet), Task 12 adds combinators.

For Task 9, each simple selector can have: a type name (`IdentToken` at the start), `#id` (`HashToken`), `.class` (`LiteralToken` "." + `IdentToken`), `[attr op value]` (`SquareBracketsBlock`). The `taxon` field on `SimpleSelector` stays `""` until Task 15 — the tests here register a single taxon in the toy taxonomy, but Task 9 doesn't yet resolve type names to taxa. Use `"__unresolved__"` as the placeholder so the test data model is consistent.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_parser_selectors.py`:

```python
"""Tests for selector parsing inside rule blocks."""

from __future__ import annotations

import pytest

from umwelt.ast import AttrFilter
from umwelt.errors import ViewParseError
from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import install_toy_taxonomy


def _sole_simple(view) -> tuple:
    """Return the sole simple selector in the sole rule of a single-rule view."""
    assert len(view.rules) == 1
    rule = view.rules[0]
    assert len(rule.selectors) == 1
    complex_sel = rule.selectors[0]
    assert len(complex_sel.parts) == 1
    return complex_sel.parts[0].selector


def test_bare_type_selector():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { }")
    sel = _sole_simple(view)
    assert sel.type_name == "thing"
    assert sel.id_value is None
    assert sel.classes == ()
    assert sel.attributes == ()


def test_universal_selector():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("* { }")
    sel = _sole_simple(view)
    assert sel.type_name == "*"


def test_id_selector():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing#alpha { }")
    sel = _sole_simple(view)
    assert sel.type_name == "thing"
    assert sel.id_value == "alpha"


def test_id_selector_allows_dotted_value():
    # e.g. filename-as-id: file#README.md
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing#README.md { }")
    sel = _sole_simple(view)
    assert sel.id_value == "README.md"


def test_class_selector():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing.highlighted { }")
    sel = _sole_simple(view)
    assert sel.classes == ("highlighted",)


def test_multiple_classes():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing.a.b.c { }")
    sel = _sole_simple(view)
    assert sel.classes == ("a", "b", "c")


def test_attribute_exists():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing[color] { }")
    sel = _sole_simple(view)
    assert sel.attributes == (AttrFilter(name="color", op=None, value=None),)


def test_attribute_equals():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color="red"] { }')
    sel = _sole_simple(view)
    assert sel.attributes == (AttrFilter(name="color", op="=", value="red"),)


def test_attribute_prefix():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color^="re"] { }')
    sel = _sole_simple(view)
    assert sel.attributes == (AttrFilter(name="color", op="^=", value="re"),)


def test_attribute_suffix():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color$="ed"] { }')
    sel = _sole_simple(view)
    assert sel.attributes == (AttrFilter(name="color", op="$=", value="ed"),)


def test_attribute_substring():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color*="e"] { }')
    sel = _sole_simple(view)
    assert sel.attributes == (AttrFilter(name="color", op="*=", value="e"),)


def test_multiple_attributes():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color="red"][id^="alpha"] { }')
    sel = _sole_simple(view)
    assert len(sel.attributes) == 2
    assert sel.attributes[0] == AttrFilter(name="color", op="=", value="red")
    assert sel.attributes[1] == AttrFilter(name="id", op="^=", value="alpha")


def test_comma_separated_selector_list():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing, widget { }")
    assert len(view.rules) == 1
    rule = view.rules[0]
    assert len(rule.selectors) == 2
    assert rule.selectors[0].parts[0].selector.type_name == "thing"
    assert rule.selectors[1].parts[0].selector.type_name == "widget"


def test_malformed_selector_raises():
    with registry_scope():
        install_toy_taxonomy()
        with pytest.raises(ViewParseError):
            # Unterminated attribute bracket
            parse("thing[color { }")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_parser_selectors.py -v`
Expected: all tests fail — the parser still produces empty selectors.

- [ ] **Step 3: Write `selector/parse.py`**

Create `src/umwelt/selector/__init__.py`:

```python
"""Selector parsing, specificity, and evaluation."""

from umwelt.selector.parse import parse_selector_list

__all__ = ["parse_selector_list"]
```

Create `src/umwelt/selector/parse.py`:

```python
"""Parse a tinycss2 prelude token list into a tuple of `ComplexSelector`.

Task 9 handles single-part compound selectors: type, id, class, attribute,
pseudo-class. Task 12 adds combinators (descendant, child, sibling).
"""

from __future__ import annotations

from typing import Any

from umwelt.ast import (
    AttrFilter,
    AttrOp,
    CompoundPart,
    ComplexSelector,
    PseudoClass,
    SimpleSelector,
    SourceSpan,
)
from umwelt.errors import ViewParseError

# Placeholder taxon — Task 15 resolves type names against the registry.
UNRESOLVED_TAXON = "__unresolved__"


def parse_selector_list(
    tokens: list[Any], source_path=None
) -> tuple[ComplexSelector, ...]:
    """Parse a tinycss2 token list into a tuple of ComplexSelector.

    The token list is the `prelude` of a qualified rule. Commas separate
    selectors in a union; each resulting ComplexSelector is a union member.
    """
    groups = _split_on_commas(tokens)
    selectors: list[ComplexSelector] = []
    for group in groups:
        sel = _parse_complex(group, source_path)
        if sel is not None:
            selectors.append(sel)
    if not selectors:
        # An empty selector list is a syntactic error; require at least one.
        raise ViewParseError(
            "empty selector", line=1, col=1, source_path=source_path
        )
    return tuple(selectors)


def _split_on_commas(tokens: list[Any]) -> list[list[Any]]:
    groups: list[list[Any]] = [[]]
    for t in tokens:
        if _is_literal(t, ","):
            groups.append([])
        else:
            groups[-1].append(t)
    return [g for g in groups if _non_whitespace(g)]


def _non_whitespace(tokens: list[Any]) -> bool:
    return any(getattr(t, "type", None) != "whitespace" for t in tokens)


def _parse_complex(tokens: list[Any], source_path) -> ComplexSelector | None:
    """Task 9 form: one compound part with no combinators."""
    compound = _parse_simple(tokens, source_path)
    if compound is None:
        return None
    part = CompoundPart(selector=compound, combinator="root", mode="root")
    return ComplexSelector(
        parts=(part,),
        target_taxon=compound.taxon,
        specificity=(0, 0, 0),  # Task 15 computes this properly.
    )


def _parse_simple(tokens: list[Any], source_path) -> SimpleSelector | None:
    """Walk a token list for one simple selector.

    Recognizes (in order): type name, id (#...), classes (.a), attributes
    ([...]), pseudo-classes (:...). Stops at whitespace (Task 9 has no
    combinators).
    """
    # Strip leading/trailing whitespace at the compound boundary.
    tokens = _strip_whitespace(tokens)
    if not tokens:
        return None

    type_name: str | None = None
    id_value: str | None = None
    classes: list[str] = []
    attributes: list[AttrFilter] = []
    pseudo_classes: list[PseudoClass] = []

    span = _first_span(tokens)
    i = 0
    while i < len(tokens):
        t = tokens[i]
        ttype = getattr(t, "type", None)

        if ttype == "whitespace":
            # In Task 9, interior whitespace terminates the compound. We'll
            # handle combinators in Task 12; for now, require no interior
            # whitespace.
            raise ViewParseError(
                "unexpected whitespace inside simple selector",
                line=int(getattr(t, "source_line", 1) or 1),
                col=int(getattr(t, "source_column", 1) or 1),
                source_path=source_path,
            )

        if ttype == "ident" and type_name is None and not classes and not attributes and not pseudo_classes and id_value is None:
            type_name = t.value
            i += 1
            continue

        if _is_literal(t, "*") and type_name is None:
            type_name = "*"
            i += 1
            continue

        if ttype == "hash":
            if id_value is not None:
                raise ViewParseError(
                    "selector already has an id",
                    line=int(getattr(t, "source_line", 1) or 1),
                    col=int(getattr(t, "source_column", 1) or 1),
                    source_path=source_path,
                )
            id_value = t.value
            i += 1
            continue

        if _is_literal(t, "."):
            # .class — the next token should be an ident
            if i + 1 >= len(tokens):
                raise ViewParseError(
                    "expected class name after '.'",
                    line=int(getattr(t, "source_line", 1) or 1),
                    col=int(getattr(t, "source_column", 1) or 1),
                    source_path=source_path,
                )
            nxt = tokens[i + 1]
            if getattr(nxt, "type", None) != "ident":
                raise ViewParseError(
                    "expected class name after '.'",
                    line=int(getattr(nxt, "source_line", 1) or 1),
                    col=int(getattr(nxt, "source_column", 1) or 1),
                    source_path=source_path,
                )
            classes.append(nxt.value)
            i += 2
            continue

        if ttype == "[] block":
            attributes.append(_parse_attribute_block(t, source_path))
            i += 1
            continue

        if _is_literal(t, ":"):
            # Pseudo-class; Task 12 expands the grammar. For Task 9, require
            # an ident after the colon and record the name (no arguments yet).
            if i + 1 >= len(tokens):
                raise ViewParseError(
                    "expected pseudo-class name after ':'",
                    line=int(getattr(t, "source_line", 1) or 1),
                    col=int(getattr(t, "source_column", 1) or 1),
                    source_path=source_path,
                )
            nxt = tokens[i + 1]
            if getattr(nxt, "type", None) == "function":
                pseudo_classes.append(
                    PseudoClass(name=nxt.lower_name, argument=_serialize_function_args(nxt))
                )
                i += 2
                continue
            if getattr(nxt, "type", None) == "ident":
                pseudo_classes.append(PseudoClass(name=nxt.value, argument=None))
                i += 2
                continue
            raise ViewParseError(
                "expected pseudo-class name",
                line=int(getattr(nxt, "source_line", 1) or 1),
                col=int(getattr(nxt, "source_column", 1) or 1),
                source_path=source_path,
            )

        raise ViewParseError(
            f"unexpected token in selector: {ttype!r}",
            line=int(getattr(t, "source_line", 1) or 1),
            col=int(getattr(t, "source_column", 1) or 1),
            source_path=source_path,
        )

    if type_name is None and id_value is None and not classes and not attributes and not pseudo_classes:
        return None

    return SimpleSelector(
        type_name=type_name,
        taxon=UNRESOLVED_TAXON,
        id_value=id_value,
        classes=tuple(classes),
        attributes=tuple(attributes),
        pseudo_classes=tuple(pseudo_classes),
        span=span,
    )


def _parse_attribute_block(block: Any, source_path) -> AttrFilter:
    """Parse the contents of a tinycss2 `[...]` block."""
    inner = _strip_whitespace(list(getattr(block, "content", []) or []))
    if not inner:
        raise ViewParseError(
            "empty attribute selector",
            line=int(getattr(block, "source_line", 1) or 1),
            col=int(getattr(block, "source_column", 1) or 1),
            source_path=source_path,
        )

    name_tok = inner[0]
    if getattr(name_tok, "type", None) != "ident":
        raise ViewParseError(
            "attribute name must be an identifier",
            line=int(getattr(name_tok, "source_line", 1) or 1),
            col=int(getattr(name_tok, "source_column", 1) or 1),
            source_path=source_path,
        )
    name: str = name_tok.value

    # Just the name? Existence check.
    if len(inner) == 1:
        return AttrFilter(name=name, op=None, value=None)

    # Otherwise we expect an operator followed by a value.
    op_tokens = inner[1:]
    # tinycss2 emits compound operators like "^=" as a single "delim-like"
    # structure: a LiteralToken("^") followed by a LiteralToken("="). We
    # parse two-character ops manually.
    op, consumed = _parse_attr_op(op_tokens, source_path)
    value_tokens = op_tokens[consumed:]
    value = _parse_attr_value(value_tokens, source_path)
    return AttrFilter(name=name, op=op, value=value)


def _parse_attr_op(
    tokens: list[Any], source_path
) -> tuple[AttrOp, int]:
    if not tokens:
        raise ViewParseError(
            "expected attribute operator",
            line=1,
            col=1,
            source_path=source_path,
        )
    first = tokens[0]
    # Single-character '='
    if _is_literal(first, "="):
        return ("=", 1)
    # Two-character operators: ^=, $=, *=, |=, ~=
    if len(tokens) >= 2 and _is_literal(tokens[1], "="):
        if _is_literal(first, "^"):
            return ("^=", 2)
        if _is_literal(first, "$"):
            return ("$=", 2)
        if _is_literal(first, "*"):
            return ("*=", 2)
        if _is_literal(first, "|"):
            return ("|=", 2)
        if _is_literal(first, "~"):
            return ("~=", 2)
    raise ViewParseError(
        "unknown attribute operator",
        line=int(getattr(first, "source_line", 1) or 1),
        col=int(getattr(first, "source_column", 1) or 1),
        source_path=source_path,
    )


def _parse_attr_value(tokens: list[Any], source_path) -> str:
    tokens = _strip_whitespace(tokens)
    if not tokens:
        raise ViewParseError(
            "expected attribute value",
            line=1,
            col=1,
            source_path=source_path,
        )
    t = tokens[0]
    ttype = getattr(t, "type", None)
    if ttype == "string":
        return t.value
    if ttype == "ident":
        return t.value
    raise ViewParseError(
        f"attribute value must be a string or identifier, got {ttype!r}",
        line=int(getattr(t, "source_line", 1) or 1),
        col=int(getattr(t, "source_column", 1) or 1),
        source_path=source_path,
    )


def _serialize_function_args(func: Any) -> str:
    """Serialize the arguments of a tinycss2 function token back to text."""
    import tinycss2

    return tinycss2.serialize(getattr(func, "arguments", []) or []).strip()


def _strip_whitespace(tokens: list[Any]) -> list[Any]:
    out = list(tokens)
    while out and getattr(out[0], "type", None) == "whitespace":
        out.pop(0)
    while out and getattr(out[-1], "type", None) == "whitespace":
        out.pop()
    return out


def _is_literal(token: Any, value: str) -> bool:
    return getattr(token, "type", None) == "literal" and getattr(token, "value", None) == value


def _first_span(tokens: list[Any]) -> SourceSpan:
    for t in tokens:
        if getattr(t, "type", None) != "whitespace":
            return SourceSpan(
                line=int(getattr(t, "source_line", 1) or 1),
                col=int(getattr(t, "source_column", 1) or 1),
            )
    return SourceSpan(line=1, col=1)
```

- [ ] **Step 4: Wire it into `parser.py`**

In `src/umwelt/parser.py`, update `_build_rule_block` to call `parse_selector_list`:

```python
from umwelt.selector.parse import parse_selector_list


def _build_rule_block(
    node: Any, warnings: list[ParseWarning], source_path: Path | None = None
) -> RuleBlock | None:
    prelude = list(getattr(node, "prelude", []) or [])
    try:
        selectors = parse_selector_list(prelude, source_path=source_path)
    except ViewParseError:
        raise
    return RuleBlock(
        selectors=selectors,
        declarations=(),  # Task 11 populates declarations
        nested_blocks=(),
        span=_span(node),
    )
```

And thread `source_path` through the call:

```python
rule = _build_rule_block(node, warnings, source_path=source_path)
```

- [ ] **Step 5: Run tests and checks**

Run: `pytest tests/core/test_parser_selectors.py tests/core/test_parser_basic.py -v`
Expected: the parser_basic tests still pass (the "single rule block" one now has a populated selector instead of empty, but the assertions are compatible); the parser_selectors tests all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/selector/ src/umwelt/parser.py tests/core/test_parser_selectors.py
git commit -m "$(cat <<'EOF'
feat(selector): parse simple selectors (type, id, class, attributes, pseudo)

parse_selector_list walks a tinycss2 prelude token list and produces
a tuple of ComplexSelector, each with a single compound part. Covers:
bare type names, universal selector, #id (with dotted values like
README.md), one or more .class selectors, attribute selectors with
all CSS3 operators (=, ^=, $=, *=, |=, ~=), pseudo-classes with or
without function arguments, comma-separated union.

The taxon field on SimpleSelector is left as "__unresolved__" in
this task; Task 15 adds registry-based taxon resolution.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Declaration parsing

**Files:**
- Modify: `src/umwelt/parser.py` (populate `RuleBlock.declarations`)
- Create: `tests/core/test_parser_declarations.py`

**Context:** Declarations inside a rule block are parsed via `tinycss2.parse_declaration_list(content)`. Each yielded node is a `Declaration` (name + value token list) or an `AtRule` (we ignore at-rules inside declaration blocks for v0.1) or a `ParseError` (raise).

The value token list can contain: identifiers, strings, numbers with units, commas (for multi-value like `only-kits: python-dev, rust-dev`). We serialize each comma-separated value back to text via `tinycss2.serialize` and trim whitespace.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_parser_declarations.py`:

```python
"""Tests for declaration parsing inside rule blocks."""

from __future__ import annotations

from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import install_toy_taxonomy


def _sole_declarations(view):
    assert len(view.rules) == 1
    return view.rules[0].declarations


def test_single_declaration():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red; }")
    decls = _sole_declarations(view)
    assert len(decls) == 1
    assert decls[0].property_name == "paint"
    assert decls[0].values == ("red",)


def test_multi_value_declaration_via_commas():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red, green, blue; }")
    decls = _sole_declarations(view)
    assert len(decls) == 1
    assert decls[0].property_name == "paint"
    assert decls[0].values == ("red", "green", "blue")


def test_repeated_declaration_multi_value():
    # `run: "a"; run: "b"` is a multi-value form; the parser produces two
    # Declaration entries and the cascade resolver (Task 22) consolidates.
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing { paint: red; paint: blue; }')
    decls = _sole_declarations(view)
    assert len(decls) == 2
    assert decls[0].values == ("red",)
    assert decls[1].values == ("blue",)


def test_string_value():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing { paint: "crimson red"; }')
    decls = _sole_declarations(view)
    assert decls[0].values == ("crimson red",)


def test_numeric_value_with_unit():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { max-glow: 512; }")
    decls = _sole_declarations(view)
    assert decls[0].property_name == "max-glow"
    assert decls[0].values == ("512",)


def test_numeric_value_with_unit_suffix():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { max-glow: 512MB; }")
    decls = _sole_declarations(view)
    assert decls[0].values == ("512MB",)


def test_declaration_without_trailing_semicolon():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red }")
    decls = _sole_declarations(view)
    assert len(decls) == 1
    assert decls[0].values == ("red",)


def test_multiple_properties():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red; max-glow: 5; }")
    decls = _sole_declarations(view)
    assert len(decls) == 2
    assert decls[0].property_name == "paint"
    assert decls[1].property_name == "max-glow"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_parser_declarations.py -v`
Expected: all tests fail — `RuleBlock.declarations` is still empty.

- [ ] **Step 3: Add declaration parsing to `parser.py`**

Add imports:

```python
from umwelt.ast import Declaration
```

Add the declaration-parsing helper at module level:

```python
def _parse_declarations(
    content: list[Any], source_path: Path | None
) -> tuple[Declaration, ...]:
    """Parse the content of a qualified-rule block into Declaration tuples."""
    if not content:
        return ()
    decl_nodes = tinycss2.parse_declaration_list(
        content, skip_comments=True, skip_whitespace=True
    )
    out: list[Declaration] = []
    for node in decl_nodes:
        if _is_parse_error(node):
            raise _parse_error_to_view_error(node, source_path)
        node_type = getattr(node, "type", None)
        if node_type != "declaration":
            # At-rules inside declaration blocks are preserved as unknown
            # but v0.1 doesn't expose them through the RuleBlock; skip for now.
            continue
        name = getattr(node, "lower_name", None) or getattr(node, "name", "")
        values = _split_declaration_values(
            list(getattr(node, "value", []) or [])
        )
        out.append(
            Declaration(
                property_name=name,
                values=tuple(values),
                span=_span(node),
            )
        )
    return tuple(out)


def _split_declaration_values(tokens: list[Any]) -> list[str]:
    """Split a declaration value token list on commas and serialize each part."""
    groups: list[list[Any]] = [[]]
    for t in tokens:
        if _is_literal(t, ","):
            groups.append([])
        else:
            groups[-1].append(t)
    result: list[str] = []
    for g in groups:
        text = tinycss2.serialize(g).strip()
        if text:
            result.append(_unquote(text))
    return result


def _unquote(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text
```

And update `_build_rule_block` to call it:

```python
def _build_rule_block(
    node: Any, warnings: list[ParseWarning], source_path: Path | None = None
) -> RuleBlock | None:
    prelude = list(getattr(node, "prelude", []) or [])
    content = list(getattr(node, "content", []) or [])
    selectors = parse_selector_list(prelude, source_path=source_path)
    declarations = _parse_declarations(content, source_path)
    return RuleBlock(
        selectors=selectors,
        declarations=declarations,
        nested_blocks=(),
        span=_span(node),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_parser_declarations.py tests/core/ -v`
Expected: all tests pass, including the prior parser tests.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/parser.py tests/core/test_parser_declarations.py
git commit -m "$(cat <<'EOF'
feat(parser): parse declarations inside rule blocks

_parse_declarations walks tinycss2's declaration-list output and
produces Declaration tuples with property_name and comma-split
values. Quoted string values are unquoted; numeric values with unit
suffixes are preserved as-is (the comparison-semantics layer
interprets them later).

Repeated property declarations produce multiple Declaration entries
on the RuleBlock; cascade resolution in Task 22 consolidates.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Parser warnings + unknown declarations

**Files:**
- Modify: `src/umwelt/parser.py` (emit warnings for duplicate declarations and unknown at-rules inside rule blocks)
- Create: `tests/core/test_parser_warnings.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_parser_warnings.py`:

```python
"""Tests for parser warnings (soft errors that don't abort parsing)."""

from __future__ import annotations

from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import install_toy_taxonomy


def test_duplicate_declaration_key_warns():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red; paint: blue; }")
    # The rule still has two declarations (cascade resolves).
    assert len(view.rules[0].declarations) == 2
    # And the parser attached a warning.
    assert any(
        "duplicate" in w.message.lower() and "paint" in w.message
        for w in view.warnings
    )


def test_no_warning_on_single_declaration():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { paint: red; }")
    assert view.warnings == ()


def test_unknown_top_level_at_rule_no_warning():
    # Unknown at-rules are preserved, not warned — they're forward-compat
    # hooks, not errors.
    with registry_scope():
        install_toy_taxonomy()
        view = parse("@future { whatever: 1; }")
    assert len(view.unknown_at_rules) == 1
    assert view.warnings == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_parser_warnings.py -v`
Expected: the first test fails — no warnings are emitted yet.

- [ ] **Step 3: Emit duplicate-key warnings in `_parse_declarations`**

Modify `_parse_declarations` to check for duplicate property names within a rule block and append `ParseWarning` entries to a caller-supplied list:

```python
def _parse_declarations(
    content: list[Any],
    source_path: Path | None,
    warnings: list[ParseWarning],
) -> tuple[Declaration, ...]:
    if not content:
        return ()
    decl_nodes = tinycss2.parse_declaration_list(
        content, skip_comments=True, skip_whitespace=True
    )
    out: list[Declaration] = []
    seen: dict[str, SourceSpan] = {}
    for node in decl_nodes:
        if _is_parse_error(node):
            raise _parse_error_to_view_error(node, source_path)
        node_type = getattr(node, "type", None)
        if node_type != "declaration":
            continue
        name = getattr(node, "lower_name", None) or getattr(node, "name", "")
        values = _split_declaration_values(
            list(getattr(node, "value", []) or [])
        )
        span = _span(node)
        if name in seen:
            warnings.append(
                ParseWarning(
                    message=f"duplicate declaration key {name!r}",
                    span=span,
                )
            )
        else:
            seen[name] = span
        out.append(
            Declaration(
                property_name=name,
                values=tuple(values),
                span=span,
            )
        )
    return tuple(out)
```

And update `_build_rule_block` to pass the warnings list in:

```python
def _build_rule_block(
    node: Any,
    warnings: list[ParseWarning],
    source_path: Path | None = None,
) -> RuleBlock | None:
    prelude = list(getattr(node, "prelude", []) or [])
    content = list(getattr(node, "content", []) or [])
    selectors = parse_selector_list(prelude, source_path=source_path)
    declarations = _parse_declarations(content, source_path, warnings)
    return RuleBlock(
        selectors=selectors,
        declarations=declarations,
        nested_blocks=(),
        span=_span(node),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_parser_warnings.py tests/core/ -v`
Expected: all tests pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/parser.py tests/core/test_parser_warnings.py
git commit -m "$(cat <<'EOF'
feat(parser): emit ParseWarning for duplicate declaration keys

Duplicate property names inside a single rule block are not errors
(cascade resolves), but they're worth surfacing so authors can notice
unintentional shadowing. Unknown top-level at-rules stay
warning-free — they're forward-compat hooks.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Slice 2 — Compound selectors + combinator modes

### Task 12: Descendant and child combinators + pseudo-class tests

**Files:**
- Modify: `src/umwelt/selector/parse.py` (parse multi-part compounds)
- Create: `tests/core/test_selector_combinators.py`

**Context:** CSS combinators are the tokens between simple selectors: whitespace for descendant (`dir file`), `>` for direct child (`dir > file`). Sibling (`+`, `~`) are in the grammar but not meaningful for entity taxonomies; v0.1 parses them but never emits mode="structural" through them — treat them as descendant for now and document the limitation.

This task replaces the Task-9 behavior of "raise on interior whitespace" with "split the token list at combinators, parse each part as a simple selector, produce multiple `CompoundPart`s."

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_selector_combinators.py`:

```python
"""Tests for compound selectors with combinators and pseudo-classes."""

from __future__ import annotations

from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import install_toy_taxonomy


def _complex(view, idx: int = 0):
    return view.rules[0].selectors[idx]


def test_descendant_two_parts():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing widget { }")
    c = _complex(view)
    assert len(c.parts) == 2
    assert c.parts[0].selector.type_name == "thing"
    assert c.parts[0].combinator == "root"
    assert c.parts[1].selector.type_name == "widget"
    assert c.parts[1].combinator == "descendant"


def test_descendant_three_parts():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing widget thing { }")
    c = _complex(view)
    assert len(c.parts) == 3
    assert [p.selector.type_name for p in c.parts] == ["thing", "widget", "thing"]
    assert [p.combinator for p in c.parts] == ["root", "descendant", "descendant"]


def test_child_combinator():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing > widget { }")
    c = _complex(view)
    assert len(c.parts) == 2
    assert c.parts[1].combinator == "child"


def test_mixed_combinators():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing > widget thing { }")
    c = _complex(view)
    assert [p.combinator for p in c.parts] == ["root", "child", "descendant"]


def test_descendant_with_attributes():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color="red"] widget[color^="bl"] { }')
    c = _complex(view)
    assert len(c.parts) == 2
    first = c.parts[0].selector
    second = c.parts[1].selector
    assert first.attributes[0].value == "red"
    assert second.attributes[0].value == "bl"


def test_not_pseudo_class():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing:not([color="red"]) { }')
    sel = view.rules[0].selectors[0].parts[0].selector
    assert len(sel.pseudo_classes) == 1
    assert sel.pseudo_classes[0].name == "not"
    assert "color" in (sel.pseudo_classes[0].argument or "")


def test_glob_pseudo_class():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing:glob("*.py") { }')
    sel = view.rules[0].selectors[0].parts[0].selector
    assert sel.pseudo_classes[0].name == "glob"
    assert sel.pseudo_classes[0].argument == '"*.py"'


def test_pseudo_class_plus_descendant():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing:glob(\"*.py\") widget { }")
    c = _complex(view)
    assert len(c.parts) == 2
    assert c.parts[0].selector.pseudo_classes[0].name == "glob"
    assert c.parts[1].selector.type_name == "widget"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_selector_combinators.py -v`
Expected: tests fail because `_parse_simple` currently raises on interior whitespace.

- [ ] **Step 3: Rewrite `_parse_complex` to handle combinators**

In `src/umwelt/selector/parse.py`, replace `_parse_complex` and related helpers with combinator-aware versions:

```python
def _parse_complex(tokens: list[Any], source_path) -> ComplexSelector | None:
    """Parse a compound selector token list into a ComplexSelector."""
    tokens = _strip_whitespace(tokens)
    if not tokens:
        return None

    # Split on combinators into (combinator, simple-token-list) pairs.
    parts_raw: list[tuple[str, list[Any]]] = []
    current: list[Any] = []
    current_combinator: str = "root"
    pending_ws = False
    i = 0
    while i < len(tokens):
        t = tokens[i]
        ttype = getattr(t, "type", None)

        if ttype == "whitespace":
            # Whitespace might be a combinator (descendant) or just padding
            # around an explicit combinator. Record that we've seen whitespace
            # and let the next token decide.
            pending_ws = True
            i += 1
            continue

        if _is_literal(t, ">"):
            # Close the current part; start a new one with "child" combinator.
            if current:
                parts_raw.append((current_combinator, current))
            current = []
            current_combinator = "child"
            pending_ws = False
            i += 1
            continue

        if _is_literal(t, "+") or _is_literal(t, "~"):
            # Sibling combinators — parse but treat as "sibling"/"adjacent".
            # Not exercised in v0.1, but the grammar permits them.
            if current:
                parts_raw.append((current_combinator, current))
            current = []
            current_combinator = "adjacent" if _is_literal(t, "+") else "sibling"
            pending_ws = False
            i += 1
            continue

        if pending_ws and current:
            # Whitespace between tokens and we're mid-part, so the whitespace
            # is a descendant combinator. Close the current part.
            parts_raw.append((current_combinator, current))
            current = [t]
            current_combinator = "descendant"
            pending_ws = False
            i += 1
            continue

        current.append(t)
        pending_ws = False
        i += 1

    if current:
        parts_raw.append((current_combinator, current))

    if not parts_raw:
        return None

    parts: list[CompoundPart] = []
    for idx, (combinator, part_tokens) in enumerate(parts_raw):
        simple = _parse_simple(part_tokens, source_path)
        if simple is None:
            raise ViewParseError(
                "empty compound part in compound selector",
                line=1,
                col=1,
                source_path=source_path,
            )
        # First part always has combinator "root" regardless of what we
        # recorded (we seeded with "root" and never rewrite it).
        combinator_kind = "root" if idx == 0 else combinator
        parts.append(
            CompoundPart(
                selector=simple,
                combinator=combinator_kind,  # type: ignore[arg-type]
                mode="root" if idx == 0 else "structural",
            )
        )

    # target_taxon is the rightmost part's taxon; Task 13 resolves it.
    target_taxon = parts[-1].selector.taxon
    return ComplexSelector(
        parts=tuple(parts),
        target_taxon=target_taxon,
        specificity=(0, 0, 0),  # Task 16 computes this.
    )
```

Also update `_parse_simple` so it no longer raises on interior whitespace — the caller now strips whitespace at combinator boundaries:

```python
def _parse_simple(tokens: list[Any], source_path) -> SimpleSelector | None:
    tokens = _strip_whitespace(tokens)
    if not tokens:
        return None
    # ... rest unchanged, but remove the "unexpected whitespace" branch
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_selector_combinators.py tests/core/ -v`
Expected: all tests pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/selector/parse.py tests/core/test_selector_combinators.py
git commit -m "$(cat <<'EOF'
feat(selector): parse compound selectors with combinators

The whitespace-splitting logic now recognizes descendant (whitespace),
child (>), and adjacent/sibling (+, ~) combinators. _parse_complex
produces a list of CompoundPart entries tagged with the combinator
kind; the first part is always "root" and subsequent parts carry the
combinator that separated them from the previous part. Mode is
"structural" for now — Task 15 adds cross-taxon context classification.

Pseudo-class tests (:not, :glob) are also added here; the grammar was
already in Task 9 but wasn't covered by tests.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Taxon resolution in the parser

**Files:**
- Modify: `src/umwelt/selector/parse.py` (resolve `type_name` against registry; populate `taxon`)
- Create: `tests/core/test_parser_resolution.py`

**Context:** Until now every `SimpleSelector` carries `taxon="__unresolved__"`. This task replaces that with a real lookup: for each parsed simple selector, call `resolve_entity_type(type_name)` and set `taxon` based on the result. A unique match wins; zero matches → `ViewParseError`; multiple matches → defer to Task 14 (disambiguation).

For Task 13 specifically, tests use the toy taxonomy (which has unique entity names: `thing`, `widget` in shapes; `actor` in actors) so every resolution is unambiguous. Ambiguous-type error handling moves to Task 14.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_parser_resolution.py`:

```python
"""Tests for entity-type resolution against the registry during parsing."""

from __future__ import annotations

import pytest

from umwelt.errors import ViewParseError
from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import install_toy_taxonomy


def _first_simple(view):
    return view.rules[0].selectors[0].parts[0].selector


def test_resolves_unique_type():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { }")
    sel = _first_simple(view)
    assert sel.type_name == "thing"
    assert sel.taxon == "shapes"


def test_resolves_cross_taxon_type():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("actor { }")
    sel = _first_simple(view)
    assert sel.type_name == "actor"
    assert sel.taxon == "actors"


def test_resolves_widget_under_shapes():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("widget { }")
    sel = _first_simple(view)
    assert sel.taxon == "shapes"


def test_universal_selector_is_wildcard_taxon():
    # `*` doesn't refer to any specific entity type; resolution leaves the
    # taxon field as "*" (sentinel) until the selector engine decides how
    # to interpret universal matching.
    with registry_scope():
        install_toy_taxonomy()
        view = parse("* { }")
    sel = _first_simple(view)
    assert sel.type_name == "*"
    assert sel.taxon == "*"


def test_unknown_type_raises():
    with registry_scope():
        install_toy_taxonomy()
        with pytest.raises(ViewParseError, match="unknown entity type 'ghost'"):
            parse("ghost { }")


def test_resolution_in_compound_parts():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing widget { }")
    c = view.rules[0].selectors[0]
    assert c.parts[0].selector.taxon == "shapes"
    assert c.parts[1].selector.taxon == "shapes"
    # target_taxon comes from the rightmost part.
    assert c.target_taxon == "shapes"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_parser_resolution.py -v`
Expected: resolution tests fail — `taxon` is still `"__unresolved__"`.

- [ ] **Step 3: Wire resolution into `_parse_simple`**

In `src/umwelt/selector/parse.py`, import the registry function and use it when constructing `SimpleSelector`:

```python
from umwelt.registry import resolve_entity_type
```

Replace the final `SimpleSelector(...)` construction with:

```python
    resolved_taxon = _resolve_taxon(type_name, tokens, source_path)
    return SimpleSelector(
        type_name=type_name,
        taxon=resolved_taxon,
        id_value=id_value,
        classes=tuple(classes),
        attributes=tuple(attributes),
        pseudo_classes=tuple(pseudo_classes),
        span=span,
    )
```

And add the helper:

```python
def _resolve_taxon(
    type_name: str | None, tokens: list[Any], source_path
) -> str:
    """Look up the entity type in the registry. Unique match wins.

    - None or "*": return a sentinel "*" — the universal selector doesn't
      map to a specific taxon.
    - Known, unique: return that taxon name.
    - Unknown: raise ViewParseError.
    - Ambiguous: defer to Task 14; for now, raise until disambiguation
      support lands.
    """
    if type_name is None or type_name == "*":
        return "*"
    taxa = resolve_entity_type(type_name)
    if not taxa:
        first_tok = next(
            (t for t in tokens if getattr(t, "type", None) != "whitespace"),
            None,
        )
        raise ViewParseError(
            f"unknown entity type {type_name!r}",
            line=int(getattr(first_tok, "source_line", 1) or 1) if first_tok else 1,
            col=int(getattr(first_tok, "source_column", 1) or 1) if first_tok else 1,
            source_path=source_path,
        )
    if len(taxa) == 1:
        return taxa[0]
    # Ambiguous — Task 14 adds the world|file syntax. For now, error.
    raise ViewParseError(
        f"ambiguous entity type {type_name!r}: registered in {taxa}",
        line=1,
        col=1,
        source_path=source_path,
    )
```

And update `_parse_complex`'s `target_taxon` computation to handle the "*" sentinel (prefer the last non-`*` part's taxon):

```python
    target_taxon = parts[-1].selector.taxon
    if target_taxon == "*":
        for p in reversed(parts):
            if p.selector.taxon != "*":
                target_taxon = p.selector.taxon
                break
    return ComplexSelector(
        parts=tuple(parts),
        target_taxon=target_taxon,
        specificity=(0, 0, 0),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_parser_resolution.py tests/core/ -v`
Expected: all tests pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/selector/parse.py tests/core/test_parser_resolution.py
git commit -m "$(cat <<'EOF'
feat(parser): resolve entity type names against the registry

Every SimpleSelector's taxon field is now populated at parse time by
calling resolve_entity_type(). Unique matches win; zero matches raise
ViewParseError("unknown entity type"); multiple matches raise
"ambiguous entity type" (Task 14 adds disambiguation syntax).

The universal selector * gets a "*" sentinel taxon; target_taxon
prefers the rightmost non-wildcard part of a compound selector.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: Disambiguation — CSS namespace syntax and at-rule scoping

**Files:**
- Modify: `src/umwelt/selector/parse.py` (accept `taxon|type`)
- Modify: `src/umwelt/parser.py` (recognize `@world { ... }` scoping and resolve inside)
- Create: `tests/core/test_parser_disambiguation.py`

**Context:** When an entity type name is registered in multiple taxa, the author must disambiguate. Two mechanisms:

1. **Inline CSS namespace** — `world|file` uses CSS3's namespace-qualified element selector syntax. The parser sees the `|` literal and splits into `(taxon, type)`.
2. **At-rule scoping** — `@world { file { ... } }` wraps the inner rules in a taxon context. Bare entity types inside the block resolve against that taxon first before global resolution.

For this task we need a second toy taxon that reuses an entity name. Extend `toy_taxonomy.py` to register an optional "doubled" mode where a `thing` entity exists in both `shapes` and `shadows` taxa.

- [ ] **Step 1: Extend the toy taxonomy helper**

Add to `tests/core/helpers/toy_taxonomy.py`:

```python
def install_doubled_taxonomy() -> None:
    """Register two taxa that both define a `thing` entity.

    For tests that need to exercise ambiguity and disambiguation.
    """
    register_taxon(name="shapes", description="shapes toy taxon")
    register_entity(
        taxon="shapes",
        name="thing",
        attributes={"id": AttrSchema(type=str, required=True)},
        description="a shapes.thing",
    )
    register_property(
        taxon="shapes",
        entity="thing",
        name="paint",
        value_type=str,
        description="paint color",
    )

    register_taxon(name="shadows", description="shadows toy taxon")
    register_entity(
        taxon="shadows",
        name="thing",
        attributes={"id": AttrSchema(type=str, required=True)},
        description="a shadows.thing",
    )
    register_property(
        taxon="shadows",
        entity="thing",
        name="opacity",
        value_type=float,
        description="opacity 0-1",
    )
```

- [ ] **Step 2: Write the failing test**

Create `tests/core/test_parser_disambiguation.py`:

```python
"""Tests for ambiguous type names and disambiguation syntax."""

from __future__ import annotations

import pytest

from umwelt.errors import ViewParseError
from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import install_doubled_taxonomy


def _first_simple(view):
    return view.rules[0].selectors[0].parts[0].selector


def test_bare_ambiguous_type_raises():
    with registry_scope():
        install_doubled_taxonomy()
        with pytest.raises(ViewParseError, match="ambiguous"):
            parse("thing { }")


def test_namespace_prefix_shapes():
    with registry_scope():
        install_doubled_taxonomy()
        view = parse("shapes|thing { }")
    sel = _first_simple(view)
    assert sel.type_name == "thing"
    assert sel.taxon == "shapes"


def test_namespace_prefix_shadows():
    with registry_scope():
        install_doubled_taxonomy()
        view = parse("shadows|thing { }")
    sel = _first_simple(view)
    assert sel.taxon == "shadows"


def test_namespace_prefix_unknown_taxon_raises():
    with registry_scope():
        install_doubled_taxonomy()
        with pytest.raises(ViewParseError, match="unknown taxon 'ghost'"):
            parse("ghost|thing { }")


def test_namespace_prefix_unknown_type_in_taxon_raises():
    with registry_scope():
        install_doubled_taxonomy()
        with pytest.raises(ViewParseError, match="no entity 'widget' in taxon 'shapes'"):
            parse("shapes|widget { }")


def test_at_rule_scope_disambiguates():
    with registry_scope():
        install_doubled_taxonomy()
        view = parse("@shapes { thing { } }")
    # The rule inside @shapes is lifted into the top-level rules with
    # thing resolved to shapes.
    assert len(view.rules) == 1
    sel = _first_simple(view)
    assert sel.taxon == "shapes"


def test_at_rule_scope_with_multiple_rules():
    with registry_scope():
        install_doubled_taxonomy()
        view = parse("@shadows { thing { } thing#beta { } }")
    assert len(view.rules) == 2
    for r in view.rules:
        assert r.selectors[0].parts[0].selector.taxon == "shadows"


def test_at_rule_scope_does_not_affect_outside():
    with registry_scope():
        install_doubled_taxonomy()
        view = parse("@shapes { thing { } } shadows|thing { }")
    assert len(view.rules) == 2
    assert view.rules[0].selectors[0].parts[0].selector.taxon == "shapes"
    assert view.rules[1].selectors[0].parts[0].selector.taxon == "shadows"


def test_unknown_scope_at_rule_is_unknown_at_rule():
    with registry_scope():
        install_doubled_taxonomy()
        # @retrieval isn't a taxon scope — it's an unknown at-rule.
        view = parse("@retrieval { thing { } }")
    assert len(view.unknown_at_rules) == 1
    # Inner rules are not lifted.
    assert view.rules == ()
```

- [ ] **Step 3: Add namespace support to `_parse_simple`**

In `src/umwelt/selector/parse.py`, extend `_parse_simple` to recognize an optional `ident "|" ident` prefix:

```python
def _parse_simple(
    tokens: list[Any],
    source_path,
    scope_taxon: str | None = None,
) -> SimpleSelector | None:
    tokens = _strip_whitespace(tokens)
    if not tokens:
        return None

    explicit_taxon: str | None = None

    # Check for an ns|type prefix: IdentToken, LiteralToken("|"), IdentToken
    if (
        len(tokens) >= 3
        and getattr(tokens[0], "type", None) == "ident"
        and _is_literal(tokens[1], "|")
        and getattr(tokens[2], "type", None) == "ident"
    ):
        explicit_taxon = tokens[0].value
        tokens = tokens[2:]

    type_name: str | None = None
    id_value: str | None = None
    classes: list[str] = []
    attributes: list[AttrFilter] = []
    pseudo_classes: list[PseudoClass] = []

    span = _first_span(tokens)
    i = 0
    while i < len(tokens):
        # ... existing loop body unchanged ...
```

And update the resolution step to use `explicit_taxon` or `scope_taxon` when set:

```python
    resolved_taxon = _resolve_taxon(
        type_name,
        tokens,
        source_path,
        explicit_taxon=explicit_taxon,
        scope_taxon=scope_taxon,
    )
```

Update `_resolve_taxon`:

```python
def _resolve_taxon(
    type_name: str | None,
    tokens: list[Any],
    source_path,
    explicit_taxon: str | None = None,
    scope_taxon: str | None = None,
) -> str:
    from umwelt.registry import get_entity, get_taxon
    from umwelt.errors import RegistryError

    if type_name is None or type_name == "*":
        return scope_taxon or "*"

    if explicit_taxon is not None:
        # Verify the taxon exists.
        try:
            get_taxon(explicit_taxon)
        except RegistryError as exc:
            raise ViewParseError(
                f"unknown taxon {explicit_taxon!r}",
                line=1,
                col=1,
                source_path=source_path,
            ) from exc
        # Verify the entity exists inside that taxon.
        try:
            get_entity(explicit_taxon, type_name)
        except RegistryError as exc:
            raise ViewParseError(
                f"no entity {type_name!r} in taxon {explicit_taxon!r}",
                line=1,
                col=1,
                source_path=source_path,
            ) from exc
        return explicit_taxon

    taxa = resolve_entity_type(type_name)
    if not taxa:
        first_tok = next(
            (t for t in tokens if getattr(t, "type", None) != "whitespace"),
            None,
        )
        raise ViewParseError(
            f"unknown entity type {type_name!r}",
            line=int(getattr(first_tok, "source_line", 1) or 1) if first_tok else 1,
            col=int(getattr(first_tok, "source_column", 1) or 1) if first_tok else 1,
            source_path=source_path,
        )
    if len(taxa) == 1:
        return taxa[0]
    # Ambiguous. Check scope.
    if scope_taxon is not None and scope_taxon in taxa:
        return scope_taxon
    raise ViewParseError(
        f"ambiguous entity type {type_name!r}: registered in {sorted(taxa)}",
        line=1,
        col=1,
        source_path=source_path,
    )
```

And thread `scope_taxon` through `_parse_complex` and `parse_selector_list`:

```python
def parse_selector_list(
    tokens: list[Any], source_path=None, scope_taxon: str | None = None
) -> tuple[ComplexSelector, ...]:
    ...
    for group in groups:
        sel = _parse_complex(group, source_path, scope_taxon=scope_taxon)
        ...
```

```python
def _parse_complex(
    tokens: list[Any], source_path, scope_taxon: str | None = None
) -> ComplexSelector | None:
    ...
    for idx, (combinator, part_tokens) in enumerate(parts_raw):
        simple = _parse_simple(part_tokens, source_path, scope_taxon=scope_taxon)
        ...
```

- [ ] **Step 4: Add at-rule scoping to `parser.py`**

In `src/umwelt/parser.py`, recognize at-rules whose name matches a registered taxon and lift their inner rules:

```python
from umwelt.errors import RegistryError
from umwelt.registry import get_taxon


def _is_taxon_scope(at_name: str) -> bool:
    try:
        get_taxon(at_name)
        return True
    except RegistryError:
        return False


def _expand_taxon_scope(
    node: Any,
    warnings: list[ParseWarning],
    source_path: Path | None,
    scope_taxon: str,
) -> list[RuleBlock]:
    """Parse the contents of an @<taxon> block as a fresh rule list.

    Inner selectors are parsed with `scope_taxon` set so bare entity names
    that are ambiguous across taxa resolve against the scope first.
    """
    inner_rules: list[RuleBlock] = []
    content = getattr(node, "content", None)
    if content is None:
        return inner_rules
    # Re-parse the block content as a stylesheet fragment.
    inner_nodes = tinycss2.parse_rule_list(
        list(content), skip_comments=True, skip_whitespace=True
    )
    for inner in inner_nodes:
        if _is_parse_error(inner):
            raise _parse_error_to_view_error(inner, source_path)
        if getattr(inner, "type", None) != "qualified-rule":
            continue
        rule = _build_rule_block(
            inner, warnings, source_path=source_path, scope_taxon=scope_taxon
        )
        if rule is not None:
            inner_rules.append(rule)
    return inner_rules
```

And in the main `parse()` loop:

```python
        elif node_type == "at-rule":
            at_name = (
                getattr(node, "lower_at_keyword", None)
                or getattr(node, "at_keyword", "")
            )
            if _is_taxon_scope(at_name):
                rules.extend(
                    _expand_taxon_scope(node, warnings, source_path, at_name)
                )
            else:
                unknown_at_rules.append(_build_unknown_at_rule(node))
```

Also thread `scope_taxon` through `_build_rule_block`:

```python
def _build_rule_block(
    node: Any,
    warnings: list[ParseWarning],
    source_path: Path | None = None,
    scope_taxon: str | None = None,
) -> RuleBlock | None:
    prelude = list(getattr(node, "prelude", []) or [])
    content = list(getattr(node, "content", []) or [])
    selectors = parse_selector_list(
        prelude, source_path=source_path, scope_taxon=scope_taxon
    )
    declarations = _parse_declarations(content, source_path, warnings)
    return RuleBlock(
        selectors=selectors,
        declarations=declarations,
        nested_blocks=(),
        span=_span(node),
    )
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/core/test_parser_disambiguation.py tests/core/ -v`
Expected: all tests pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/selector/parse.py src/umwelt/parser.py tests/core/helpers/toy_taxonomy.py tests/core/test_parser_disambiguation.py
git commit -m "$(cat <<'EOF'
feat(parser): disambiguate ambiguous types via ns|type and @taxon scoping

Two mechanisms to disambiguate entity type names registered by
multiple taxa:

1. CSS3 namespace-qualified selectors: shapes|thing resolves to the
   shapes taxon regardless of how many taxa register 'thing'. Unknown
   taxon or missing entity in the named taxon raise ViewParseError
   with specific messages.

2. At-rule scoping: @shapes { thing { } } lifts the inner rules into
   the top level with scope_taxon=shapes, so bare 'thing' resolves
   against shapes first before global resolution. At-rules whose name
   doesn't match any registered taxon are preserved as UnknownAtRule
   (forward compat).

Also adds install_doubled_taxonomy to the toy-taxonomy helper for
tests that need to exercise genuine ambiguity.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: Combinator mode classification (structural vs context)

**Files:**
- Modify: `src/umwelt/selector/parse.py` (set `mode` on each `CompoundPart` based on taxon comparison)
- Create: `tests/core/test_parser_modes.py`

**Context:** Each combinator's mode is determined by comparing the taxa on either side:
- Both sides same taxon → `"structural"` (within-taxon descent via plugin parent/child)
- Different taxa → `"context"` (cross-taxon context qualifier)
- First part is always `"root"`

A universal selector (`*`, taxon=`"*"`) is treated as matching any taxon — it never triggers context mode on its own.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_parser_modes.py`:

```python
"""Tests for combinator mode classification."""

from __future__ import annotations

from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import install_toy_taxonomy


def _parts(view):
    return view.rules[0].selectors[0].parts


def test_within_taxon_descendant_is_structural():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing widget { }")
    parts = _parts(view)
    assert parts[0].mode == "root"
    assert parts[1].mode == "structural"


def test_within_taxon_child_is_structural():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing > widget { }")
    parts = _parts(view)
    assert parts[1].mode == "structural"


def test_cross_taxon_descendant_is_context():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("actor thing { }")
    parts = _parts(view)
    assert parts[0].mode == "root"
    assert parts[1].mode == "context"


def test_three_level_mixed_modes():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("actor thing widget { }")
    parts = _parts(view)
    assert [p.mode for p in parts] == ["root", "context", "structural"]


def test_target_taxon_is_rightmost():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("actor thing { }")
    c = view.rules[0].selectors[0]
    assert c.target_taxon == "shapes"


def test_universal_on_right_inherits_taxon():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing * { }")
    c = view.rules[0].selectors[0]
    # The rightmost is *, so target_taxon falls back to the left part.
    assert c.target_taxon == "shapes"


def test_universal_on_left_is_structural_root():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("* widget { }")
    parts = _parts(view)
    # The leading * is always root mode regardless of taxon.
    assert parts[0].mode == "root"
    # The widget under * treats the previous part as matching any taxon;
    # we classify this as structural (no cross-taxon barrier).
    assert parts[1].mode == "structural"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_parser_modes.py -v`
Expected: tests fail — all non-root parts currently have `mode="structural"` unconditionally.

- [ ] **Step 3: Classify combinator mode in `_parse_complex`**

Update the compound-part construction in `_parse_complex`:

```python
    parts: list[CompoundPart] = []
    previous_taxon: str | None = None
    for idx, (combinator, part_tokens) in enumerate(parts_raw):
        simple = _parse_simple(part_tokens, source_path, scope_taxon=scope_taxon)
        if simple is None:
            raise ViewParseError(
                "empty compound part in compound selector",
                line=1,
                col=1,
                source_path=source_path,
            )
        if idx == 0:
            mode = "root"
            combinator_kind = "root"
        else:
            combinator_kind = combinator
            # Classify: structural if same taxon or either side is universal.
            if (
                previous_taxon == simple.taxon
                or previous_taxon == "*"
                or simple.taxon == "*"
            ):
                mode = "structural"
            else:
                mode = "context"
        parts.append(
            CompoundPart(
                selector=simple,
                combinator=combinator_kind,  # type: ignore[arg-type]
                mode=mode,  # type: ignore[arg-type]
            )
        )
        previous_taxon = simple.taxon
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_parser_modes.py tests/core/ -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/selector/parse.py tests/core/test_parser_modes.py
git commit -m "$(cat <<'EOF'
feat(selector): classify combinator mode structural vs context

Each non-root CompoundPart's mode is set at parse time by comparing
the taxa on either side of the combinator: same taxon -> structural
(within-taxon descendant or child via plugin's parent/child relation),
different taxa -> context (cross-taxon context qualifier where the
rule fires only when the qualifier condition holds).

The universal selector (*) is treated as matching any taxon, so it
never introduces a context boundary on its own.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: Specificity computation

**Files:**
- Create: `src/umwelt/selector/specificity.py`
- Modify: `src/umwelt/selector/parse.py` (call into specificity to populate `ComplexSelector.specificity`)
- Create: `tests/core/test_specificity.py`

**Context:** CSS3 specificity is a tuple `(ids, classes+attributes+pseudos, types)`. For a compound selector, each simple selector contributes its own tuple and the compound's total is the component-wise sum. Document order is only consulted when specificity ties.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_specificity.py`:

```python
"""Tests for CSS3 specificity computation."""

from __future__ import annotations

from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import install_toy_taxonomy


def _spec(view, rule_idx: int = 0, sel_idx: int = 0):
    return view.rules[rule_idx].selectors[sel_idx].specificity


def test_bare_type_is_0_0_1():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { }")
    assert _spec(view) == (0, 0, 1)


def test_universal_selector_is_0_0_0():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("* { }")
    assert _spec(view) == (0, 0, 0)


def test_id_selector_is_1_0_0():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing#alpha { }")
    assert _spec(view) == (1, 0, 1)


def test_attribute_selector_is_0_1_1():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color="red"] { }')
    assert _spec(view) == (0, 1, 1)


def test_class_selector_is_0_1_1():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing.highlighted { }")
    assert _spec(view) == (0, 1, 1)


def test_pseudo_class_is_0_1_1():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing:glob("*.py") { }')
    assert _spec(view) == (0, 1, 1)


def test_descendant_accumulates():
    # thing widget -> (0,0,1) + (0,0,1) = (0,0,2)
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing widget { }")
    assert _spec(view) == (0, 0, 2)


def test_complex_compound_specificity():
    # thing#alpha[color="red"] widget.highlighted
    # left: (1,1,1)
    # right: (0,1,1)
    # total: (1,2,2)
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing#alpha[color="red"] widget.highlighted { }')
    assert _spec(view) == (1, 2, 2)


def test_cross_taxon_compound_accumulates_same():
    # The mode classification doesn't affect specificity — both parts
    # contribute their tuples regardless.
    with registry_scope():
        install_toy_taxonomy()
        view = parse('actor[role="admin"] thing#beta { }')
    assert _spec(view) == (1, 1, 2)


def test_multiple_selectors_each_get_specificity():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing, thing#alpha { }")
    assert view.rules[0].selectors[0].specificity == (0, 0, 1)
    assert view.rules[0].selectors[1].specificity == (1, 0, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_specificity.py -v`
Expected: all fail — specificity is still `(0, 0, 0)` placeholder.

- [ ] **Step 3: Implement specificity computation**

Create `src/umwelt/selector/specificity.py`:

```python
"""CSS3 specificity computation for umwelt selectors.

Per CSS3, specificity is a tuple (ids, classes+attrs+pseudos, types):

- Count of IDs in the selector.
- Count of classes + attribute selectors + pseudo-classes.
- Count of type selectors (the universal selector * contributes 0).

For a compound selector, each simple selector's tuple is summed
component-wise.
"""

from __future__ import annotations

from umwelt.ast import ComplexSelector, SimpleSelector


def simple_specificity(selector: SimpleSelector) -> tuple[int, int, int]:
    ids = 1 if selector.id_value is not None else 0
    classes_attrs_pseudos = (
        len(selector.classes)
        + len(selector.attributes)
        + len(selector.pseudo_classes)
    )
    types = 1 if (selector.type_name is not None and selector.type_name != "*") else 0
    return (ids, classes_attrs_pseudos, types)


def compound_specificity(compound: ComplexSelector) -> tuple[int, int, int]:
    total_ids = 0
    total_cap = 0
    total_types = 0
    for part in compound.parts:
        ids, cap, types = simple_specificity(part.selector)
        total_ids += ids
        total_cap += cap
        total_types += types
    return (total_ids, total_cap, total_types)
```

Update `src/umwelt/selector/parse.py` to use it when constructing `ComplexSelector`:

```python
from umwelt.selector.specificity import compound_specificity

# ... inside _parse_complex, replace the ComplexSelector construction:
    selector = ComplexSelector(
        parts=tuple(parts),
        target_taxon=target_taxon,
        specificity=(0, 0, 0),  # placeholder; rebuild below with real spec
    )
    final_spec = compound_specificity(selector)
    return ComplexSelector(
        parts=tuple(parts),
        target_taxon=target_taxon,
        specificity=final_spec,
    )
```

Or — cleaner — compute the specificity before constructing, by calling `simple_specificity` directly as parts are built. Either approach is fine; pick whichever keeps the code readable.

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_specificity.py tests/core/ -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/selector/specificity.py src/umwelt/selector/parse.py tests/core/test_specificity.py
git commit -m "$(cat <<'EOF'
feat(selector): compute CSS3 specificity for compound selectors

simple_specificity computes (ids, classes+attrs+pseudos, types) for
a single SimpleSelector; compound_specificity sums the per-part
tuples component-wise for the whole ComplexSelector. The parser
populates ComplexSelector.specificity from compound_specificity
during selector construction.

Cross-taxon mode classification does not affect specificity — both
structural and context qualifiers contribute equally to the tuple.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Slice 3 — Validator framework, selector matching, cascade

### Task 17: Validator framework

**Files:**
- Create: `src/umwelt/registry/validators.py`
- Modify: `src/umwelt/registry/taxa.py` (add `validators` field)
- Modify: `src/umwelt/registry/__init__.py`
- Create: `src/umwelt/validate.py`
- Modify: `src/umwelt/parser.py` (call `validate()` when `validate=True`)
- Create: `tests/core/test_validate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_validate.py`:

```python
"""Tests for the per-taxon validator dispatcher."""

from __future__ import annotations

import pytest

from umwelt.ast import ParseWarning, SourceSpan
from umwelt.errors import ViewValidationError
from umwelt.parser import parse
from umwelt.registry import (
    register_taxon,
    register_validator,
    registry_scope,
)
from umwelt.validate import validate
from tests.core.helpers.toy_taxonomy import install_toy_taxonomy


class _RecordingValidator:
    """Validator that records which rules it saw. Raises nothing."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def validate(self, rules, warnings):
        for rule in rules:
            for sel in rule.selectors:
                self.seen.append(sel.parts[-1].selector.type_name or "*")


class _RejectingValidator:
    """Validator that raises ViewValidationError for rule with 'widget' type."""

    def validate(self, rules, warnings):
        for rule in rules:
            for sel in rule.selectors:
                if sel.parts[-1].selector.type_name == "widget":
                    raise ViewValidationError("widgets are not allowed in v0.1 core tests")


class _WarningValidator:
    """Validator that appends a ParseWarning for every thing rule."""

    def validate(self, rules, warnings):
        for rule in rules:
            for sel in rule.selectors:
                if sel.parts[-1].selector.type_name == "thing":
                    warnings.append(
                        ParseWarning(
                            message="thing flagged by validator",
                            span=rule.span,
                        )
                    )


def test_validator_sees_its_taxon_rules():
    with registry_scope():
        install_toy_taxonomy()
        v = _RecordingValidator()
        register_validator(taxon="shapes", validator=v)
        parse("thing { } widget { }")
    assert v.seen == ["thing", "widget"]


def test_validator_does_not_see_other_taxa():
    with registry_scope():
        install_toy_taxonomy()
        v = _RecordingValidator()
        register_validator(taxon="shapes", validator=v)
        parse("actor { }")  # actors taxon
    assert v.seen == []


def test_rejecting_validator_raises():
    with registry_scope():
        install_toy_taxonomy()
        register_validator(taxon="shapes", validator=_RejectingValidator())
        with pytest.raises(ViewValidationError, match="widgets are not allowed"):
            parse("widget { }")


def test_validator_appends_warnings():
    with registry_scope():
        install_toy_taxonomy()
        register_validator(taxon="shapes", validator=_WarningValidator())
        view = parse("thing { }")
    assert any("flagged by validator" in w.message for w in view.warnings)


def test_validate_flag_disables_validators():
    with registry_scope():
        install_toy_taxonomy()
        register_validator(taxon="shapes", validator=_RejectingValidator())
        # With validate=False, the rejecting validator never runs.
        view = parse("widget { }", validate=False)
    assert len(view.rules) == 1


def test_multiple_validators_per_taxon_all_run():
    with registry_scope():
        install_toy_taxonomy()
        a = _RecordingValidator()
        b = _RecordingValidator()
        register_validator(taxon="shapes", validator=a)
        register_validator(taxon="shapes", validator=b)
        parse("thing { }")
    assert a.seen == ["thing"]
    assert b.seen == ["thing"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_validate.py -v`
Expected: `ImportError` on `umwelt.validate` or missing `register_validator`.

- [ ] **Step 3: Implement the validator registry and dispatcher**

Add to `src/umwelt/registry/taxa.py`:

```python
@dataclass
class RegistryState:
    taxa: dict[str, TaxonSchema] = field(default_factory=dict)
    entities: dict[tuple[str, str], "EntitySchema"] = field(default_factory=dict)
    properties: dict[tuple[str, str, str], "PropertySchema"] = field(default_factory=dict)
    matchers: dict[str, "MatcherProtocol"] = field(default_factory=dict)
    # Multiple validators per taxon allowed; they all run in registration order.
    validators: dict[str, list["ValidatorProtocol"]] = field(default_factory=dict)
```

Extend the `TYPE_CHECKING` block to include `ValidatorProtocol`.

Create `src/umwelt/registry/validators.py`:

```python
"""Validator protocol and registration."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from umwelt.registry.taxa import _current_state, get_taxon


@runtime_checkable
class ValidatorProtocol(Protocol):
    """A validator inspects rules in its taxon and emits warnings or errors.

    `rules` is the full list of RuleBlocks whose target_taxon equals the
    validator's registered taxon. The validator mutates the shared `warnings`
    list for soft findings and raises ViewValidationError for hard failures.
    """

    def validate(self, rules: list[Any], warnings: list[Any]) -> None:
        ...


def register_validator(*, taxon: str, validator: ValidatorProtocol) -> None:
    get_taxon(taxon)
    state = _current_state()
    state.validators.setdefault(taxon, []).append(validator)


def get_validators(taxon: str) -> list[ValidatorProtocol]:
    state = _current_state()
    return list(state.validators.get(taxon, []))
```

Re-export from `src/umwelt/registry/__init__.py`:

```python
from umwelt.registry.validators import ValidatorProtocol, get_validators, register_validator
```

Add to `__all__`.

Create `src/umwelt/validate.py`:

```python
"""Dispatch registered per-taxon validators over a parsed view."""

from __future__ import annotations

from umwelt.ast import ParseWarning, RuleBlock, View
from umwelt.registry import get_validators, list_taxa


def validate(view: View) -> View:
    """Run every registered validator over its taxon's rules.

    Returns a new `View` with any accumulated warnings attached. Hard
    failures raise ViewValidationError from the validator itself.
    """
    warnings_list: list[ParseWarning] = list(view.warnings)
    # Group rules by the rightmost selector's target_taxon.
    grouped: dict[str, list[RuleBlock]] = {}
    for rule in view.rules:
        for sel in rule.selectors:
            grouped.setdefault(sel.target_taxon, []).append(rule)
            break  # One rule -> one taxon group per rule; use first selector's taxon.
    for taxon in list_taxa():
        rules = grouped.get(taxon.name, [])
        for validator in get_validators(taxon.name):
            validator.validate(rules, warnings_list)
    return View(
        rules=view.rules,
        unknown_at_rules=view.unknown_at_rules,
        warnings=tuple(warnings_list),
        source_text=view.source_text,
        source_path=view.source_path,
    )
```

Modify `src/umwelt/parser.py` — at the end of `parse()`:

```python
    view = View(
        rules=tuple(rules),
        unknown_at_rules=tuple(unknown_at_rules),
        warnings=tuple(warnings),
        source_text=text,
        source_path=source_path,
    )
    if validate:
        from umwelt.validate import validate as run_validators

        view = run_validators(view)
    return view
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_validate.py tests/core/ -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/validate.py src/umwelt/registry/ tests/core/test_validate.py src/umwelt/parser.py
git commit -m "$(cat <<'EOF'
feat(validate): dispatch per-taxon validators after parsing

ValidatorProtocol is a runtime-checkable Protocol with one method,
validate(rules, warnings). Multiple validators per taxon are allowed
and run in registration order. Each validator receives the rules
whose target_taxon matches and can either append ParseWarning
entries or raise ViewValidationError.

parse() runs the dispatcher automatically unless validate=False is
passed. The test fixtures cover: recording (sees its own taxon),
exclusion (doesn't see other taxa), rejection (raises), warning
accumulation, the validate=False escape hatch, and multi-validator
per taxon.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 18: Selector match engine — simple selectors

**Files:**
- Create: `src/umwelt/selector/match.py`
- Create: `tests/core/test_selector_match_simple.py`

**Context:** For each simple selector, `match_simple` takes the selector and the full candidate list (from `matcher.match_type(type_name)`) and returns only the entities that satisfy all of: id match, every class in `classes`, every attribute filter, every pseudo-class predicate.

Matchers expose entity attributes via a callable convention: each entity is an opaque handle that the matcher knows how to introspect. For the toy matchers, entities are dataclasses with fields (`id`, `color`, etc.) accessible via `getattr`. For a real filesystem matcher, entities would be `Path` objects with `.name`, `.suffix`, etc. computed from attributes.

The match engine uses a helper `matcher.get_attribute(entity, name) -> Any` that the matcher supplies. We add this to `MatcherProtocol`.

- [ ] **Step 1: Extend `MatcherProtocol` with `get_attribute`**

Update `src/umwelt/registry/matchers.py`:

```python
@runtime_checkable
class MatcherProtocol(Protocol):
    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        ...

    def children(self, parent: Any, child_type: str) -> list[Any]:
        ...

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        ...

    def get_attribute(self, entity: Any, name: str) -> Any:
        """Return the value of an attribute on an entity, or None if absent.

        Used by the selector match engine to evaluate attribute filters.
        """
        ...

    def get_id(self, entity: Any) -> str | None:
        """Return the entity's identity value (used by `#id` selectors).

        Return None when the entity has no natural identity; `#id` selectors
        won't match such entities.
        """
        ...
```

- [ ] **Step 2: Update the toy matchers to implement the new methods**

In `tests/core/helpers/toy_taxonomy.py`, extend `ToyShapesMatcher` and `ToyActorsMatcher`:

```python
@dataclass
class ToyShapesMatcher:
    things: list[ToyThing] = field(default_factory=list)

    def match_type(self, type_name: str, context: Any = None) -> list[ToyThing]:
        return [t for t in self.things if t.type_name == type_name]

    def children(self, parent: ToyThing, child_type: str) -> list[ToyThing]:
        return [
            t for t in self.things if t.type_name == child_type and t.parent_id == parent.id
        ]

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        return False

    def get_attribute(self, entity: ToyThing, name: str) -> Any:
        return getattr(entity, name, None)

    def get_id(self, entity: ToyThing) -> str | None:
        return entity.id
```

Same pattern for `ToyActorsMatcher`:

```python
    def get_attribute(self, entity: ToyActor, name: str) -> Any:
        return getattr(entity, name, None)

    def get_id(self, entity: ToyActor) -> str | None:
        return entity.id
```

- [ ] **Step 3: Write the failing test**

Create `tests/core/test_selector_match_simple.py`:

```python
"""Tests for simple-selector predicate matching."""

from __future__ import annotations

from umwelt.parser import parse
from umwelt.registry import registry_scope
from umwelt.selector.match import match_simple
from tests.core.helpers.toy_taxonomy import (
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)


def _things():
    return [
        ToyThing(type_name="thing", id="alpha", color="red"),
        ToyThing(type_name="thing", id="beta", color="blue"),
        ToyThing(type_name="thing", id="gamma", color="red"),
    ]


def test_match_bare_type_returns_all():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing { }")
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert len(matched) == 3


def test_match_id_filters_by_name():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing#beta { }")
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert len(matched) == 1
    assert matched[0].id == "beta"


def test_match_attribute_equals():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color="red"] { }')
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert {t.id for t in matched} == {"alpha", "gamma"}


def test_match_attribute_prefix():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color^="r"] { }')
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert {t.id for t in matched} == {"alpha", "gamma"}


def test_match_attribute_suffix():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color$="ue"] { }')
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert {t.id for t in matched} == {"beta"}


def test_match_attribute_substring():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color*="lu"] { }')
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert {t.id for t in matched} == {"beta"}


def test_match_multiple_attributes_are_anded():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color="red"][id^="al"] { }')
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert {t.id for t in matched} == {"alpha"}


def test_match_attribute_absent_excludes():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing[missing] { }")
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert matched == []


def test_match_universal_returns_all_candidates():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("* { }")
    simple = view.rules[0].selectors[0].parts[0].selector
    matched = match_simple(simple, shapes, shapes.things)
    assert len(matched) == 3
```

- [ ] **Step 4: Implement `match_simple`**

Create `src/umwelt/selector/match.py`:

```python
"""Selector matching against a matcher's world.

`match_simple(simple, matcher, candidates)` returns the subset of
`candidates` that satisfy a simple selector's predicates (id, classes,
attribute filters, pseudo-classes).

`match_complex(complex_sel, registry, eval_context)` walks a compound
selector using the combinator mode classification: structural parts
navigate parent/child relationships via `matcher.children`, context
parts gate the rule via `matcher.condition_met`.
"""

from __future__ import annotations

import fnmatch
from typing import Any

from umwelt.ast import AttrFilter, PseudoClass, SimpleSelector
from umwelt.registry.matchers import MatcherProtocol


def match_simple(
    simple: SimpleSelector,
    matcher: MatcherProtocol,
    candidates: list[Any],
) -> list[Any]:
    """Return candidates satisfying the simple selector's predicates."""
    return [c for c in candidates if _matches_simple(simple, matcher, c)]


def _matches_simple(
    simple: SimpleSelector, matcher: MatcherProtocol, entity: Any
) -> bool:
    # Type check (for non-universal selectors, the caller is responsible
    # for ensuring candidates are of the right type).
    if simple.id_value is not None:
        if matcher.get_id(entity) != simple.id_value:
            return False
    for attr in simple.attributes:
        if not _matches_attribute(attr, matcher, entity):
            return False
    for pseudo in simple.pseudo_classes:
        if not _matches_pseudo(pseudo, matcher, entity):
            return False
    return True


def _matches_attribute(
    attr: AttrFilter, matcher: MatcherProtocol, entity: Any
) -> bool:
    value = matcher.get_attribute(entity, attr.name)
    if value is None:
        return False
    if attr.op is None:
        return True  # [attr] — existence check
    expected = attr.value or ""
    str_value = str(value)
    if attr.op == "=":
        return str_value == expected
    if attr.op == "^=":
        return str_value.startswith(expected)
    if attr.op == "$=":
        return str_value.endswith(expected)
    if attr.op == "*=":
        return expected in str_value
    if attr.op == "~=":
        return expected in str_value.split()
    if attr.op == "|=":
        return str_value == expected or str_value.startswith(expected + "-")
    return False


def _matches_pseudo(
    pseudo: PseudoClass, matcher: MatcherProtocol, entity: Any
) -> bool:
    if pseudo.name == "glob":
        # :glob("pattern") — match the entity's path/name against fnmatch.
        # The matcher's "name" or "path" attribute is the subject.
        pattern = (pseudo.argument or "").strip().strip('"').strip("'")
        # Prefer a "path" attribute; fall back to "name" if absent.
        value = matcher.get_attribute(entity, "path") or matcher.get_attribute(
            entity, "name"
        )
        if value is None:
            return False
        return fnmatch.fnmatchcase(str(value), pattern)
    if pseudo.name == "not":
        # :not(inner) — Task 19 extends this with full sub-selector evaluation.
        # For now, Task 18 only handles simple :not with an attribute filter
        # inside — the argument is the serialized inner selector text.
        # v0.1-core keeps :not as a declarative-only stub.
        return True
    return True  # Unknown pseudo-classes are treated as always-match in v0.1.
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/core/test_selector_match_simple.py -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean. (You may need to update the `NullMatcher` in `test_registry_matchers.py` to add `get_attribute` and `get_id` stubs.)

- [ ] **Step 6: Commit**

```bash
git add src/umwelt/selector/match.py src/umwelt/registry/matchers.py tests/core/helpers/toy_taxonomy.py tests/core/test_selector_match_simple.py tests/core/test_registry_matchers.py
git commit -m "$(cat <<'EOF'
feat(selector): implement simple-selector predicate matching

match_simple filters a candidate list by id (matcher.get_id),
attribute filters (matcher.get_attribute), and pseudo-classes.
The :glob("pattern") pseudo-class uses fnmatch against a "path"
or "name" attribute. Attribute operators =, ^=, $=, *=, ~=, |=
are all supported with the usual CSS semantics.

MatcherProtocol gains get_attribute and get_id as the bridge
between the selector engine and the matcher's opaque entities.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 19: Selector match engine — compound selectors with structural and context modes

**Files:**
- Modify: `src/umwelt/selector/match.py` (add `match_complex`)
- Create: `tests/core/test_selector_match_complex.py`

**Context:** `match_complex(complex_sel, registry, eval_context)` walks the compound parts left-to-right. For each part:

- **root** / first structural-ish part: call `matcher.match_type(type_name)`, then filter via `match_simple`. Establishes the initial entity set.
- **structural**: for each current entity, call `matcher.children(entity, child_type_name)`; collect and filter.
- **context**: consult `qualifier_matcher.condition_met(selector, eval_context)`. If False → return `[]`. If True → continue with the current entity set unchanged.

The `registry` argument is a small adapter with `get_matcher(taxon)` — tests pass the globally-registered matchers indirectly through `registry_scope()`.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_selector_match_complex.py`:

```python
"""Tests for compound-selector matching with structural and context modes."""

from __future__ import annotations

from umwelt.parser import parse
from umwelt.registry import get_matcher, registry_scope
from umwelt.selector.match import match_complex
from tests.core.helpers.toy_taxonomy import (
    ToyActor,
    ToyActorsMatcher,
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)


def _things_with_widgets():
    return [
        ToyThing(type_name="thing", id="alpha", color="red"),
        ToyThing(type_name="widget", id="w1", color="red", parent_id="alpha"),
        ToyThing(type_name="widget", id="w2", color="blue", parent_id="alpha"),
        ToyThing(type_name="thing", id="beta", color="blue"),
        ToyThing(type_name="widget", id="w3", color="red", parent_id="beta"),
    ]


def test_structural_descendant_matches_children():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing widget { }")
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    # Every widget has a thing parent, so all three widgets match.
    assert {w.id for w in matched} == {"w1", "w2", "w3"}


def test_structural_with_attribute_on_parent():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing[color="red"] widget { }')
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    # Only alpha (red) → widgets w1, w2.
    assert {w.id for w in matched} == {"w1", "w2"}


def test_structural_with_attribute_on_child():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse('thing widget[color="red"] { }')
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    # Red widgets: w1, w3.
    assert {w.id for w in matched} == {"w1", "w3"}


def test_context_qualifier_met():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset({"admin"}),
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse('actor[role="admin"] thing { }')
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    # The qualifier is met, so all things match.
    assert {t.id for t in matched} == {"alpha", "beta"}


def test_context_qualifier_unmet():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset(),  # no active actor
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse('actor[role="admin"] thing { }')
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    assert matched == []


def test_three_level_compound():
    shapes = ToyShapesMatcher(things=_things_with_widgets())
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset({"admin"}),
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse('actor[role="admin"] thing widget { }')
        complex_sel = view.rules[0].selectors[0]
        matched = match_complex(complex_sel, _registry_adapter(), eval_context=None)
    # Qualifier met; navigate thing → widget for all things.
    assert {w.id for w in matched} == {"w1", "w2", "w3"}


class _TestRegistryAdapter:
    def get_matcher(self, taxon: str):
        return get_matcher(taxon)


def _registry_adapter():
    return _TestRegistryAdapter()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_selector_match_complex.py -v`
Expected: `ImportError` on `match_complex`.

- [ ] **Step 3: Implement `match_complex`**

Append to `src/umwelt/selector/match.py`:

```python
from umwelt.ast import ComplexSelector


class _RegistryAdapter:
    """Thin adapter around the plugin registry for selector matching."""

    def get_matcher(self, taxon: str) -> MatcherProtocol:
        from umwelt.registry import get_matcher

        return get_matcher(taxon)


def match_complex(
    complex_sel: ComplexSelector,
    registry: Any | None = None,
    eval_context: Any = None,
) -> list[Any]:
    """Walk a compound selector and return the final matched entity set.

    `registry` is any object with a `get_matcher(taxon) -> MatcherProtocol`
    method. If None, the global registry is used directly.
    `eval_context` is passed to cross-taxon context qualifiers.
    """
    registry = registry or _RegistryAdapter()
    current: list[Any] | None = None
    for part in complex_sel.parts:
        if part.mode == "context":
            qualifier_matcher = registry.get_matcher(part.selector.taxon)
            if not qualifier_matcher.condition_met(part.selector, eval_context):
                return []
            continue

        matcher = registry.get_matcher(part.selector.taxon)
        if current is None:
            # First structural/root part: start the navigation.
            type_name = part.selector.type_name or "*"
            if type_name == "*":
                # Universal — the matcher doesn't know about * natively; use
                # a best-effort approach: match every type the matcher owns.
                candidates: list[Any] = []
                # v0.1 approach: expect the matcher to treat match_type("*") as
                # "every entity." Matchers that don't support * should document.
                candidates = matcher.match_type("*")
            else:
                candidates = matcher.match_type(type_name)
        else:
            # Subsequent structural part: navigate from the previous frontier.
            type_name = part.selector.type_name or "*"
            candidates = []
            for parent in current:
                candidates.extend(matcher.children(parent, type_name))

        current = [c for c in candidates if _matches_simple(part.selector, matcher, c)]
        if not current:
            return []

    return current or []
```

Extend the toy matchers' `match_type` to handle `"*"`:

```python
    def match_type(self, type_name: str, context: Any = None) -> list[ToyThing]:
        if type_name == "*":
            return list(self.things)
        return [t for t in self.things if t.type_name == type_name]
```

Same for `ToyActorsMatcher`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_selector_match_complex.py tests/core/ -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/selector/match.py tests/core/helpers/toy_taxonomy.py tests/core/test_selector_match_complex.py
git commit -m "$(cat <<'EOF'
feat(selector): walk compound selectors with structural + context modes

match_complex walks the parts of a ComplexSelector left-to-right.
Root/structural parts accumulate a candidate set via
matcher.match_type (first part) and matcher.children (subsequent).
Context parts gate: if matcher.condition_met returns False, the
rule drops entirely (returns []); otherwise navigation continues
with the current entity set.

This is the full actor-conditioned policy evaluation from the
selector-semantics decisions: one view can express rules like
'actor[role=admin] thing widget' and the match engine correctly
navigates the thing -> widget hierarchy only when the admin actor
qualifier is met in the eval_context.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: Cascade resolver

**Files:**
- Create: `src/umwelt/cascade/__init__.py`
- Create: `src/umwelt/cascade/resolver.py`
- Create: `tests/core/test_cascade.py`

**Context:** `resolve(view, eval_context) -> ResolvedView` walks every rule, runs `match_complex` to find the rule's target entities, groups results by target taxon, and for each `(taxon, entity, property)` picks the winning rule via CSS specificity (with document order as tiebreaker). Property-level cascade means one rule can win on one property while another rule wins on a different property for the same entity.

`ResolvedView` is a typed dict shape: `{taxon_name: {entity_handle: {property_name: value}}}` — but since entity handles are matcher-specific and not hashable in general, we use a list-of-entries representation per taxon instead.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_cascade.py`:

```python
"""Tests for the cascade resolver."""

from __future__ import annotations

from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import (
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)


def _things():
    return [
        ToyThing(type_name="thing", id="alpha", color="red"),
        ToyThing(type_name="thing", id="beta", color="blue"),
    ]


def _get(resolved, taxon, entity_id, prop):
    for e, props in resolved.entries(taxon):
        if e.id == entity_id:
            return props.get(prop)
    return None


def test_single_rule_sets_property():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing { paint: green; }")
        resolved = resolve(view)
    assert _get(resolved, "shapes", "alpha", "paint") == "green"
    assert _get(resolved, "shapes", "beta", "paint") == "green"


def test_specificity_wins():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            "thing { paint: green; } "
            'thing[color="red"] { paint: crimson; }'
        )
        resolved = resolve(view)
    # alpha is red; the more specific rule wins.
    assert _get(resolved, "shapes", "alpha", "paint") == "crimson"
    # beta is blue; only the first rule applies.
    assert _get(resolved, "shapes", "beta", "paint") == "green"


def test_document_order_breaks_specificity_ties():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            'thing[color="red"] { paint: crimson; } '
            'thing[color="red"] { paint: scarlet; }'
        )
        resolved = resolve(view)
    # Both rules have equal specificity; later wins.
    assert _get(resolved, "shapes", "alpha", "paint") == "scarlet"


def test_property_level_cascade():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            "thing { paint: green; max-glow: 100; } "
            'thing#alpha { paint: crimson; }'
        )
        resolved = resolve(view)
    # alpha wins paint from the id rule; max-glow still from the base rule.
    assert _get(resolved, "shapes", "alpha", "paint") == "crimson"
    assert _get(resolved, "shapes", "alpha", "max-glow") == "100"
    # beta gets both from the base rule.
    assert _get(resolved, "shapes", "beta", "paint") == "green"
    assert _get(resolved, "shapes", "beta", "max-glow") == "100"


def test_per_taxon_scoping():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing { paint: green; } actor { allowed: true; }")
        resolved = resolve(view)
    # shapes cascade has thing rules.
    assert _get(resolved, "shapes", "alpha", "paint") == "green"
    # actors cascade is independent; no shapes rule can affect it.
    assert list(resolved.entries("actors")) == []  # no matched actors in the toy world


def test_union_selector_distributes():
    shapes = ToyShapesMatcher(things=_things())
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            'thing[color="red"], thing[color="blue"] { paint: bright; }'
        )
        resolved = resolve(view)
    assert _get(resolved, "shapes", "alpha", "paint") == "bright"
    assert _get(resolved, "shapes", "beta", "paint") == "bright"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_cascade.py -v`
Expected: `ImportError` on `umwelt.cascade.resolver`.

- [ ] **Step 3: Implement the cascade resolver**

Create `src/umwelt/cascade/__init__.py`:

```python
"""Cascade resolver."""

from umwelt.cascade.resolver import ResolvedView, resolve

__all__ = ["ResolvedView", "resolve"]
```

Create `src/umwelt/cascade/resolver.py`:

```python
"""Per-taxon cascade resolver.

Walks every rule in a parsed View, evaluates selectors via match_complex,
groups results by the rule's target_taxon, and for each
(entity, property) picks the winning rule via CSS specificity with
document order as the tiebreaker.

The output is a ResolvedView, keyed by taxon. Each taxon's contents is
a list of (entity, {property: value}) pairs — a list rather than a dict
because entity handles are opaque and not necessarily hashable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from umwelt.ast import ComplexSelector, RuleBlock, View
from umwelt.selector.match import match_complex


@dataclass(frozen=True)
class _RuleApplication:
    rule_index: int
    selector_index: int
    specificity: tuple[int, int, int]
    rule: RuleBlock
    selector: ComplexSelector


@dataclass
class ResolvedView:
    """Cascade-resolved view: per-taxon, per-entity, per-property values."""

    _by_taxon: dict[str, list[tuple[Any, dict[str, str]]]] = field(default_factory=dict)

    def entries(self, taxon: str) -> Iterator[tuple[Any, dict[str, str]]]:
        """Iterate (entity, {property: value}) pairs for a taxon."""
        for pair in self._by_taxon.get(taxon, []):
            yield pair

    def add(self, taxon: str, entity: Any, properties: dict[str, str]) -> None:
        self._by_taxon.setdefault(taxon, []).append((entity, properties))

    def taxa(self) -> list[str]:
        return list(self._by_taxon.keys())


def resolve(view: View, eval_context: Any = None) -> ResolvedView:
    """Resolve a parsed view through per-taxon CSS cascade."""
    # 1. Expand the view's rules into one application per (rule, selector),
    # tagged with document order and specificity.
    apps: list[_RuleApplication] = []
    for r_idx, rule in enumerate(view.rules):
        for s_idx, sel in enumerate(rule.selectors):
            apps.append(
                _RuleApplication(
                    rule_index=r_idx,
                    selector_index=s_idx,
                    specificity=sel.specificity,
                    rule=rule,
                    selector=sel,
                )
            )

    # 2. For each application, evaluate the selector and collect matched
    # entities grouped by the rule's target taxon.
    # Per-taxon accumulator: list of (entity_key, entity, matching_applications)
    per_taxon: dict[str, list[tuple[int, Any, list[_RuleApplication]]]] = {}
    for app in apps:
        matched = match_complex(app.selector, eval_context=eval_context)
        for entity in matched:
            key = id(entity)  # entities are not generally hashable
            bucket = per_taxon.setdefault(app.selector.target_taxon, [])
            # Find or create the slot for this entity.
            slot: list[_RuleApplication] | None = None
            for k, _e, lst in bucket:
                if k == key:
                    slot = lst
                    break
            if slot is None:
                slot = []
                bucket.append((key, entity, slot))
            slot.append(app)

    # 3. For each (taxon, entity), run the property-level cascade.
    resolved = ResolvedView()
    for taxon, bucket in per_taxon.items():
        for _key, entity, applications in bucket:
            properties: dict[str, str] = {}
            # Determine the winner per property.
            winners: dict[str, _RuleApplication] = {}
            for app in applications:
                for decl in app.rule.declarations:
                    current = winners.get(decl.property_name)
                    if current is None:
                        winners[decl.property_name] = app
                        continue
                    # Compare specificity; ties go to later document order.
                    if app.specificity > current.specificity:
                        winners[decl.property_name] = app
                    elif app.specificity == current.specificity:
                        if (app.rule_index, app.selector_index) > (
                            current.rule_index,
                            current.selector_index,
                        ):
                            winners[decl.property_name] = app
            # Collect the winning declaration values.
            for prop_name, app in winners.items():
                # Find the declaration with this property name in the winning rule.
                for decl in app.rule.declarations:
                    if decl.property_name == prop_name:
                        # For multi-value lists, join with commas; for
                        # single-value, use the value directly.
                        if len(decl.values) == 1:
                            properties[prop_name] = decl.values[0]
                        else:
                            properties[prop_name] = ", ".join(decl.values)
                        break
            resolved.add(taxon, entity, properties)

    return resolved
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_cascade.py tests/core/ -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/cascade/ tests/core/test_cascade.py
git commit -m "$(cat <<'EOF'
feat(cascade): per-taxon resolver with property-level CSS cascade

resolve(view, eval_context) walks every rule, evaluates selectors
via match_complex, groups matched entities by target_taxon, and
runs per-property cascade: specificity wins; document order breaks
ties. Different properties on the same entity can come from different
rules — property-level cascade, not whole-rule cascade.

ResolvedView holds a list of (entity, {property: value}) per taxon
because entity handles are opaque and not necessarily hashable.
entries(taxon) and taxa() let consumers walk the result.

Union selectors (comma-separated) are distributed automatically
because the resolver iterates per-selector within a rule.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 21: Comparison-prefix properties in cascade

**Files:**
- Create: `tests/core/test_cascade_comparison.py`

**Context:** The parser already parses declarations with any property name, and the registry holds comparison metadata for properties registered with a non-`exact` comparison. The cascade resolver stores whichever declared value wins. No new production code — this task locks in the behavior as a regression test and verifies the integration from parse → cascade → value-with-comparison-metadata.

- [ ] **Step 1: Write the test**

Create `tests/core/test_cascade_comparison.py`:

```python
"""Integration tests: comparison-prefix properties flow through parse → cascade."""

from __future__ import annotations

from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import get_property, registry_scope
from tests.core.helpers.toy_taxonomy import (
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)


def _get(resolved, taxon, entity_id, prop):
    for e, props in resolved.entries(taxon):
        if e.id == entity_id:
            return props.get(prop)
    return None


def test_max_property_parsed_and_cascaded():
    shapes = ToyShapesMatcher(
        things=[ToyThing(type_name="thing", id="alpha", color="red")]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse("thing { max-glow: 100; }")
        resolved = resolve(view)
    assert _get(resolved, "shapes", "alpha", "max-glow") == "100"


def test_comparison_metadata_is_queryable():
    with registry_scope():
        install_toy_taxonomy()
        prop = get_property("shapes", "thing", "max-glow")
        assert prop.comparison == "<="
        assert prop.value_attribute == "glow_level"


def test_max_cascades_by_specificity_not_by_value():
    # The cascade picks the winning rule by specificity, not by "tightest
    # value". A later low-specificity max-glow: 50 does not override an
    # earlier high-specificity max-glow: 200.
    shapes = ToyShapesMatcher(
        things=[ToyThing(type_name="thing", id="alpha", color="red")]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            'thing[color="red"] { max-glow: 200; } '
            "thing { max-glow: 50; }"
        )
        resolved = resolve(view)
    # The attribute-selector rule is more specific; it wins regardless of value.
    assert _get(resolved, "shapes", "alpha", "max-glow") == "200"


def test_exact_and_max_properties_cascade_independently():
    shapes = ToyShapesMatcher(
        things=[ToyThing(type_name="thing", id="alpha", color="red")]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        view = parse(
            "thing { paint: green; max-glow: 100; } "
            "thing#alpha { paint: crimson; }"
        )
        resolved = resolve(view)
    # paint won by the id rule; max-glow stays from the base rule.
    assert _get(resolved, "shapes", "alpha", "paint") == "crimson"
    assert _get(resolved, "shapes", "alpha", "max-glow") == "100"
```

- [ ] **Step 2: Run**

Run: `pytest tests/core/test_cascade_comparison.py -v`
Expected: all pass (no production changes needed; this test locks in existing behavior).

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_cascade_comparison.py
git commit -m "$(cat <<'EOF'
test(cascade): lock in comparison-prefix property behavior

Integration tests asserting that max-*/min-*/only-*/etc. properties
flow through parse -> cascade correctly: their declared values are
preserved in ResolvedView, the registry holds the comparison
metadata queryable via get_property, and cascade picks the winning
rule by specificity regardless of which value is "tighter." That
last point matters for the ratchet: cascade is about rule priority,
not monotonic tightening.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 22: Pattern-valued properties

**Files:**
- Create: `tests/core/test_cascade_patterns.py`

**Context:** Pattern properties (`allow-pattern`, `deny-pattern`, `only-match`) are declarations with comma-separated values, parsed into `Declaration.values` as a tuple of strings. The parser already handles this from Task 10; the registry already supports `comparison="pattern-in"` from Task 6. This task adds integration tests that verify end-to-end round-trip.

- [ ] **Step 1: Write the test**

Create `tests/core/test_cascade_patterns.py`:

```python
"""Integration tests: pattern-valued declarations round-trip through cascade."""

from __future__ import annotations

from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import (
    AttrSchema,
    register_entity,
    register_property,
    register_taxon,
    registry_scope,
)
from tests.core.helpers.toy_taxonomy import (
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)


def _install_pattern_property():
    """Register shapes/thing + an allow-pattern pattern property."""
    install_toy_taxonomy()
    register_property(
        taxon="shapes",
        entity="thing",
        name="allow-pattern",
        value_type=list,
        comparison="pattern-in",
        description="glob patterns allowed for this thing",
    )


def _get(resolved, taxon, entity_id, prop):
    for e, props in resolved.entries(taxon):
        if e.id == entity_id:
            return props.get(prop)
    return None


def test_single_pattern_value():
    shapes = ToyShapesMatcher(
        things=[ToyThing(type_name="thing", id="alpha", color="red")]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        register_property(
            taxon="shapes",
            entity="thing",
            name="allow-pattern",
            value_type=list,
            comparison="pattern-in",
            description="glob allowlist",
        )
        view = parse('thing { allow-pattern: "git *"; }')
        resolved = resolve(view)
    assert _get(resolved, "shapes", "alpha", "allow-pattern") == "git *"


def test_multiple_pattern_values_comma_separated():
    shapes = ToyShapesMatcher(
        things=[ToyThing(type_name="thing", id="alpha", color="red")]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        register_property(
            taxon="shapes",
            entity="thing",
            name="allow-pattern",
            value_type=list,
            comparison="pattern-in",
            description="glob allowlist",
        )
        view = parse(
            'thing { allow-pattern: "git *", "pytest *", "ruff *"; }'
        )
    decls = view.rules[0].declarations
    assert decls[0].values == ("git *", "pytest *", "ruff *")
    resolved = resolve(view)
    # The cascade resolver joins multi-value properties with ", " by default.
    assert _get(resolved, "shapes", "alpha", "allow-pattern") == "git *, pytest *, ruff *"


def test_pattern_cascades_with_specificity():
    shapes = ToyShapesMatcher(
        things=[
            ToyThing(type_name="thing", id="alpha", color="red"),
            ToyThing(type_name="thing", id="beta", color="blue"),
        ]
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes)
        register_property(
            taxon="shapes",
            entity="thing",
            name="allow-pattern",
            value_type=list,
            comparison="pattern-in",
            description="glob allowlist",
        )
        view = parse(
            'thing { allow-pattern: "*"; } '
            'thing[color="red"] { allow-pattern: "git *", "pytest *"; }'
        )
        resolved = resolve(view)
    # alpha (red) gets the more specific rule.
    assert _get(resolved, "shapes", "alpha", "allow-pattern") == "git *, pytest *"
    # beta gets the base rule.
    assert _get(resolved, "shapes", "beta", "allow-pattern") == "*"
```

- [ ] **Step 2: Run**

Run: `pytest tests/core/test_cascade_patterns.py -v`
Expected: all pass (no production changes needed).

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_cascade_patterns.py
git commit -m "$(cat <<'EOF'
test(cascade): lock in pattern-valued property round-trip

allow-pattern / deny-pattern / only-match are declarations with
comma-separated glob values. The parser produces tuples of string
values (Task 10 already handled the splitting); the registry stores
them with comparison='pattern-in'; the cascade resolver joins
multi-value declarations with ', ' when presenting them in
ResolvedView. Consumers that realize pattern properties at runtime
(claude-plugins hooks, kibitzer-hooks) handle the glob matching
themselves — the core layer stays declarative.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 23: Compound-selector cascade with context qualifiers

**Files:**
- Create: `tests/core/test_cascade_compound.py`

**Context:** The cascade resolver uses `match_complex` to evaluate every selector, which already handles context qualifiers correctly (Task 19). This task adds integration tests that exercise the full pipeline: parse a view with cross-taxon compound selectors, evaluate against a toy world where the qualifier is / isn't met, and verify the cascade outcome matches the selector-semantics spec (target-taxon scoping, specificity accumulation).

- [ ] **Step 1: Write the test**

Create `tests/core/test_cascade_compound.py`:

```python
"""Integration tests: compound selectors drive cascade correctly."""

from __future__ import annotations

from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import registry_scope
from tests.core.helpers.toy_taxonomy import (
    ToyActor,
    ToyActorsMatcher,
    ToyShapesMatcher,
    ToyThing,
    install_toy_taxonomy,
)


def _world():
    shapes = ToyShapesMatcher(
        things=[
            ToyThing(type_name="thing", id="alpha", color="red"),
            ToyThing(type_name="thing", id="beta", color="blue"),
        ]
    )
    return shapes


def _get(resolved, taxon, entity_id, prop):
    for e, props in resolved.entries(taxon):
        if e.id == entity_id:
            return props.get(prop)
    return None


def test_context_qualifier_met_applies_rule():
    shapes = _world()
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset({"admin"}),
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse(
            "thing { paint: green; } "
            'actor[role="admin"] thing { paint: admin-only; }'
        )
        resolved = resolve(view)
    # Qualifier met: admin rule wins on specificity (compound adds to it).
    assert _get(resolved, "shapes", "alpha", "paint") == "admin-only"
    assert _get(resolved, "shapes", "beta", "paint") == "admin-only"


def test_context_qualifier_unmet_drops_rule():
    shapes = _world()
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset(),  # no active actor
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse(
            "thing { paint: green; } "
            'actor[role="admin"] thing { paint: admin-only; }'
        )
        resolved = resolve(view)
    # Qualifier unmet: the compound rule drops, the base rule wins.
    assert _get(resolved, "shapes", "alpha", "paint") == "green"
    assert _get(resolved, "shapes", "beta", "paint") == "green"


def test_target_taxon_from_compound_is_rightmost():
    shapes = _world()
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset({"admin"}),
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse('actor[role="admin"] thing { paint: admin-only; }')
        resolved = resolve(view)
    # The rule targets the shapes taxon even though the qualifier
    # references the actors taxon.
    shapes_entries = list(resolved.entries("shapes"))
    actors_entries = list(resolved.entries("actors"))
    assert len(shapes_entries) == 2
    assert actors_entries == []


def test_compound_specificity_beats_simple_specificity():
    shapes = _world()
    actors = ToyActorsMatcher(
        actors=[ToyActor(type_name="actor", id="admin", role="admin")],
        active_ids=frozenset({"admin"}),
    )
    with registry_scope():
        install_toy_taxonomy(shapes_matcher=shapes, actors_matcher=actors)
        view = parse(
            # specificity (0,1,1): [color] + type
            'thing[color="red"] { paint: bright-red; } '
            # specificity (0,2,2): [role] + type + [role] + type ??? actually
            # (1 attr on actor) + (0 on thing) + (1 actor type) + (1 thing type)
            # = (0, 1, 2)
            'actor[role="admin"] thing { paint: admin-only; }'
        )
        resolved = resolve(view)
    # For alpha (red): both rules match; compound has (0,1,2) vs simple (0,1,1).
    # Compound wins.
    assert _get(resolved, "shapes", "alpha", "paint") == "admin-only"
    # For beta (blue): only the compound rule matches.
    assert _get(resolved, "shapes", "beta", "paint") == "admin-only"
```

- [ ] **Step 2: Run**

Run: `pytest tests/core/test_cascade_compound.py tests/core/ -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_cascade_compound.py
git commit -m "$(cat <<'EOF'
test(cascade): integration tests for compound-selector cascade

Verifies the selector-semantics spec end-to-end: compound selectors
targeting a rightmost entity drive cascade in that entity's taxon
regardless of which other taxa the qualifier references, context
qualifiers gate rule inclusion (unmet -> rule drops; met -> rule
participates with its compound specificity), and compound specificity
correctly accumulates so cross-taxon qualifiers beat simple same-taxon
attribute filters.

This locks in the invariant that actor-conditioned policy expressed
via compound selectors is equivalent to writing separate rules per
actor, but with the cascade machinery doing the gating automatically.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Slice 4 — Compiler protocol, CLI, utilities, acceptance

### Task 24: Compiler protocol and registry

**Files:**
- Create: `src/umwelt/compilers/__init__.py`
- Create: `src/umwelt/compilers/protocol.py`
- Modify: `src/umwelt/registry/taxa.py` (no code change, just allow a `compilers` field if you want to centralize — alternative: keep compilers in their own module-level dict since they're not taxon-scoped)
- Create: `tests/core/test_compiler_protocol.py`

**Context:** Compilers are registered globally, not per-taxon, because one compiler (e.g. `nsjail`) may consume rules from multiple taxa (`world`, `state`). We keep the compiler registry in `compilers/protocol.py` as a module-level dict rather than a field on `RegistryState`; the trade-off is that compiler registration is not scope-overridable the same way taxon registration is. For test isolation, `clear_compilers()` is provided.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_compiler_protocol.py`:

```python
"""Tests for the Compiler protocol and registry."""

from __future__ import annotations

from typing import Any

import pytest

from umwelt.cascade.resolver import ResolvedView
from umwelt.compilers import (
    Compiler,
    available,
    clear_compilers,
    get as get_compiler,
    register as register_compiler,
)
from umwelt.errors import RegistryError


class _NullCompiler:
    target_name = "null"
    target_format = "str"
    altitude = "semantic"

    def compile(self, view: ResolvedView) -> str:
        return ""


class _EchoCompiler:
    target_name = "echo"
    target_format = "list"
    altitude = "os"

    def compile(self, view: ResolvedView) -> list[str]:
        return [taxon for taxon in view.taxa()]


def test_register_and_get():
    clear_compilers()
    register_compiler("null", _NullCompiler())
    assert get_compiler("null").target_name == "null"


def test_available_lists_registered_names():
    clear_compilers()
    register_compiler("null", _NullCompiler())
    register_compiler("echo", _EchoCompiler())
    assert set(available()) == {"null", "echo"}


def test_unknown_compiler_raises():
    clear_compilers()
    with pytest.raises(RegistryError, match="no compiler registered"):
        get_compiler("ghost")


def test_duplicate_registration_last_wins_with_warning(recwarn):
    clear_compilers()
    register_compiler("null", _NullCompiler())
    register_compiler("null", _NullCompiler())
    # At least one warning emitted.
    assert any("already registered" in str(w.message) for w in recwarn.list)


def test_clear_compilers_empties_registry():
    register_compiler("null", _NullCompiler())
    clear_compilers()
    assert available() == []


def test_protocol_runtime_check():
    assert isinstance(_NullCompiler(), Compiler)
    assert isinstance(_EchoCompiler(), Compiler)


def test_compile_against_resolved_view():
    clear_compilers()
    register_compiler("echo", _EchoCompiler())
    rv = ResolvedView()
    rv.add("world", object(), {"editable": "true"})
    rv.add("capability", object(), {"allow": "true"})
    compiler = get_compiler("echo")
    result = compiler.compile(rv)
    assert set(result) == {"world", "capability"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_compiler_protocol.py -v`
Expected: `ModuleNotFoundError: No module named 'umwelt.compilers'`.

- [ ] **Step 3: Implement the protocol and registry**

Create `src/umwelt/compilers/protocol.py`:

```python
"""Compiler protocol and registry.

Core umwelt ships zero concrete compilers. The sandbox consumer (and
third-party consumers) register theirs via `register(name, compiler)`
at import time.
"""

from __future__ import annotations

import warnings
from typing import Any, Literal, Protocol, runtime_checkable

from umwelt.cascade.resolver import ResolvedView
from umwelt.errors import RegistryError

Altitude = Literal["os", "language", "semantic", "conversational"]


@runtime_checkable
class Compiler(Protocol):
    """A compiler translates a ResolvedView to a target's native config.

    Compilers MUST:
      - Be pure (same ResolvedView -> same output).
      - Have no hard runtime dependency on the target tool's Python wrapper.
      - Declare an altitude.
      - Silently drop rules they cannot realize (out-of-altitude context
        qualifiers, unrealized pattern properties, unknown taxa).
    """

    target_name: str
    target_format: str
    altitude: Altitude

    def compile(self, view: ResolvedView) -> str | list[str] | dict:
        ...


_REGISTRY: dict[str, Compiler] = {}


def register(name: str, compiler: Compiler) -> None:
    """Register a compiler under `name`. Duplicate registration warns."""
    if name in _REGISTRY:
        warnings.warn(
            f"compiler {name!r} already registered; replacing",
            stacklevel=2,
        )
    _REGISTRY[name] = compiler


def get(name: str) -> Compiler:
    """Look up a registered compiler by name."""
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise RegistryError(f"no compiler registered for target {name!r}") from exc


def available() -> list[str]:
    """Return the sorted list of registered compiler names."""
    return sorted(_REGISTRY.keys())


def clear_compilers() -> None:
    """Empty the compiler registry. For test isolation."""
    _REGISTRY.clear()
```

Create `src/umwelt/compilers/__init__.py`:

```python
"""The compiler protocol and registry for enforcement targets.

Core umwelt ships zero concrete compilers. Consumers register theirs
via register() at import time.
"""

from umwelt.compilers.protocol import (
    Altitude,
    Compiler,
    available,
    clear_compilers,
    get,
    register,
)

__all__ = [
    "Altitude",
    "Compiler",
    "available",
    "clear_compilers",
    "get",
    "register",
]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_compiler_protocol.py tests/core/ -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/compilers/ tests/core/test_compiler_protocol.py
git commit -m "$(cat <<'EOF'
feat(compilers): add Compiler protocol + registry with altitude

Compiler is a runtime-checkable Protocol with target_name,
target_format, and altitude class attributes plus a compile()
method that takes a ResolvedView and returns the target's native
format (str, list, or dict).

The registry is module-global with register/get/available and a
clear_compilers helper for test isolation. Duplicate registration
warns (last-write-wins) rather than raising — this matches the
v0.1 decision to prefer warnings over errors for forward compat.

No concrete compilers ship in core; the sandbox consumer and third
parties register theirs at import time.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 25: CLI — `umwelt parse` and `umwelt inspect`

**Files:**
- Create: `src/umwelt/cli.py`
- Create: `src/umwelt/inspect_util.py`
- Create: `tests/core/test_cli.py`
- Create: `tests/core/fixtures/toy.umw`

**Context:** The CLI is argparse-based and dispatches to sub-commands. v0.1-core ships three: `parse`, `inspect`, `check`. This task handles `parse` and `inspect`; Task 26 adds `check`. The CLI needs a fixture view file that uses the toy taxonomy — but the toy taxonomy is registered in test code, not imported as a real package. For the CLI tests, we use a small shim: an environment variable `UMWELT_PRELOAD_TOY=1` that imports the test helper and calls `install_toy_taxonomy()` before running the command.

- [ ] **Step 1: Create the CLI fixture**

Create `tests/core/fixtures/toy.umw`:

```
# A toy view against the test taxonomy.
thing { paint: green; max-glow: 100; }
thing#alpha { paint: crimson; }
thing[color="blue"] { paint: navy; }
```

- [ ] **Step 2: Write the failing test**

Create `tests/core/test_cli.py`:

```python
"""Tests for the umwelt CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "toy.umw"


def _run(args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["UMWELT_PRELOAD_TOY"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "umwelt.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_parse_prints_ast():
    result = _run(["parse", str(FIXTURE)])
    assert result.returncode == 0, result.stderr
    assert "thing" in result.stdout
    assert "paint" in result.stdout


def test_parse_nonexistent_file():
    result = _run(["parse", "/tmp/definitely-not-here.umw"])
    assert result.returncode != 0
    assert "No such file" in result.stderr or "not found" in result.stderr.lower()


def test_inspect_reports_rule_counts():
    result = _run(["inspect", str(FIXTURE)])
    assert result.returncode == 0, result.stderr
    assert "3 rules" in result.stdout or "3 rule" in result.stdout
    assert "shapes" in result.stdout  # taxon name


def test_inspect_lists_property_names():
    result = _run(["inspect", str(FIXTURE)])
    assert result.returncode == 0
    assert "paint" in result.stdout
    assert "max-glow" in result.stdout


def test_parse_syntax_error_exits_nonzero(tmp_path):
    bad = tmp_path / "bad.umw"
    bad.write_text("thing { color: ")  # unterminated
    result = _run(["parse", str(bad)])
    assert result.returncode != 0


def test_help_works():
    result = _run(["--help"])
    assert result.returncode == 0
    assert "umwelt" in result.stdout
    assert "parse" in result.stdout
    assert "inspect" in result.stdout
```

- [ ] **Step 3: Write the CLI module**

Create `src/umwelt/inspect_util.py`:

```python
"""Structural summary of a parsed/resolved view for umwelt inspect."""

from __future__ import annotations

from collections import defaultdict

from umwelt.ast import View


def format_inspection(view: View) -> str:
    """Return a human-readable structural summary of a view."""
    lines: list[str] = []
    total_rules = len(view.rules)
    rule_word = "rule" if total_rules == 1 else "rules"
    lines.append(f"{total_rules} {rule_word}, {len(view.warnings)} warnings")
    lines.append("")

    # Group rules by target taxon.
    by_taxon: dict[str, list] = defaultdict(list)
    for rule in view.rules:
        if rule.selectors:
            taxon = rule.selectors[0].target_taxon
            by_taxon[taxon].append(rule)

    for taxon in sorted(by_taxon.keys()):
        rules = by_taxon[taxon]
        lines.append(f"# {taxon} ({len(rules)} rule(s))")
        for rule in rules:
            sel_strs = [_selector_str(s) for s in rule.selectors]
            prop_names = sorted({d.property_name for d in rule.declarations})
            lines.append(f"  {', '.join(sel_strs)}")
            for name in prop_names:
                values = [
                    d.values for d in rule.declarations if d.property_name == name
                ]
                lines.append(f"      {name}: {values}")
        lines.append("")

    if view.warnings:
        lines.append("Warnings:")
        for w in view.warnings:
            lines.append(f"  line {w.span.line}: {w.message}")

    return "\n".join(lines)


def _selector_str(complex_sel) -> str:
    """A best-effort string rendering of a ComplexSelector."""
    parts: list[str] = []
    for i, part in enumerate(complex_sel.parts):
        simple = part.selector
        s = simple.type_name or "*"
        if simple.id_value:
            s += f"#{simple.id_value}"
        for cls in simple.classes:
            s += f".{cls}"
        for attr in simple.attributes:
            if attr.op is None:
                s += f"[{attr.name}]"
            else:
                s += f'[{attr.name}{attr.op}"{attr.value}"]'
        for pseudo in simple.pseudo_classes:
            if pseudo.argument:
                s += f":{pseudo.name}({pseudo.argument})"
            else:
                s += f":{pseudo.name}"
        if i == 0:
            parts.append(s)
        else:
            combinator_str = {
                "descendant": " ",
                "child": " > ",
                "sibling": " ~ ",
                "adjacent": " + ",
            }.get(part.combinator, " ")
            parts.append(f"{combinator_str}{s}")
    return "".join(parts)
```

Create `src/umwelt/cli.py`:

```python
"""Command-line interface for umwelt."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from pprint import pformat

from umwelt.errors import ViewError
from umwelt.inspect_util import format_inspection
from umwelt.parser import parse


def _preload_toy_taxonomy_if_requested() -> None:
    """For tests: if UMWELT_PRELOAD_TOY=1, install the toy taxonomy.

    The CLI is otherwise vocabulary-agnostic — it parses whatever taxa
    are currently registered, which in production is whatever the
    consumer imported. This hook is solely for test runs.
    """
    if os.environ.get("UMWELT_PRELOAD_TOY") == "1":
        try:
            # We can't import from tests/ at runtime in production; guard.
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from tests.core.helpers.toy_taxonomy import install_toy_taxonomy

            install_toy_taxonomy()
        except Exception:
            pass


def _cmd_parse(args: argparse.Namespace) -> int:
    _preload_toy_taxonomy_if_requested()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(pformat(view, width=100))
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    _preload_toy_taxonomy_if_requested()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_inspection(view))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="umwelt",
        description="umwelt — the common language of the specified band",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_parse = subparsers.add_parser("parse", help="parse a view and print the AST")
    p_parse.add_argument("file", help="path to a .umw view file")
    p_parse.set_defaults(func=_cmd_parse)

    p_inspect = subparsers.add_parser(
        "inspect", help="print a structural summary of a view"
    )
    p_inspect.add_argument("file", help="path to a .umw view file")
    p_inspect.set_defaults(func=_cmd_inspect)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_cli.py -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/cli.py src/umwelt/inspect_util.py tests/core/test_cli.py tests/core/fixtures/
git commit -m "$(cat <<'EOF'
feat(cli): add umwelt parse and umwelt inspect subcommands

Argparse-based CLI with two subcommands so far. parse prints the
pformat-rendered View AST; inspect prints a human-readable structural
summary grouped by target taxon with selector renderings and property
names per rule. Errors print to stderr with a non-zero exit code
(1 for parse/validation errors, 2 for missing files).

For tests, UMWELT_PRELOAD_TOY=1 loads the toy taxonomy before running
the subcommand — a dedicated escape hatch, not a production feature.
Real consumers import their own vocabulary modules which register
their taxa at import time.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 26: `umwelt check` subcommand

**Files:**
- Create: `src/umwelt/check_util.py`
- Modify: `src/umwelt/cli.py` (add the `check` subcommand)
- Create: `tests/core/test_check.py`

**Context:** `umwelt check` runs the full pipeline: parse, validate (implicit in parse), run every registered compiler, and report which rules each compiler realized vs. dropped. In v0.1-core there are no concrete compilers, so `check` reports "0 compilers registered" — but the scaffolding is in place for v0.1-sandbox and v0.2 to hook in.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_check.py`:

```python
"""Tests for the umwelt check subcommand."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "toy.umw"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["UMWELT_PRELOAD_TOY"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "umwelt.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_check_clean_fixture_exits_zero():
    result = _run(["check", str(FIXTURE)])
    assert result.returncode == 0, result.stderr


def test_check_reports_rule_count():
    result = _run(["check", str(FIXTURE)])
    assert "3 rule" in result.stdout or "3 rules" in result.stdout


def test_check_notes_zero_compilers_in_core():
    result = _run(["check", str(FIXTURE)])
    assert "0 compilers" in result.stdout or "no compilers" in result.stdout.lower()


def test_check_reports_validation_error(tmp_path):
    # An empty rule block is valid but a path-escape would fail a real
    # validator. Since we don't have sandbox validators in core, we
    # test the "file not found" path which returns non-zero.
    result = _run(["check", "/tmp/absent-file.umw"])
    assert result.returncode != 0


def test_check_syntax_error(tmp_path):
    bad = tmp_path / "bad.umw"
    bad.write_text("thing { color: ")
    result = _run(["check", str(bad)])
    assert result.returncode != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_check.py -v`
Expected: the check subcommand isn't registered yet.

- [ ] **Step 3: Implement `check_util` and add the subcommand**

Create `src/umwelt/check_util.py`:

```python
"""Pipeline check: parse + validate + run every registered compiler."""

from __future__ import annotations

from umwelt.ast import View
from umwelt.cascade.resolver import resolve
from umwelt.compilers import available, get


def format_check(view: View) -> str:
    """Return a human-readable check report for a parsed view."""
    lines: list[str] = []
    total_rules = len(view.rules)
    rule_word = "rule" if total_rules == 1 else "rules"
    lines.append(f"Parsed: {total_rules} {rule_word}, {len(view.warnings)} warnings")

    if view.warnings:
        for w in view.warnings:
            lines.append(f"  warning (line {w.span.line}): {w.message}")

    compilers = available()
    if not compilers:
        lines.append("Compilers: 0 compilers registered (core-only)")
        return "\n".join(lines)

    lines.append(f"Compilers: {len(compilers)} registered")
    resolved = resolve(view)
    for name in compilers:
        compiler = get(name)
        try:
            output = compiler.compile(resolved)
            lines.append(f"  {name} ({compiler.altitude}): OK")
            if isinstance(output, str):
                lines.append(f"    {len(output)} bytes emitted")
            elif isinstance(output, list):
                lines.append(f"    {len(output)} items emitted")
            elif isinstance(output, dict):
                lines.append(f"    {len(output)} keys emitted")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"  {name} ({compiler.altitude}): FAILED — {exc}")

    return "\n".join(lines)
```

Modify `src/umwelt/cli.py` — add the `check` subcommand:

```python
from umwelt.check_util import format_check


def _cmd_check(args: argparse.Namespace) -> int:
    _preload_toy_taxonomy_if_requested()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_check(view))
    return 0
```

And register it in `build_parser`:

```python
    p_check = subparsers.add_parser(
        "check", help="parse, validate, and run every registered compiler"
    )
    p_check.add_argument("file", help="path to a .umw view file")
    p_check.set_defaults(func=_cmd_check)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_check.py tests/core/ -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/check_util.py src/umwelt/cli.py tests/core/test_check.py
git commit -m "$(cat <<'EOF'
feat(cli): add umwelt check subcommand

check parses the view, reports parse warnings, runs cascade resolve
(so any resolver errors surface), iterates every registered compiler,
and reports per-compiler realization (OK/FAILED + output size).

v0.1-core ships no concrete compilers, so check currently prints
"0 compilers registered (core-only)" — the scaffolding is in place
for the sandbox consumer's nsjail/bwrap/lackpy-namespace/kibitzer-hooks
compilers to appear here once they're registered at import time.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 27: `umwelt dry-run` scaffold

**Files:**
- Create: `src/umwelt/dry_run.py`
- Modify: `src/umwelt/cli.py` (add the `dry-run` subcommand)
- Create: `tests/core/test_dry_run.py`

**Context:** `umwelt dry-run` resolves a view against a supplied world snapshot and prints which entities each rule matched. In v0.1-core, the world snapshot is the currently-registered taxa's matchers — which is only meaningful when the caller preloads a matcher with concrete state. For the toy taxonomy, the CLI preload helper installs a matcher with an empty initial entity list; the test supplies content via a helper.

v0.1-core ships a minimal dry-run: it resolves the view and prints the cascaded properties per entity. A richer form (which-rule-matched-which-entity breakdown) is a v1.1 concern.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_dry_run.py`:

```python
"""Tests for the umwelt dry-run subcommand."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "toy.umw"


def _run(args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["UMWELT_PRELOAD_TOY"] = "1"
    env["UMWELT_PRELOAD_TOY_THINGS"] = "alpha:red,beta:blue"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "umwelt.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_dry_run_reports_resolved_properties():
    result = _run(["dry-run", str(FIXTURE)])
    assert result.returncode == 0, result.stderr
    # The fixture sets paint=crimson for alpha and paint=navy for beta
    # (thing[color="blue"]). The dry-run should surface this.
    assert "alpha" in result.stdout
    assert "crimson" in result.stdout
    assert "navy" in result.stdout


def test_dry_run_reports_shared_max_glow():
    result = _run(["dry-run", str(FIXTURE)])
    assert result.returncode == 0
    assert "max-glow" in result.stdout
    assert "100" in result.stdout


def test_dry_run_no_matches_reports_empty(tmp_path):
    empty = tmp_path / "empty.umw"
    empty.write_text("thing#never { paint: void; }")
    result = _run(["dry-run", str(empty)])
    assert result.returncode == 0
    assert "(no matches)" in result.stdout or "0 entities" in result.stdout
```

- [ ] **Step 2: Extend the CLI preload helper**

Modify `_preload_toy_taxonomy_if_requested` in `src/umwelt/cli.py`:

```python
def _preload_toy_taxonomy_if_requested() -> None:
    if os.environ.get("UMWELT_PRELOAD_TOY") != "1":
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from tests.core.helpers.toy_taxonomy import (
            ToyShapesMatcher,
            ToyThing,
            install_toy_taxonomy,
        )

        things_env = os.environ.get("UMWELT_PRELOAD_TOY_THINGS", "")
        things: list[ToyThing] = []
        for entry in filter(None, things_env.split(",")):
            if ":" not in entry:
                continue
            ident, color = entry.split(":", 1)
            things.append(
                ToyThing(type_name="thing", id=ident.strip(), color=color.strip())
            )
        shapes = ToyShapesMatcher(things=things)
        install_toy_taxonomy(shapes_matcher=shapes)
    except Exception:
        pass
```

- [ ] **Step 3: Implement `dry_run.py` and the subcommand**

Create `src/umwelt/dry_run.py`:

```python
"""Dry-run resolver: print per-entity resolved properties."""

from __future__ import annotations

from umwelt.ast import View
from umwelt.cascade.resolver import resolve


def format_dry_run(view: View) -> str:
    lines: list[str] = []
    resolved = resolve(view)
    taxa = resolved.taxa()
    if not taxa:
        lines.append("(no matches)")
        return "\n".join(lines)
    for taxon in sorted(taxa):
        entries = list(resolved.entries(taxon))
        lines.append(f"# {taxon} ({len(entries)} entities)")
        for entity, properties in entries:
            ident = getattr(entity, "id", None) or getattr(entity, "name", None) or repr(entity)
            lines.append(f"  {ident}")
            for prop_name in sorted(properties):
                lines.append(f"    {prop_name}: {properties[prop_name]}")
        lines.append("")
    return "\n".join(lines)
```

Add the subcommand in `src/umwelt/cli.py`:

```python
from umwelt.dry_run import format_dry_run


def _cmd_dry_run(args: argparse.Namespace) -> int:
    _preload_toy_taxonomy_if_requested()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_dry_run(view))
    return 0


# In build_parser():
    p_dry = subparsers.add_parser(
        "dry-run", help="resolve a view and print per-entity cascaded properties"
    )
    p_dry.add_argument("file", help="path to a .umw view file")
    p_dry.set_defaults(func=_cmd_dry_run)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_dry_run.py tests/core/ -v`
Expected: all pass.

Run: `mypy src/ && ruff check src/ tests/`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/umwelt/dry_run.py src/umwelt/cli.py tests/core/test_dry_run.py
git commit -m "$(cat <<'EOF'
feat(cli): add umwelt dry-run subcommand

dry-run parses a view, runs cascade resolution, and prints per-entity
resolved properties grouped by target taxon. No compilers involved —
this is the 'what does the cascade actually say' inspection utility,
the one an author reaches for when a rule isn't behaving as expected.

The CLI preload helper now accepts UMWELT_PRELOAD_TOY_THINGS for the
toy matcher's content, so tests can drive the dry-run against a known
world without writing a real matcher.

A richer dry-run that reports which rules matched which entities
(rather than just the cascaded output) is a v1.1 feature.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 28: README, CHANGELOG, v0.1-core acceptance

**Files:**
- Modify: `README.md`
- Create: `CHANGELOG.md`
- Modify: `pyproject.toml` (bump version to `0.1.0-core`)
- Modify: `docs/vision/README.md` (update status line)

**Context:** The final task rounds off v0.1-core with public-facing docs, a version bump to a pre-release tag, and the status update on the vision docs. No new code, no new tests — this task is about shipping what's already built.

- [ ] **Step 1: Write `README.md`**

Replace the current stub `README.md` with:

```markdown
# umwelt

*The common language of the specified band. A CSS-shaped declarative format for policy specification.*

**Status:** v0.1-core — the vocabulary-agnostic core (parser, registry, selector engine, cascade resolver, compiler protocol, CLI). No concrete compilers yet; the first enforcement target (nsjail) lands in v0.2.

For the framing and the rest of the vision, see [`docs/vision/`](docs/vision/).

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+.

## Quick start

umwelt is vocabulary-agnostic: core umwelt knows nothing about files, tools, or networks. Consumers register their own taxa at import time. Until a consumer does that, bare views won't parse because there are no entity types to resolve against.

For v0.1-core, the only available vocabulary is the toy taxonomy shipped with the test suite. To try the CLI against it:

```bash
UMWELT_PRELOAD_TOY=1 UMWELT_PRELOAD_TOY_THINGS="alpha:red,beta:blue" \
  umwelt dry-run tests/core/fixtures/toy.umw
```

In v0.2 (next milestone), the sandbox consumer registers the first real vocabulary (`world` / `capability` / `state`) and provides the workspace runtime. That's when `umwelt` becomes meaningful for real sandboxing work.

## What's here

- `src/umwelt/` — the core package: parser, AST, plugin registry, selector engine, cascade resolver, compiler protocol, CLI.
- `docs/vision/` — the vision docs (format, entity model, policy layer, package design).
- `docs/superpowers/specs/` — the approved design specs.
- `docs/superpowers/plans/` — the implementation plans.
- `tests/core/` — unit and integration tests for core umwelt.

## Development

```bash
# Install in editable mode with dev tools.
pip install -e ".[dev]"

# Run the tests.
pytest -q

# Lint.
ruff check src/ tests/

# Type check.
mypy src/
```

## License

MIT — see [`LICENSE`](LICENSE).
```

- [ ] **Step 2: Create `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to umwelt are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows semantic versioning.

## [Unreleased]

## [0.1.0-core] — 2026-04-10

The vocabulary-agnostic core of umwelt. No concrete enforcement compilers
yet; this milestone establishes the parser, AST, plugin registry, selector
engine, cascade resolver, compiler protocol, and CLI.

### Added

- **Parser**: tinycss2-backed parser for CSS-shaped view files. Produces a
  frozen-dataclass AST (`View`, `RuleBlock`, `ComplexSelector`,
  `SimpleSelector`, `CompoundPart`, `Declaration`, `PseudoClass`,
  `AttrFilter`, `UnknownAtRule`, `ParseWarning`). Preserves unknown
  at-rules for forward compatibility.
- **Registry**: `register_taxon`, `register_entity`, `register_property`,
  `register_matcher`, `register_validator`, `register_compiler`. Taxon
  registration is scope-overridable via `registry_scope()` for tests.
- **Selector engine**: CSS3 subset including type, id, class, attribute
  selectors (=, ^=, $=, *=, ~=, |=), pseudo-classes (:not, :glob),
  combinators (descendant, child), union (comma), namespace
  disambiguation (`ns|type`), and at-rule scoping (`@world { ... }`).
  Combinators are classified as *structural* (within-taxon) or *context*
  (cross-taxon) at parse time via registry lookup.
- **Specificity**: CSS3 specificity computation with accumulation across
  compound selectors.
- **Cascade resolver**: per-taxon cascade scoped to the rightmost
  entity's taxon, specificity wins, document order breaks ties,
  property-level cascade so different properties on the same entity can
  come from different rules.
- **Compiler protocol**: `Compiler` runtime-checkable Protocol with
  `target_name`, `target_format`, `altitude`, and `compile(ResolvedView)`.
  Compiler registry with `register` / `get` / `available` /
  `clear_compilers`.
- **CLI**: `umwelt parse`, `umwelt inspect`, `umwelt check`,
  `umwelt dry-run` subcommands.
- **Documentation**: vision docs (`docs/vision/`) and superpowers specs
  (`docs/superpowers/specs/`).

### Deferred

- Concrete compilers (`nsjail`, `bwrap`, `lackpy-namespace`,
  `kibitzer-hooks`) — v0.2 onward, in the sandbox consumer.
- Workspace builder, writeback, hook dispatcher — v0.1-sandbox.
- Selector-level node extraction via pluckit — v1.1.
- The `delegate-context` compiler (view transparency) — v1.1.
- `source` / `project` entity — v1.1+.
- View bank and git-history distillation — v2.

[Unreleased]: https://github.com/teaguesterling/umwelt/compare/v0.1.0-core...HEAD
[0.1.0-core]: https://github.com/teaguesterling/umwelt/releases/tag/v0.1.0-core
```

- [ ] **Step 3: Bump version in `pyproject.toml`**

Change the version line:

```toml
version = "0.1.0-core"
```

- [ ] **Step 4: Update `docs/vision/README.md` status line**

Find and replace:

```markdown
## Status

Pre-implementation. The architecture is specified; ...
```

with:

```markdown
## Status

**v0.1-core landed** on 2026-04-10. The vocabulary-agnostic core is shipping: parser, AST, plugin registry, selector engine with cross-taxon compound selector support, cascade resolver, compiler protocol, and CLI. No concrete compilers yet; v0.1-sandbox registers the first-party `world`/`capability`/`state` vocabulary and ships the workspace runtime, and v0.2 adds the nsjail compiler. See [`docs/superpowers/plans/`](../superpowers/plans/) for the active implementation plans.
```

- [ ] **Step 5: Run the full test suite and check everything is green**

Run: `pytest -q`
Expected: all tests pass (should be 100+ tests across Slices 1-4).

Run: `ruff check src/ tests/`
Expected: clean.

Run: `mypy src/`
Expected: clean.

Run the CLI manually:

```bash
UMWELT_PRELOAD_TOY=1 UMWELT_PRELOAD_TOY_THINGS="alpha:red,beta:blue" \
  python -m umwelt.cli parse tests/core/fixtures/toy.umw
UMWELT_PRELOAD_TOY=1 UMWELT_PRELOAD_TOY_THINGS="alpha:red,beta:blue" \
  python -m umwelt.cli inspect tests/core/fixtures/toy.umw
UMWELT_PRELOAD_TOY=1 UMWELT_PRELOAD_TOY_THINGS="alpha:red,beta:blue" \
  python -m umwelt.cli check tests/core/fixtures/toy.umw
UMWELT_PRELOAD_TOY=1 UMWELT_PRELOAD_TOY_THINGS="alpha:red,beta:blue" \
  python -m umwelt.cli dry-run tests/core/fixtures/toy.umw
```

Expected: all four commands produce reasonable output and exit 0.

- [ ] **Step 6: Commit**

```bash
git add README.md CHANGELOG.md pyproject.toml docs/vision/README.md
git commit -m "$(cat <<'EOF'
chore(release): v0.1.0-core — vocabulary-agnostic core ships

Ships the v0.1-core milestone: parser, AST, plugin registry, selector
engine with cross-taxon compound selector support, cascade resolver,
compiler protocol, CLI (parse/inspect/check/dry-run). Zero concrete
compilers — those land in v0.1-sandbox and v0.2.

Updates:
- README.md: install, quick start against the toy taxonomy, development
  workflow, license.
- CHANGELOG.md: full 0.1.0-core entry with added features and deferred
  items (compilers, workspace, pluckit, delegate-context, source entity,
  view bank).
- pyproject.toml: version 0.1.0-core.
- docs/vision/README.md: status line updated to reflect v0.1-core
  landing.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7: Tag the release**

```bash
git tag -a v0.1.0-core -m "v0.1.0-core — vocabulary-agnostic core of umwelt"
git log --oneline | head -30
```

Expected: the tag points at the Task 28 commit; the log shows the full 29-task chain across four slices.

---

## Self-review

Reviewing the plan against the spec with fresh eyes.

**1. Spec coverage (§§3-5, §9 of `2026-04-10-umwelt-v01-core-and-sandbox-scoping-design.md`):**

| Spec section | Covered by |
|---|---|
| §3.1 Module layout (core) | Task 0 (bootstrap), Tasks 1-3 (errors/AST/init), Tasks 4-7 (registry), Tasks 8-11 (parser), Tasks 12-16 (selectors), Tasks 17-23 (validate/match/cascade), Tasks 24-27 (compilers/CLI), Task 28 (acceptance). |
| §3.2 Parser | Tasks 8-11 (structure, selectors, declarations, warnings) and 12-16 (combinators, resolution, disambiguation, modes, specificity). |
| §3.3 AST | Task 2 (dataclasses), Task 15 (mode population), Task 16 (specificity population). |
| §3.4 Registry | Tasks 4 (taxa), 5 (entities), 6 (properties), 7 (matchers), 17 (validators). Compiler registry in Task 24. |
| §3.5 Selector engine | Tasks 9-16 (parser output), 18 (match_simple), 19 (match_complex). |
| §3.6 Cascade resolver | Task 20 (basic + property-level), Tasks 21-23 (comparison, pattern, compound integration). |
| §3.7 Compiler protocol | Task 24. |
| §3.8 Validator framework | Task 17. |
| §3.9 CLI | Task 25 (parse/inspect), Task 26 (check), Task 27 (dry-run). |
| §4 Testing strategy | Every task has TDD tests; toy taxonomy helper in Task 7. |
| §5 Acceptance criteria | Task 28 runs the full suite + manual CLI smoke test. |
| §9.1-9.4 Slice plan | Tasks 0-11 (Slice 1), 12-16 (Slice 2), 17-23 (Slice 3), 24-28 (Slice 4). |

Spec requirements not explicitly covered that need flagging:

- **Port-ready decomposition (§10 of spec):** every task that writes a pure function (parser, selector parse, specificity, match, cascade resolve) preserves the pure-function contract. This isn't a standalone task — it's a design constraint enforced implicitly throughout. No gap.
- **Open-question resolutions (§11 of spec):** carried forward in the docs; no code impact.

**2. Placeholder scan:**

Ran a scan for TBD / TODO / "implement later" / "similar to Task N" / "add appropriate error handling". None found.

Two soft spots to flag for the executor:

- Task 18 treats `:not(...)` as always-match — it's an incomplete implementation marked with a v0.1-core-stub comment. If the integration tests in Task 23 or the CLI tests in Tasks 25-27 exercise `:not`, they should be updated to not depend on the full semantics. The plan doesn't use `:not` in any fixture or test assertion beyond Task 12's parse-time test, so this is fine.
- Task 9's `_parse_simple` has a "require no interior whitespace" branch that Task 12 removes. Make sure the Task 12 diff is applied correctly (there's a `# ... rest unchanged, but remove the "unexpected whitespace" branch` comment there — the executor should literally delete those lines, not leave them).

**3. Type consistency:**

Function and type names used across tasks:

- `SimpleSelector.taxon` — introduced in Task 2, populated in Task 13, used in Tasks 15, 17, 18, 19, 20. ✓
- `ComplexSelector.target_taxon` — introduced Task 2, populated Task 13 + Task 15, used in Tasks 17, 20, 23. ✓
- `ComplexSelector.specificity` — introduced Task 2, populated Task 16, used in Task 20. ✓
- `CompoundPart.mode` — introduced Task 2, populated Task 15, used in Task 19. ✓
- `register_taxon` / `register_entity` / `register_property` / `register_matcher` / `register_validator` / `register` (compiler) — signature consistent across Tasks 4, 5, 6, 7, 17, 24. ✓
- `MatcherProtocol` methods — introduced Task 7 (`match_type`, `children`, `condition_met`), extended Task 18 (`get_attribute`, `get_id`). Toy matchers updated in both tasks. ✓
- `ResolvedView.entries(taxon)` / `.add(taxon, entity, properties)` / `.taxa()` — introduced Task 20, used in Tasks 21, 22, 23 (via `_get` helper in tests), Task 24 (compiler tests), Task 26 (check util), Task 27 (dry-run util). ✓
- `match_simple(simple, matcher, candidates)` / `match_complex(complex_sel, registry, eval_context)` — introduced Task 18 and Task 19; used in Task 20's resolver. ✓
- `parse(source, validate=True)` — signature consistent across all tasks. ✓
- `registry_scope()` context manager — introduced Task 4, used in every test from Task 4 onward. ✓
- `install_toy_taxonomy(shapes_matcher=None, actors_matcher=None)` — signature consistent; extended in Task 14 with `install_doubled_taxonomy()` as a separate helper. ✓

No type drift detected.

**4. Scope check:**

The plan is focused on v0.1-core. It does not touch the sandbox consumer (that's v0.1-sandbox, covered by the next plan). It stays within the single subsystem boundary the spec defines. No decomposition needed.

**5. Task sizing:**

29 tasks is at the upper end of what a single plan should contain, but each task is bite-sized (2-5 minute steps × 5-8 steps per task = ~15-30 minutes per task). Total estimated work: 8-15 focused hours. This matches the spec's "weekend one" framing for v0.1-core.

Self-review complete. The plan is internally consistent, spec-aligned, and ready to hand off.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-10-umwelt-v01-core.md`.** Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task. The orchestrator reviews between tasks and can course-correct without polluting the working context. Best for a plan this size (29 tasks) because it keeps the feedback loop tight and the context window fresh.

**2. Inline Execution** — Execute tasks in this session using the `executing-plans` skill with batch checkpoints. Lower ceremony, higher context consumption. Works for plans of this size but you lose the fresh-context review between tasks.

Which approach?

