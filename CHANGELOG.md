# Changelog

All notable changes to umwelt are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows semantic versioning.

## [Unreleased]

## [0.3.0] — 2026-04-12

The audit and bwrap milestone. Adds a second OS-altitude compiler (bwrap),
world#env-name filtering, the executable entity type, and a security-aware
audit command with cascade widening detection.

### Added

- **Executable entity** (`exec` in the `world` taxon): declares binary paths
  and PATH search directories inside the jail. Attributes: `name`, `path`.
  Properties: `path`, `search-path`. Parent: `world`.
- **world#env-name filtering**: `resolve(view, world="dev")` and
  `umwelt dry-run --world dev` pre-filter rules to only those matching the
  named environment (or unscoped global rules). The `compile` subcommand
  also accepts `--world`.
- **bwrap compiler** (`umwelt.sandbox.compilers.bwrap`): OS-altitude compiler
  that translates resolved views into `bwrap` argv arrays. File entities →
  `--bind`/`--ro-bind`, mounts → `--bind`/`--ro-bind`/`--tmpfs`, network deny
  → `--unshare-net`, env → `--setenv`, executable search-path → `--setenv PATH`,
  resource limits → `--die-with-parent` + `prlimit`. Output is a `BwrapCompilation`
  dataclass with an `argv` list.
- **umwelt audit** (`umwelt.audit`): security-aware policy audit with per-entity
  resolved property attribution (source line numbers) and cascade widening
  detection. `umwelt audit view.umw [--world env]` prints a human-readable
  report. Widening = a later rule loosens a permission set by an earlier rule
  (e.g. `editable: false` → `editable: true`).

## [0.2.0] — 2026-04-12

The first enforcement compiler milestone. The nsjail compiler translates
resolved umwelt views into nsjail protobuf textproto configs that nsjail
accepts via `--config`.

### Added

- **nsjail compiler** (`umwelt.sandbox.compilers.nsjail`): translates
  OS-altitude constructs from a resolved view into nsjail textproto.
  File entities → bind mounts (rw based on `editable`), network `deny: "*"` →
  `clone_newnet: true`, resource limits → `rlimit_as`/`rlimit_cpu`/
  `rlimit_nofile`/`time_limit`, env `allow: true` → `envar` passthrough.
  Non-OS constructs (tools, hooks, actor qualifiers) are silently dropped.
- **Value parser** (`umwelt.sandbox.compilers._value_parser`): converts
  declaration values like `"512MB"` → 512 (MB int), `"5m"` → 300 (seconds),
  `"64MB"` → `"64M"` (tmpfs string).
- **nsjail runner** (`umwelt.sandbox.runners.nsjail`): convenience wrapper
  that compiles a view, writes a temp config, and invokes the nsjail binary
  via `subprocess.run`. Returns `NsjailResult` with returncode/stdout/stderr.
- **CLI `compile` subcommand**: `umwelt compile --target nsjail view.umw`
  resolves the view and prints the textproto to stdout.
- **CLI `run` subcommand**: `umwelt run --target nsjail view.umw -- cmd`
  compiles + runs a command inside nsjail (requires nsjail on PATH).
- **Snapshot fixtures** (`_fixtures/expected/nsjail/`): expected textproto
  outputs for minimal, auth-fix, and readonly-exploration views.

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
