# Note: umwelt views as logic programs — relatives, precedents, and what's novel

*Captured 2026-04-14, post-v0.5 design discussion. Intended as source material for a future blog post and as a reference when situating umwelt in the authorization-policy literature. Not user-facing — this is for whoever has to defend design choices against "isn't this just OPA?" questions.*

---

## Thesis

A umwelt view is a **Datalog program with CSS-shaped concrete syntax, a Viable-System-Model-partitioned predicate schema, and defeasible cascade semantics.** Every primitive in our language maps to a standard logic-programming primitive. The novelty is in the *schema*, the *syntax*, and the *subject* (LLM agents, not users or services) — not in the underlying formalism.

This note is a map of the territory.

---

## 1. The translation: view → Horn clauses

Each simple selector is a predicate application. Each attribute filter is a conjunct. The descendant combinator is just `∧`. `:has(...)` is existential. `of=` is unification — the `of` relation binds one axis's entity to another's.

Example. In umwelt syntax:

```css
inferencer#opus tool[name="Edit"] use[of="file#/src/auth.py"] {
  editable: true;
}
```

As a Horn clause:

```prolog
editable(U, true) :-
    inferencer(Inf), id(Inf, 'opus'),
    tool(T), name(T, 'Edit'),
    use(U), of(U, File),
    file(File), id(File, '/src/auth.py').
```

No construct in our syntax lacks a standard logic-programming translation:

| umwelt syntax | Logic-programming counterpart |
|---|---|
| `element` | unary predicate `element/1` |
| `#id` | `id(X, 'value')` conjunct |
| `.class` | `has_class(X, 'value')` conjunct |
| `[attr="value"]` | `attr(X, 'value')` conjunct |
| `[attr^="prefix"]` | `attr(X, V), prefix(V, 'prefix')` |
| `A B` (descendant) | `∧` (conjunction) |
| `A:has(B)` | existential quantification |
| `{ prop: value; }` | rule head |
| `use[of="X"]` | binding via the `of` relation |
| cascade specificity | defeasible preference over multiply-derived facts |

The view is a logic program in a narrow sense: finite-relation, non-recursive, deterministic over the closed world of entities declared in the view plus runtime state (active mode, current inferencer, current tool). That puts it in **Datalog**, not full Prolog — no function symbols, no recursion (yet), guaranteed termination, PTIME evaluation.

### Why this matters

If views are Datalog, the compiler protocol is queryable. Each compiler asks a different question of the same program:

- **nsjail**: `{(M, P, RO) : mount(M) ∧ path(M, P) ∧ readonly(M, RO)}`
- **bwrap**: same set, different encoding
- **lackpy-namespace**: `{T : tool(T) ∧ allow(T, true)}` plus denied/max-level/patterns
- **kibitzer-hooks** (v0.6): `{(Mode, P) : active(Mode) ∧ editable(U, true) ∧ of(U, F) ∧ path(F, P)}`

Today we hand-roll each compiler. Long-term, compiling views to Datalog IR and letting each compiler register queries collapses the compiler protocol into one primitive: `query: ResolvedView × Goal → FactSet`.

---

## 2. Cascade as defeasible reasoning

Pure Prolog resolves rule conflicts by search order. Datalog resolves by fixed-point — if two rules produce contradictory facts, the program has no stable model.

Neither is what CSS does, and neither is what we want.

umwelt's cascade matches **Defeasible Logic Programming** (García & Simari, 2004). Multiple rules can derive contradictory `editable(U, _)` facts; a meta-rule picks the winner by specificity. The specific reference in the DeLP literature is *generalized specificity*: rule R₁ defeats R₂ if R₁'s body is strictly more specific than R₂'s (more conjuncts, more bindings, stricter patterns).

Our `axis_count`-first specificity ordering is an approximation of strict generalized specificity. "Rules that touch more axes win over rules that touch fewer" is a weaker condition than "rules whose body conjuncts are a superset of other rules' bodies," but the two coincide for the selectors we care about. Tightening this to actual subset-defeat is a research-grade project; the approximation gets us 95% of the practical benefit.

**Answer Set Programming with preferences** (Brewka's *Logic Programming with Ordered Disjunction*, 2003) is the other formal foundation worth knowing. ASP + preferences handles multiple stable models by ranking them; our cascade is a one-answer special case of this.

### The specified-band connection

The Ma series' specified-band guarantee reduces, in logic-programming terms, to:

> Every entailed fact has a proof tree, and proof trees use only rules in the committed view.

Datalog gives us this natively via SLD resolution — proof trees are a side effect of evaluation. That's the audit story. S3\*'s job is to emit those proof trees as decisions are made, so every permission the delegate exercises is traceable to rules in the view.

This is directly the **proof-carrying authorization** tradition — Lampson (1999), Appel & Felten (PCA, late '90s), Abadi's delegation logic (2000s). We inherit their soundness machinery by choosing Datalog as the substrate.

---

## 3. The landscape — who else does this

### Currently deployed

**OPA / Rego** (Open Policy Agent, CNCF graduated 2021). Closest living relative. Rego is Datalog with extensions (set comprehensions, aggregations, partial evaluation). Deployed at Netflix, Pinterest, Capital One, Atlassian, Goldman Sachs. Kubernetes admission control uses it by default. *The* reference point for "logic-based cloud-native policy." Our differentiation from OPA: subject is an LLM agent, not a human or service; syntax is CSS, not a custom DSL; schema is VSM-partitioned; ratchet is a first-class authoring loop.

**Amazon Cedar** (launched 2023). Designed as an XACML successor with formal verification. Cedar's `principal / action / resource` decomposition converged on roughly our `(intel, op, use)` trio from the opposite design direction — they started from authorization practice and arrived at a three-axis partition; we started from VSM theory and arrived at the same shape. Worth noting the convergence in the blog post: when you take agent authorization seriously, some version of this trio is forced. Cedar's formal-verification work (published in the POPL/PLDI orbit) sets the bar for policy-language soundness proofs; if we want to make the specified-band guarantee rigorous in a paper, Cedar's approach is the template.

**Oso / Polar** (YC 2020). Literally a Prolog-for-authorization company. Polar is Prolog with surface-syntax ergonomics. Used in production at Intercom, Wayfair. Pivoted to a managed service (OSO Cloud) mid-2020s. Relevant as proof that "Prolog-shaped policy language" is commercially viable, not just academically interesting.

**SpiceDB / Permify / Warrant** — Zanzibar-family (Google's paper, 2019). Graph authorization over a database of relation tuples. Not Datalog exactly, but same Herbrand-universe-of-relations flavor. Aimed at fine-grained sharing (Google Docs–style ACLs). Not directly comparable to our agent-authorization use case; mention in passing as "adjacent but solving a different problem."

**Soufflé** (Oracle, 2016–present). Datalog engine for program analysis. Very active. Spawned successor languages (Flix, Datafun). If we ever need a production-grade Datalog backend, Soufflé is the reference implementation.

### Academic precursors (mostly 2000s)

**Binder** (DeTreville, MSR 2002). Distributed authorization in Datalog with explicit delegation predicates. Cited constantly but never productized. Ideas absorbed into OPA and Cedar. For delegate-chain reasoning (v1.1+ umwelt), Binder's delegation-predicate approach is the template.

**SD3** (Jim, 2001). Secure Dynamic Distributed Datalog. Policy language with proof-carrying enforcement. Same era as Binder, similar fate — influential research, no product.

**Cassandra** (Becker & Sewell, 2004). Another Datalog-based authorization system for medical records. Noteworthy for formal semantics given in the paper. Dead but cited.

**Datalog with Negation as Failure** (Ullman's textbook, 1989 and since). The formal foundation. Any serious treatment of our cascade semantics needs to cite Ullman.

### Research currents (active now)

**Differential Dataflow / Materialize** (McSherry, 2010s–present). Incremental Datalog evaluation at scale. If umwelt ever needs fast re-evaluation on view changes (live-edit in an IDE, streaming observation feeds), differential dataflow is the right engine.

**Flix** (active, major publications in POPL/ICFP). Datalog-with-effects, algebraic-effects-adjacent. Interesting for hook-dispatch semantics (our hooks are side-effecting; Flix has a story for that in a Datalog setting).

**Cedar's verification work** (Amazon, POPL 2024 and adjacent). Formal-methods applied to policy languages. Sets the bar for "our semantics are provably sound."

**Inductive Logic Programming** (Muggleton, FOIL, Progol, Aleph, 1990s–present). The tradition the ratchet lives in. Modern ILP systems (Metagol, Popper) do program synthesis from positive/negative examples. Our ratchet is specified ILP — rule induction without a learned model in the loop, just structural pattern mining over observation traces. The specified-band framing rules out neural ILP methods.

### Dead ends

**XACML** (OASIS, 2003–2010s). XML-based authorization. Committee-designed bloat. Nobody writes XACML by hand. Cedar's design doc explicitly cites XACML's failure modes as constraints: readable syntax, no XML, formal semantics. The umwelt equivalent of XACML's mistake would be emitting our Datalog IR as the user-facing syntax — don't. **The user writes CSS; the compiler sees Datalog.**

**OWL-full for access control**. OWL is based on description logic, not Datalog. OWL-full is undecidable in general. Some authorization research tried to use it (2005–2010). Didn't scale. Interesting as a cautionary tale about choosing too-expressive a formalism.

### The pattern in who survives

Every productized policy language of the last twenty years has:

1. A restricted logic-programming core (Datalog or near-Datalog).
2. A readable surface syntax that isn't the logic directly.
3. A compiler that lowers to an executable form.
4. Separation between authoring (what the policy says) and enforcement (what the gates do).

That's the shape we're building. Nothing novel in the structural choice.

The novel parts are three, and they're worth defending explicitly.

---

## 4. What's genuinely novel in umwelt

### A. CSS syntax as the authoring surface

OPA/Rego, Cedar, Polar, Binder, SD3 — every prior language invented its own DSL. The syntax was always a fresh cognitive load. Users had to learn the language before they could write a policy.

umwelt bets that **CSS is already a cognitive primitive for the agent-adjacent audience**. Every web developer, every documentation author, every person who has styled an HTML page knows how selectors work. Cascade is intuitive because people have debugged CSS specificity conflicts. Classes vs. IDs, attribute filters, descendant combinators — this is prior knowledge.

If we're right, umwelt is readable-on-first-contact. If we're wrong, we've invented yet another DSL with the added cost of surprising readers who expected CSS behavior and got policy behavior.

This is a UX bet, not a logic bet. The Datalog underneath is standard.

### B. VSM as the predicate schema

Stafford Beer's Viable System Model gets cited in:
- Organizational cybernetics (steady work since the 1970s)
- Agent-architecture literature (Stuart Russell's *Human Compatible*, Dietterich on reliable AI — passing mentions)
- Software-architecture retrospectives (occasional invocations)

**What I cannot find in the literature**: using VSM as the *partitioning of a policy language's predicate domains*. Using S1..S5 to structure *what the subject-predicates of a Datalog authorization schema should be*.

This is the move to defend. The argument:

1. Every authorization system has subjects, actions, and resources at minimum.
2. Agent authorization additionally needs: coordination (the harness), control (current regulation), intelligence (the model), identity (the principal), and audit (the observer).
3. These seven role-kinds aren't arbitrary — they're the five VSM systems plus environment and S3\* bypass.
4. Beer already worked out what each system does and how they relate. We inherit that for free.
5. The S3↔S4 inversion from Beer's original (regulator dominates regulated) is the specific move that makes the specified band coherent.

This is genuine novelty. The Ma series should own it.

### C. `use[of=...]` as the action-axis projection — additive to world-axis, not a replacement

Standard OS thinking separates a **file** (on disk, maybe on a read-only mount) from a **file descriptor** (a process's permissioned access to the file). A write succeeds only if both allow it. Capability theory (Levy, *Capability-Based Computer Systems*, 1984) formalizes the descriptor side as an unforgeable reference carrying permission.

umwelt lifts **both** into the policy syntax as first-class, independently-queryable predicates:

- `file.editable` / `mount.readonly` / `tool.allow` — *world-axis*: property-of-the-resource. "Is this file mounted writable?" "Does this network endpoint exist?"
- `use[of="file#X"].editable` / `use[of="tool#Y"].allow` — *action-axis*: property-of-the-access. "Does this access path grant edit rights through this tool?"

An enforcement decision conjoins them: the delegate can write to `X` iff `file#X.editable ∧ ∃use U. of(U, file#X) ∧ use.editable(U)`.

What's new relative to the landscape:

- **OPA/Rego** derives permissions at query time from relations — no syntactic primitive for the capability itself; the distinction between "resource is editable" and "this user has edit access" is encoded implicitly in rule bodies.
- **Cedar** puts permissions on `(principal, action, resource)` triples, collapsing the two axes into one evaluation.
- **Polar** puts permissions on predicates, similar to OPA.
- **umwelt** has distinct, first-class syntax for each axis. `file { editable: true }` expresses resource-nature; `use[of=file#X] { editable: true }` expresses access-grant. Both participate in cascade independently.

This matters for altitude stacking: OS-altitude enforcers (nsjail, bwrap) should read the world-axis (mount-level rw/ro); language-altitude enforcers (lackpy, kibitzer) should read the action-axis (per-delegate tool gating). The split in the syntax mirrors the split in enforcement.

Minor novelty in isolation but worth claiming — it makes audit explanations simpler ("resource R is editable (rule line 12); use U of R is editable (rule line 48); delegate exercised U") and it's the construct that lets the three-way join (`inferencer × tool × use[of=file]`) read naturally without conflating nature with access.

### D. Agent as subject

Every authorization language of the last twenty years had a human or a service account as the subject. The subject was deterministic, had stable identity, and acted on behalf of a known party.

LLM agents are:
- **Non-deterministic** in action choice.
- **Unbounded** in action-space expressivity (prompt-engineered tools appear and disappear).
- **Stochastic** in outcome given the same inputs.
- **Signal-generating** in their failures (ratchet-feedback).

The Ma series takes seriously that this changes what authorization *is*. Permissions aren't gates on a deterministic caller; they're bounds on a possibility-space. Failure isn't an error; it's input to the next iteration's ratchet.

This is the framing the blog post should lead with. "What if the subject of your policy language is an LLM?" Everything else — VSM, CSS syntax, `use[of=...]`, the ratchet — follows from answering that question rigorously.

### E. The ratchet as specified ILP

Ratchet = configuration ratchet = turn observations into specified rules.

ILP (Inductive Logic Programming) has a thirty-year literature: Muggleton's FOIL (1990), Progol, Aleph, modern Metagol and Popper. Given positive and negative examples, induce a logic program that covers the positives and excludes the negatives.

What's ours: **specified ILP** — rule induction without a neural or learned component in the mining loop. The ratchet sees failure traces, runs structural pattern matching, and proposes candidate rules in the *same Datalog our views are in*. The proposals are pasteable into the view. No model in the regulator.

The "specified" qualifier is doing work. Modern ILP work increasingly uses neural oracle loops (DeepProbLog, neural-symbolic integration). The Ma framing rules those out — the specified-band requires no opaque component anywhere in the authoring loop. That puts us closer to pre-2010 ILP (Progol, Aleph) than to current research, but with modern computing resources the classical approaches are probably sufficient for our scale.

### F. Proof trees as the audit artifact

Not novel in isolation. Lampson's "Proof-carrying authorization" (1999), Appel & Felten's PCA work, Abadi's delegation logic all have proof trees as core artifacts.

Newly relevant because: agent audit is a live problem *right now*. When a Claude Code instance makes a decision nobody understood in retrospect, "why did you let it do that?" is the question that matters. Grep-able logs of tool calls don't answer it. Proof trees do.

Old technique, new audience.

---

## 5. The zeitgeist, sharpened

**Is logic-programming-for-policy a dead tradition or a live one?** Live, but with a specific shape.

- **Cloud-native human/service authorization**: solved. OPA won. Cedar is the formally-verified second-generation.
- **Agent-to-tool authorization**: nascent. No standard language. Every framework (LangChain, AutoGPT, Claude Code hooks, OpenAI function-calling, MCP) hand-rolls its own ad-hoc guards.

We sit at the second category. The first category's solutions don't transfer cleanly:
- OPA's pull-based evaluation (service calls into OPA for each request) doesn't match hook-driven agent flow.
- Cedar's principal/action/resource trio doesn't cover coordination or intelligence.
- Polar's inheritance model targets RBAC, not stance-based regulation.

The space is open, and it's a market — Oso's pivot to AI-agent authorization (mid-2020s) is evidence that somebody with enough capital sees the opportunity. The question isn't whether to fight for this space; it's what shape the winning language has.

Our bet: agent-policy is different enough from service-policy that it needs a different schema (VSM), a different authoring surface (CSS), and a different feedback loop (ratchet). If we're right, umwelt is the reference language for the specified band. If we're wrong, we've built a well-designed boutique DSL.

---

## 6. Open questions and research directions

Worth flagging for later work:

1. **Strict generalized specificity** — prove or disprove that `axis_count`-first cascade approximates DeLP's subset-defeat. If it doesn't, find the counterexample and decide whether to fix it or accept the approximation.
2. **Datalog IR as compiler target** — v1.x project. If views compile to Datalog IR and compilers register queries, the compiler protocol collapses to one primitive. Interesting engineering problem.
3. **Recursive rules** — currently disallowed. Some policies want them ("transitively deny everything reachable from a denied resource"). Datalog with stratified negation handles this; requires careful semantics work.
4. **Formal soundness proof** — following Cedar's template, mechanize the specified-band guarantee in Lean or Coq. Paper-grade work.
5. **ILP backend for the ratchet** — currently ad-hoc pattern matching. Replacing with Aleph or Metagol would be rigorous. Open question whether the ergonomic cost is worth the formal gain.
6. **Differential evaluation** — live-updating views as observations stream in. Materialize-style incremental Datalog. Useful for IDE integrations.

---

## 7. References (for the blog post to plunder)

Not exhaustive. Just the names the blog author will want to have in hand.

**Foundational**:
- Ullman, *Principles of Database and Knowledge-Base Systems* (Datalog semantics, 1989)
- Levy, *Capability-Based Computer Systems* (1984)
- Beer, *Brain of the Firm* (VSM, 1972); *The Heart of Enterprise* (1979); *Diagnosing the System for Organizations* (1985)
- Muggleton, "Inductive Logic Programming" (1991)

**Classical access-control**:
- Lampson, "Computer Security in the Real World" (2000); proof-carrying authorization work (1999)
- Abadi, "Logic in Access Control" (2003), "A Calculus for Access Control in Distributed Systems" (1993)
- Appel & Felten, "Proof-Carrying Authentication" (1999)

**Datalog-based policy (2000s)**:
- DeTreville, "Binder, a Logic-Based Security Language" (2002)
- Jim, "SD3: A Trust Management System with Certified Evaluation" (2001)
- Becker & Sewell, "Cassandra: Flexible Trust Management, Applied to Electronic Health Records" (2004)

**Modern deployments**:
- Sandall et al., OPA / Rego (CNCF project, ~2016–present)
- Cutler et al., Cedar (Amazon, 2023); formal verification paper (POPL 2024 or adjacent)
- Oso / Polar (company launched 2020)
- Zanzibar paper (Google, 2019); SpiceDB as open-source successor

**Defeasible reasoning**:
- García & Simari, "Defeasible Logic Programming: An Argumentative Approach" (2004)
- Brewka, "Logic Programming with Ordered Disjunction" (2003)

**Research currents**:
- McSherry et al., Differential Dataflow (2013–present)
- Madsen et al., Flix (ongoing)
- Scholz et al., Soufflé (2016–present)
- Cropper & Dumančić, Popper (modern ILP, late 2010s–present)

**The Ma series itself**:
- `judgementalmonad.com/blog/ma/00-intro` and subsequent posts
- `judgementalmonad.com/blog/fuel/00-ratchet-review`

---

## 8. One-paragraph summary (for if somebody stops us in the hallway)

> A umwelt view is a Datalog program written in CSS syntax, partitioned by Stafford Beer's Viable System Model, cascading by generalized specificity, emitting proof trees for audit, and authored iteratively via an ILP-style ratchet over observed agent behavior. We're one of several tools reapplying logic-programming to policy in the LLM-agent era — alongside Oso, OPA, and Cedar — but the only one whose schema is VSM-derived and whose subject is explicitly a non-deterministic agent rather than a deterministic user or service. The formalism is forty years old; the syntax is thirty years old; the application is new.

---

*End of note. Blog author: everything in §4–§6 is fair game for a post; §7 is the citation pool.*
