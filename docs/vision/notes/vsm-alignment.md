# Note: VSM alignment — umwelt taxa as Beer's Viable System Model

*Captured 2026-04-14 during the v0.5 VSM restructure. Reader's on-ramp
to "why Beer?" Companions: the formal spec at
`docs/superpowers/specs/2026-04-13-umwelt-v05-vsm-restructure-design.md`
and the Datalog-framing note at `logic-semantics.md`.*

---

## What VSM gave us

Stafford Beer's Viable System Model (VSM, 1972–1985) names five systems
inside an organism embedded in its environment:

| System | Beer's name | What it does |
|---|---|---|
| S5 | Identity / policy | Who are we; what's our purpose. |
| S4 | Intelligence | Outside-and-then: scanning environment, anticipating. |
| S3 | Internal control | Inside-and-now: moment-to-moment regulation. |
| S3\* | Audit | Bypass channel; direct observation of S1 without S2/S3 interference. |
| S2 | Coordination | Anti-oscillation among S1 units. |
| S1 | Operations | The doing. |
| — | Environment | What S1 acts on and what S4 watches. |

Before v0.5, umwelt had five taxa (`world`, `capability`, `state`,
`actor`, `policy`) that were a mixed bag: `state` smeared S2 (hooks), S3
(budgets, jobs), and S4 (observations) into one bucket; `actor` smeared
S1 (executor), S4 (inferencer), and S5 (principal) into another. That's
why adding modes had no clean home: `state` was three different systems
wearing one hat.

v0.5 splits them along Beer's axes. Seven taxa:

| umwelt taxon | VSM system | Entities (v0.5) |
|---|---|---|
| `principal` | S5 | principal |
| `world` | environment | file, dir, mount, network, env, exec, resource |
| `audit` | S3\* | observation, manifest |
| `control` (alias of `state`) | S3 | budget, job; mode (v1.1+) |
| `coordination` (alias of `state`) | S2 | hook |
| `intelligence` (alias of `actor`) | S4 | inferencer |
| `operation` (alias of `capability`) | S1 | tool, kit, executor, use |

The VSM names are aliases in v0.5 so legacy code keeps working; `state`
and `actor` still resolve correctly. A physical split (separate
`coordination` and `control` taxa with separate matchers) is a v0.6+
concern.

## The outside-in chain

VSM is usually diagrammed as nested envelopes. umwelt preserves that
nesting in selector order:

```
audit                                     ← outside everything (S3*)
  principal                               S5    "running-in"
    world                                 S0    "in"
      control                             S3    "with mode / under budget"
        coordination                      S2    "via harness"
          intelligence                    S4    "reasoned-by inferencer"
            operation                     S1    "through tool"
              use[of=...]                       "operating on resource"
```

A rule like:

```css
principal#Teague world#sandbox-123 mode.testing harness#claude-code
  inferencer#opus-46 tool#Bash exec#sed use[of="file#/foo.txt"]
  { editable: true; }
```

reads naturally as a single cross-axis conjunction. The descendant
combinator is one syntactic primitive; the meaning of each crossing is
emergent from which axes it joins.

## The S3↔S4 inversion

In Beer's VSM, S3 (inside/now) and S4 (outside/then) are **peers** that
resolve tension at S5. umwelt inverts this for bounded delegation:
**S3/S2 dominate S4**. The regulator (coordination + control) constrains
the reasoner (intelligence); the reasoner doesn't resolve tension with
S3 as a peer.

This is the architectural move that makes the specified band coherent.
A delegate is a system whose own S4 is bounded by an externally-imposed
S3. Without this inversion, a sufficiently capable inferencer could
reason its way past its regulator — which is precisely the failure mode
the specified band is designed to prevent.

## Audit outside the world

S3\* bypasses normal reporting. Beer's point: the auditor sees S1
directly without going through S2/S3 interpretation. umwelt honors this
architecturally: `@audit { ... }` is an at-rule scope that sits *outside*
the world hierarchy. Audit entries are selectable from any scope, never
subject to world-qualifiers.

This maps naturally to how observation tools work in practice:
`blq`, `ratchet-detect`, `strace` watch *from outside* the delegate's
world. The observation stream they produce flows into `@audit`; it does
not live inside `world`.

## Why this matters for compilers

Compilers live at different altitudes (OS, language, semantic). Each
altitude reads a subset of the VSM axes:

| Compiler | Altitude | Reads | Writes |
|---|---|---|---|
| nsjail | OS | world-axis (file, mount, resource, network, env, exec) | nsjail textproto |
| bwrap | OS | world-axis | bwrap argv |
| lackpy-namespace | language | operation-axis (tool allow/deny, use for tool-level gating) | Python dict |
| kibitzer-hooks (v0.6) | semantic | control (mode writable), operation (use for per-tool gating) | TOML |

The VSM partition tells each compiler which axes are in-scope. No
compiler reads audit (that's what dedicated observation consumers will
do in v0.7).

## Why this matters for authors

If you can say "this rule is about the principal," or "about the
harness," or "about the current mode," the rule has a single home and
the rest of the view is uncluttered. CSS-cascade familiarity carries
over: more axes named → more specific rule → wins the cascade.

## Further reading

- `docs/superpowers/specs/2026-04-13-umwelt-v05-vsm-restructure-design.md` — the formal spec.
- `docs/vision/notes/logic-semantics.md` — Datalog framing of the same structure.
- `docs/vision/evaluation-framework.md` — claim ledger; G1 is the VSM-fidelity claim this note supports.
- Beer, *Brain of the Firm* (1972), *The Heart of Enterprise* (1979), *Diagnosing the System for Organizations* (1985).
