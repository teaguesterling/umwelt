# Compilers

*The compiler layer is umwelt's translation surface: it takes a parsed `View` and emits whatever native configuration format each enforcement target already accepts. This document is the compiler taxonomy and registry. Individual compilers have their own detail docs in this directory. For the framing of why compilers are the translation boundary, see [`../policy-layer.md`](../policy-layer.md) — umwelt is the common language of the specified band, and compilers are how each enforcement tool reads it.*

## Where compilers live

**Core umwelt ships zero concrete compilers.** `umwelt.compilers` defines the `Compiler` protocol and the registry; concrete compilers live in consumers. The first-party sandbox consumer (`umwelt.sandbox.compilers.*`) ships nsjail, bwrap, lackpy-namespace, and kibitzer-hooks as its first-class targets. Third-party consumers register their own compilers via the same API — `register_compiler("<name>", CompilerImpl())` at import time — and become available to `umwelt compile --target <name>` without any modification to core umwelt.

This split is load-bearing: it's what lets umwelt be *vocabulary-agnostic* at the core. A consumer that registers a non-sandbox taxonomy (e.g., an access-control domain) can provide its own compilers against its own entities without waiting for core umwelt to learn about its vocabulary.

## What a compiler does

A compiler is a pure function: `ResolvedView → target-native-format`. It reads an umwelt AST after cascade resolution and produces text (or structured data) that a specific enforcement tool can consume directly. Compilers:

- **Never import the target tool's Python wrapper at runtime.** The compiler targets the tool's *native* config format — textproto for nsjail, argv for bwrap, YAML for kubernetes, sbatch for slurm, etc. umwelt stays a leaf dependency.
- **Declare their altitude.** Each compiler carries an `altitude` attribute: `os`, `language`, `semantic`, or `conversational`. The altitude determines which cross-taxon context qualifiers the compiler can realize (see [`../entity-model.md`](../entity-model.md) §4.3). An OS-altitude compiler like nsjail has no concept of "acting tool" — rules qualified by `tool[name="Bash"]` context are outside its altitude and are dropped silently.
- **Silently drop rules they can't realize.** Unknown taxa, out-of-altitude context qualifiers, and pattern properties whose targets don't support runtime matching are all dropped rather than raising errors. This is the composition model: one view, multiple compilers, each realizing what its target can enforce. The `dry-run` and `check` utilities report per-target which rules were realized. A rule that no compiler can realize is still a valid view (it documents intent) — it's just declarative-only at every currently-registered altitude.
- **Are pure transformations.** Same `ResolvedView` in, same output out. No side effects. No filesystem access. No network calls. The compiler's job is translation, not execution. (Runners handle execution; see `../package-design.md`.)
- **Register themselves** via `umwelt.compilers.register("<name>", compiler_impl)` at consumer import time. The CLI dispatches to the registered compiler by name.

See [`../package-design.md`](../package-design.md#the-compiler-protocol) for the `Compiler` protocol definition and [`../entity-model.md`](../entity-model.md) §4.3 for the cascade-target + altitude-filtering semantics.

## Taxonomy: locality and enforcement semantics

The existing compilers (nsjail, bwrap) are **local OS sandboxes** — they wrap a process on a single host with kernel-level isolation, and the delegate runs right there. Future compilers split along two axes:

### Axis 1: Locality (local vs remote)

| Locality | Meaning | Implications |
|---|---|---|
| **Local** | Delegate runs on the same machine as umwelt | Write-back and `@after-change` hooks can run synchronously after the delegate finishes. `@budget` maps to rlimits / cgroups on the local kernel. |
| **Remote** | Delegate runs on a different machine via a scheduler or API | Write-back requires shared filesystem or explicit stage-in/stage-out. `@after-change` hooks must be expressed as dependent jobs or post-hooks. `@budget` is usually a resource *request* to the scheduler, not direct enforcement. |

### Axis 2: Execution model (synchronous vs asynchronous)

| Model | Meaning | Implications |
|---|---|---|
| **Synchronous** | umwelt's `run_in_X` blocks until the delegate finishes | Familiar API. Caller gets the result directly. Suitable for interactive and CI workflows. |
| **Asynchronous** | umwelt submits a job and returns a handle | Needed for schedulers (slurm, kubernetes Jobs). Caller polls, waits, or listens for completion separately. Runners expose both modes (`run_*_sync` and `run_*_async`) where relevant. |

### The grid

|  | Synchronous | Asynchronous |
|---|---|---|
| **Local** | nsjail, bwrap, firejail, podman-foreground, docker-foreground | docker-detach, podman-detach |
| **Remote (container)** | apptainer (typically runs inside slurm; sync within that scope) | kubernetes Job, AWS Batch |
| **Remote (scheduler)** | — *(rare; sync remote execution usually means SSH, which umwelt doesn't target directly)* | slurm (`sbatch`), kubernetes Job, nomad, lsf |

The grid shows that most "remote" compilers are also "async" — the network hop usually forces a job-queue model. The one interesting exception is apptainer, which is typically invoked *inside* a slurm job, making it sync-within-the-enclosing-context. apptainer composes well with slurm: a single view can compile to both a slurm submission script and the apptainer invocation that script runs.

## Implemented and documented

Compilers with full design docs in this directory. Implementation may still be pending, but the design is pinned down.

| Compiler | Target format | Altitude | Locality | Status | Doc |
|---|---|---|---|---|---|
| `nsjail` | protobuf textproto | OS | local | design complete | [`nsjail.md`](./nsjail.md) |
| `bwrap` | argv list | OS | local | design complete | [`bwrap.md`](./bwrap.md) |

## Planned compilers

Targets that are in scope for umwelt but don't yet have design docs. Each one is a concrete compiler target worth writing a spec for when the time comes.

### Local OS sandboxes

| Compiler | Target format | Status | Notes |
|---|---|---|---|
| `docker` | `docker run` argv (or Dockerfile fragment) | planned | Most common container runtime. Requires daemon. Maps cleanly to `@source` (bind mounts), `@network` (`--network none`), `@budget` (`--memory`, `--cpus`), `@env` (`-e`). |
| `podman` | `podman run` argv | planned | Docker-compatible CLI, rootless by default. Compiler likely ≈85% shared with docker; could be a mode switch rather than a separate file. |
| `apptainer` | `apptainer exec` argv | planned | HPC-friendly container runtime (formerly Singularity). No daemon, user-namespace-based. Often invoked inside slurm jobs; composes with the slurm compiler. |
| `firejail` | argv | low priority | Desktop Linux sandbox, widely installed but less featureful than bwrap or nsjail. May not be worth a dedicated compiler given bwrap already covers this niche. |
| `systemd-run --scope` | argv with unit properties | low priority | Uses systemd's resource control primitives. Available on any systemd-based Linux. Cheap to add if someone wants it. |

### Remote / scheduler targets

| Compiler | Target format | Status | Notes |
|---|---|---|---|
| `slurm` | sbatch script | planned | The HPC scheduler. `@source` → stage-in directives or shared-filesystem paths. `@budget` → `--mem`, `--time`, `--cpus-per-task`. `@after-change` → dependent jobs via `--dependency=afterok`. `@network` → partition selection or network isolation constraint. Async by nature. |
| `kubernetes` | Job or Pod YAML manifest | planned | Cloud-native orchestrator. `@source` → `volumes` + `volumeMounts`. `@budget` → `resources.limits`. `@network` → `networkPolicy`. `@env` → `env` list. `@after-change` → Job post-hooks or dependent Jobs. Requires cluster credentials at runner time. |
| `nomad` | HCL job spec | low priority | HashiCorp's scheduler. Similar in shape to slurm but with a different syntax. Straightforward to add if a user wants it. |
| `aws-batch` | submit-job JSON via AWS SDK | speculative | AWS-specific. Might be worth a compiler if umwelt is used in cloud batch workflows, but the authentication and API surface make it substantially more involved than the others. |

### Language and semantic altitude compilers

These target enforcement mechanisms that aren't OS sandboxes but still consume views. They're in scope because the sandbox tower has multiple altitudes and umwelt owns the spec layer for all of them.

| Compiler | Target format | Status | Notes |
|---|---|---|---|
| `lackpy-namespace` | Python dict (lackpy namespace config) | planned | Language altitude. Reads `@tools` and a future `@namespace` at-rule, emits a lackpy namespace/tool restriction config. |
| `kibitzer-hooks` | kibitzer rule dict | planned | Semantic altitude. Reads `@tools` (for hook-based enforcement of allow/deny during a Claude Code session) and emits a kibitzer rule configuration. |

### Conversational altitude

| Compiler | Target format | Status | Notes |
|---|---|---|---|
| `delegate-context` | prompt fragment | v1.1 committed | The view-transparency compiler (the [SELinux coda](../policy-layer.md#the-selinux-coda-and-view-transparency) from the policy-layer framing). Walks a resolved view, pulls descriptions from the registered plugin metadata, and emits a prompt fragment the delegate can read to model its own constraints. Consumes description fields from every taxon / entity / property registration. The governed actor sees its own bounds rather than learning them empirically. Load-bearing for the Ma framework's "transparent specification" principle. |
| `retrieval-prompt` | prompt fragment + example selection | speculative | Reads a future `@retrieval` or `@context` at-rule and emits a prompt-composition directive for the delegate's harness. Distinct from `delegate-context` — retrieval-prompt is about *what* to put in the delegate's context (examples, history), `delegate-context` is about *describing the bounds* the delegate operates under. Speculative until we have a concrete consumer. |

## Protocol variations: how local and remote compilers differ

The basic `Compiler` protocol is `View → target-native-format`, but the grid above introduces complications that need small protocol extensions without breaking the core abstraction.

### Write-back semantics

- **Local compilers** assume the workspace builder creates virtual files on the local filesystem, the delegate modifies them in place, and umwelt's write-back layer splices changes back after the delegate exits. The compiler itself doesn't know or care about this — its output is just the jail/sandbox config.
- **Remote compilers** need to encode stage-in and stage-out. The workspace builder runs locally, but the delegate runs on a remote host, so the files must travel somehow. Two strategies:
  1. **Shared filesystem**: the workspace root is on a shared mount (NFS, Lustre, EFS) accessible from both umwelt's host and the delegate's host. No stage-in needed; the compiler output just points at the shared path.
  2. **Explicit transfer**: the compiler output includes stage-in commands (`sbcast`, `kubectl cp`, container volume mounts from an object store) that materialize the workspace on the delegate's host, and stage-out commands that bring the result back.

The `run_in_*` runners handle the stage-in/stage-out dance; the compiler just emits a descriptor of what needs to move.

### `@after-change` hook dispatch

- **Local compilers**: hooks run synchronously in umwelt's process after the delegate exits and write-back completes. The hook dispatcher is the `umwelt.hooks` module.
- **Remote compilers**: hooks have two options:
  1. **Local post-hook**: umwelt waits for the remote job to finish, pulls results back, and runs hooks locally. Works for sync-ish scheduler usage where the caller blocks on completion.
  2. **Remote dependent job**: umwelt submits a follow-up job that runs the hooks on the scheduler itself, with a dependency on the main job's completion. Necessary for truly async workflows where the caller has already returned before the main job finishes.

The choice is per-runner, not per-compiler. A single slurm compiler output can drive either hook strategy depending on how the runner is invoked.

### `@budget` as request vs enforcement

- **Local compilers**: `@budget` maps to rlimits and timeouts that the kernel enforces strictly. The delegate gets killed at the wall-time limit. Period.
- **Remote compilers**: `@budget` is typically a *request* to the scheduler. The scheduler uses it for placement decisions and may kill the job at the requested time, but the semantics differ per scheduler (slurm kills at `--time`; kubernetes sets `activeDeadlineSeconds`; aws-batch has a job timeout). Documentation for each compiler must be explicit about whether the request is enforced strictly or loosely.

For views that want strict enforcement regardless of target, the runner can add a post-submission wrapper — e.g., slurm jobs can wrap the delegate in a `timeout` call that enforces wall-time even if the scheduler's own timer is lenient.

### Return value of compile-then-run

- **Local runners** return a `SubprocessResult` synchronously after the delegate exits.
- **Remote runners** offer two variants:
  - `run_*_sync(view, command)` → blocks until the remote job finishes, returns the final result
  - `run_*_async(view, command)` → submits the job, returns a `JobHandle` (opaque per-runner), caller polls or waits independently

All of this is on the *runner* side (`umwelt.runners.*`), not the compiler side. Compilers stay pure; runners handle the execution model.

## How to add a new compiler

The procedure, for anyone (human or agent) wanting to extend umwelt with a new target:

1. **Pick a host package for the compiler.** First-party sandbox compilers live under `src/umwelt/sandbox/compilers/<target>.py`. Third-party compilers live in their own package (e.g., `umwelt-kubernetes`, `blq-umwelt-compiler`) and are installed alongside umwelt. Core umwelt ships no concrete compilers.
2. **Write a design doc in this directory (or in the host package's own docs for third-party compilers).** Use [`nsjail.md`](./nsjail.md) or [`bwrap.md`](./bwrap.md) as a template. Include: declared altitude (`os` / `language` / `semantic` / `conversational`), scope (which entity types and properties the compiler realizes), mapping table (entity + property → target output), worked example (view file + expected output side-by-side), handling of out-of-altitude cross-taxon qualifiers (what the compiler drops), pattern-property realization (if any), testing strategy, open questions.
3. **Implement the compiler module.** Pure function `compile(view: ResolvedView) -> str | list[str] | dict`. The compiler reads the resolved view (post-cascade) and walks its target taxon's rules. No runtime dependency on the target tool's Python wrapper. Declare `target_name`, `target_format`, and `altitude` as class attributes. Register via `umwelt.compilers.register("<target>", CompilerInstance())` at import time.
4. **Implement a runner** (optional) if the runner shape differs from the local-subprocess default. First-party runners live under `src/umwelt/sandbox/runners/<target>.py`; third-party runners live alongside their compiler. For remote targets, expose both `run_<target>_sync` and `run_<target>_async` variants.
5. **Write fixtures** — 2–3 reference view files paired with expected `<target>` output in the host package's `_fixtures/expected/<target>/` directory.
6. **Write unit tests** for the mapping table and snapshot tests against the fixtures, including tests that show the compiler correctly dropping out-of-altitude context qualifiers and unrealized pattern properties.
7. **Write an integration test** (skipped if the target binary/endpoint isn't available) that runs a trivial delegate under the new target end-to-end.
8. **Update this index** (or the host package's own catalog) to move the compiler from "planned" to "implemented and documented."

The procedure is the same whether the target is local or remote, sync or async, first-party or third-party. The Compiler protocol and the plugin registry handle the differences behind the scenes.

## What compilers don't do

Explicit non-goals for the compiler layer, worth stating because they come up:

- **Compilers do not execute anything.** They produce configuration. Runners execute. Keeping execution out of compilers means compilers stay pure, deterministic, and testable without external dependencies.
- **Compilers do not validate that the target tool will actually accept their output.** The compiler emits what its spec says it should emit; runtime errors from the target (malformed textproto, unknown flag, missing image) surface through the runner layer, not the compiler. Optional integration tests exercise the round-trip.
- **Compilers do not hold state across calls.** Each `compile(view)` is independent. If the same view is compiled twice, the output is identical. (Exception: bwrap's `@env` reads `os.environ` at compile time, which is a known quirk documented in [`bwrap.md`](./bwrap.md).)
- **Compilers do not coordinate with each other.** A view can be compiled to multiple targets simultaneously (by calling multiple compilers), but the compilers don't know about each other's output. The caller composes them if needed.
- **Compilers do not authenticate or manage credentials.** For remote targets (slurm, kubernetes), credentials are the runner's problem. The compiler just emits the job specification; `kubectl apply` or `sbatch` is what actually submits, and that's a runner concern.
- **Compilers do not version-negotiate with the target tool.** If nsjail changes its protobuf schema in a way that breaks umwelt's output, that's a umwelt bug to fix in the compiler. Users pin a umwelt version that works with their target tool versions.

## Status of this document

This is a taxonomy / index / scaffolding doc. It enumerates the compiler design space without committing to individual design docs for every target yet. The implemented and documented compilers (nsjail, bwrap) are real; the planned ones are placeholders that record intent without locking in detail. When a planned compiler becomes a priority, someone writes its detail doc using the procedure in "How to add a new compiler" above, and updates the tables in this document accordingly.

Not every planned compiler will ship. The point of listing them is to establish that the umwelt format is intended to be multi-target, to make the design space legible, and to prevent accidental assumptions that "umwelt is an nsjail tool" or "umwelt is a bwrap tool" from creeping in. umwelt is a view compiler; the targets are whatever the sandbox tower contains.
