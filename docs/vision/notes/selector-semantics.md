# Note: Selector Semantics — Design Decisions and Open Questions

*Captured during a blog-editing session on 2026-04-10 after the core vision docs were written. Records decisions and open questions that should feed into the next revision of `view-format.md` and `entity-model.md`.*

**Context**: This note was produced during a design discussion about the surface syntax for selectors. The blog drafts at `judgementalmonad.com/drafts/umwelt-the-layer-we-found.md` and `drafts/the-sandbox-tower.md` have been updated to reflect the decisions below. The vision docs in this directory currently reflect the earlier state (taxon-prefixed entity names, no cross-taxon compound selectors); when someone next revises them, the decisions here should land.

---

## Decision: drop the taxon prefix

**Current state in the vision docs**: `world file[path^="src/auth/"] { editable: true; }` — entity names are prefixed with their taxon.

**Decision**: bare entity names are canonical. No prefix.

```
file[path^="src/auth/"]     { editable: true; }
tool[name="Bash"]            { allow: false; }
hook[event="after-change"]   { run: "pytest"; }
network                      { deny: "*"; }
resource[kind="memory"]      { limit: 512MB; }
```

**Rationale**:

1. **CSS alignment.** The prefix is not how CSS actually works. `div.active` is not `document div.active`. Introducing a namespace prefix that doesn't appear elsewhere in the language quietly breaks the "borrow CSS exactly" dialect-design move — the whole point of which is that every code-trained model already knows the surface syntax. A non-CSS namespace convention the model has to learn at the view-authoring layer undermines the payoff.

2. **Verbosity with no common-case benefit.** `world file[path^="src/"]` is longer than `file[path^="src/"]` for a disambiguation that matters in ~0% of views. Most views use one consumer's vocabulary at a time (usually the sandbox consumer), and the prefix is redundant.

3. **Reader cognitive overhead.** The prefix exposes the plugin system at the view-authoring layer. Authors shouldn't have to know "taxa are a thing" to write a view — they should just write `file[...]` and have it work.

4. **Registry handles disambiguation at registration time.** The cascade-scoping concern that motivated the prefix (world rules don't compete with capability rules) is solved by tagging each AST node with its owning taxon at parse time. The registry knows which taxon registered `file`, and the cascade resolver scopes per target-taxon automatically. The syntax doesn't need to expose the taxon; the registry does the lookup.

**Handling real collisions**: when two taxa try to register the same entity name, the second registration errors. If there's a legitimate need to have both (e.g., `world.file` and `doc.file`), the registering consumer either renames one (`world.file` and `doc.document`) or the grammar provides an explicit disambiguation form via at-rule scoping (see below).

**What to update in the vision docs**:

- `view-format.md`: strip `world` / `capability` / `state` prefixes from all examples and grammar. Rewrite section 5 ("Selectors — canonical form") with bare entity names. Rewrite section 7 ("Sandbox vocabulary: desugaring") with bare entity names on the right-hand side.
- `entity-model.md`: section 4 (selector grammar) drops the prefix throughout. Section 5 (cascade) keeps the per-taxon scoping rule, but the scoping is determined by registry lookup, not by syntactic prefix. Section 7 (desugaring) updates the right-hand side.
- `policy-layer.md`: examples that use prefixed entity names get rewritten.
- `package-design.md`: any example view files in the doc get rewritten.

---

## Decision: cross-taxon compound selectors with context-qualifier semantics

**New capability**: selectors can compose entities from different taxa using the descendant combinator. When the combinator connects entities from different taxa, it has **context-qualifier semantics** rather than structural descendant semantics.

```
tool[name="Bash"] file[path="src/auth/"] { editable: false; }
```

reads as: "when the acting tool is Bash, files in `src/auth/` are not editable." The first selector (`tool[name="Bash"]`) is the **context** — it conditions when the rule applies. The rightmost selector (`file[path="src/auth/"]`) is the **target** — the entity the declaration attaches to.

**Three-level form** composes cross-taxon context with within-taxon structural descent:

```
tool[name="Bash"] file[path="src/auth/"] .fn#protected { editable: false; }
```

"When Bash acts on files in `src/auth/`, the `protected` function inside those files is not editable." The first combinator is cross-taxon context qualification (tool → file); the second is within-taxon structural descent via the `file → node` parent-child relationship the plugin declares (with `.fn` as a class selector for the semantic kind of the node entity).

**Semantic split at the combinator level**:

- **Within a taxon**: descendant combinator is CSS-standard structural descent via the plugin's declared parent-child relationships. `dir[name="src"] file[path$=".py"]` is "a .py file descended from `src/`."
- **Across taxa**: descendant combinator is context qualification. `tool[name="Bash"] file[...]` is "in the context of Bash as the acting tool, matching files."

The parser distinguishes the two modes by looking up the taxa of the combined entities at parse time. When both sides are in the same taxon, structural; when they're in different taxa, contextual.

**Cascade with compound selectors**: cascade is scoped to the **target taxon** (the rightmost entity), not to every selector in the rule. A rule with selector `tool[name="Bash"] file[path="src/auth/"]` is a `file` rule (in whatever taxon registered `file`, i.e., the world taxon) with extra specificity contributed by the `tool` qualifier. It competes against other `file` rules in the world taxon's cascade. The `tool` qualifier bumps specificity but doesn't move the rule into a different cascade scope.

**Specificity accumulates rightward**: each context selector contributes its full specificity tuple, summed into the rule's total specificity. Standard CSS specificity (IDs, classes, attributes, pseudos, types) computed per-selector, then summed across all selectors in the rule.

Example cascade with compound selectors:

```
file[path="src/auth/"]                                    { editable: true;  }   /* (0,1,1) */
tool[name="Bash"] file[path="src/auth/"]                 { editable: false; }   /* (0,2,2) */
tool[name="Edit"] file[path="src/auth/"]                 { editable: true;  }   /* (0,2,2) */
```

- For `Edit` invocation on `src/auth/`: rules 1 and 3 apply; rule 3 wins on specificity → editable (redundant with baseline, but documents intent).
- For `Bash` invocation on `src/auth/`: rules 1 and 2 apply; rule 2 wins on specificity → not editable.
- For any other tool (Grep, Read, etc.) on `src/auth/`: only rule 1 applies → editable.

Clean and decidable.

**What to update in the vision docs**:

- `view-format.md`: add compound-selector syntax to the grammar section. Add a new subsection explaining the within-taxon-vs-cross-taxon combinator split. Add worked examples with cross-taxon compound selectors.
- `entity-model.md`: section 4 (selector grammar) needs the cross-taxon combinator semantics. Section 5 (cascade) needs the "cascade scoped to target taxon, specificity accumulates" rule. Add a subsection on how cascade handles compound selectors.
- `policy-layer.md`: note that selectors can express actor-conditioned policy directly, without requiring separate rules for each actor.

---

## Decision: declaration-level patterns for runtime/invocation-time matching

**The question**: can selectors match on invocation-time state like tool arguments? E.g., `tool#Bash[args*="foo"]` — "Bash called with args containing 'foo'."

**Decision**: v1 selectors match **static attributes only**. Dynamic matching (args, call-site state, runtime context) uses **declaration-level patterns** inside `{}`, not selectors. Example:

```
tool[name="Bash"] {
  allow-pattern: "git *", "pytest *", "black *";
  deny-pattern:  "rm -rf *", "curl *", "ssh *";
}
```

**Rationale**:

1. **Selector/runtime split is cleaner.** Selectors operate on the parsed AST and are evaluated statically during compilation or hook dispatch. Keeping them to static-attribute matching preserves selector-evaluation decidability and makes the parser independent of runtime state. Runtime concerns go into declarations where they're property-typed and well-bounded.

2. **Compilation target compatibility.** Static selectors compile cleanly to every target — nsjail, bwrap, lackpy namespace, kibitzer hooks. Dynamic selectors would require every compiler to emit runtime-evaluation machinery for the context predicate, and some targets (nsjail textproto) can't express that at all. Keeping it declarative lets each compiler handle patterns in whatever form its target supports (argv allowlists, permission regex, etc.).

3. **Matches the existing permission model.** Claude Code's current permission system uses tool-name + argv-pattern matching. Declaration-level patterns map directly to this model, so the compiler for the claude-plugins hook target is a near-1:1 translation.

**v1.1+ possibility**: invocation-time selectors via a dedicated namespace or pseudo-class. Options:

- `tool:call[args*="foo"]` — pseudo-class indicating "the current invocation of this tool" with call-site attributes available
- `@on-call tool[name="Bash"]` — at-rule scoping that establishes an invocation-time evaluation context
- Separate at-rule entirely: `@call { tool[name="Bash"][args*="foo"] { deny: true; } }`

Defer until a concrete v1 use case forces the decision. The declaration-level pattern approach is enough for the currently-known cases.

**What to update in the vision docs**:

- `view-format.md`: note that declaration values can include patterns; add `allow-pattern` / `deny-pattern` as recognized properties in the capability taxon.
- `entity-model.md`: section 4.3 (declarations with comparison semantics) gains a subsection on pattern properties. The pattern comparison is property-level ("matches this glob"), registered as another comparison category alongside `max-`, `min-`, `only-`, `any-of-`.
- Pattern syntax: shell-glob for filesystem paths, substring-match for argument strings. Probably `fnmatch` semantics. Needs a decision about whether regex is ever supported (probably not in v1).

---

## Open question: source / project as a new structural layer

**The raised question**: should the world taxon grow a `source` (or `project`) entity representing "a logical grouping of files" — distinct from filesystem hierarchy?

**Motivation**: in monorepos and multi-repo setups, files belong to logical groupings (packages, repositories, `@source` declarations) that aren't captured by `dir > file > node`. Views sometimes want to say "files in the auth package" or "files belonging to source X" rather than "files whose path matches this pattern."

**Proposed form**:

```
source[name="auth"] file[path$=".py"] { editable: true; }
tool[name="Bash"] source[name="auth"] file[path$=".py"] .fn#protected { editable: false; }
```

The four-level form: actor context → source context → file target → node sub-target.

**Open questions to resolve before committing**:

1. **Is `source` a new entity type in the world taxon, or a new taxon (e.g., `project`)?** If source is about filesystem-adjacent groupings, it probably lives in world. If source is about broader project/workspace/repo concepts, it probably lives in its own taxon.

2. **How does `source` relate to the existing `@source(path)` at-rule sugar?** The current `@source("src/auth")` desugars to `file[path^="src/auth/"]` (a path-prefix match). If `source[name="auth"]` becomes an entity, the at-rule could desugar to `source[name="auth"] file[...]` instead, making the source grouping first-class in the AST.

3. **Where does the `name` of a source come from?** A filesystem path (`src/auth`)? A `pyproject.toml` package name? A git submodule name? An `@source(name="auth", path="src/auth")` declaration? Each option has tradeoffs; the simplest is "author specifies it via an extended `@source` at-rule with a `name` argument."

4. **How does cascade interact with source groupings?** If one `source` block sets defaults and another overrides them, does the override walk the source hierarchy? Probably yes via standard cascade specificity, but needs spec.

5. **Is there a need for multiple source roots in one view?** A view that spans packages would want to name them: `source[name="auth"]`, `source[name="billing"]`, `source[name="common"]`. Should they be siblings, or does a project-level entity nest them?

**v1 handling**: no `source` entity. Author uses path-prefix matching on `file` directly. The gap is real but can be filled in v1.1 without disrupting v1 views.

**What to update in the vision docs when this lands**:

- `entity-model.md` section 3.1 gets a new entity `source` with attributes `name`, `root_path`, and whatever grouping metadata makes sense. Parent relationship: `source → dir → file → node` (making source the structural parent of dirs).
- `view-format.md` gets the updated desugaring for `@source(name="X", path="Y") { ... }`.

---

## Open question: cross-taxon structural relationships

**The raised question**: the current proposal has the cross-taxon descendant combinator as context-qualifier semantics. What about legitimate structural relationships between entities from different taxa?

**Examples**:

- `hook` is *triggered by* a `tool` — the hook's event is fired by a particular tool's invocation.
- `job` is *owned by* an `actor` — which actor is running this job?
- `file` is *produced by* a `tool` — which tool created this file?
- `budget` is *consumed by* a `job` — which job drained this budget?

These are structural relationships that span taxa. The current proposal forces them into context-qualifier form ("when the tool is X, the hook is ...") which is semantically different from the structural form ("the hook triggered by tool X is ...").

**Proposed solution**: explicit cross-taxon structural relationships via **pseudo-classes**. The plugin registering a taxon can declare cross-taxon relationships as pseudo-class matchers:

```
hook:triggered-by(tool[name="Bash"])  { ... }
job:owned-by(actor#delegate)          { ... }
file:produced-by(tool[name="Write"])  { ... }
```

The pseudo-class takes a selector argument (any valid selector for the related taxon) and matches entities that have the declared structural relationship to anything the argument matches.

**Distinction from context qualifiers**: a context qualifier says "when X is active, apply this rule." A structural pseudo-class says "entities that stand in this structural relationship to X." The former is about runtime actor state; the latter is about declared relationships between entities in the graph.

Both are useful. v1 should commit to context qualifiers (they're needed for the actor-conditioned policies we want to express). Pseudo-class structural relationships are a v1.1+ addition — they require each taxon to declare its cross-taxon relationships explicitly and each matcher to support the navigation, which is more infrastructure than v1 wants to take on.

**What to update in the vision docs when this lands**:

- `entity-model.md` section 4 gains a new subsection on cross-taxon structural pseudo-classes.
- Section 6 (plugin registration) gains a `register_relationship` API for declaring cross-taxon relationships.
- Compilers that want to handle these (primarily kibitzer-hooks and future audit compilers) need to support pseudo-class evaluation.

---

## Summary of what needs to land in v1

1. **Strip taxon prefixes** from all entity-name examples in `view-format.md`, `entity-model.md`, `policy-layer.md`, and `package-design.md`. Use bare names (`file`, `tool`, `hook`, `network`, `resource`, `budget`, `job`, `actor`).
2. **Document cascade-scoping-via-registry**: the cascade resolver looks up each entity's owning taxon at parse time and scopes cascade per target taxon. The syntax doesn't expose taxa.
3. **Add cross-taxon compound selectors** with context-qualifier semantics. Update `entity-model.md` section 4 (grammar) and section 5 (cascade).
4. **Add declaration-level pattern properties** (`allow-pattern`, `deny-pattern`) for runtime matching, distinct from static-attribute selectors. Update `entity-model.md` section 4.3.
5. **Keep at-rule scoping** (`@when`, `@world`, etc.) as optional sugar for repetitive cases. Flat form is canonical; at-rule is convenience.

## Summary of v1.1+ gaps

1. **`source` or `project` entity** for logical file groupings beyond filesystem hierarchy.
2. **Invocation-time selectors** (`tool:call[args*="..."]` or `@on-call`) if declaration-level patterns turn out to be insufficient.
3. **Cross-taxon structural pseudo-classes** (`hook:triggered-by(...)`, `job:owned-by(...)`) for declared relationships between entities from different taxa.
4. **`file#name.py.bak` tricky edge case**: the greedy id-value grammar handles this but an author who wanted class-after-id on a filename id can't. Decide whether to add an explicit disambiguation form.

---

## Pointer back to the blog drafts

The decisions above have already been reflected in the blog drafts at `judgementalmonad.com/drafts/`:

- `umwelt-the-layer-we-found.md` — Decision 7 section has been updated with bare entity names, the cross-taxon compound selector semantics, and the explanation of why the prefix was dropped.
- `the-sandbox-tower.md` — the entity-selector example in the delegation-becomes-contractual section has been updated to bare names and compound selectors.

When the vision docs here are next revised, the blog drafts are the provenance artifact showing how the decisions got made and what the intended semantics are.
