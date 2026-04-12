# umwelt

**Define what an AI agent can see, edit, call, and trigger — in a file that reads like CSS.**

```css
world#auth-fix {
  file[path^="src/auth/"] { editable: true; }
  file[path^="src/"]      { editable: false; }
  tool[name="Read"]        { allow: true; }
  tool[name="Bash"]        { allow: false; }
  network                  { deny: "*"; }
  resource[kind="memory"]  { limit: 512MB; }
  hook[event="after-change"] { run: "pytest tests/auth/"; }
}
```

umwelt parses this, builds a virtual workspace from it, and translates it into whatever config format your sandbox tool already accepts.

## Get started

<div class="grid cards" markdown>

- :material-book-open-variant: **[Writing Views](guide/writing-views.md)**

    Learn to write `.umw` files from scratch — files, tools, hooks, budgets, environments, compound selectors.

- :material-cog: **[How It Works](guide/how-it-works.md)**

    The entity model, plugin architecture, pivots between world models, and the ecosystem linker role.

- :material-github: **[GitHub](https://github.com/teaguesterling/umwelt)**

    Source code, issues, and the full README with install instructions.

</div>

## Quick install

```bash
pip install -e ".[dev]"    # from source
```

```bash
umwelt inspect src/umwelt/_fixtures/auth-fix.umw
umwelt dry-run src/umwelt/_fixtures/auth-fix.umw
```

## Why umwelt?

Every tool in the AI agent stack has its own way to restrict what an agent can do: nsjail has textproto, bwrap has argv flags, lackpy has namespace dicts, kibitzer has hook rules. They're all describing the same thing in different languages.

umwelt is the **common language**. One view file. Every enforcement tool reads the parts it can enforce.

The theoretical foundation is in [The Ma of Multi-Agent Systems](https://judgementalmonad.com/blog/ma/00-intro). The practitioner companion is [Ratchet Fuel](https://judgementalmonad.com/blog/fuel/).
