# umwelt v0.5 Design — VSM-Aligned DOM Restructure

*Pre-implementation design for the v0.5 milestone. Replaces the current five-taxon model (`world`/`capability`/`state`/`actor`/`policy`) with a VSM-aligned (Stafford Beer) multi-axis DOM, introduces `use[of=...]` as the action-axis permission primitive, defines cross-axis cascade specificity, and kicks the kibitzer-hooks compiler into v0.6 where it slots naturally into the restructured taxa.*

**Status:** draft, pre-implementation.
**Date:** 2026-04-13.
**Depends on:** `docs/vision/entity-model.md`, `docs/vision/notes/selector-semantics.md`, the Ma series on the specified-band Harness, Beer's *Brain of the Firm* / *Heart of Enterprise* (VSM).
**Prerequisite:** v0.4.0 shipped (nsjail + bwrap + lackpy-namespace compilers, diff utility, PyPI-ready).
**Next step after approval:** invoke `writing-plans` to produce a concrete v0.5 implementation plan sequenced by the vertical slices in §10.

---

## 1. Motivation and scope

The current five-taxon model (`world`, `capability`, `state`, `actor`, `policy`) smears responsibilities across concepts. The `state` taxon in particular wears three hats — hook (coordination), budget/job (control), observation (intelligence) — which is why adding kibitzer's *mode* concept has no clean home: `state` is three different systems in a trenchcoat.

Beer's Viable System Model names the systems we're actually working with:

- **S1 Operations** — the doing parts.
- **S2 Coordination** — anti-oscillation. The Harness.
- **S3 Control** — "inside and now." Resource allocation to S1 in the current moment.
- **S3\*** — the audit channel. Bypasses normal reporting.
- **S4 Intelligence** — "outside and then." Environmental scanning.
- **S5 Identity** — purpose; resolves S3↔S4 tension.

Applied to delegation:

- S1 is tools and effects.
- S2 is the Harness (claude-code, lackpy, kibitzer).
- S3 is the mode / controller / budget — kibitzer's `[modes.*]` config is exactly S3.
- S3\* is blq / ratchet-detect / strace — observation from outside the delegate's world.
- S4 is the inferencer itself.
- S5 is the principal — the human or outer agent who commissioned the delegate.

This milestone restructures umwelt's taxa to these axes, so subsequent compiler work (kibitzer-hooks in v0.6, observation compilers in v0.7, etc.) slots in without torturing the vocabulary.

### Deliverables

1. **VSM-aligned taxa** (§2) replacing the current five-taxon model.
2. **`use[of=...]` primitive** (§3) — the action-axis permissioned projection of a world resource. **Additive, not replacing** — world-axis permissions on resources (`file { editable: true; }`) and action-axis permissions on uses (`use[of=file#X] { editable: true; }`) are semantically independent (see §3a).
3. **`audit` placed outside the world** (§4) — architectural, not conventional.
4. **Mode as a class, not an ID** (§5) — `mode.implement`, compositional across worlds.
5. **Cross-axis cascade** (§6) — specificity counts contributions from every axis a selector names.
6. **Migration path** (§9) — every current entity mapped to its new axis; existing views work unchanged because world-axis properties remain.
7. **v0.5 vertical slices** (§10) — each buildable independently, each leaving the test suite green.

### Explicit non-goals for v0.5

- **The kibitzer-hooks compiler.** Moved to v0.6. v0.5 creates the taxa that make the compiler trivial; v0.6 actually ships it.
- **The S3\* audit compiler.** v0.7+.
- **Full S5 / principal modeling.** v0.5 adds the `principal` taxon root and a single `principal` entity with name + intent fields; richer principal modeling (cross-delegate lineage, grade lattice) is v1.1+.
- **The security pass and public API freeze.** Originally bundled into v0.5 in the roadmap; shifted to v0.6 / v0.7 because the restructure is already a full milestone on its own. v0.5 preserves all existing compiler outputs bit-for-bit; the security pass needs to sit on the post-restructure API.
- **Cross-axis cascade across all combinators.** v0.5 implements cross-axis specificity for descendant combinators; sibling combinators (`+`, `~`) remain v1.1+ per existing deferrals.
- **`:has()` implementation.** The design uses `:has()` semantics in examples (world:has(file#...)) but v0.5 parses-but-doesn't-evaluate; evaluation is v1.1.

---

## 2. The VSM-aligned taxa

Current taxa → new taxa:

| Current | New | System | Rationale |
|---|---|---|---|
| `world` | `world` | S0 (environment) | Unchanged name; narrowed — holds *existence* of resources only. |
| `capability` (tool, kit) | `operation` | S1 | `tool`, `effect`, `kit` live here; `kit` remains but classifies as S1 when used as a bundle-of-ops. |
| `capability` (exec) | `world` | S0 | `exec` is a world-side binding (a binary that exists in the environment). Moves to world. |
| `state.hook` | `coordination` | S2 | Hooks are the coordination primitive by definition. |
| `state.budget`, `state.job`, *(new)* `mode` | `control` | S3 | Current-moment regulation. `mode` lands here cleanly. |
| *(new)* `observation`, `state.manifest` | `audit` | S3\* | Cross-cut observer. Outside the world. |
| `actor.inferencer` | `intelligence` | S4 | The reasoner. |
| `actor.executor` | `operation` | S1 | Executors are how operations get dispatched. |
| `actor.principal` | `principal` | S5 | Promoted to its own top-level taxon. |
| `policy` | *removed* | — | Policy isn't a taxon; policy is what the whole view *is*. |

The seven new taxa:

1. **`principal`** — S5. Commissioning authority. One principal per view (in v1).
2. **`world`** — S0. Environment. Holds files, dirs, mounts, network, env, exec, resources.
3. **`audit`** — S3\*. Outside the world. Observation entries, manifest, ratchet signals.
4. **`control`** — S3. Mode, controller, budget, job.
5. **`coordination`** — S2. Hook, scheduler.
6. **`intelligence`** — S4. Inferencer.
7. **`operation`** — S1. Tool, effect, kit, executor.

### The outside-in authority chain

```
audit                                  ← outside everything (S3*)
  │   observes all below without being subject to them
  │
  ▼
principal         S5    commissioning identity
  │
  ▼
world             S0    environment chosen for the delegate
  │
  ▼
control           S3    current-moment regulation (mode, budget, controller)
  │
  ▼
coordination      S2    the harness — arbitrates the triad below
  │
  ├─ intelligence S4    the reasoner
  ├─ operation    S1    the action (tool, effect)
  │                     and uses cross-link the action axis to world resources:
  │                         use[of="file#..."]
  │                         use[of="network#..."]
  │                         use[of="exec#..."]
```

Authority flows inward. Operations flow upward (reports go through audit; S2 reports to S3; S3 reports to S5; audit sees everything directly).

The S3↔S4 inversion relative to Beer is deliberate and worth naming: in bounded delegation the regulator dominates the regulated. Coordination and control *constrain* the inferencer; the inferencer doesn't resolve tension with S3 as a peer. This is the architectural move that makes the specified band coherent — the delegate is a system whose own S4 is bounded by an externally-imposed S3.

---

## 3. `use[of=...]` — the action-axis permission primitive

The core insight: **permissions don't live on resources, they live on uses of resources.**

A `file` in world just *is*. Whether a delegate can edit it depends on whether the delegate holds an editable `use` of it. Same file, different modes, different permissions — the file doesn't change; the uses do. This matches OS capability theory (process holds fd, permissions on the fd, not the inode) and HTTP (resource has a URI; permissions on the request, not the URI).

### Syntax

```css
/* world axis — existence only */
file#/src/auth.py           { language: python; size: 2048; }
exec#bash                   { path: "/bin/bash"; }

/* action axis — permissions via use */
use[of="file#/src/auth.py"] { editable: true; visible: true; show: outline; }
use[of="exec#bash"]         { allow: true; }

/* cross-axis: specific use in a specific context */
mode.implement use[of-like="file#/src/**/*.py"] { editable: true; }
inferencer#opus tool[name="Edit"] use[of="file#/src/auth.py"] { editable: true; }
```

### §3a — World-axis permissions vs action-axis permissions

**Critical distinction:** these are two independent concepts, not two surface syntaxes for the same thing.

Think of it as the OS-level distinction between a **read-only mount** and a **user's file-permission bits**:

- A file mounted read-only → no user can write regardless of their permissions. That's a **world-axis** property of the resource itself.
- A user without write permission on a mounted-writable file → this user cannot write, others might. That's an **action-axis** property of an access path.

A successful write requires **both**: the resource must be editable (world-axis) AND the delegate must hold an editable use (action-axis).

#### Both axes carry permission properties — with different meanings

| Property | World axis (property-of-resource) | Action axis (property-of-access) |
|---|---|---|
| `editable` | `file.editable` / `dir.editable` — "the resource itself is editable (not read-only at mount/inode level)" | `use.editable` — "this access path grants edit rights" |
| `visible` | `file.visible` / `dir.visible` — "the resource is visible in the workspace" | `use.visible` — "this access path reveals the resource" |
| `show` | `file.show` — "what projection of the resource is materialized (body / outline / signature)" | `use.show` — "what the delegate sees through this access" |
| `allow` / `deny` | `tool.allow` / `network.deny` — "this capability is available in the world" | `use.allow` / `use.deny` — "the delegate can invoke this capability through this access" |
| `allow-pattern` / `deny-pattern` | `tool.allow-pattern` — "what invocations exist" | `use.allow-pattern` — "what invocations this access path permits" |

Both axes remain registered in v0.5. Both are first-class. Neither desugars to the other.

#### Compiler altitude mapping (no change in v0.5)

- **nsjail** (OS altitude) reads world-axis properties. Mount-level rw/ro for `file.editable`, `mount.readonly`. This is correct — nsjail enforces resource-nature, not per-delegate access.
- **bwrap** (OS altitude) same.
- **lackpy-namespace** (language altitude) will read action-axis properties in v0.6+. Tool-level `use.allow` gates what the delegate can invoke. This is correct — language altitude enforces per-delegate access.
- **kibitzer-hooks** (semantic altitude, v0.6) mixes: path-writability per mode is world-axis (`file.editable` + mode scope); per-tool gating is action-axis (`use[of=tool#X].allow`).

#### Properties that are exclusively on one axis

| Property | Entity | Why exclusive |
|---|---|---|
| `path`, `name`, `size`, `language` | `file` (world) | Identity, not permission. |
| `source`, `type`, `readonly` (mount-level) | `mount` (world) | Host-level mount config. |
| `host`, `port`, `kind` | `network` (world) | Endpoint identity. |
| `limit` | `resource` (world) | Absolute world-level cap. |
| `of`, `of-kind`, `of-like` | `use` (action) | Link back into the world axis. |

### The `of=` attribute

`of=` takes a selector string pointing into the world axis. Supported forms:

```css
use[of="file#/src/auth.py"]              /* exact file by ID */
use[of="file:glob('src/**/*.py')"]       /* glob within of= */
use[of-like="file#/src"]                 /* prefix-like match */
use[of-kind="file"]                      /* kind-scoped: all file uses */
use[of-kind="network"]                   /* all network uses */
```

Parsing `of=` produces a nested selector that evaluates against the same world entities the outer view describes. `use[of="file#/foo"]` is *not* cross-reference resolution; it's a nested selector match against world-axis entities.

### Defaults

The default behavior depends on which axis is being queried. A view without any `use` rules means no action-axis permissions are declared; the world-axis permissions on `file`, `tool`, etc. still apply through their own cascade. The full-access decision conjoins both axes.

Views can mix both styles idiomatically:

```css
/* world-axis: this file is read-only at the resource level */
file[path="/etc/secrets.conf"] { editable: false; visible: false; }

/* action-axis: the delegate's access path has these permissions */
use { visible: true; editable: false; }                           /* default deny-edit */
mode.implement use[of-like="file#/src"] { editable: true; }       /* mode grants edit on src */
```

Both declarations are active. A write to `/etc/secrets.conf` fails at the world-axis check even if the mode's use rule would otherwise grant edit.

---

## 4. `audit` outside the world

Beer's S3\* channel bypasses normal reporting — the auditor sees S1 directly without going through S2/S3. If that's the architectural claim, `audit` cannot be *inside* the world it audits.

Structurally:

```css
@audit {
  observation#coach { source: "kibitzer"; }
  observation#ratchet { source: "ratchet-detect"; }
  manifest#current { path: ".umwelt/manifest.json"; }
}

principal#Teague { intent: "code review"; }
world#sandbox-123 { /* ... */ }
```

`@audit { ... }` is an at-rule scope. Entries inside it:

- Are parsed into the view AST as audit-axis nodes.
- Are not subject to world-scoped context qualifiers.
- Can be selected from outside world selectors: `audit observation#coach { enabled: true; }` matches regardless of which world is active.

In v0.5 the audit taxon is registered and the at-rule parses, but no audit compiler ships. The audit entries are the contract for v0.7's observation compiler.

---

## 5. Mode as a class, not an ID

CSS semantics:

- `#foo` — ID selector. Unique per document. Specificity 100.
- `.foo` — class selector. Repeatable, compositional. Specificity 10.

Modes are compositional (an actor can be in `.testing.strict`), repeat across worlds (same `.testing` class applies in dev and staging), and don't uniquely identify a document element. They're classes.

```css
mode.testing                { /* every mode with the testing class */ }
mode.testing.strict         { /* narrower: both classes present */ }
world#dev mode.testing      { /* testing mode, dev world context */ }
```

This lets a single view declare multiple modes that can stack:

```css
mode.implement { /* base implement mode */ }
mode.implement.tdd { /* implement + tdd-flavor */ }
mode.explore { writable: "none"; }
```

At runtime, the active mode-set determines which rules apply. The kibitzer-hooks compiler (v0.6) will emit one `[modes.<name>]` block per distinct class it finds, with permissions conjoined via their class intersection.

---

## 6. Cross-axis cascade

Selector specificity in CSS is `(ids, classes+attrs+pseudos, elements)`. The current umwelt cascade accumulates specificity within a selector but the selector's structure is (implicitly) single-axis.

With axes explicit, specificity needs to count contributions from each axis a selector touches:

```
specificity = (
  axis_count,           # how many axes the selector names
  principal_ids,
  world_ids + world_classes + world_attrs,
  control_ids + control_classes + control_attrs,
  coordination_ids + coordination_classes + coordination_attrs,
  intelligence_ids + intelligence_classes + intelligence_attrs,
  operation_ids + operation_classes + operation_attrs,
  audit_ids + audit_classes + audit_attrs,
  use_ids + use_attrs,
)
```

Tuple comparison left-to-right. `axis_count` first means "a selector that touches more axes is more specific" — a rule that conjoins (inferencer, tool, use) beats a rule that names just one axis.

Example ordering (highest to lowest specificity):

1. `inferencer#opus tool[name=Edit] use[of="file#/src/auth.py"] { editable: true }` — 3 axes, ID on each.
2. `mode.implement use[of-like="file#/src/**/*.py"] { editable: true }` — 2 axes, class + attr.
3. `use[of="file#/src/auth.py"] { editable: true }` — 1 axis, ID.
4. `use { editable: true }` — 1 axis, bare element.

### Why axis_count first

Without `axis_count` primacy, a single-axis rule with many attribute filters could outrank a cross-axis rule with few filters. That's wrong for our semantics — cross-axis rules are *more contextualized* and should win. A rule that says "in implement mode, for Bash tool, use this file is editable" is specifically about that triple; a rule that says "this file is editable" is a blanket statement. The triple must win.

### Compatibility

Existing single-axis views produce the same cascade order as v0.4 because `axis_count=1` for every rule — the new field is uniform across legacy views and doesn't reorder them. Only views that *introduce* cross-axis selectors benefit from the new ordering.

---

## 7. The full DOM — worked example

The user's end-to-end example, annotated:

```css
principal#Teague
  world#sandbox-123:has(file#/foo.txt)
  mode.testing
  harness#claude-code
  inferencer#opus-46
  tool#Bash
  exec#sed
  use[of="file#/foo.txt"]
  { editable: true; }
```

Reading left-to-right, axis by axis:

| Selector | Axis | System | Reading |
|---|---|---|---|
| `principal#Teague` | principal | S5 | "commissioned by Teague" |
| `world#sandbox-123:has(file#/foo.txt)` | world | S0 | "in a sandbox that contains /foo.txt" |
| `mode.testing` | control | S3 | "with testing mode active" |
| `harness#claude-code` | coordination | S2 | "under claude-code harness" |
| `inferencer#opus-46` | intelligence | S4 | "using Opus 4.6" |
| `tool#Bash` | operation | S1 | "via the Bash tool" |
| `exec#sed` | world | S0 | "dispatching to sed" |
| `use[of="file#/foo.txt"]` | action-link | — | "the use of /foo.txt" |
| `{ editable: true; }` | — | — | declaration |

Eight axis-crossings. The combinator is one descendant-combinator throughout; the *meaning* of each crossing is emergent from which axes it joins. `principal→world` reads "running in"; `tool→exec` reads "dispatches to"; `exec→use` reads "operates on." One syntax, many readings, no new combinators.

This is the same overload CSS already accepts: `.sidebar a` means either "a link that happens to be inside sidebar" or "a link styled by sidebar context," depending on which the stylesheet author cares about. The DOM doesn't encode the reading; the reader resolves it from which axes are being crossed.

---

## 8. The `principal` taxon in v0.5 — minimal shape

Adding S5 to the DOM doesn't require full principal modeling. v0.5 ships:

```css
principal[name="..."]?     /* attribute */
principal#<id>              /* ID selector */

principal#Teague {
  intent: "code review";
  grade: 2;                 /* optional, per Ma grade lattice */
}
```

With two properties:

- `intent: str` — free-form description of why this delegate was commissioned. Consumed by audit and by human review. Compilers in v0.5 ignore it.
- `grade: int` — optional Ma-grade label (0–4). Compilers ignore it in v0.5; the audit compiler (v0.7) will consume it.

The principal appears in selectors as the outermost qualifier. If no `principal` appears, rules apply across all principals (legacy behavior).

Full principal modeling (multiple principals, delegation lineage, capability-inheritance rules) is v1.1+.

---

## 9. Migration path

This is an **additive restructuring**. World-axis properties (`file.editable`, `tool.allow`, etc.) remain registered and functional. The action-axis is new and independent. No legacy-shim is needed — existing v0.4 views keep working because their rules still populate the world-axis entities and properties they always did.

### What changes

- New taxa (`principal`, `audit`) and new taxon-aliases (`operation`, `coordination`, `control`, `intelligence`) are registered.
- New `use` entity registered in the operation axis. `use[of=...]` selectors produce `UseEntity` instances during resolve.
- Cross-axis cascade specificity (§6) widens the specificity tuple. Single-axis v0.4 rules retain identical ordering (`axis_count=1` for all of them).

### What stays the same

- Every world-axis property registered in v0.4 (`file.editable`, `tool.allow`, `network.deny`, `mount.readonly`, etc.) remains registered and carries its same meaning.
- `file { editable: true; }` is a first-class way to express resource-level permission and is not desugared.
- All three compilers (nsjail, bwrap, lackpy-namespace) continue reading world-axis properties and produce byte-identical output for every v0.4 fixture. Task 6 in the plan adds snapshot tests to guard this.

### Vision-doc updates

`docs/vision/entity-model.md` updated (not replaced) to document both axes.
`docs/guide/entity-reference.md` regenerated with the new `use`, `principal`, `observation`, `manifest` entries.
A new `docs/vision/notes/vsm-alignment.md` captures the Beer mapping and the S3↔S4 inversion justification.
`docs/vision/notes/logic-semantics.md` clarifies that world-axis and action-axis permissions are independent predicates.

### Compiler compatibility (no v0.5 changes)

In v0.5, all three existing compilers continue reading the same entity types and properties they did in v0.4. The `use` entity is populated but unread. v0.6 compiler work will decide which axes each compiler should read from (see §3a altitude mapping).

### Test migration

The existing 490-test suite passes unchanged (v0.4-shape rules still populate world-axis entries via existing matchers). New tests under `tests/registry/`, `tests/sandbox/`, and `tests/cascade/` cover:

- Taxon-alias transparency.
- Use-based permission cascade (action-axis).
- Cross-axis specificity ordering.
- Principal / audit taxa parse and resolve.
- Byte-compat snapshots against v0.4 fixtures.

---

## 10. Vertical slices

v0.5 decomposes into five slices, each a buildable, testable, shippable unit. Each leaves the suite green.

### Slice A — Taxa registration (land first)

- Register new VSM taxon aliases (`operation`, `coordination`, `control`, `intelligence`) alongside existing `capability`/`state`/`actor`; aliases are transparent across all registry submodules.
- Register `use` entity under the `operation` taxon (world entities are linked via the `of=` attribute, not by re-parenting).
- All existing tests continue to pass because world-axis registrations are untouched.

### Slice B — `use[of=...]` as first-class entity

- Register `use` with properties `editable`, `visible`, `show`, `allow`, `deny`, `allow-pattern`, `deny-pattern`.
- Implement `of=` attribute parsing (selector-valued, nested match).
- Implement `of-like=` and `of-kind=` forms.
- No compiler changes in v0.5 — they continue reading world-axis as before.
- Snapshot tests confirm byte-identical output for all v0.4 fixtures.

### Slice C — Cross-axis cascade

- Extend `Specificity` to carry per-axis counts.
- Rewrite `cmp_specificity` to do the axis_count-first tuple comparison.
- Add ~15 tests covering cross-axis ordering, tie-breaks within an axis, and `axis_count` primacy.

### Slice D — Audit and principal taxa

- Register `principal` with `name`, `intent`, `grade`.
- Register `audit` with `observation`, `manifest` entities.
- Parse `@audit { ... }` at-rule into audit-axis nodes.
- No compiler changes (audit compiler is v0.7).
- Tests: parse + cascade over principal and audit; verify compilers ignore them without error.

### Slice E — Documentation + release

- Regenerate `docs/guide/entity-reference.md` from the new registry.
- Replace `docs/vision/entity-model.md`; preserve v0.4 as historical.
- Add `docs/vision/notes/vsm-alignment.md`.
- Update CHANGELOG.
- Tag `v0.5.0`.

Sequence: A → B → C → D → E. A-B-C can be parallelized across sub-agents if desired; D depends on A; E depends on all.

---

## 11. Open questions resolved

| Question | Resolution |
|---|---|
| Where does `mode` live? | S3 control. Class selector, not ID. |
| Is audit inside or outside the world? | Outside. Architectural S3\* bypass. |
| Do resources live in world or under coordination? | World. `use` projects them into the action axis. |
| What name for the action-link entity? | `use` (with `of=` attribute). Considered `handle`, `ref`; `use` wins because permissions are on *usage*, and SVG precedent exists. |
| Do modes compose? | Yes — `mode.implement.tdd` is legal; kibitzer compiler derives distinct mode blocks from class sets. |
| Does audit_count primacy break existing cascades? | No — every legacy rule has `axis_count=1`, uniform comparison. |
| Is the kibitzer-hooks compiler in v0.5? | No — moved to v0.6 so v0.5 can land the restructure cleanly. The v0.6 compiler is ~1 slice of work once v0.5 lands. |
| Are the `security pass` and `public API freeze` in v0.5? | No — deferred to v0.6 / v0.7. v0.5 is the restructure milestone. |
| Do exec entities move with world? | Yes — exec is S0, a world-side binding (a binary that exists in the environment). `tool` stays S1 (the verb), but dispatches via `exec` which lives in world. |
| Does `policy` remain a taxon? | No — removed. A view *is* policy; policy isn't one of its parts. |

---

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Ambiguity between world-axis and action-axis permissions confuses authors. | §3a explicitly documents the distinction with the mount-vs-user-permission analogy. Entity-reference doc cross-references both axes. Error messages name the axis where a property was declared. |
| Cross-axis specificity surprises existing view authors. | `axis_count=1` for every legacy rule → no reordering. Document the rule prominently. |
| `use[of=...]` nested selector parsing adds parser complexity. | Reuse the existing selector parser; `of=` value is parsed by re-entering the same parser. Small, localized change. |
| The VSM framing adds cognitive load for users who don't know Beer. | Docs lead with concrete examples first, theory second. VSM becomes an organizing principle behind the scenes, not a prerequisite for users. |
| v0.5 is too large as a single milestone. | Decomposed into five slices. Each slice is independently testable and shippable — we can tag and release at any intermediate point. |

---

## 13. What comes after v0.5

The roadmap clarifies with v0.5 as foundation:

- **v0.6 — kibitzer-hooks compiler + S3\* audit compiler hints.** Now a small, clean compiler because S3 modes and S2 hooks live in dedicated taxa.
- **v0.7 — observation consumer + full audit compiler.** blq and ratchet-detect output consumed as audit entries.
- **v0.8 — security pass.** Parser hardening, fuzz tests, threat model. Rests on the post-restructure API.
- **v0.9 — public API freeze.** `__all__` explicit, deprecation policy, API-stability commitments.
- **v1.0 — PyPI publish.**

Each now slots onto a DOM that already has the right shape for it.

---

## 14. Approval gate

After approval, `writing-plans` produces `docs/superpowers/plans/2026-04-13-umwelt-v05.md` sequenced by the five slices in §10. The plan contains task-by-task test specifications, file-by-file change lists, and CHANGELOG entries.
