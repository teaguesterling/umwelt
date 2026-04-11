# umwelt: The Policy Layer

*A readable policy-specification layer for a specified-band Harness. Views are crystallization artifacts; compilers translate them into whatever enforcement tool's native format the target altitude expects.*

---

## What umwelt actually is

**umwelt is the common language of the specified band.**

A specified-band Harness regulates across multiple altitudes — OS sandboxes, language interpreters, semantic hooks, conversational context — and across multiple tools at each altitude. Every component involved needs to agree on what's being regulated, why, and to what bounds. Without a shared vocabulary, each tool invents its own: nsjail has protobuf textproto, bwrap has argv flags, lackpy has namespace dicts, kibitzer has hook rules, blq has TOML sandbox specs, claude-plugins has settings.json. All of them are describing variants of the same thing — what the actor can see, edit, call, trigger, and consume — but none of them can read each other's descriptions, and none of them compose.

umwelt is the lingua franca those tools translate from. A view file (`.umw`) declares, in CSS-shaped syntax, what entities exist in the world the actor operates inside and what policies apply to them. Compilers translate the view into whatever native format each enforcement tool already accepts — nsjail textproto, bwrap argv, lackpy namespace dict, kibitzer hook rules. Observation tools produce evidence in the same vocabulary so the ratchet can propose revisions. The Harness's own regulatory intent is written down as views. The specified band has a shared language because umwelt defines one, and every component in the band — enforcers, observers, auditors, coaches, consumers — can read it.

This document is the *framing*: why umwelt exists as its own thing, what architectural slot it fills, and what it is not. The format itself is specified in [`view-format.md`](./view-format.md), the entity model in [`entity-model.md`](./entity-model.md), and the compiler taxonomy in [`compilers/index.md`](./compilers/index.md).

umwelt is a dependency-leaf package. It parses views, represents them in memory, applies policy rules via selectors and cascade, and emits native configs for the enforcement targets. It imports no enforcement tool's Python wrapper at runtime. The things umwelt consumers care about — sandboxes, namespaces, hook systems, retrieval policies — are at altitudes umwelt describes but never runs. That's the whole reason it can *be* the common language: it has no loyalty to any particular enforcement tool, so every tool can compile from it without coupling.

---

## The load-bearing context: the specified band

umwelt's architecture only makes sense against a specific theory of how multi-actor systems stay regulatable. That theory is developed in depth in the [Ma of Multi-Agent Systems](https://judgementalmonad.com/blog/ma/00-intro) series. The parts umwelt depends on:

**Every multi-actor system has four kinds of participant** (Principal, Inferencer, Executor, Harness) and every message passes through the Harness. The Harness is at the hub *because* it's the only participant whose behavior you can fully describe by reading its rules — it has specified decision surface.

**The grade of any actor is a pair `(world coupling, decision surface)`** on a product lattice. Characterization difficulty is supermodular: reducing either axis has larger effects when the other is high. A trained Inferencer with broad world coupling is nearly impossible to characterize; the same Inferencer with scoped world coupling is manageable.

**The specified band is the region where decision surface stays transparent regardless of world coupling.** The Linux kernel sits at `(open, specified)` — vast world coupling, transparent rules, readable source. The Harness must stay in the specified band. The moment you put trained judgment in the regulatory loop — LLM-based safety evaluation, ML anomaly detection, trained routing — the cross-term activates and the regulator becomes as opaque as what it regulates. That's the failure mode every modern security-with-ML system walks into.

**The OS existence proof**: you can regulate arbitrary computation at high world coupling while staying specified. The trick is layered regulation:

- **Layer 1 — Constraints**: bound what's *possible*. Namespaces, cgroups, seccomp filters, capabilities. These don't observe; they limit. `pid_namespaces` doesn't care what your process is trying to do; it just makes certain things impossible.
- **Layer 2 — Observation**: report what *happened*. `/proc`, audit logs, strace, process tables. These don't decide; they produce data for the policy layer. Specified observation.
- **Layer 3 — Policy**: decide what's *allowed*, with specified rules over observed state. SELinux, AppArmor, firewall rules. The rules are readable. They operate over vast observed state. The composition of three specified layers is still specified.

**umwelt is the authoring layer for Layer 3.** Views are the specified policy. Compilers emit Layer 1 configs from views. Observation is delegated to other tools (blq, ratchet-detect, kibitzer, strace) — umwelt consumes their outputs but does not observe directly. Enforcement is delegated to Layer 1 (nsjail, bwrap, lackpy's validator, kibitzer's hooks). Inference is forbidden in the policy layer — view rules must be specified, readable, and decidable by machinery in the Harness.

---

## Why CSS

The choice of surface syntax is not cosmetic. It's the load-bearing design decision of the whole package.

CSS already is a policy language. Styling is *one* policy domain — presentational. The primitives CSS provides — selectors (pattern match against a hierarchical queryable world), cascade (conflict resolution across overlapping rules with specificity and document order), declarations (properties attached to matched entities), forward compatibility (unknown constructs ignored with a warning) — are not specific to rendering pixels. They're a general-purpose pattern for *broadly or finely selecting entities in a structured world and attaching policy to the matches*.

Two specific arguments, from the [Ma framework](https://judgementalmonad.com/blog/ma/02-the-space-between) and the [Lackey Papers](https://judgementalmonad.com/blog/tools/lackey/03-the-specialization-lives-in-the-language):

**Dialect design is cheaper than fine-tuning.** You want a specified target language that LLMs can produce reliably on day one without training. The cheapest path is to pick a surface syntax the model already knows deeply. Every code-trained LLM has seen CSS millions of times — grammar, selectors, cascade, everything down to the punctuation. Borrowing that familiarity means the model can produce valid view files from the prompt alone, with no fine-tuning and minimal examples. The dialect's *domain* (sandbox policies) is new; the dialect's *shape* (CSS) is old. pluckit made the same move: selectors for code instead of selectors for HTML, because the grammar transfers even when the domain doesn't.

**Variety attenuation applied to policy.** CSS is what Beer's cybernetics calls a *variety attenuator*: it restricts the output space the author (or generator) can produce. A valid CSS stylesheet is a tiny subset of possible text, and the restrictions are exactly what make it parseable, validatable, and compilable. The same attenuation applies to umwelt views: the grammar restricts the policy space to things the Harness can decidably evaluate. A view is always in the specified band because its grammar forbids the constructs that would push it out.

Combined: CSS gives umwelt a surface that LLMs can write, humans can read, validators can check, and compilers can translate. Nothing else on the shelf provides all four at once with this little design work.

---

## The architectural slot, in one picture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                    The Specified-Band Harness                   │
│                                                                 │
│   ┌──────────────┐       ┌──────────────┐      ┌──────────────┐ │
│   │   Discovery  │──────▶│  umwelt view │─────▶│  Enforcement │ │
│   │   (Layer 2)  │       │   (Layer 3)  │      │   (Layer 1)  │ │
│   └──────────────┘       └──────────────┘      └──────────────┘ │
│          ▲                       │                     │       │
│          │                       │                     │       │
│      observes                compiles               bounds     │
│          │                       ▼                     ▼       │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              Actor (Inferencer + Executor)               │  │
│   │  operates inside the umwelt the view describes           │  │
│   └──────────────────────────────────────────────────────────┘  │
│                              │                                 │
│                          generates                             │
│                              ▼                                 │
│                       failure stream ─────┐                    │
│                                            │                    │
│                                     ratchet feedback           │
│                                            │                    │
│          (discovery observes failures, crystallizes new view)  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

- **Discovery tools** (blq, ratchet-detect, strace, kibitzer observation mode) sit in Layer 2. They observe what the actor actually does — files read, tools called, resources consumed, failures hit. They produce specified data for crystallization. umwelt does not do discovery; it consumes discovery outputs.
- **umwelt views** sit in Layer 3. A view is a *crystallization artifact*: the current committed understanding of what the actor needs, expressed as specified policy over entities. Views are readable, hashable, version-controllable, diffable — they behave like source code because they are.
- **Compilers** translate views into Layer 1 enforcement configs. nsjail textproto, bwrap argv, lackpy namespace restriction dict, kibitzer hook rules — each enforcement target has its own native format, and the compiler writes directly to it. No intermediate Python wrapper.
- **Enforcement tools** (nsjail, bwrap, lackpy's validator, kibitzer's semantic hooks) bound what's possible at their altitude. umwelt does not enforce — it describes bounds in a form enforcement tools accept.
- **The ratchet** closes the loop. When the actor's failure stream shows that the current view is wrong (too loose, too tight, missing a capability, blocking a legitimate operation), the discovery tools capture the evidence and the view is revised. Each revision is a turn of the ratchet. The view grows more accurate with use. This is the process documented in [Ratchet Fuel](https://judgementalmonad.com/blog/fuel/) and [The Configuration Ratchet](https://judgementalmonad.com/blog/ma/the-configuration-ratchet).

The diagram is in the specified band because every arrow in it is specified: discovery is specified analysis of observed data (SQL over event logs, not trained models), view parsing is specified (a CSS-shaped grammar), compilation is specified (a mapping table from entities to target configs), enforcement is specified (kernel-level constraints).

And every arrow in the diagram *speaks the same language*. Discovery tools write their output in the umwelt vocabulary (as proposed view revisions). Compilers read the umwelt vocabulary and emit target-native configs. Enforcers consume the compiler outputs but could, in principle, also read umwelt views directly for auditing purposes. The ratchet loop closes through the shared language: observation → view revision → compilation → enforcement → observation, all talking about the same entities, the same attributes, the same policy declarations at every step. That's what "common language" means in operational terms — not just "a format a lot of tools support" but "a vocabulary the whole regulatory loop uses end-to-end."

---

## What umwelt is

**A format.** The `.umw` view file: CSS-shaped declarative policy, readable by humans, writable by LLMs borrowing pre-trained CSS familiarity, parseable by tinycss2, checkable by a validator, compilable to native enforcement configs.

**A parser + AST.** `umwelt.parse(text) -> View` is a pure function. The View is a frozen dataclass representing the rules. The parser accepts unknown at-rules and declarations with warnings, preserving them for forward compatibility.

**An entity-model framework.** Views attach policy to entities. The entity taxonomy is *pluggable*: core umwelt defines no taxa, and consumers (sandbox, blq, lackpy, kibitzer, …) register their own taxa with typed attributes and selector semantics. Registration makes entities first-class declarations — each has a description, a category, documentation — which aids discoverability and lets tooling enumerate the policy surface of any installed consumer. See [`entity-model.md`](./entity-model.md) for the full model.

**A cascade resolver.** When multiple rules match the same entity, the cascade picks the winner via document order and selector specificity — CSS's conflict resolution, generalized to any entity type. Cascade is always specified.

**A compiler registry.** Each enforcement target has a compiler module. The compiler is a pure function `compile(view: View) -> target_format`. New targets register themselves; umwelt has no built-in coupling to any specific enforcement tool.

**A set of utilities for the ratchet.** `compile --target X` (translate policy to a native config), `dry-run` (evaluate which entities each rule matches against a supplied world snapshot without invoking the enforcement tool), `check` (validate and report warnings), and — as a first-class capability — `ratchet`: given a trace of actor behavior, propose a minimal policy consistent with the observed behavior. The ratchet utility is where umwelt stops being a parser and starts being a feedback loop.

---

## What umwelt is *not*

**Not an enforcement mechanism.** umwelt emits configs for enforcement tools; it does not execute actors or gate tool calls itself. nsjail enforces nsjail configs. bwrap enforces bwrap flags. lackpy's namespace validator enforces tool restrictions. kibitzer's hooks enforce `@tools` rules at the semantic altitude. umwelt produces the specifications those systems consume.

**Not a discovery tool.** umwelt does not observe. Observation tools (blq for build/test/command runs, ratchet-detect for Claude Code conversation logs, strace for syscall-level observation, kibitzer for in-session tool usage) each have their own job, their own data stores, and their own query surfaces. umwelt reads their outputs when it's time to ratchet a view, but it does not capture events directly.

**Not a runtime orchestrator.** Running a delegate in a sandbox, dispatching tool calls, composing multi-agent pipelines — those are orchestration concerns, handled by lackpy / kibitzer / agent-riggs / claude-plugins. umwelt provides the policy-layer input to those systems; it does not replace any of them.

**Not a fine-tuned DSL.** The grammar is fixed and specified. umwelt does not learn, adapt, or infer. The ratchet is not a training loop; it's a specified analysis over captured failures that proposes a new view for human review. The view is the result of the ratchet, not its machinery.

**Not a policy enforcement point (PEP).** Views describe bounds. Enforcement tools decide how to realize them. If an nsjail compiler emits a textproto that nsjail subsequently rejects, that's a compiler bug; umwelt does not re-implement nsjail's config validator. If a view describes a bound that no current compiler can express, the rule is still valid in the view — future compilers may be able to realize it. Forward compatibility applies at the policy layer, not at enforcement.

**Not a controller in Beer's VSM sense.** umwelt is specified coordination (System 2). The thing that decides *which* view to apply for a given task, *when* to ratchet, *whether* to escalate — that's control (System 3), and it lives in a different layer. lackpy's mode controller, kibitzer's coaching engine, and blq's tighten workflow are examples of System 3 functions that consume umwelt views; umwelt itself has no decision loop.

---

## Relationship to adjacent tools

The stack has been filling in one project at a time. Each project owns a sharp scope; umwelt exists to be the place view-layer concerns live so none of the others has to grow an awkward sub-component for them.

### Ma (theoretical framework)

[The Ma of Multi-Agent Systems](https://judgementalmonad.com/blog/ma/00-intro) is the theory umwelt is a concrete instantiation of. The specified-band argument, the grade lattice, the layered-regulation strategy, the four actors, and the configuration ratchet all come from that series. Reading the Ma series is not a prerequisite for using umwelt — views work fine as "a sandbox DSL with compilers." But the architecture's load-bearing reasons are there, and design decisions in umwelt that would otherwise look arbitrary (why only specified rules, why CSS, why no trained components, why the entity taxonomy looks the way it does) become necessary once the Ma framing is in place.

### blq

[blq](https://github.com/teaguesterling/lq) is the build-log query tool and the first concrete umwelt consumer. blq already has a sandbox spec model: eight dimensions (network, filesystem, timeout, memory, cpu, processes, tmpfs, paths), named presets (readonly, test, build, integration, unrestricted, none), a profile/suggest/tighten workflow, and Ma-grade annotations (grade_w, effects_ceiling) stored alongside every run. blq also has the observation half of the ratchet implemented — it captures resource usage from cgroups, parses strace output, stores everything in DuckDB, and already writes `sandbox suggest` and `sandbox tighten` queries.

What blq does not have — and what umwelt provides — is a *shared format* for expressing these specs across consumers. blq's sandbox specs are TOML tables attached to named commands in `commands.toml`. They work for blq. They do not compose with lackpy's namespace restrictions, kibitzer's hook rules, or agent-riggs' audit queries — each of those tools would need its own ad-hoc format. A view file expresses the same information in a form all of them can consume. The sandbox consumer of umwelt will read blq's TOML-shaped specs at first and generate views from them; eventually (if it's worth doing) the flow inverts and blq consumes views directly.

The ratchet utilities in umwelt are designed to interoperate with blq's event store: given a blq database and a current view, propose the minimum view consistent with observed runs. This is exactly what blq's `sandbox tighten` does at the single-spec level; umwelt generalizes it to multi-spec views that span tools, workspaces, and hooks together.

### ratchet-detect

[`ratchet-detect`](https://judgementalmonad.com/blog/tools/ratchet-detect) is the observation tool for Claude Code conversation logs. It reads the JSONL event store, runs DuckDB queries to find repeated bash patterns, classifies failures into a taxonomy, and reports ratchet candidates. It is the counterpart to blq but for Harness-level conversations instead of command executions. Both are specified observation tools that produce data umwelt's ratchet utility can consume.

### pluckit

[pluckit](https://github.com/teaguesterling/pluckit) is jQuery for source code — CSS selectors over AST nodes via tree-sitter and sitting_duck's DuckDB extension. umwelt depends on pluckit (optionally, v1.1+) for evaluating nested selectors inside `@source` blocks at node granularity. The dependency is one-directional: umwelt imports pluckit; pluckit does not know umwelt exists. pluckit and umwelt share the CSS-selector grammar but target different worlds — pluckit's world is the AST, umwelt's world is the entity graph the views describe, with source code as one of many taxa.

### lackpy

[lackpy](https://github.com/teaguesterling/lackpy) is the language-altitude sandbox — restricted Python execution, structured tool calls, namespace validation, kit-based tool organization. lackpy is the primary delegate orchestrator: it reads a view, builds a workspace, dispatches the delegate, enforces the namespace, and returns results. lackpy imports umwelt for the view runtime. lackpy does not know about nsjail or bwrap — those are OS-altitude concerns handled by umwelt's compilers. lackpy cares about the language-altitude compiler (future `compilers/lackpy_namespace.py`), which emits a lackpy namespace restriction dict directly from a view.

### kibitzer

[kibitzer](https://github.com/teaguesterling/kibitzer) is the observation-and-coaching layer for running Claude Code sessions. It watches tool calls, compares them against view-derived rules, and fires coaching messages when the agent is about to do something outside the view's allowance. kibitzer consumes umwelt for the `@tools` rules and their hook-based enforcement, via the `compilers/kibitzer_hooks.py` compiler. kibitzer is semantic-altitude enforcement; it handles what the OS sandbox can't see (tool choice, context injection, session-level patterns).

### agent-riggs

[agent-riggs](https://github.com/teaguesterling/agent-riggs) is the cross-session auditor. It consumes umwelt views and the view bank (v2 concern) to identify patterns that recur across conversations, teams, or projects. It's the meta-ratchet — the tool that finds ratchet candidates across ratchet candidates. agent-riggs operates on views as data, not as executable policy.

### sitting_duck

[sitting_duck](https://github.com/teaguesterling/sitting_duck) is the DuckDB extension for CSS-selector AST queries. It's the substrate pluckit sits on and has no direct relationship with umwelt. Listed here for completeness of the stack.

---

## The ratchet, applied to policy

The configuration ratchet says: high-ma exploration → specified artifact → low-ma application, repeated. For tools, the artifact is a structured tool interface; for configurations, it's a cached config; for security, it's a profile; for diagnostics, it's a runbook. For umwelt, **the artifact is a view.**

Every view represents the current committed understanding of what the actor needs. Views evolve through the same two-stage turn:

**Stage 1 — Discovery.** The actor runs against a looser view (or no view at all, for truly novel tasks). The discovery tools capture what happened: which files were read, which tools were called, which resources were consumed, which failures were hit. This is specified observation (DuckDB over event logs, cgroup stats, strace output) — no trained judgment in the loop.

**Stage 2 — Crystallization.** The observations are turned into a view revision. What `@source` patterns would match the files actually read? What `@tools` allowlist would admit the tools actually used? What `@budget` limits would accommodate the observed resource usage with headroom? The view compiles to enforcement configs and replaces the previous one. The ratchet turns.

This is what blq's `sandbox suggest` and `sandbox tighten` do at the single-spec level — and what umwelt's ratchet utility generalizes to multi-spec views that span workspaces, tools, budgets, and hooks simultaneously. The ratchet at umwelt's scale crystallizes not just a resource limit but a full operating envelope.

The ratchet does not auto-commit changes. The crystallized view is proposed to a human (or to a System-3 controller) for review and commit. The automation is specified end to end, but the commit point is human judgment. This is the same structure as blq's `sandbox tighten --dry-run` followed by a manual `--apply`, generalized.

### Type honesty for views

The [two-stage turn post](https://judgementalmonad.com/blog/fuel/02-the-two-stage-turn) introduces *type honesty*: a crystallized artifact's interface contract must be backed by its implementation. `CurrentTime() -> Timestamp` is honest; `Bash("date") -> IO String` is also honest, but the type is broader because the implementation is broader. You cannot narrow a type you can't back with structural commitments.

Applied to views: the view's policy commitments must be backed by the compiler's ability to realize them in enforcement. If a view says `@network { deny: * }` and the nsjail compiler emits `clone_newnet: true`, the policy is honest — the enforcement tool bounds what's possible. If a view says `@tools { allow: Read }` and no compiler can enforce tool restrictions at the current altitude, the view is *aspirational* at that altitude — still valid, still useful as documentation and for altitudes that can enforce it, but not backed by structural commitments at the OS altitude. The view's honesty is per-altitude, and compilers declare what altitude they enforce at.

This has a concrete consequence for v1: the compiler metadata includes an altitude declaration (OS / language / semantic / conversational) and umwelt can report, per view, which rules are honestly enforced by the currently-registered compilers vs. which are declarative-only. The `dry-run` utility surfaces this — "this view's `@tools` rules will not be enforced by any registered compiler; consider installing `umwelt-kibitzer`."

---

## The SELinux coda and view transparency

Post 8 of the Ma series warns about the SELinux failure mode: a policy that's specified from the administrator's perspective but opaque to the governed actor. The actor can't model its own environment because the constraints are invisible, so it wastes decision surface learning the boundaries empirically by probing and failing. That waste is a direct tax on system performance — permission denials that could have been avoided if the rule was in the actor's scope.

The design implication for umwelt is explicit and load-bearing:

**Views should be projectable into the governed actor's scope.**

Concretely: there should be a first-class compiler target (or a dedicated utility) that renders a view as a prompt fragment, a README section, a tool-description appendix — whatever form lets the actor read its own constraints. The Inferencer operating under a view should be able to reason about what's allowed and what isn't, not learn it by trial and error. This is an instance of the *variety amplifier* pattern from Beer's variety engineering: the constraint is re-projected into the actor's world, expanding its effective model without changing its own decision surface.

This is planned as a v1.1 compiler target: `compilers/delegate_context.py` or similar, emitting a view in a form consumable by the Inferencer's prompt construction. The entity model document flags the requirement so the taxonomy leaves room for it.

---

## Non-goals, stated explicitly

**No training data path.** The ratchet is specified analysis, not machine learning. No view is ever fine-tuned, gradient-descended, or statistically inferred. The crystallization step is SQL (or equivalent specified analysis) over captured events, and the output is a view revision reviewed by a human or a specified controller. If a view ever depends on trained judgment to generate or validate, it's no longer in the specified band and the whole architecture fails.

**No runtime enforcement loop.** umwelt does not run the actor and check rules as the actor acts. That's what nsjail and lackpy and kibitzer do, each at their own altitude, using configs umwelt compiled for them. umwelt's runtime is limited to: parse a view, build a workspace, dispatch hooks, compile to a target, and — with the ratchet — propose a revision from observed data. No live policy evaluation, no in-loop decision-making.

**No opinions about orchestration.** umwelt does not care whether you're running a single-agent Claude Code session, a multi-agent planner/worker/reviewer pipeline, a batch job farm, or a long-running MCP server. Views describe policy for the actor-in-their-umwelt, regardless of how the actor is invoked. The only thing umwelt asks of its consumers is that they give it a `View` and a world to build the manifest against.

**No view authoring UX.** v1 is read-only: views are parsed, validated, compiled, and dry-run-able. Programmatic view construction (`View.to_string()`, AST-to-text emission) is a v1.1 feature, needed first by the ratchet utility and then by the view bank and agent-riggs. Interactive view editing, visual configuration, or a GUI builder is entirely out of scope.

**No view bank in v1.** Storage of views across projects, retrieval by similarity, distillation of git history into views — these are phase-2 concerns, documented in a future `view-bank.md`. The module slot exists in the package layout; its contents are empty until the first-party consumers need it.

---

## How to read the rest of the docs

This document (`policy-layer.md`) is the framing. Start here for *why* umwelt looks the way it does.

[`view-format.md`](./view-format.md) is the format reference: grammar, at-rules, declarations, worked examples. Start here for *what a view file looks like*.

[`entity-model.md`](./entity-model.md) is the model reference: entity taxa, attribute schemas, selector grammar, cascade semantics, plugin registration. Start here for *what entities views attach policy to and how selectors match them*.

[`package-design.md`](./package-design.md) is the implementation reference: module layout, public API, runtime components, roadmap. Start here for *how the package is built*.

[`implementation-language.md`](./implementation-language.md) records the Python-plus-tinycss2 choice and the port-ready decomposition principle.

[`compilers/index.md`](./compilers/index.md) is the taxonomy of enforcement targets: which are implemented, which are planned, how to add a new one.

[`compilers/nsjail.md`](./compilers/nsjail.md) and [`compilers/bwrap.md`](./compilers/bwrap.md) specify the OS-altitude compilers in detail.

The README sits above all of these as the one-paragraph orientation.

---

## Status

Pre-implementation. The architecture is specified; the package layout is designed; the v0.1 walking skeleton is scoped. The first concrete code lands once the entity model is agreed (see [`entity-model.md`](./entity-model.md)) and the v0.1-core specification in `docs/superpowers/specs/` is updated to reflect the vocabulary-agnostic structure.

umwelt exists because the view-layer concern kept falling out of every tool that tried to host it — lackpy, blq, kibitzer, agent-riggs, claude-plugins. Each of those has a sharp scope and absorbing view-layer concerns bent their identity. umwelt owns the concern so they don't have to — and the payoff isn't just that lackpy and kibitzer and the others get to keep their identities, it's that for the first time they share a vocabulary. The common language of the specified band. One format every component in the regulatory loop can read, write, compile, and reason about. That's what umwelt is for.
