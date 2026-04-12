# Note: exec entity, tool backends, and kits-as-view-fragments

*Captured during post-v0.2 design discussion on 2026-04-12. Records the exec entity design, the tool/exec distinction, the multi-backend model, and the kit-as-view-fragment insight.*

---

## The tool/exec distinction

**`tool`** (capability taxon) = what the delegate can ASK FOR. An interface: name, schema, description. It might be backed by an MCP server, a Python function, a subprocess, or nothing (a harness-handled operation like Read/Edit). The delegate says "I want to use X" and the harness decides how to realize it.

**`exec`** (world taxon) = how something actually RUNS INSIDE THE JAIL. A binary on the filesystem with a concrete path. The exec exists whether or not any tool references it — `/bin/sh` is in the jail regardless of which tools are available.

The relationship: a tool MAY invoke an exec (`tool[name="Bash"] { exec: "bash"; }`), but many tools don't (Read is handled by the harness, never enters the jail). An exec can exist without any tool referencing it (system binaries available for hook commands).

---

## The exec entity (v0.3)

Register `exec` in the world taxon:

```css
exec[name="bash"]    { path: "/bin/bash"; }
exec[name="python3"] { path: "/usr/bin/python3"; }
exec[name="pytest"]  { path: "/usr/local/bin/pytest"; }
exec                 { search-path: "/bin:/usr/bin:/usr/local/bin"; }
```

Properties:
- `path` — absolute path to the binary inside the jail
- `search-path` — PATH-like colon-separated search directories (on the bare `exec` type, this is the default PATH for the jail)

Compilers consume exec entities:
- nsjail: emits `envar: "PATH=..."` from `search-path`
- bwrap: emits `--setenv PATH ...`
- Runners: resolve command names against exec entities before invoking the jail

The hook dispatcher resolves `run: "pytest tests/"` → `/usr/local/bin/pytest tests/` via exec entity lookup before passing to subprocess.

---

## Multi-backend tools (v0.4+)

Not all tools are filesystem executables. The backend property on a tool declares how it's realized:

```css
tool[name="Bash"]   { backend: exec; exec: "bash"; }
tool[name="search"] { backend: mcp; server: "fledgling"; }
tool[name="query"]  { backend: duckdb; connection: "blq://events"; }
tool[name="edit"]   { backend: python; module: "lackpy.tools.edit"; }
```

The policy layer (allow/deny/max-level/patterns) is the same regardless of backend. Each backend type has its own compiler:
- `exec` → nsjail/bwrap handle it
- `mcp` → an MCP integration compiler (v0.4+)
- `python` → lackpy handles it
- `duckdb` → duckdb_mcp handles it

---

## Kits as view fragments

A kit is a package of tools with their implementations declared. In umwelt, a kit IS a view fragment — same grammar, same cascade:

```css
kit#python-dev {
  tool[name="python3"] { exec: "python3"; max-level: 4; }
  tool[name="pytest"]  { exec: "pytest"; max-level: 2; }
  tool[name="ruff"]    { exec: "ruff"; max-level: 1; }
  exec { search-path: "/usr/bin:/usr/local/bin"; }
}
```

Using a kit in a view:

```css
@import "kits/python-dev.umw";

world#auth-fix {
  kit#python-dev { allow: true; }
  tool[name="python3"] { max-level: 2; }  /* override: tighten */
}
```

Kit rules come in via @import. View rules cascade on top — the view can override anything the kit declared. Standard CSS cascade.

Implications:
- **MCP servers ARE kits.** The MCP manifest + a kit `.umw` = full tool package.
- **The ratchet produces kits.** Promoted bash patterns become tool definitions in a kit view.
- **lackpy's kits become `.umw` files.** No custom kit format needed.
- **Kit composition is view composition.** Multiple kits imported, cascade resolves conflicts.
- **`@import` is load-bearing.** It's how kits compose. Priority moved up; needed by v0.4.

---

## Future: on-the-fly MCP assembly

A kit `.umw` file contains enough information to generate an MCP server manifest: tool names, schemas (from attributes), backend bindings. A hypothetical compiler:

```bash
umwelt compile --target mcp-manifest kits/python-dev.umw
```

→ emits a working MCP server config that registers the declared tools. This is a compiler target, same shape as nsjail or bwrap.

Even further: `umwelt compile --target duckdb-mcp` could generate a duckdb_mcp config that exposes SQL macros as MCP tools, with their computation levels and patterns declared in the kit view.

Deferred. Captured for the v1.0+ roadmap.

---

## v0.3 scope from this discussion

1. Register `exec` as a world-taxon entity with `path` and `search-path` properties
2. nsjail compiler emits `envar: "PATH=..."` from exec's search-path
3. bwrap compiler emits `--setenv PATH ...`
4. Hook dispatcher resolves commands via exec entity search-path
5. `tool → exec` bridge property: `tool[name="Bash"] { exec: "bash"; }`
6. Inline kit declarations (kit rules in the same file); @import deferred to v0.4

What's NOT in v0.3:
- MCP backend binding (`backend: mcp; server: "fledgling";`)
- Python backend binding (`backend: python; module: "..."`)
- DuckDB backend binding
- @import for kit composition
- On-the-fly MCP assembly
