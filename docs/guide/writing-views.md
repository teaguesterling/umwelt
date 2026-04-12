# Writing Views

A view is a `.umw` file that describes what an AI agent operating inside it can see, edit, call, and trigger. This guide starts with the smallest possible view and builds up, one concept at a time.

## Your first view

```css
file[path="src/main.py"] { editable: true; }
```

That's a complete view. It says: the agent can edit `src/main.py`. Everything else about the agent's environment is unspecified (defaults apply).

Save it as `first.umw` and inspect it:

```bash
umwelt inspect first.umw
```

## Matching files

Selectors work like CSS. You match files by their attributes:

```css
file[path="src/main.py"]          /* exact path */
file[path^="src/"]                /* path starts with src/ */
file[path$=".py"]                 /* path ends with .py */
file[path*="/auth/"]              /* path contains /auth/ */
file[name="README.md"]            /* exact filename */
file:glob("src/**/*.py")          /* shell glob pattern */
```

These are standard CSS attribute selectors. If you've written CSS, you already know the grammar.

## The cascade: later rules win

When multiple rules match the same file, the later rule wins (on equal specificity):

```css
file[path^="src/"]      { editable: false; }   /* all of src: read-only */
file[path^="src/auth/"] { editable: true; }    /* auth files: editable */
```

A file at `src/auth/login.py` matches both rules. They have equal specificity (one attribute selector + one type selector each), so the later rule wins → editable.

A file at `src/common/util.py` matches only the first rule → read-only.

This is CSS cascade, applied to file policy instead of visual style.

## More specificity = higher priority

Specificity works exactly like CSS. Each selector component adds weight:

| Component | Specificity contribution |
|---|---|
| `file` (type) | (0, 0, 1) |
| `[path^="src/"]` (attribute) | (0, 1, 0) |
| `#README.md` (id) | (1, 0, 0) |
| `.test` (class) | (0, 1, 0) |

A selector with higher specificity always wins, regardless of document order:

```css
file[path^="src/"]                { editable: false; }   /* (0,1,1) */
file#README.md                    { editable: true; }    /* (1,0,1) — wins even though earlier */
```

## Restricting tools

The `tool` entity type controls what tools the agent can call:

```css
tool[name="Read"]  { allow: true; }
tool[name="Edit"]  { allow: true; }
tool[name="Grep"]  { allow: true; }
tool[name="Bash"]  { allow: false; }
tool[name="Write"] { allow: false; }
```

You can also cap the computation level (from the [Ma framework's nine-level taxonomy](https://judgementalmonad.com/blog/ma/07-computation-channels)):

```css
tool[name="Bash"] { allow: true; max-level: 2; }
```

`max-level: 2` means Bash is allowed but only for read + compute operations — no writes, no subprocess spawning, no network. The `max-` prefix is a comparison operator built into the property name: it means "the permitted value is ≤ the declared value."

For runtime restrictions on what commands Bash can run:

```css
tool[name="Bash"] {
  allow: true;
  max-level: 2;
  allow-pattern: "git *", "pytest *", "ruff *";
  deny-pattern: "rm -rf *", "curl *", "sudo *";
}
```

Pattern properties use shell-glob syntax and are evaluated at runtime by whatever enforcement tool realizes them.

## Hooks: run commands after changes

```css
hook[event="after-change"] {
  run: "pytest tests/auth/ -x";
  run: "ruff check src/auth/";
  run: "mypy src/auth/";
}
```

After the agent modifies any file, these commands run in order. If one fails, the others still run — the results are all reported back. Commands execute in the real project directory (not the virtual workspace).

## Resource limits

```css
resource[kind="memory"]    { limit: 512MB; }
resource[kind="wall-time"] { limit: 5m; }
resource[kind="cpu-time"]  { limit: 3m; }
resource[kind="max-fds"]   { limit: 128; }
resource[kind="tmpfs"]     { limit: 64MB; }
```

These compile to nsjail rlimits, bwrap wrappers (prlimit/timeout), or equivalent mechanisms on other targets. Missing limits mean "tool default."

## Network policy

```css
network { deny: "*"; }
```

v1 supports only full network denial. v1.1 will add hostname allowlists:

```css
network[host="api.github.com"] { allow: true; }
network { deny: "*"; }
```

## Environment variables

```css
env[name="CI"]         { allow: true; }
env[name="PYTHONPATH"] { allow: true; }
env                    { allow: false; }   /* deny everything else */
```

The specific rules have higher specificity than the bare `env` selector, so named variables are allowed while the default denies everything else. Standard CSS cascade.

## Named environments

Use `world#name` to define named environments in one file:

```css
/* Global defaults — apply to all environments */
network { deny: "*"; }
hook[event="after-change"] { run: "ruff check src/"; }

/* Development: everything editable, Bash allowed */
world#dev file { editable: true; }
world#dev tool[name="Bash"] { allow: true; max-level: 4; }
world#dev resource[kind="wall-time"] { limit: 30m; }

/* CI: read-only, tight limits */
world#ci file { editable: false; }
world#ci tool[name="Bash"] { allow: true; max-level: 2; }
world#ci resource[kind="memory"] { limit: 512MB; }
world#ci resource[kind="wall-time"] { limit: 5m; }

/* Exploration: read-only, no editing tools */
world#explore tool { allow: false; }
world#explore tool[name="Read"] { allow: true; }
world#explore tool[name="Grep"] { allow: true; }
world#explore file { editable: false; }
```

Resolve against a specific environment:

```bash
umwelt dry-run --world dev project.umw
umwelt dry-run --world ci project.umw
```

Rules outside any `world#name` scope are shared defaults. Rules inside a `world#name` scope only apply in that environment. The `world#name` qualifier adds specificity, so environment-specific rules naturally override defaults.

## Actor-conditioned policy (compound selectors)

You can condition rules on which tool is acting:

```css
file[path^="src/auth/"]                       { editable: true; }
tool[name="Bash"] file[path^="src/auth/"]     { editable: false; }
tool[name="Edit"] file[path^="src/auth/"]     { editable: true; }
```

When Edit operates on auth files → editable. When Bash operates on auth files → not editable. When any other tool operates → editable (base rule).

This uses **compound selectors**: the tool qualifier on the left conditions when the rule fires; the file on the right is what the declaration applies to. The cascade target is always the rightmost entity.

Combine with environments:

```css
world#dev tool[name="Bash"] file[path^="src/"] { editable: true; }
world#ci tool[name="Bash"] file[path^="src/"]  { editable: false; }
```

## The @ shorthand

For common patterns, umwelt supports at-rule shorthand that desugars to entity selectors during parsing:

| Shorthand | Equivalent entity-selector form |
|---|---|
| `@source("src/auth") { * { editable: true; } }` | `file[path^="src/auth/"] { editable: true; }` |
| `@source("src/**/*.py") { * { editable: false; } }` | `file:glob("src/**/*.py") { editable: false; }` |
| `@tools { allow: Read, Edit; deny: Bash; }` | `tool[name="Read"] { allow: true; }` `tool[name="Edit"] { allow: true; }` `tool[name="Bash"] { allow: false; }` |
| `@after-change { test: pytest; }` | `hook[event="after-change"] { run: "pytest"; }` |
| `@network { deny: *; }` | `network { deny: "*"; }` |
| `@budget { memory: 512MB; }` | `resource[kind="memory"] { limit: 512MB; }` |
| `@env { allow: CI; }` | `env[name="CI"] { allow: true; }` |

Both forms are first-class. Mix them freely. The @ syntax is shorter for simple cases; the entity-selector form is more powerful (compound selectors, named environments, fine-grained attribute matching).

## CSS nesting (grouping rules)

When many rules share a prefix, use CSS nesting to avoid repetition:

```css
world#auth-fix {
  file[path^="src/auth/"] { editable: true; }
  file[path^="src/"]      { editable: false; }

  tool[name="Read"]  { allow: true; }
  tool[name="Edit"]  { allow: true; }
  tool[name="Bash"]  { allow: false; }

  resource[kind="memory"]    { limit: 512MB; }
  resource[kind="wall-time"] { limit: 5m; }
  network { deny: "*"; }

  hook[event="after-change"] {
    run: "pytest tests/auth/ -x";
    run: "ruff check src/auth/";
  }
}
```

The inner rules are descendants of `world#auth-fix`. This is standard CSS nesting — no special umwelt syntax.

## Navigating into source code

When you need to target specific code constructs (not just files), selectors can descend into the AST:

```css
file[path="src/auth/login.py"] node.function#authenticate {
  show: body;
  editable: true;
}

file[path="src/auth/login.py"] node.class#User {
  show: outline;
  editable: false;
}
```

The `file → node` boundary is a **pivot** — the selector crosses from the filesystem world into the AST world. On the left of the pivot, the filesystem matcher finds the file. On the right, the AST matcher (sitting_duck / pluckit) finds the code construct.

Node selectors use the same grammar as pluckit's CSS selectors for code:
- `node.function` — a function definition
- `node.class` — a class definition
- `node#authenticate` — a node named "authenticate"
- `node[kind="method"]` — a method by kind attribute

This is a v1.1 feature; v1 parses node selectors but doesn't evaluate them.

## Comments

Three comment styles are supported:

```css
/* CSS block comment */
// C-style line comment
# Unix-style line comment (use with care — # also starts CSS id selectors)
```

Prefer `/* */` for comments inside views. It's the CSS-native style and avoids any ambiguity with `#id` selectors.

## What happens when you parse a view

1. **Tokenize** — tinycss2 breaks the text into CSS tokens.
2. **Parse** — umwelt walks the tokens, recognizes selectors and declarations, desugars @ shorthand.
3. **Resolve entity types** — each entity name (`file`, `tool`, `hook`) is looked up in the plugin registry to find its taxon.
4. **Classify combinators** — descendant selectors within the same taxon are structural (containment); across taxa they're context qualifiers (gating).
5. **Compute specificity** — CSS3 specificity, accumulated across compound selectors.
6. **Validate** — per-taxon validators check for path traversal, allow/deny conflicts, etc.
7. **Resolve cascade** — for each entity, the winning rule per property is determined by specificity + document order.

The output is a `ResolvedView`: per-entity, per-property resolved values, ready for compilers to translate to enforcement configs.

## Next steps

- **[How umwelt Works](how-it-works.md)** — the entity model, plugin architecture, and how umwelt connects the ecosystem.
- **[Vision docs](../vision/)** — the architecture specs (entity model, policy layer, format reference, package design).
- **[The Ma of Multi-Agent Systems](https://judgementalmonad.com/blog/ma/00-intro)** — the theoretical framework behind the design.
