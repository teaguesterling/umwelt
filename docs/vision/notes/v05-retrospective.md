# Note: v0.5 retrospective — what emerged, what's right, what's missing

*Captured 2026-04-17 after v0.5.2 shipped and the ducklog IR prototype landed. An honest assessment of the project's state for future sessions to build on.*

---

## What emerged that wasn't planned

**Beer's VSM as the organizing principle.** The v0.5 plan started as "add kibitzer modes." The question "where does mode go?" led to Beer, which led to the seven-taxon restructure, which kept being productive: kibitzer's issues #1-3 (written independently of our spec) arrived at the same S3/S2/S3* decomposition. When a framework predicts the shape of work nobody asked it to predict, that's the best signal you get.

**The world-axis / action-axis distinction.** We nearly got this wrong. The initial spec had permissions "moving from" world entities "onto" use entities. The user caught that `file { editable: true }` (the resource is editable, like a mount being writable) is fundamentally different from `use[of=file#X] { editable: true }` (this access path grants edit, like user permission bits). A successful enforcement decision conjoins both axes. This distinction has real compiler consequences: OS-altitude reads world-axis, language-altitude reads action-axis.

**umwelt as specification engine, not runtime.** Dissolved three design problems simultaneously: runtime-state overlay (not umwelt's job), template substitution (consumer's job), mode filtering at resolve time (consumer queries with a mode parameter). The user's formulation: "umwelt defines the way things *are* and *should be*; other tools do the configuration and validation to assert that."

**DuckDB as the canonical IR.** Emerged from a "should we consider DuckDB?" question and within hours we had a working compiler. The view-stack architecture (materialized policy + live provider views + derived cascade + compiler views) is clean and leverages DuckDB's strengths. The convergence with the existing ecosystem (blq, sitting_duck, agent-riggs all speak DuckDB) wasn't planned; it's emergent from the right substrate choice.

**Providers as views.** We initially proposed INSERT-based entity population. The user pushed to "providers should be views." That's architecturally correct: the world is discovered state that changes constantly; a view is always current without a refresh step. The policy is the one materialized thing because it's an authored commitment, not a live feed.

## What's right

**The view stack.** Policy (materialized) → providers (live views over glob/json/toml) → entities (union of providers) → cascade_candidates (compiled selectors × live entities) → resolved_properties (comparison-aware) → compiler views (nsjail/bwrap/lackpy/kibitzer). Every layer is a SQL view. No procedural logic. Query it and you get the current answer.

**Comparison-type dispatch.** `exact` (highest specificity wins), `<=` (tightest bound, MIN), `>=` (loosest floor, MAX), `pattern-in` (set union, STRING_AGG). Each is a SQL view; the unified `resolved_properties` is a UNION ALL BY NAME. Adding a new comparison type is adding one more branch.

**Verification as SQL.** Claims A1, A2, A5, A6, C1 are "this view returns zero rows." Mechanized verification inside the artifact itself. No external test framework needed.

**The evaluation framework.** ~35 falsifiable claims across 9 categories with tier assignments (0=foundational, 3=aspirational). Red flags / stopping rules. Current-state table updated per milestone. The one-sentence test: "Claims {X} are verified; claim {Y} is open; no Tier-0 claims are falsified."

## What's wrong or missing

**The selector-to-SQL compiler is the weakest link.** Regex-based, handles ~60% of selector syntax. A production version needs to walk the AST and emit SQL per node type. This is the bridge between umwelt and ducklog; if the compiler is wrong, the pipeline is untrustworthy. The sitting_duck convergence (CSS selectors → DuckDB queries over AST tables) suggests extracting this into a shared library.

**B1 (enforcement fidelity) is unverified.** Nobody has ever: parsed a `.umw` → compiled to nsjail textproto → launched a real sandbox → attempted a forbidden operation → verified it was blocked. Byte-compat snapshots verify output *stability*, not *correctness*. This is Tier-0 and it's open.

**F1 (delegate actually bounded) is unverified.** No adversarial agent run has ever tested whether a compiled view actually constrains an LLM delegate. This is Tier-0 and it's open.

**The claim ledger is growing faster than evidence.** ~35 claims, ~8 verified. Every new feature implies new claims. The ratio should concern us.

**Mode-filtered queries don't exist.** The resolved world shows all modes competing simultaneously. A `resolved_for_mode('implement')` macro is needed but not built.

**No real consumer has ever read from a ducklog database.** The "common language" claim is unvalidated until kibitzer (or lackpy, or blq) actually reads its config from a `.duckdb` file instead of its own native format.

## Priority recommendation for the next milestone

Not more features. Three things:

1. **Fix the selector-to-SQL compiler** — walk the AST, emit SQL per node type. Handle structural descendants, `:glob()`, class selectors, `of=` nested selectors. This makes the ducklog pipeline trustworthy.

2. **Build the round-trip enforcement harness** — parse → compile → nsjail → sandbox → probe. Even three test cases would be the first empirical evidence for B1 (Tier-0). Worth more than all snapshot tests combined.

3. **Get one real consumer on ducklog** — kibitzer reading `kibitzer_modes` from a `.duckdb` file instead of TOML. First empirical validation of the "common language" claim.

Everything else (transitions, datalog extension, formal verification, user studies) is downstream of these three.

## What to preserve

- **The specification-engine boundary.** umwelt specifies; consumers enforce. Don't add runtime state.
- **The view-stack architecture.** Materialized policy; live provider views; derived resolution. Don't add INSERT-based population steps.
- **The evaluation framework's discipline.** No new claim without a test. No test without a claim. Tag tests with claim IDs.
- **The preference for simple forms.** `mode.X tool#Y` over `use[of=tool#...]` when sufficient. Don't reach for the general construct when the simple one works.

---

*End of retrospective. The direction is right; the verification is behind. Close the gap before adding surface area.*
