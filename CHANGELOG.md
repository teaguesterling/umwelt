# Changelog

All notable changes to umwelt are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows semantic versioning.

## [Unreleased]

## [0.1.0] — 2026-04-11

The sandbox consumer milestone. The vocabulary-agnostic core from v0.1.0-core
is unchanged; this release adds the first real consumer (`umwelt.sandbox`) and
ships it as the default CLI vocabulary.

### Added

- **Sandbox vocabulary**: `world` taxon (file, dir, resource, network, env,
  mount), `capability` taxon (tool, kit), `state` taxon (hook, job, budget).
  Registered automatically by the CLI at startup.
- **WorldMatcher**: resolves file/dir entities from the real filesystem using
  path-attribute selectors (`path^=`, `path$=`, `path*=`, `name=`) and the
  `:glob()` pseudo-class.
- **CapabilityMatcher** and **StateMatcher**: in-memory matchers for tool/kit
  and hook/job/budget entities respectively.
- **Validators**: `WorldValidator` (editable/visible type checks),
  `CapabilityValidator` (allow/max-level type checks).
- **WorkspaceBuilder**: materializes a virtual workspace from a resolved view —
  editable files become copies, read-only files become symlinks. Path-traversal
  guard rejects escapes outside `base_dir`.
- **WriteBack**: reconciles delegate edits back to real files. Detects and
  classifies each entry as `NoOp`, `Applied`, `Rejected`, or `Conflict`.
  Strict mode raises `ViewViolation` on any rejected or conflicted entry.
- **HookDispatcher**: runs shell commands for lifecycle hook rules with timeout
  and working-directory support.
- **At-rule sugar desugaring**: `@source`, `@tools`, `@after-change`,
  `@network`, `@budget`, `@env` transform to entity-selector form at parse time.
- **Reference fixtures**: `minimal.umw`, `readonly-exploration.umw`,
  `auth-fix.umw`, `actor-conditioned.umw` under `src/umwelt/_fixtures/`.
- **CLI**: replaced `UMWELT_PRELOAD_TOY` hack with `_load_default_vocabulary()`
  that auto-imports `umwelt.sandbox` if available.

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
