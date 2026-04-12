# Note: Roadmap additions from the post-v0.2 design session

*Captured 2026-04-12. Additions to the roadmap from the design discussions about cascade safety, audit visualization, and the world browser.*

---

## v0.3 additions (alongside bwrap + world#env-name + mount topology + exec entity)

### `umwelt audit` — security-aware policy visualizer

Evolve `umwelt check` into a security audit tool. The output shows:

- Per-entity resolved policy with the source rule and specificity
- **Widening warnings**: every cascade interaction where a later rule WIDENS access (editable: false → true, allow: false → true, deny removed)
- Enforcement coverage: which rules are backed by a registered compiler vs. declarative-only
- Per-environment breakdown when multiple `world#name` environments exist

This is also the data source for the v1.1 delegate-context compiler — the audit output and the agent's constraint prompt are two renderings of the same resolved policy.

---

## v0.5 additions (alongside security pass + API freeze)

### Cascade Layers (`@layer`) — tightening-only cascade

Adopt CSS Cascade Layers for explicit priority ordering with security direction:

```css
@layer base {
  file { editable: false; }
  tool { allow: false; }
  network { deny: "*"; }
}

@layer task {
  file[path^="src/auth/"] { editable: true; }
  tool[name="Read"] { allow: true; }
}

@layer locked {
  file[path^="secrets/"] { editable: false !locked; }
}
```

- `@layer` gives named priority tiers (base < task < override)
- `!locked` (or `!sealed`) prevents later layers from loosening a value
- The ratchet produces tighten-only layers by default
- Security-critical rules in a `locked` layer can't be overridden

This makes the cascade safe for policy: widening requires explicit escalation, not just adding a later rule.

---

## v0.9 / v1.0 — The World Browser

A visual (and textual) browser/editor for umwelt views. DevTools for policy.

### What it looks like

**Entity tree panel** (left):
```
▾ world#auth-fix
  ▾ mount[path="/workspace/src"]
    ▾ dir[name="src"]
      ▾ dir[name="auth"]
        ▸ file[name="login.py"]     ← EDITABLE
        ▸ file[name="oauth.py"]     ← EDITABLE
      ▾ dir[name="common"]
        ▸ file[name="util.py"]      ← read-only
  ▸ resource[kind="memory"]          512MB
  ▸ network                          BLOCKED
  ▸ env[name="CI"]                   allowed

▾ capability
  ▸ tool[name="Read"]                ALLOWED
  ▸ tool[name="Edit"]                ALLOWED
  ▸ tool[name="Bash"]                DENIED

▾ state
  ▸ hook[event="after-change"]       2 commands
```

**Computed policy panel** (right, for selected entity):
```
file[name="login.py"]
  path:     src/auth/login.py
  editable: true         ← from line 5 (0,1,1)
  visible:  true         ← default
  show:     (not set)

  Cascade:
    line 3: file[path^="src/"]      { editable: false }   ← overridden
    line 5: file[path^="src/auth/"] { editable: true }    ← winner
    ⚠ Widens access from line 3
```

**Pivot navigation:**
- Click `file[name="login.py"]` → expands into AST nodes (sitting_duck):
  ```
  ▾ node.function#authenticate    ← editable: true (inherited)
  ▾ node.class#User              ← editable: false (line 7)
  ```
- Click a `table` entity → expands into DuckDB rows
- Each pivot level shows its own computed policy

**Rule source panel** (bottom):
```css
/* line 3 */ file[path^="src/"]      { editable: false; }  ← matches 4 files
/* line 5 */ file[path^="src/auth/"] { editable: true; }   ← matches 2 files ⚠
/* line 7 */ tool[name="Bash"]       { allow: false; }     ← matches 1 tool
```

### The editing experience

- Click a property value → edit inline → view file updates
- Right-click an entity → "Add rule for this entity" → inserts a new rule
- Drag a rule between `@layer` blocks to change priority
- Real-time warnings as you edit (cascade widening, unenforceable rules)
- "Diff from last committed view" shows what changed

### The tooling stack

All the pieces exist:
- **sitting_duck**: AST queries for the code-node pivot
- **webbed**: HTML rendering for the browser UI
- **duck_block_utils**: generic document element rendering
- **DuckDB**: queries everything (entity resolution, cascade computation could be SQL)
- **markdown rendering**: for inline documentation from property descriptions
- **pluckit**: CSS selector → AST navigation for the code pivot

The world browser is a composition of these tools using umwelt's entity model as the DOM and the view's rules as the stylesheet. It's not a new tool — it's the existing ecosystem connected through umwelt's common language.

### Why this matters

The world browser closes the loop on transparency. The Ma framework's SELinux coda says: the governed actor should be able to see its own constraints. The world browser is how a HUMAN sees them — not as raw text, but as an explorable, annotated, policy-aware view of exactly what the agent can and can't do. It's the policy equivalent of Chrome DevTools' Elements panel: you SEE the DOM, you SEE the styles, you SEE the cascade, you can edit and the page updates.

For the ratchet: the world browser becomes the review interface. `umwelt ratchet` proposes a tightened view; the human reviews the diff IN the world browser, seeing exactly which entities are affected and how. The audit warnings highlight where access changed. The human clicks "accept" or edits the proposal. The ratchet turns.

---

## Updated roadmap

```
v0.1.0-core    ████████████████████  DONE — vocabulary-agnostic core
v0.1.0         ████████████████████  DONE — sandbox consumer
v0.2.0         ████████████████████  DONE — nsjail compiler
v0.3           ░░░░░░░░░░░░░░░░░░░░  bwrap compiler, world#env-name, mount topology,
               ░░░░░░░░░░░░░░░░░░░░  exec entity, umwelt audit visualizer
v0.4           ░░░░░░░░░░░░░░░░░░░░  @import, kits-as-views, lackpy integration, PyPI
v0.5           ░░░░░░░░░░░░░░░░░░░░  @layer (cascade safety), kibitzer, security pass,
               ░░░░░░░░░░░░░░░░░░░░  API freeze
v0.6           ░░░░░░░░░░░░░░░░░░░░  ratchet (blq observation → view proposal)
v0.7           ░░░░░░░░░░░░░░░░░░░░  delegate-context compiler (SELinux coda)
v0.8           ░░░░░░░░░░░░░░░░░░░░  multi-backend tools (mcp, python, duckdb)
v0.9           ░░░░░░░░░░░░░░░░░░░░  world browser (visual policy explorer)
v1.0           ░░░░░░░░░░░░░░░░░░░░  ship — PyPI, docs, blog post
```
