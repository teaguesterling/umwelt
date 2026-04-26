# umwelt

*The common language of the specified band. A CSS-shaped declarative format and runtime for writing down what a delegated actor can see, edit, call, trigger, and consume — in a form every enforcement tool, observation tool, auditor, and coaching layer in a multi-actor system can read, compile, and reason about.*

## What umwelt is

**umwelt is the common language of the specified band.**

A specified-band Harness regulates a multi-actor system across multiple altitudes — OS sandboxes, language interpreters, semantic hooks, conversational context — and across multiple tools at each altitude. Every component in that regulatory loop needs to agree on what's being regulated, why, and to what bounds. Without a shared vocabulary, each tool invents its own: nsjail has protobuf textproto, bwrap has argv flags, lackpy has namespace dicts, kibitzer has hook rules, blq has TOML sandbox specs, claude-plugins has settings.json. All of them describe variants of the same thing — what the actor can see, edit, call, trigger, and consume — but none of them can read each other's descriptions, and none of them compose.

umwelt is the lingua franca those tools translate from. A **view** file (`.umw`) declares, in CSS-shaped syntax, what entities exist in the world the actor operates inside and what policies apply to them. Compilers translate the view into whatever native format each enforcement tool already accepts. Observation tools produce evidence in the same vocabulary so a ratchet utility can propose revisions. The Harness's own regulatory intent is written down as views. The specified band has a shared language because umwelt defines one, and every component in the band — enforcers, observers, auditors, coaches, consumers — can read it.

umwelt owns one concept and the machinery around it: **the view**. Views are produced by outer agents (humans or larger models) to bound the behavior of inner agents (delegates, subprocesses, small models). Views are consumed by enforcement tools at multiple altitudes, each compiling the view into its own native enforcement mechanism. umwelt parses views, represents them in memory, applies policy rules via selectors and cascade, and emits native configs for each enforcement target. It imports no enforcement tool's Python wrapper at runtime — that's what lets it *be* the common language, since it has no loyalty to any particular enforcement tool.

The name is Jakob von Uexküll's 1934 biosemiotics term: the self-centered perceptual world an organism experiences, constituted by what it can sense and act on. A view *is* the umwelt the delegate experiences — the slice of reality it has access to. Outside the umwelt does not exist from the delegate's perspective.

## Why it exists

Two things were missing from the delegation stack.

**A shared format.** The sandbox tower is real: enforcement happens at multiple altitudes (OS, language, semantic, conversational), and each altitude catches a different class of violation. The altitudes don't substitute for each other; they stack. Every time view-layer concerns came up as a submodule of an existing tool — lackpy, pluckit, kibitzer, agent-riggs, blq, claude-plugins — the tool's identity started to bend. Each has a sharp scope and the view layer didn't belong inside any of them. umwelt exists so none of those tools has to grow an awkward sub-component for the same concern, and so the components can finally share a vocabulary.

**A theory that makes the architecture necessary.** The *Ma of Multi-Agent Systems* series ([intro](https://judgementalmonad.com/blog/ma/00-intro)) develops the theoretical grounding: the Harness must stay in the **specified band** (transparent decision surface regardless of world coupling) to remain characterizable; the OS existence proof shows this is viable at any scale via layered regulation (constraint + observation + policy); the [configuration ratchet](https://judgementalmonad.com/blog/ma/the-configuration-ratchet) converts high-ma exploration into specified artifacts; and the [fuel series](https://judgementalmonad.com/blog/fuel/) makes it practical. umwelt is the *policy specification layer* of this architecture — Layer 3 in the three-layer regulation strategy, the authoring surface for the specified artifacts the ratchet produces. The reasoning behind every umwelt design decision bottoms out in that theory.

For the short version of the theory, see [the ratchet review](https://judgementalmonad.com/blog/fuel/00-ratchet-review). For the full version, see the Ma series. For umwelt's framing within it, see [`policy-layer.md`](./policy-layer.md).

## What umwelt is not

- **Not an enforcement mechanism.** Enforcement is nsjail, bwrap, lackpy's validator, kibitzer's hooks. umwelt emits configuration for these tools; it does not execute delegates or gate tool calls itself.
- **Not a discovery tool.** Observation is blq, ratchet-detect, strace, auditd. umwelt consumes their outputs during the ratchet step; it does not capture events directly.
- **Not an orchestrator.** Running delegates, dispatching tool calls, composing multi-agent pipelines — those are handled by lackpy / kibitzer / agent-riggs / claude-plugins. umwelt provides the policy-layer input to those systems.
- **Not a code parser.** Code parsing is pluckit / sitting_duck. umwelt calls pluckit (v1.1+) when it needs to evaluate node-level selectors inside a `file` block, but umwelt does not know about tree-sitter or AST node types.
- **Not a runtime policy evaluator.** Views describe bounds; enforcement tools realize them. umwelt does not re-implement enforcement tools' own config validators — if a compiler emits a textproto nsjail subsequently rejects, that's a compiler bug, not a umwelt runtime concern.
- **Not a fine-tuned DSL.** The grammar is fixed and specified. The ratchet is specified analysis over captured events, not machine learning. No trained judgment enters the policy layer.
- **Not a controller in Beer's VSM sense.** umwelt is specified coordination. The decision about *which* view to apply, *when* to ratchet, *whether* to escalate, is control, and lives elsewhere.
- **Not a view bank (in v1).** Eventually umwelt will grow storage, retrieval, and git-history distillation of views, but that's a phase-2 concern. v1 is format + runtime + compilers.
- **Not a dependency on any Python wrapper of any enforcement tool.** umwelt emits text configs for their native formats. You can use umwelt on a system that has only the enforcement binaries installed, with no Python wrappers present.

## The architecture in one picture

```
┌────────────────────────────────────────────────────────────────────┐
│                       The Specified-Band Harness                   │
│                                                                    │
│   Layer 2              Layer 3                 Layer 1             │
│   observation          policy                  enforcement         │
│   (observed state)     (umwelt views)          (bounds)            │
│                                                                    │
│   ┌──────────┐         ┌──────────────┐        ┌───────────────┐   │
│   │   blq    │         │              │        │   nsjail      │   │
│   │ ratchet- │ ──────▶ │ umwelt view  │ ─────▶ │   bwrap       │   │
│   │  detect  │         │   (.umw)     │        │   lackpy      │   │
│   │  strace  │         │              │        │   kibitzer    │   │
│   └──────────┘         └──────────────┘        └───────────────┘   │
│        ▲                      │                       │           │
│        │                  compiles                 bounds         │
│        │                  (pure fn)                  │            │
│        │                      ▼                       ▼           │
│        │              native target configs                       │
│        │                                                          │
│        │                                                          │
│   ┌────┴────────────────────────────────────────────────────┐     │
│   │            Actor (Inferencer + Executor)                │     │
│   │   operates inside the umwelt the view describes         │     │
│   └─────────────────────────────────────────────────────────┘     │
│                            │                                      │
│                       failure stream                               │
│                            │                                      │
│                    ratchet feedback                               │
│                            │                                      │
│      (observation crystallizes new view → new enforcement)         │
└────────────────────────────────────────────────────────────────────┘

Core umwelt is the middle column. The observation column is other tools
(blq, ratchet-detect, etc.) feeding data into the ratchet utility. The
enforcement column is other tools (nsjail, bwrap, etc.) consuming
compiled configs. umwelt translates between them without implementing
either.
```

The package itself splits into two layers:

```
┌──────────────────────────────────────────────┐
│              core umwelt                     │
│                                              │
│  • parser + AST (tinycss2-backed)            │
│  • selector evaluation engine                │
│  • cascade resolver (CSS specificity)        │
│  • compiler protocol + registry              │
│  • validator framework                       │
│  • taxon + entity + property registry        │
│  • utilities: inspect, dry-run, check,       │
│    diff, ratchet                             │
│                                              │
│  No hardcoded vocabulary. No enforcement.    │
│  No observation. Vocabulary-agnostic.        │
└────────────────┬─────────────────────────────┘
                 │ registers taxa,
                 │ entities, properties,
                 │ matchers, compilers
┌────────────────┴─────────────────────────────┐
│       first-party sandbox consumer           │
│            (umwelt.sandbox)                  │
│                                              │
│  • vocabulary registration:                  │
│      world / capability / state              │
│  • workspace builder                         │
│  • writeback + manifest                      │
│  • hook dispatcher                           │
│  • nsjail compiler                           │
│  • bwrap compiler                            │
│  • lackpy-namespace compiler                 │
│  • kibitzer-hooks compiler                   │
│                                              │
│  One consumer of core umwelt among many.     │
│  Ships in the same package for convenience.  │
└──────────────────────────────────────────────┘

Other consumers (blq integration, agent-riggs integration, future
policy domains) register their own taxa and compilers against core
umwelt the same way the sandbox consumer does. None of them are
privileged; all are regular consumers of the common-language contract.
```

## Status

**v0.6.0 released.** Building on v0.5.2 (VSM-aligned taxa, `use[of=...]`, cross-axis cascade, DuckDB compile target). v0.6 adds:

- **Resource block model**: Single `resource` entity with properties replaces per-resource singletons. Cleaner vocabulary and CSS selectors.
- **World State Layer** (`umwelt.world`): YAML-based world file parser with shorthand expansion, vocabulary validation, and three-level materialization (summary/outline/full). `umwelt materialize` CLI command. PyYAML dependency.
- **PolicyEngine** (`umwelt.policy`): Consumer-facing Python API wrapping a compiled SQLite database. Three constructors (`from_files`, `from_db`, programmatic builder). Four query modes: resolve (cascade resolution), trace (explain why), lint (smell detection), select (entity filtering). COW `extend()` for immutable fork-and-specialize. World file entities populate the same SQL schema as matchers. Typed projection views (tools, modes, etc.) embedded in compiled databases.
- **Mode filtering**: `mode#review tool { allow: false }` gates rules by active mode. Both in-memory cascade resolver and SQL PolicyEngine paths support `mode` parameter. Unscoped rules always apply; mode-gated rules only fire when that mode is active.
- **Fixed constraints**: Post-cascade clamping for safety-critical properties via `fixed_raw` in world files. Applied after cascade resolution regardless of mode.
- **World file composition**: `require:`, `include:`, `exclude:` for composing world files with cycle detection and merge-order semantics.
- **CompositeMatcher**: Multiple matchers per taxon, enabling plugin coexistence.
- **Plugin autodiscovery**: Entry point registration via `umwelt.plugins` for third-party plugins.
- **Cross-taxon validators**: `CrossTaxonValidatorProtocol` for pre-compilation invariant checks spanning taxa.
- **Altitude filtering**: `PropertySchema.altitude` field with `_filter_by_altitude()` so compilers only receive properties at their enforcement altitude.
- **Compiler `**options`**: `Compiler.compile()` accepts caller context (`workspace_root`, `mode`, etc.).
- **Shared event schema**: Six observation properties on `audit/observation` for consistent tool monitoring across plugins.

PolicyEngine replaces the separate ducklog package for consumers like Kibitzer and Lackpy — they query resolved policy via `engine.resolve()` instead of raw SQL. See [`docs/superpowers/specs/2026-04-20-policy-engine-design.md`](../superpowers/specs/2026-04-20-policy-engine-design.md) for the full design spec.

854 tests total. See [`docs/superpowers/plans/`](../superpowers/plans/) for the active implementation plans and [`docs/vision/evaluation-framework.md`](./evaluation-framework.md) for the claim ledger.

## Document map

| File | Purpose |
|---|---|
| [`README.md`](./README.md) | This file — orientation and scope. |
| [`policy-layer.md`](./policy-layer.md) | **The framing.** umwelt as the common language of the specified band. Three-layer regulation. Why CSS. What umwelt is and is not. Relationship to the rest of the stack. |
| [`entity-model.md`](./entity-model.md) | **The structural contract.** Five taxa (world / capability / state / actor / policy). Selector grammar. Cascade. Declaration comparison semantics. Plugin registration. Desugaring from legacy at-rules. |
| [`view-format.md`](./view-format.md) | The view file format: grammar, at-rules, selectors, declarations, worked examples. |
| [`package-design.md`](./package-design.md) | Full package architecture, module layout, public API, runtime, roadmap. Core + sandbox split. |
| [`implementation-language.md`](./implementation-language.md) | Language choice (Python vs Rust), parser dependency (tinycss2), port-ready decomposition principle. |
| [`compilers/index.md`](./compilers/index.md) | Compiler taxonomy — implemented and planned, local-vs-remote locality axis, sync-vs-async, how to add new compilers. |
| [`compilers/nsjail.md`](./compilers/nsjail.md) | Mapping from view constructs to nsjail's protobuf textproto format. |
| [`compilers/bwrap.md`](./compilers/bwrap.md) | Mapping from view constructs to bwrap's argv format. |
| [`world-state.md`](./world-state.md) | **The world state layer.** Three-layer architecture (vocabulary/world/policy = DTD/DOM/CSS). YAML world files, discovery recipes, projections, materialization, SQL schema extensions. |
| [`linter.md`](./linter.md) | **The cross-format linter.** Lint pass over world file + policy as a pair. Directional properties, permissive-override detection, specificity conflict analysis, drift detection. |
| [`evaluation-framework.md`](./evaluation-framework.md) | **The claim ledger.** ~35 falsifiable claims, evaluation methodology per category, stopping rules. |
| [`notes/vsm-alignment.md`](./notes/vsm-alignment.md) | Beer's VSM as the organizing principle for umwelt's taxa. |
| [`notes/logic-semantics.md`](./notes/logic-semantics.md) | umwelt views as Datalog programs. Landscape: OPA, Cedar, Polar, Binder. What's novel. |
| [`notes/v05-retrospective.md`](./notes/v05-retrospective.md) | Honest assessment: what emerged, what's right, what's missing. |
| [`../superpowers/specs/2026-04-20-policy-engine-design.md`](../superpowers/specs/2026-04-20-policy-engine-design.md) | **PolicyEngine design spec.** Knowledge query API, SQL compiler extensions, world file population, projections, lint, observability. |

Future documents (not yet written):

- `compilers/lackpy-namespace.md` — mapping to lackpy's namespace/tool restriction config
- `compilers/kibitzer-hooks.md` — mapping to kibitzer hook rules for in-session `@tools` enforcement (v0.6)
- `compilers/delegate-context.md` — the SELinux-coda view-projection compiler (v1.1)
- `runtime.md` — workspace builder, write-back, hook dispatcher design (currently folded into `package-design.md`)
- `view-bank.md` — phase 2: storage schema, retrieval, git-history distillation
- `security.md` — threat model, parser hardening, enforcement boundaries

## Recommended reading order

For newcomers who want the *why*: start with [`policy-layer.md`](./policy-layer.md), then read the [Ma series intro](https://judgementalmonad.com/blog/ma/00-intro) and the [ratchet review](https://judgementalmonad.com/blog/fuel/00-ratchet-review) for the theoretical grounding.

For newcomers who want the *what*: start with [`view-format.md`](./view-format.md) for the format, then [`entity-model.md`](./entity-model.md) for the structural contract.

For implementers: [`package-design.md`](./package-design.md) and [`implementation-language.md`](./implementation-language.md), then the compiler mapping tables in [`compilers/`](./compilers/).

## Related projects in the stack

umwelt is one piece of a larger specified-band regulation tool suite. Each piece has a sharp scope; umwelt exists to be the format layer that lets them interoperate.

- **[Ma of Multi-Agent Systems](https://judgementalmonad.com/blog/ma/00-intro)** — the theoretical framework. Specified band, grade lattice, four actors, layered regulation, configuration ratchet. umwelt is a concrete instantiation of the policy layer of this framework.
- **[Ratchet Fuel](https://judgementalmonad.com/blog/fuel/)** — the practitioner companion. Failures as product roadmap, the two-stage turn, sandbox specs as type signatures. umwelt's ratchet utility implements the crystallization stage for multi-dimension views.
- **[ducklog](https://github.com/teaguesterling/ducklog)** — the original relational backend (being replaced by `umwelt.policy`). Compiled views to DuckDB policy databases. The selector-to-SQL compiler and cascade resolution have been absorbed into `umwelt.compilers.sql`; the consumer-facing query layer is now `umwelt.policy.PolicyEngine`. `umwelt compile --target duckdb` still works for the DuckDB dialect. ducklog remains for backwards compatibility but new consumers should use PolicyEngine directly.
- **[kibitzer](https://github.com/teaguesterling/kibitzer)** — observation and coaching at the semantic altitude. Migrating from `ducklog.consumers.kibitzer` to `umwelt.policy.PolicyEngine` for mode definitions and tool surfaces.
- **[lackpy](https://github.com/teaguesterling/lackpy)** — language-altitude sandbox. Primary umwelt consumer for delegate orchestration. Consumes the `compilers/lackpy-namespace` compiler or ducklog's `lackpy_tool_config` view.
- **[blq](https://github.com/teaguesterling/lq)** — build log query. Captures observations (resource usage, command traces, strace output) that the ratchet utility consumes. DuckDB-native — shares the database substrate with ducklog.
- **[ratchet-detect](https://github.com/teaguesterling/judgementalmonad.com/blob/main/tools/ratchet-detect/)** — observation tool for Claude Code conversation logs. Another observation source for the ratchet utility.
- **[pluckit](https://github.com/teaguesterling/pluckit)** — CSS selectors for code. Called by umwelt (v1.1+) for selector-level extraction inside `file` blocks. Same CSS-as-variety-attenuator move applied to code AST.
- **[agent-riggs](https://github.com/teaguesterling/agent-riggs)** — cross-session auditor. Consumes umwelt views as data for pattern discovery across conversations.
- **[sitting_duck](https://github.com/teaguesterling/sitting_duck)** — DuckDB extension for CSS-selector AST queries. Convergent design with ducklog's selector-to-SQL compiler — same CSS→SQL pattern over different tables.
- **[nsjail-python](https://github.com/teaguesterling/nsjail-python)** — Python wrapper for nsjail. Not a dependency of umwelt; umwelt emits nsjail's native textproto directly.
