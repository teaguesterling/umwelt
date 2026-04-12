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
