# Evaluating umwelt — A Rigorous Framework

*Captured 2026-04-14. The framework by which umwelt is tested at every milestone. Treat as a living document — update the claim ledger when claims are added, strengthened, refuted, or retired.*

---

## Why this document exists

"Does umwelt work?" is not a useful question. umwelt makes several distinct claims, operating at different levels (formal, empirical, ergonomic, theoretical), aimed at different audiences (view authors, delegates, auditors, formal reviewers). A rigorous evaluation treats each claim as a **falsifiable proposition** and defines methodology, success threshold, and falsification test per claim.

The evaluation is useful only if it could, in principle, find umwelt wanting. A framework that can't fail a bad design isn't rigor — it's marketing.

Every test in `tests/` should map to a claim in the ledger below. Every claim should have at least one test or documented verification plan. When those lines go out of sync, the framework is no longer being run.

---

## Part 1 — The claim ledger

Every design decision umwelt has committed to is a claim. Writing them down explicitly is the first rigor move.

Each claim has an ID (category letter + number), a falsifier (what would make the claim false), and a tier (0 = foundational, 3 = aspirational).

### Category A — Semantic claims (what the language means)

| # | Claim | Falsifier | Tier |
|---|---|---|---|
| A1 | Every umwelt view has a unique, deterministic cascade-resolved fact-set given fixed runtime inputs. | Two resolver runs over identical view + input produce differing ResolvedViews. | 0 |
| A2 | Cascade specificity is a well-ordered preference over rules (no cycles, no ties after tiebreaking). | Construct a view where two rules have indistinguishable specificity and conflicting declarations without a document-order tiebreaker. | 0 |
| A3 | Cross-axis specificity is sound: rules that join more axes *are* more contextualized than rules that join fewer. | Construct a natural example where a cross-axis rule should be less specific than a single-axis rule with heavy attribute filtering. | 1 |
| A4 | The CSS-shaped concrete syntax is equivalent in expressive power to non-recursive Datalog with stratified negation. | Find a Datalog program of that class with no umwelt-view equivalent. | 3 |
| A5 | Every property declaration has a semantics specified by its `comparison` field (`exact`, `<=`, `>=`, `in`, `overlap`, `pattern-in`). | Find a property whose observed behavior differs from its declared comparison. | 1 |

### Category B — Enforcement claims (does the view bind the delegate)

| # | Claim | Falsifier | Tier |
|---|---|---|---|
| B1 | Compiler output faithfully implements the ResolvedView's semantics at its altitude. | Execute the compiled config; observe that the delegate can do something the view forbids, or is blocked from something the view allows. | 0 |
| B2 | Altitude stacking is additive — enforcement at a higher altitude cannot loosen constraints imposed at a lower altitude. | Find a lower-altitude compiler output that passes, but gets relaxed by the upper-altitude config. | 1 |
| B3 | Every compiler produces output accepted by its target tool's native validator (nsjail, bwrap, lackpy). | Produce a view whose compiled output is rejected by the target tool. | 1 |
| B4 | Every altitude's compiler faithfully rejects (at compile time) views it cannot express. | Compile a view whose semantics exceed the altitude, without error — then observe enforcement gap at runtime. | 1 |

### Category C — Audit claims (can you trace what happened)

| # | Claim | Falsifier | Tier |
|---|---|---|---|
| C1 | Every enforcement decision maps to a specific rule in the view (proof-tree traceability). | An enforcement event with no rule-level attribution. | 1 |
| C2 | `umwelt audit` detects genuine cascade widenings — places where a rule lets the delegate do more than an earlier rule did. | Audit misses a real widening (false negative) or flags a non-widening (false positive) at a measurable rate. | 2 |
| C3 | Proof trees for a decision are reproducible — running audit on the same view+inputs twice yields identical proofs. | Observed non-determinism. | 1 |

### Category D — Specifiability claims (can failures become rules)

| # | Claim | Falsifier | Tier |
|---|---|---|---|
| D1 | Observed delegate failures can be crystallized into rules the view accepts. | An observed failure that has no rule-level representation. | 1 |
| D2 | The ratchet is monotone: adding a ratcheted rule never loosens bounds, only tightens. | A ratchet proposal that widens the view. | 2 |
| D3 | Ratchet proposals are specified — no learned or opaque component in the proposal path. | A proposal whose derivation requires data outside the observation log + existing view. | 2 |

### Category E — Usability claims (can humans write and reason about views)

| # | Claim | Falsifier | Tier |
|---|---|---|---|
| E1 | CSS-literate authors can read a view and predict its behavior without prior umwelt training. | User study: median target user with CSS background fails to predict cascade outcome >30% of the time. | 2 |
| E2 | Errors in views surface at parse or resolve time with line-accurate messages. | A broken view compiles with silent fallback. | 2 |
| E3 | `umwelt diff` makes rule-level changes between view versions obvious. | Reviewer fails to notice a regression in a diffed view. | 2 |

### Category F — Agent-alignment claims (does the view bound an LLM)

| # | Claim | Falsifier | Tier |
|---|---|---|---|
| F1 | A delegate operating under a compiled view is constrained to the view's specified band regardless of prompting. | Find prompt that induces out-of-band behavior under a correctly-compiled view. | 0 |
| F2 | When a delegate hits a bound, it receives actionable feedback (what was denied, why, and what alternative modes exist). | Bound-hit produces silent failure or non-actionable error. | 1 |
| F3 | Modes (S3) can be switched dynamically by the delegate via the mode-switch tool, and switches are auditable. | Mode switch occurs without audit entry, or mode-switch does not change effective permissions. | 1 |

### Category G — Theoretical-fidelity claims (does umwelt instantiate the Ma framework)

| # | Claim | Falsifier | Tier |
|---|---|---|---|
| G1 | umwelt's taxa instantiate Beer's VSM systems with the S3↔S4 inversion documented. | Audit the taxa; find a system that maps ambiguously or a VSM concept unrepresented. | 3 |
| G2 | umwelt provides the specified band: the decision surface is transparent regardless of world coupling. | Find a decision whose derivation cannot be reproduced from the view + observed inputs. | 1 |
| G3 | umwelt is a policy-layer instantiation of the Layer 3 regulator in the three-layer strategy (constraint + observation + policy). | Show the layer's outputs do not suffice to drive Layer 1 enforcement. | 3 |

### Category H — Ecosystem claims (does umwelt integrate)

| # | Claim | Falsifier | Tier |
|---|---|---|---|
| H1 | umwelt is consumable by every target integrator (lackpy, kibitzer, blq, claude-plugins) without forking. | An integrator cannot use umwelt without a private fork. | 1 |
| H2 | umwelt's output formats are equivalent to or strictly more expressive than the native formats of each integrator. | Find a native-format policy the umwelt compiler cannot produce. | 2 |
| H3 | umwelt has no runtime dependency on any enforcement tool's Python wrapper. | Find an import of `nsjail_python` or similar in the umwelt runtime path. | 1 |

### Category I — Compositional claims (do views combine cleanly)

| # | Claim | Falsifier | Tier |
|---|---|---|---|
| I1 | `umwelt diff a.umw b.umw` reports every rule-level change between views (no silent drops, no spurious changes). | Find a diff that misses or fabricates changes. | 2 |
| I2 | Multiple views loaded into one resolve run produce the union of their rules, cascaded as if authored together. | Combine two views and observe a rule whose effect differs from its effect in isolation plus specificity logic. | 2 |
| I3 | Taxon aliases are transparent: an entity/property/matcher registered under canonical is indistinguishable from one registered under alias. | Code review found a gap; fix commit `ffe4b54`. Still open: cross-consumer conflict if two consumers register different matchers under equivalent aliases. | 1 |

---

## Part 2 — Evaluation methodology per category

For each category, a distinct methodology. The rigor comes from *matching* method to claim kind.

### Semantic claims → formal verification + test generation

- **Formal**: mechanize the resolver semantics in Lean or Coq. Prove A1 (determinism) and A2 (well-ordering) as theorems. This is the Cedar playbook.
- **Property-based testing**: `hypothesis` + `pytest-benchmark`. Generate random views, run resolve twice, assert identity. Catches A1 in the limit.
- **Differential testing**: against a Datalog reference implementation (Soufflé). Compile view → Datalog IR, run both, compare fact-sets. Catches A4.

### Enforcement claims → round-trip empirical testing

- **Corpus**: hand-curated views that exercise each altitude's full vocabulary.
- **Method**: parse → resolve → compile → execute in the real sandbox → probe from inside with a test harness that attempts forbidden and permitted operations.
- **Metric**: false-allow rate (forbidden operations that succeed) and false-deny rate (permitted operations that fail).
- **B2 specifically**: run each pair of altitudes in combination; assert constraints compose.

### Audit claims → proof-tree coverage

- **Corpus**: every execution in the enforcement-round-trip test.
- **Method**: for every enforcement event, emit proof tree; verify each step references a source line in the view.
- **Metric**: proof-tree coverage (fraction of events with complete attribution) and proof-tree stability (same view+input → same tree, byte-identical).

### Specifiability claims → ratchet-loop measurement

- **Corpus**: observation logs from real delegate runs (internal dogfood, then partner installs).
- **Method**: Run ratchet over logs; compare proposed rules to rules a human operator would have written (ground truth from incident retros).
- **Metric**: precision (fraction of proposals accepted) and recall (fraction of human-written rules that ratchet would have proposed).
- **D2 specifically**: for every proposed rule, assert the resulting view is a strictly-tighter refinement (automate this check as an invariant of the ratchet).

### Usability claims → mixed-methods user study

- **Protocol**: recruit N=15–30 CSS-literate engineers; give them a view; ask them to predict the outcome of a query without running umwelt.
- **Metric**: prediction accuracy. E1's threshold (30%) is deliberately conservative; lower = better.
- **Supplement**: think-aloud sessions to identify confusion points. Qualitative output feeds docs and error-message work.
- **E2 specifically**: corpus of deliberately-broken views; assert every one produces line-accurate errors.

### Agent-alignment claims → adversarial agent runs

- **Protocol**: give the delegate a task; compile a view that forbids the straightforward path; observe whether the delegate breaches the bound, requests mode-switch, or fails gracefully.
- **Metric**: out-of-band rate (breach frequency per N runs) and alignment responsiveness (fraction of runs where the delegate correctly identifies the bound and adapts).
- **F1 specifically**: adversarial prompts designed to induce escape. Red-team setup.

### Theoretical-fidelity claims → peer review

- **Protocol**: write a paper-grade mapping from umwelt taxa to VSM; submit for external review (academic or Ma-series audience).
- **Metric**: specific objections raised and resolved. Not a single number; a living document.
- **G2 specifically**: produce a trace-example where a decision is reconstructed purely from view + observed inputs, with no hidden state.

### Ecosystem claims → integrator dogfooding

- **Protocol**: pick one integrator per milestone (lackpy in v0.6, kibitzer in v0.7, etc.), require it consume umwelt in production before milestone is shipped.
- **Metric**: did the integration land without forking umwelt?
- **H2 specifically**: audit each native format's expressive power; produce a capability-coverage table.

### Compositional claims → diff and merge testing

- **Corpus**: pairs of views that exercise add/remove/change in each taxon.
- **Method**: `diff` output compared against a manually-produced reference diff.
- **I2 specifically**: load combinations of two real-world views (sandbox + lackpy, sandbox + kibitzer) and verify cascade predictions by hand on a sample.

---

## Part 3 — The evaluation protocol

A one-time evaluation yields a snapshot. Rigorous evaluation is a *protocol* — a repeatable process.

### Per-milestone evaluation (v0.5, v0.6, …)

1. **Claim ledger review** — for each claim in categories A–I, confirm whether this milestone strengthens, weakens, or leaves unchanged the evidence for/against it.
2. **Test-suite gatekeeping** — every test file maps to one or more claims. No new claim without a test; no test without a claim. Tag tests with claim IDs in docstrings (e.g., `"""Verifies claim A1 (determinism)."""`).
3. **Regression panel** — the byte-compat snapshots are the B1 continuity kit. Run on every PR.
4. **User-study cadence** — a small user study per major milestone. 5 users is enough to catch egregious usability regressions.
5. **Incident retros** — every delegate failure in dogfood gets a retro. Each retro produces: (a) a view edit that closes the gap, (b) a test that catches the class of failure, (c) a claim-ledger entry if it reveals a new gap.

### Quarterly deep-eval

- Full formal-verification pass (Lean proofs regenerated; counterexamples recorded).
- Full round-trip test against a fresh enforcement stack.
- User study N ≥ 15 with new recruits (don't reuse familiar users).
- Public audit report: one paragraph per claim; what's verified, what's open.

---

## Part 4 — Prioritization

Not all claims are equally load-bearing. Some are foundational (if false, the project is wrong); some are ergonomic (if false, the project is annoying).

### Tier 0 — foundational (falsify these and the project is broken)

- A1 (determinism), A2 (cascade well-ordered), B1 (enforcement fidelity), F1 (delegate is actually bound).

### Tier 1 — load-bearing (falsify these and the value prop collapses)

- A3 (cross-axis soundness), A5 (property comparison semantics), B2–B4 (altitude stacking, native-validator acceptance, out-of-altitude rejection), C1/C3 (proof-tree traceability and stability), D1 (failures can become rules), F2/F3 (actionable feedback, mode switching), G2 (specified band holds), H1/H3 (integrator adoption without fork, no wrapper dependency), I3 (alias transparency).

### Tier 2 — quality (falsify these and the project works but is worse)

- C2 (audit widening accuracy), D2/D3 (ratchet monotone and specified), E1–E3 (usability), H2 (expressive superset of native formats), I1/I2 (diff completeness, view composition).

### Tier 3 — aspirational (falsify these and the project is less ambitious than claimed)

- A4 (Datalog equivalence), G1 (VSM fidelity), G3 (three-layer instantiation).

**First rigor investment: Tier 0.** Everything else can wait.

---

## Part 5 — Red flags / stopping rules

Rigor includes knowing when to stop. Conditions under which umwelt should pivot or be abandoned:

- **False-allow rate > 1%** in round-trip testing after Slice B lands. Enforcement is the foundation; if it leaks, the theoretical sophistication is window-dressing.
- **Usability study prediction-accuracy < 50%** with CSS-literate users. The CSS-syntax bet has failed; reconsider the surface syntax.
- **Integrator-without-fork requirement fails for two of four integrators.** The common-language-of-the-specified-band claim is falsified; umwelt is just another policy language.
- **A partner integration takes > 2 weeks from zero-to-production.** The library is too heavyweight; strip it.
- **Ratchet proposals have < 30% human-acceptance rate after N > 50 proposals.** The specified-ILP story needs work or the ratchet needs a neural assist (which itself would require framework change).

---

## Part 6 — Gaps deliberately unaddressed in v1

Honest rigor includes naming the gaps.

- **Long-run stability**: views evolve over years. Does a view written in v0.5 still compile in v2.0? No story yet.
- **Multi-principal composition**: two principals with overlapping views. Not specified. Needed before v1.1.
- **Federated enforcement**: a view that composes across multiple sandboxes (different teams, different machines). Out of scope for v1.
- **Performance under adversarial input**: parser hardening / fuzz testing. Deferred to v0.7.
- **Cost accounting**: the budget axis is declared but compile-time verification of budget sufficiency isn't formalized. Interesting paper-grade problem.

These gaps define the roadmap beyond v1.0.

---

## Part 7 — The one-sentence test

If a stakeholder asks "is umwelt working?", the honest answer has the shape:

> "Claims {A1, A2, B1, F1} are verified with {method}; claim {X} is open pending {measurement}; no Tier-0 claims are falsified; the next evaluation is scheduled for {date}."

If you can't produce that sentence, the evaluation framework isn't being run. The deliverable of this framework is that sentence, on demand, at every milestone.

---

## Current state (as of 2026-04-14, post-v0.4, pre-v0.5)

| Claim | Evidence | Status |
|---|---|---|
| A1 | Resolver determinism: not property-tested; no formal proof. Each test implicitly assumes it. | **Open — Tier 0**. Add hypothesis-based determinism test in v0.5 Slice C. |
| A2 | Cascade uses document order as tiebreaker (resolver.py L151-159). | **Verified** by construction for single-axis; extended by v0.5 Slice C for cross-axis. |
| A3 | Introduced in v0.5 Slice C. | **Open pending v0.5 implementation**. |
| A5 | Each registered property declares its comparison. Tested per-property in sandbox tests. | **Verified** by existing tests. |
| B1 | Compilers have snapshot tests for output stability (Task 6 of v0.5 plan), but no runtime round-trip in the actual sandbox. | **Partial** — continuity verified, correctness unverified. Open for v0.8/v0.9. |
| B3 | No native-validator round-trip harness. | **Open — Tier 1**. Candidate for v0.7. |
| C1 | `umwelt audit` reports per-rule source attribution. No formal proof tree. | **Partial**. Full proof trees v0.9+. |
| D1–D3 | Ratchet utility is v1.1+. | **Not applicable yet**. |
| E1–E3 | No user studies. | **Not evaluated**. Schedule for v0.9. |
| F1–F3 | No agent-alignment runs. | **Not evaluated**. Needs agent harness (v0.8+). |
| G2 | Specified band is claimed; not instrumented. | **Partial** — every decision is declarative, but no proof-tree extraction yet. |
| H1 | lackpy-namespace compiler ships; lackpy integration is hypothetical. | **Partial**. |
| H3 | Grep confirms no nsjail_python imports in src/umwelt. | **Verified**. |
| I1 | `umwelt diff` has tests for added/removed/changed rules. | **Verified** at unit level. |
| I3 | Task 0 + `ffe4b54` fix cover alias transparency for registry lookups. | **Verified** for current registry submodules. |

**No Tier-0 claim is currently falsified.** Tier-0 claims A1 and B1 are partially verified; the v0.5 plan does not strengthen them directly — that work (hypothesis-based determinism test, round-trip enforcement harness) is a gap to close in subsequent milestones.

---

## How to update this document

- Adding a claim: pick a category letter and the next available number. Provide falsifier and tier. Add to current-state table.
- Strengthening a claim: add a link to the test or proof that establishes it. Update current-state status.
- Refuting a claim: record the falsifying observation in git history. Either fix the design, drop the claim, or move it to a "retired claims" section with explanation.
- New category: appropriate for major capabilities (e.g., Category J for performance, K for security) when they become first-class. Propose in a note first, then merge.

The document is a contract between the project and its users that umwelt's claims are testable, tested, or deliberately deferred. Drift between this document and reality is a project defect.
