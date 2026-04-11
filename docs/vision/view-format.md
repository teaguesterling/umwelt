# The View Format

*Grammar, syntactic forms, worked examples. This is the canonical reference for what a view file looks like. For what it means, see [`entity-model.md`](./entity-model.md). For why it's shaped this way, see [`policy-layer.md`](./policy-layer.md).*

## Overview

A **view** is a CSS-shaped text file that declares what an actor operating inside it can see, edit, call, and trigger. Views are produced by an outer agent (human or model) to bound the behavior of an inner agent. Views are consumed by umwelt's compilers, which read them and emit each target tool's native config format.

Views have two valid syntactic forms, both accepted by the parser:

1. **Entity-selector form** — the canonical form. CSS selectors matching entities from registered taxa, with declarations attaching policy.
2. **At-rule sugar** — a shorter, more sandbox-focused form using CSS at-rules like `@source`, `@tools`, `@after-change`. Desugars to entity-selector form during parsing.

Both forms compile to the same AST. Authors can use either, mix them in the same file, or pick based on which is clearer for the task. The canonical form is the entity-selector form because it generalizes to any registered taxon; the at-rule sugar is convenient specifically for the sandbox vocabulary and is preserved for familiarity.

A minimal view in each form:

**Entity-selector form:**

```
file[path^="src/auth/"] { editable: true; }
file                    { editable: false; }

tool[name="Read"]  { allow: true; }
tool[name="Edit"]  { allow: true; }
tool[name="Bash"]  { allow: false; }

network { deny: "*"; }

resource[kind="memory"]   { limit: 512MB; }
resource[kind="wall-time"]{ limit: 60s; }

hook[event="after-change"] {
  run: "pytest tests/test_auth.py";
  run: "ruff check src/auth.py";
}
```

**At-rule sugar form (equivalent):**

```
@source("src/auth/**/*.py")    { * { editable: true; } }
@source("**/*.py")              { * { editable: false; } }

@tools {
  allow: Read, Edit;
  deny:  Bash;
}

@network { deny: *; }

@budget {
  memory:    512MB;
  wall-time: 60s;
}

@after-change {
  test: pytest tests/test_auth.py;
  lint: ruff check src/auth.py;
}
```

Both specify: the delegate sees an auth-editable slice of the codebase (read-only elsewhere), can call Read and Edit but not Bash, can't reach the network, has a 512MB / 60s budget, and must pass the test and lint hooks after any edit.

## Design properties

The format is built around a handful of load-bearing choices. Understanding them makes the rest of the reference make sense.

1. **CSS-shaped surface syntax.** Every code-trained LLM has seen massive amounts of CSS — grammar, selectors, cascade, everything down to the punctuation. Borrowing the syntax means neither humans nor models have to be taught the grammar; the validator does the work that would otherwise require fine-tuning. See [Lackey Papers §3](https://judgementalmonad.com/blog/tools/lackey/03-the-specialization-lives-in-the-language) for the full dialect-design argument.

2. **Selectors describe what to match; declarations describe what to do.** CSS's two-layer grammar separates pattern matching (`file[path^="src/"]`) from policy (`{ editable: true; }`). umwelt preserves the separation unchanged.

3. **Unknown constructs are ignored with a warning.** The parser preserves unrecognized at-rules, entity types, and declarations in the AST with a warning flag. Compilers silently ignore constructs outside their altitude or their registered taxonomy. This is the forward-compatibility hook: when new taxa appear, old compilers keep working; when new compilers appear, existing views become usable with them.

4. **Declarative, not imperative.** A view describes *what the world is* for the delegate. It does not describe *what the delegate should do*. Intent lives in the task prompt; bounds live in the view.

5. **Self-contained when entities are specified.** A view's selectors carry enough information to match entities against any world snapshot. Hand the view to any consumer with the right taxa registered and it knows exactly which entities to bind policy to. No external configuration required.

6. **Specified end-to-end.** Every selector predicate is decidable. Every declaration has specified comparison semantics (see [`entity-model.md`](./entity-model.md) §4.3). No trained judgment, no LLM-based matching, no opaque runtime evaluation. The grammar deliberately forbids constructs that would push views out of the specified band.

## Grammar

```
view            := (at_rule | rule_block | comment)*

at_rule         := '@' ident (arguments)? '{' (nested_rule | declaration)* '}'
                 | '@' ident (arguments)? ';'
arguments       := '(' value (',' value)* ')'

rule_block      := selector_list '{' (rule_block | declaration)* '}'
selector_list   := selector (',' selector)*
selector        := simple_selector (combinator simple_selector)*
combinator      := whitespace | '>' | '+' | '~'
simple_selector := type_name? (hash | class | attribute | pseudo)*
type_name       := ident | '*'
hash            := '#' ident_value
class           := '.' ident
attribute       := '[' ident (attr_op value)? ']'
attr_op         := '=' | '^=' | '$=' | '*=' | '~=' | '|='
pseudo          := ':' ident ('(' pseudo_arg ')')?
pseudo_arg      := selector | quoted_string | number

declaration     := ident ':' value (',' value)* ';'
value           := quoted_string | bare_word | number unit? | url_value

unit            := 'KB' | 'MB' | 'GB' | 'TB'
                 | 'ms' | 's' | 'm' | 'h'
                 | 'pct'
                 | ident            /* extensible; plugins can register units */

quoted_string   := '"' ... '"' | "'" ... "'"
bare_word       := [a-zA-Z_][a-zA-Z0-9_-]*
number          := [0-9]+ ('.' [0-9]+)?
comment         := '#' until newline | '/*' until '*/' | '//' until newline
ident           := [a-zA-Z_][a-zA-Z0-9_-]*
ident_value     := [a-zA-Z0-9_.-]+  /* ids can contain dots and underscores */
```

Lexical notes:

- Whitespace is insignificant outside strings.
- Identifiers are case-insensitive (`@Source` and `@source` are equivalent; `EDITABLE: TRUE` and `editable: true` are equivalent).
- Units are case-insensitive (`512mb` == `512MB`).
- Comments can be `#`, `//`, or `/* */`. All three are accepted.
- Strings use single or double quotes. Escape sequences in v1: `\\`, `\"`, `\'`, `\n`, `\t`.
- Paths and globs inside string values are case-sensitive (filesystem conventions apply).

## Selectors (canonical form)

Selectors match entities from a registered taxon. The grammar is a subset of CSS3 with umwelt-specific additions. A full reference is in [`entity-model.md`](./entity-model.md) §4; this section is the format-level summary.

### Basic selectors

```
file                        any file entity
file#README.md              the file with name (id) README.md
file.test                   files tagged with class 'test'
file[path]                  files that have a path attribute
file[path="README.md"]      files with path equal to the literal string
file[path^="src/"]          files with path starting with "src/"
file[path$=".py"]           files with path ending with ".py"
file[path*="/auth/"]        files with path containing "/auth/"
file[tags~="test"]          files with "test" as one of their whitespace-separated tags
```

### Combinators

```
dir[name="src"] file        any file descended from a dir named "src"  (descendant)
dir > file                  any file that is a direct child of a dir     (direct child)
file[path^="src/"], file[path^="tests/"]    union — both selectors share the declaration block
```

### Negation and containment

```
file:not([path$=".md"])               files whose path does not end with ".md"
dir:has(file[name="pyproject.toml"])  directories containing a pyproject.toml   (v1.1+)
```

### Pseudo-class extensions

Pseudo-classes are CSS's established extension point. umwelt adds one in v1:

```
file:glob("src/**/*.py")           files whose path matches the shell glob
file:glob("tests/**/test_*.py")
dir:glob("src/*/internal")
```

The `:glob()` pseudo-class uses `fnmatch` semantics with `**` meaning "any path segments" — same as `pathlib.Path.glob`. Use it when the pattern isn't expressible as prefix/suffix/substring attribute selectors.

### Taxon resolution and disambiguation

Entity types are resolved against the plugin registry at parse time. When you write `file { editable: true; }`, the parser looks up `file` across all registered taxa; if exactly one taxon owns it, that's the match. Bare types are the default form. The format stays CSS-shaped: you write `button`, not `html body button`.

```
/* Default form: bare entity types, resolved automatically */
file[path^="src/"]          { editable: true; }
tool[name="Bash"]           { allow: false; }
hook[event="after-change"]  { run: "pytest"; }
```

Two disambiguation mechanisms exist for the rare case that a type name is ambiguous (multiple taxa define it) or the author wants explicit scoping as documentation:

**CSS namespace syntax (inline):** CSS3 uses `ns|type` for namespace-qualified elements (`svg|circle`). umwelt reuses the same syntax for taxon qualification when needed:

```
world|file[path^="src/"]          { editable: true; }
audit|file[path^="src/secrets"]   { flag: sensitive; }
```

**At-rule scoping (block):** Groups rules under a taxon name. Inside `@world { ... }`, bare entity types resolve against the `world` taxon first. Useful for visually partitioning views with many rules in one taxon.

```
@world {
  file[path^="src/"] { editable: true; }
}
@capability {
  tool[name="Bash"] { allow: false; }
}
@state {
  hook[event="after-change"] { run: "pytest"; }
}
```

All three forms — bare, `taxon|type`, and at-rule scoping — are interchangeable. Mix freely. Cascade is scoped per taxon — a `world` rule and a `capability` rule never compete even if a conceptual overlap exists, because they apply to disjoint entity sets. See [`entity-model.md`](./entity-model.md) §5.1 for how the target taxon is resolved from the rightmost entity in compound selectors.

### Compound selectors: within-taxon structure, cross-taxon context

The descendant combinator has two meanings, distinguished by whether the entities on each side share a taxon. The parser resolves taxa via registry lookup at parse time; authors don't annotate the mode.

**Within a taxon** — structural descent via plugin-declared parent/child relationships:

```
dir[name="src"] file[name$=".py"]                 /* .py files inside a src dir */
file[path^="src/auth/"] node[kind="function"]    /* functions inside src/auth files */
```

**Across taxa** — context qualifier. The left selector conditions *when* the rule fires; the rightmost selector is the **target** the declaration attaches to:

```
tool[name="Bash"] file[path^="src/auth/"] { editable: false; }
          /* when Bash is the acting tool, auth files are not editable */

actor#delegate file[path^="secrets/"] { visible: false; }
          /* sub-delegate actors cannot see secrets */

job[delegate="true"] resource[kind="memory"] { max-limit: 256MB; }
          /* delegated jobs have a tighter memory cap than their parent */
```

**Three-level compound** — cross-taxon context plus within-taxon structural descent:

```
tool[name="Bash"] file[path^="src/auth/"] node[kind="function"][name="protected"] {
  editable: false;
}
```

Reads: "when Bash is the acting tool, the `protected` function inside files in `src/auth/` is not editable." The first combinator (`tool → file`) is cross-taxon context; the second combinator (`file → node`) is within-taxon structural descent.

**Cascade with compound selectors.** The rule's cascade target is its rightmost entity (the thing declarations attach to), and the cascade lives in whichever taxon owns that entity. Context qualifiers contribute specificity but do not move the rule into a different cascade scope. See [`entity-model.md`](./entity-model.md) §5.3 for the full semantics and worked examples.

**Compilers drop rules they can't realize.** A compiler emitting for a specific enforcement altitude (OS for nsjail/bwrap, semantic for kibitzer-hooks, language for lackpy-namespace) silently drops rules whose context qualifier is outside its altitude. This is not an error — the same view can be compiled to multiple targets, each realizing what its target can enforce. The `dry-run` and `check` utilities report which rules were realized by which compilers so authors can see whether their view is honored at each altitude.

## Declarations

Declarations attach policy to matched entities. The simple form is familiar CSS — `key: value;`.

### Simple declarations

```
editable: true;
allow: true;
deny: "*";
limit: 512MB;
run: "pytest tests/auth/";
```

### Declarations with comparison semantics

Some property names carry built-in comparison semantics. The prefix of the name encodes how the value is interpreted as a policy constraint:

| Property prefix | Comparison | Meaning |
|---|---|---|
| (none) | exact | "set this property to this value" |
| `max-` | `≤` | "permitted values are ≤ the declared value" |
| `min-` | `≥` | "permitted values are ≥ the declared value" |
| `only-` | `∈` | "permitted values are from the declared set" |
| `any-of-` | overlap | "permitted values overlap with the declared set" |

Examples:

```
tool          { max-level: 2; }             /* tools capped at computation level ≤ 2 */
resource[kind="memory"] { max-limit: 512MB; }    /* memory cap at most 512MB */
tool          { only-kits: python-dev, rust-dev; }   /* only these kits allowed */
```

The comparison is property-level, not selector-level. The selector chooses which entities the rule applies to; the declaration's comparison says how to interpret the value against the entity's attribute. See [`entity-model.md`](./entity-model.md) §4.5 for the full semantics.

### Pattern-valued declarations (runtime matching)

Selectors match **static** attributes (file paths, tool names, entity kinds) — things that can be evaluated without running anything. For **runtime** matching on call-site state (tool arguments, invocation context), umwelt uses pattern-valued declarations rather than selector extensions. The pattern sits in the declaration block and is evaluated by whichever component realizes the property at runtime.

```
tool[name="Bash"] {
  allow-pattern: "git *", "pytest *", "black *", "ruff *";
  deny-pattern:  "rm -rf *", "curl *", "ssh *", "sudo *";
}

tool[name="Edit"] {
  allow-pattern: "*";                      /* no argv restriction */
}

tool[name="Write"] {
  only-match: "src/**/*.py", "tests/**";   /* Write only in source + tests */
}
```

Pattern semantics are `fnmatch`-style shell globs for v1. Plugins can register additional pattern properties (regex, path-prefix, etc.) with their own comparison categories.

Keeping runtime matching out of the selector grammar preserves three properties of the view format: selector evaluation stays decidable, static analysis tools (`inspect`, `dry-run`, `diff`) can reason about views without a runtime, and compilers can each realize patterns in whatever form their target accepts (nsjail argv allowlist, claude-plugins permission rules, kibitzer hook regex). Compilers that cannot realize runtime matching drop pattern properties the same way they drop out-of-altitude context qualifiers. See [`entity-model.md`](./entity-model.md) §4.4 for details.

### Multi-value declarations

Some declarations accept multiple values. Two equivalent syntaxes are supported:

```
/* Repeat the property */
hook[event="after-change"] {
  run: "pytest tests/auth/";
  run: "ruff check src/auth/";
  run: "mypy src/auth/";
}

/* Or use a comma-separated list */
tool {
  only-kits: python-dev, rust-dev, node-dev;
}
```

Plugins declare per-property whether repetition or comma-list (or both) is accepted. In v1, `run:` accepts repetition; list-valued properties like `only-kits:` accept comma lists.

## At-rule sugar

For authors familiar with the original sandbox-focused form or who find at-rules more natural, the parser accepts the legacy form as sugar. The sugar desugars to entity-selector form internally; compilers never see the at-rule form.

### `@source(path_or_glob) { ... }`

Desugars to `file[...] { ... }` with the argument translated into a selector. Nested wildcard rules (`* { editable: true; }`) apply as the default for all matched files.

```
@source("src/auth/**/*.py") {
  * { editable: true; }
}
```

equivalent to:

```
file:glob("src/auth/**/*.py") { editable: true; }
```

Nested selector rules inside `@source` (v1.1 via pluckit) desugar to `file ... node[...]` selectors:

```
@source("src/auth") {
  .fn#authenticate      { show: body; editable: true; }
}
```

equivalent to:

```
file[path^="src/auth/"] node[kind="function"][name="authenticate"] {
  show: body;
  editable: true;
}
```

### `@tools { ... }`

Desugars to `tool[...] { allow: ... }` and `kit[...] { allow: ... }` rules.

```
@tools {
  allow: Read, Edit, Grep;
  deny:  Bash;
  kit:   python-dev;
}
```

equivalent to:

```
tool[name="Read"]    { allow: true; }
tool[name="Edit"]    { allow: true; }
tool[name="Grep"]    { allow: true; }
tool[name="Bash"]    { allow: false; }
kit[name="python-dev"] { allow: true; }
```

### `@after-change { ... }`

Desugars to `hook[event="after-change"] { run: ... }`.

```
@after-change {
  test: pytest tests/auth/ -x;
  lint: ruff check src/auth/;
  fmt:  black --check src/auth/;
}
```

equivalent to:

```
hook[event="after-change"] {
  run: "pytest tests/auth/ -x";
  run: "ruff check src/auth/";
  run: "black --check src/auth/";
}
```

The labelled form (`test:`, `lint:`, `fmt:`) retains the labels as command annotations in v1.1+; v1 treats them as descriptive only and runs the commands in document order.

### `@network { ... }`

Desugars to `network { ... }`.

```
@network { deny: *; }
```

equivalent to:

```
network { deny: "*"; }
```

v1.1+ will support explicit hostname allowlists:

```
@network { allow: api.github.com, registry.npmjs.org; deny: *; }
```

equivalent to:

```
network[host="api.github.com"]      { allow: true; }
network[host="registry.npmjs.org"]  { allow: true; }
network                              { deny: "*"; }
```

### `@budget { ... }`

Desugars to one `resource[kind=...] { limit: N }` rule per dimension.

```
@budget {
  memory:    512MB;
  wall-time: 60s;
  cpu-time:  30s;
  max-fds:   128;
  tmpfs:     64MB;
}
```

equivalent to:

```
resource[kind="memory"]    { limit: 512MB; }
resource[kind="wall-time"] { limit: 60s;   }
resource[kind="cpu-time"]  { limit: 30s;   }
resource[kind="max-fds"]   { limit: 128;   }
resource[kind="tmpfs"]     { limit: 64MB;  }
```

### `@env { ... }`

Desugars to `env[name=...] { allow|deny: ... }` rules.

```
@env {
  allow: CI, PYTHONPATH, GITHUB_TOKEN;
  deny:  *;
}
```

equivalent to:

```
env[name="CI"]           { allow: true; }
env[name="PYTHONPATH"]   { allow: true; }
env[name="GITHUB_TOKEN"] { allow: true; }
env                       { allow: false; }    /* default: deny */
```

Cascade resolves the conflict: specific entity rules (with `name="CI"`) have higher specificity than the wildcard `env`, so the named variables are allowed and everything else is denied.

### Complete desugaring table

A full table of the sandbox vocabulary's at-rule sugar is in [`entity-model.md`](./entity-model.md) §7.

## Worked examples

### A read-only exploration view

```
# Exploration: read everything, edit nothing, just inspect.

file[path^="src/"]       { editable: false; }
file[path^="tests/"]     { editable: false; }

tool[name="Read"]   { allow: true; }
tool[name="Grep"]   { allow: true; }
tool[name="Glob"]   { allow: true; }

network                  { deny: "*"; }
resource[kind="wall-time"] { limit: 60s; }
```

Use case: "look at the codebase and tell me where the auth logic lives." The delegate can't change anything, can't run commands, can't reach the network. It has 60 seconds.

### A bounded edit view with a test hook

```
# Fix the admin login bug. Editable: auth only. Tests must pass after.

file[path^="src/auth/"]     { editable: true;  }
file[path^="src/"]          { editable: false; }       /* rest of src is context */
file[path^="tests/auth/"]   { editable: false; }

tool[name="Read"] { allow: true; }
tool[name="Edit"] { allow: true; }
tool[name="Grep"] { allow: true; }
tool[name="Glob"] { allow: true; }
tool[name="Bash"] { allow: false; }
tool[name="Write"]{ allow: false; }

network                    { deny: "*"; }
resource[kind="memory"]    { limit: 512MB; }
resource[kind="wall-time"] { limit: 5m; }

hook[event="after-change"] {
  run: "pytest tests/auth/ -x";
  run: "ruff check src/auth/";
}
```

The equivalent sugar form:

```
@source("src/auth/**/*.py") { * { editable: true; } }
@source("src/**/*.py")      { * { editable: false; } }
@source("tests/auth/**/*.py") { * { editable: false; } }

@tools {
  allow: Read, Edit, Grep, Glob;
  deny:  Bash, Write;
}

@network { deny: *; }
@budget  { memory: 512MB; wall-time: 5m; }

@after-change {
  test: pytest tests/auth/ -x;
  lint: ruff check src/auth/;
}
```

Both parse to the same AST. Compilers produce identical output.

### A test-runner view with computation level cap

```
# Run the tests in an isolated sandbox. Allow Bash, but cap at level 2 (read+compute).

file[path^="tests/"]       { editable: false; }
file[path^="src/"]         { editable: false; }
dir[path="/tmp/test-workspace"] file { editable: true; }

tool[name="Read"]     { allow: true; }
tool[name="Bash"]     { allow: true; max-level: 2; }

network                    { deny: "*"; }
resource[kind="memory"]    { limit: 1GB; }
resource[kind="wall-time"] { limit: 10m; }
resource[kind="tmpfs"]     { limit: 128MB; }

env[name="PYTHONPATH"]     { allow: true; }
env[name="PYTEST_ADDOPTS"] { allow: true; }
env                         { allow: false; }
```

Note the `max-level: 2` on `tool[name="Bash"]`. Bash is allowed but capped at computation level 2 (data channels + read + compute only) — no writes, no network, no subprocess spawning. The combination of allowing Bash for test invocation while capping its computation level is a pattern that the at-rule sugar can't express; entity-selector form is required for computation-level constraints.

### An actor-conditioned view with cross-taxon compound selectors

```
# Auth files are read-only to most tools, editable via Edit,
# and forbidden entirely when Bash is the acting tool.

file[path^="src/auth/"]                          { editable: false; }   /* baseline */
tool[name="Edit"] file[path^="src/auth/"]       { editable: true;  }   /* Edit can edit auth */
tool[name="Bash"] file[path^="src/auth/"]       { editable: false;
                                                  visible:  false; }   /* Bash can't even see auth */

# Runtime argv restriction on Bash: only safe commands.
tool[name="Bash"] {
  allow-pattern: "git *", "pytest *", "ruff *", "black *";
  deny-pattern:  "rm -rf *", "curl *", "ssh *", "sudo *";
}

resource[kind="memory"]     { limit: 512MB; }
resource[kind="wall-time"]  { limit: 5m; }
network { deny: "*"; }

hook[event="after-change"] {
  run: "pytest tests/auth/ -x";
  run: "ruff check src/auth/";
}
```

The three cascade-related rules on `file[path^="src/auth/"]` all target `file` (the rightmost entity is the target taxon). They compete in the `world` taxon's cascade, with specificity accumulating across compound-selector parts — the two tool-qualified rules beat the baseline because they have higher compound specificity.

**What each compiler realizes.** The OS-altitude compilers (`nsjail`, `bwrap`) see `file[path^="src/auth/"] { editable: false }` as bind-mount permissions and honor it; they silently drop the tool-qualified rules because "acting tool" is not an OS-altitude concept. The semantic-altitude compiler (`kibitzer-hooks`) realizes the tool-qualified rules as in-session hook rules. The claude-plugins hook compiler realizes the `allow-pattern` / `deny-pattern` on Bash as permission checks at tool dispatch time. No single compiler handles all the rules, which is the point — the view describes *intent* across altitudes, and the enforcement stack realizes what it can at each one. `umwelt dry-run` and `umwelt check` report which rules were honored per target.

### A kitchen-sink view exercising multiple taxa

```
# Maximum coverage. Mixed forms.

/* Filesystem via the sandbox sugar */
@source("src/**/*.py") {
  * { editable: false; }
}

@source("src/auth/**/*.py") {
  * { editable: true; }
}

/* Scratch via entity-selector form */
dir[path="/tmp/work"] file { editable: true; }

/* Tools and capabilities, mixing allowlist and level cap */
kit[name="python-dev"]  { allow: true; }
tool[name="Bash"]       { allow: false; }
tool[altitude="os"]     { max-level: 4; }

/* Runtime budget */
resource[kind="memory"]     { limit: 512MB; }
resource[kind="wall-time"]  { limit: 5m; }
resource[kind="cpu-time"]   { limit: 3m; }
resource[kind="max-fds"]    { limit: 128; }
resource[kind="tmpfs"]      { limit: 64MB; }

/* Network and env */
network { deny: "*"; }
env[name="CI"]          { allow: true; }
env[name="PYTHONPATH"]  { allow: true; }
env[name="GITHUB_TOKEN"]{ allow: true; }
env                     { allow: false; }

/* Post-change hooks */
hook[event="after-change"] {
  run: "pytest tests/auth/ -x";
  run: "ruff check src/auth/";
  run: "black --check src/auth/";
}

/* An unknown at-rule — parsed and preserved, ignored by v1 compilers. */
@retrieval {
  context: last-3-commits;
  include: src/auth/.
}
```

The view mixes at-rule sugar (`@source`, `@retrieval`) and entity-selector form (`world`, `capability`, `state`). Mixing is always valid; the parser canonicalizes everything to entity-selector form internally.

## Semantics of multiple blocks

### Multiple matches on the same entity

Cascade resolves conflicts within a single taxon, following CSS3 specificity rules. See [`entity-model.md`](./entity-model.md) §5 for the full cascade semantics. Short version:

1. More specific selectors beat less specific ones.
2. Equal specificity → later rule wins (document order).
3. Cascade is scoped per taxon; rules in different taxa never conflict.

Example:

```
file                             { editable: false; }      /* specificity (0,0,1) */
file[path^="src/"]               { editable: true;  }      /* specificity (0,1,1) — beats above */
file[path^="src/generated/"]     { editable: false; }      /* specificity (0,1,1) — beats above via doc order */
```

For `src/generated/protobuf_pb2.py`: three rules match, the last wins → read-only.

### Multiple hooks in the same event

All hook commands run in order. Failures do not abort subsequent hooks by default; the dispatcher runs all of them and reports results. The caller decides what to do with failures.

```
hook[event="after-change"] {
  run: "pytest tests/auth/";    /* runs first */
  run: "ruff check src/";       /* runs second, even if pytest failed */
  run: "mypy src/";             /* runs third */
}
```

### Multiple taxa

A view can mix as many taxa as the running environment has registered. The only constraint is that each rule's selector identifies a taxon (either via the prefix form `file ...` or the at-rule form `@world { file ... }`). Rules in different taxa never interact at the cascade layer.

## Case sensitivity

- **At-rule names, entity type names, declaration keys**: case-insensitive.
- **Declaration values from known enumerations** (`true`/`false`, unit names): case-insensitive.
- **Paths, globs, shell commands**: case-sensitive (filesystem and shell conventions apply).
- **Tool names, kit names, env variable names**: case-sensitive (matches the underlying tool or OS naming).

## Whitespace and formatting

Insignificant outside strings. The parser accepts any reasonable formatting. The reference style is:

```
@at-rule(argument) {
  key: value;
  key: value1, value2;

  .selector { key: value; }
}

file[path^="src/"] {
  editable: true;
}
```

With declarations aligned for readability but not required.

## Error handling

The parser raises `ViewParseError` on syntactic errors with line and column of the offending token. Semantic errors (unknown unit suffix, contradictory declarations, paths that escape the base directory) are detected by `umwelt.validate` and raise `ViewValidationError` with the offending AST node attached.

Unknown at-rules, unknown entity types, and unknown declarations inside recognized at-rules are **warnings, not errors** in v1. The AST preserves them with a warning flag; compilers silently ignore what they don't understand; forward compatibility holds. A `strict=True` mode turns warnings into errors for fail-fast validation.

## File extension

The working convention is `.umw`. Distinct, short, memorable, not overloaded. Alternative candidates considered: `.view` (collides with Django), `.css` (misleading). A view file opens cleanly in any text editor without triggering CSS mode.

## What this document doesn't cover

- **The entity model.** See [`entity-model.md`](./entity-model.md) for what entities exist, how selectors match them, how cascade resolves, and how plugins register their own taxa.
- **The framing.** See [`policy-layer.md`](./policy-layer.md) for why umwelt looks this way and how it fits the specified-band regulation strategy.
- **Individual compiler mapping tables.** See [`compilers/`](./compilers) — one file per compiler.
- **Runtime behavior.** Workspace builder, write-back, hook dispatcher — in [`package-design.md`](./package-design.md) (sandbox consumer's runtime).
- **Security analysis.** Threat model, parser hardening — future `security.md`.
- **The view bank.** Storage, retrieval, distillation — future `view-bank.md`.
- **Selector semantics for code nodes.** Selectors inside `file ... node` follow pluckit / sitting_duck conventions — documented there, not here. v1 treats node selectors as opaque strings; v1.1 evaluates them via pluckit.

## Versioning the format

The view format follows semantic versioning from v1.0 onward. The version is implicit (not declared in the file) in v1 — readers assume v1 semantics. v2 may introduce a `@version` or `@umwelt-version` declaration if breaking changes become necessary. For now, unknown constructs being silent-ignored-with-warning is sufficient forward compatibility.
