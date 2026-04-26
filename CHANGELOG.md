# Changelog

All notable changes to umwelt are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows semantic versioning.

## [Unreleased]

## [0.6.0] — 2026-04-26

### Added
- **Resource block model** — single `resource` entity with properties (`memory`, `wall-time`, `cpu-time`, `tmpfs`) replaces per-resource singletons (`MemoryEntity`, `WallTimeEntity`, etc.). CSS selectors now use `resource { memory: 512MB; }` instead of `memory { limit: 512MB; }`.
- **Mode filtering** — `mode#review tool { allow: false }` gates rules by active mode. Both in-memory cascade resolver (`StateMatcher.condition_met()` with `active_mode` context) and SQL PolicyEngine (`mode` parameter on `resolve`/`resolve_all`/`trace`/`check`/`require`). Unscoped rules always apply; mode-gated rules only fire when that mode is active. `mode_qualifier` column on `cascade_candidates` table.
- **Fixed constraints** — post-cascade clamping for safety-critical properties. `fixed_raw` in world files maps selectors to property values that override cascade results. `fixed_constraints` table and `effective_properties` view in SQL schema.
- **CompositeMatcher** — multiple matchers per taxon via `CompositeMatcher` wrapper. Enables plugin coexistence where two plugins register matchers for the same taxon.
- **Plugin autodiscovery** — `umwelt.plugins` entry point group. Third-party packages register plugins via `pyproject.toml` entry points; `umwelt.registry.plugins.discover_plugins()` loads them at startup.
- **MCP-projected tool attributes** — `param-count` and `output-type` attributes on the `tool` entity type, populated by future MCP generator plugins.
- **Plugin guide documentation** — `docs/guide/plugins.md` (586 lines), `docs/guide/policy-engine.md` (456 lines), `docs/guide/world-files.md` (363 lines).
- 200+ new tests (832 total). `tests/policy/test_mode_filtering.py` (20 tests), `tests/sandbox/test_active_mode.py` (12 tests).

### Changed
- `populate_from_world` now always includes entity `id` as a `name` attribute in the JSON column, matching matcher-discovered entity behavior. Fixes `tool[name="Read"]` selectors in the SQL path.
- PolicyEngine `resolve`, `resolve_all`, `trace`, `check`, `require` methods accept optional `mode` parameter.
- Sandbox compilers (nsjail, bwrap) updated to read resource properties from block entity instead of individual resource entities.
- `@budget` at-rule desugars to `resource { ... }` instead of individual `memory { limit: ... }` / `wall-time { limit: ... }` rules.

### Fixed
- Mode-filtered queries now respect fixed constraints (post-cascade clamping applied after mode-filtered resolution).
- Projection entities now get `name` attribute fallback, consistent with declared entities.

## [0.5.2] — 2026-04-16

### Added
- **`mode` entity** registered under the `control`/`state` taxon.
  Authored as ID selectors: `mode#implement`, `mode#review`, etc.
  Classes remain for categories: `mode#implement.tdd`. v0.5.2 supports
  mode as a cross-axis context qualifier in cascade (always active at
  view-resolve time); runtime mode-filtering is a v0.6 concern
  coordinated with kibitzer's `ChangeToolMode`.
- **`tool.visible` property**. Defaults to following `allow`. Distinct
  from `tool.allow`: `allow: false` blocks invocation; `visible: false`
  hides the tool from the delegate's menu. Useful for mode-gated tool
  surfaces (see kibitzer #1).
- **Cross-axis idioms section** in `docs/guide/entity-reference.md`
  documenting `mode#<id> tool[name=...]` for mode-gated tool surfaces,
  with guidance on when to reach for `use[of=...]` instead. Three-axis
  (principal × mode × tool) example included.
- New tests in `tests/sandbox/test_mode_tool_idiom.py` verifying
  mode-tool cascade, axis-count ordering, and three-axis narrowing.

## [0.5.1] — 2026-04-16

### Fixed
- Re-anchor the v0.5 release tag onto `main`. The v0.5.0 tag points at
  the pre-squash branch commit (reachable via its ref on GitHub); v0.5.1
  is the same content, tagged on the squash-merge commit of `main`. No
  code, docs, or test changes.

## [0.5.0] — 2026-04-14

### Added
- **VSM-aligned taxa**: `principal` (S5) and `audit` (S3*) as new top-level
  taxa; `operation`, `coordination`, `control`, `intelligence` as aliases
  of `capability`/`state`/`actor`. Legacy taxon names remain fully functional.
- **`use[of=...]` entity** — first-class permissioned projection of a
  world resource into the action axis. Carries action-axis permission
  properties: `editable`, `visible`, `show`, `allow`, `deny`,
  `allow-pattern`, `deny-pattern`. Additive to world-axis permissions on
  `file`/`dir`/`tool`/`network` — the two axes are semantically
  independent (see spec §3a).
- **`@audit { ... }` at-rule** for declaring audit-taxon entries
  (observation, manifest) outside the world.
- **Cross-axis cascade specificity**: selectors that join more taxa-axes
  are more specific. Specificity tuple widened from `(ids, cls, types)`
  to `(axis_count, principal, world, state, actor, capability, audit, other)`.
  Single-axis v0.4 rules retain identical ordering because `axis_count=1`
  is uniform across them.
- **Byte-compat snapshot suite** across all 5 fixtures × 3 compilers
  (nsjail, bwrap, lackpy-namespace) guards compiler output against
  unintended drift.
- **Resolver determinism property test** across all fixtures and a
  50-run stability check.
- **Taxon-alias resolution** in registry (`resolve_taxon`) — entity,
  property, matcher, and validator lookups all route through canonical
  names transparently.

### Changed
- `ComplexSelector.specificity` type widened from `tuple[int, int, int]`
  to `tuple[int, ...]`.
- `umwelt.registry` public API exports `register_taxon_alias` and
  `resolve_taxon`.

### Notes
- Compilers (nsjail, bwrap, lackpy-namespace) continue to read world-axis
  entities directly in v0.5. The v0.6 work will decide which compilers
  should migrate to reading the action-axis (e.g., lackpy for per-tool
  gating via `use[of=tool#X]`).
- Kibitzer-hooks compiler deferred to v0.6. Security pass deferred to v0.7.
- Evaluation framework (`docs/vision/evaluation-framework.md`) introduced
  as the reference for claims verified/open per milestone. v0.5 verifies
  or strengthens claims A1, A2, A3, A5, A6, B1-continuity, G1, H1, H3, I1,
  I3.

## [0.4.0] — 2026-04-13

The lackpy-namespace, diff, and PyPI milestone. Adds the first
language-altitude compiler (lackpy-namespace), a rule-level diff utility,
nsjail PATH emission from exec entities, and a new example view for code
review delegation. Package now builds a valid wheel and sdist.

### Added

- **lackpy-namespace compiler** (`umwelt.sandbox.compilers.lackpy_namespace`):
  language-altitude compiler that reads `capability`-taxon entries (tool
  allow/deny, kit allow, max-level, patterns) and emits a Python dict for
  lackpy's namespace validator. Supports `allowed_tools`, `denied_tools`,
  `kits`, `max_level`, `tool_levels`, `allow_patterns`, `deny_patterns`.
- **umwelt diff** (`umwelt diff a.umw b.umw`): new subcommand and
  `umwelt.diff_util` module. Compares two parsed views rule-by-rule and
  reports added, removed, changed, and unchanged rules.
- **lackpy-delegate fixture** (`src/umwelt/_fixtures/lackpy-delegate.umw`):
  example read-only code review environment. Limits tools to Read/Grep/Glob
  with max-level 1, denies network, 256MB/2m budget, after-change hook.
- **nsjail PATH emission**: bare `ExecEntity` with a `search-path` property
  now emits a `PATH=...` envar in the nsjail config.

### Changed

- `umwelt compile` now formats dict output as indented JSON (`json.dumps`
  indent=2) instead of Python `repr`. This affects the lackpy-namespace
  compiler and any future dict-returning compilers.
- `umwelt check` now reports 3 registered compilers: nsjail, bwrap,
  lackpy-namespace.

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

[Unreleased]: https://github.com/teaguesterling/umwelt/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/teaguesterling/umwelt/compare/v0.5.2...v0.6.0
[0.5.2]: https://github.com/teaguesterling/umwelt/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/teaguesterling/umwelt/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/teaguesterling/umwelt/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/teaguesterling/umwelt/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/teaguesterling/umwelt/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/teaguesterling/umwelt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/teaguesterling/umwelt/compare/v0.1.0-core...v0.1.0
[0.1.0-core]: https://github.com/teaguesterling/umwelt/releases/tag/v0.1.0-core
