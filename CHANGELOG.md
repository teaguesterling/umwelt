# Changelog

All notable changes to umwelt are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows semantic versioning.

## [Unreleased]

## [0.1.0-core] — 2026-04-11

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
