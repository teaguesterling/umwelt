# umwelt

*The common language of the specified band. A CSS-shaped declarative format for policy specification.*

**Status:** v0.1.0 — core + sandbox consumer shipped. The sandbox vocabulary (`world` / `capability` / `state`) is registered automatically. Workspace builder, writeback, hook dispatcher, and at-rule sugar desugaring are all in place. Concrete enforcement compilers (nsjail, bwrap) land in v0.2.

For the framing and the rest of the vision, see [`docs/vision/`](docs/vision/).

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+.

## Quick start

The sandbox vocabulary is auto-loaded by the CLI. Try the canonical sandbox example:

```bash
umwelt parse src/umwelt/_fixtures/auth-fix.umw
umwelt inspect src/umwelt/_fixtures/auth-fix.umw
umwelt dry-run src/umwelt/_fixtures/auth-fix.umw
```

The `auth-fix.umw` view lets a delegate edit `src/auth/`, read everything else, and runs `pytest` + `ruff` after any change.

## What's here

- `src/umwelt/` — the core package: parser, AST, plugin registry, selector engine, cascade resolver, compiler protocol, CLI.
- `src/umwelt/sandbox/` — the sandbox consumer: vocabulary, matchers, workspace builder, writeback, hook dispatcher, at-rule sugar.
- `src/umwelt/_fixtures/` — reference `.umw` view files (minimal, readonly-exploration, auth-fix, actor-conditioned).
- `docs/vision/` — the vision docs (format, entity model, policy layer, package design).
- `docs/superpowers/specs/` — the approved design specs.
- `docs/superpowers/plans/` — the implementation plans.
- `tests/core/` — unit and integration tests for core umwelt.
- `tests/sandbox/` — unit and integration tests for the sandbox consumer.

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
