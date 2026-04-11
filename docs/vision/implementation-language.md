# Implementation Language

*Should umwelt be Python, Rust with Python bindings, or something else? And if Python, should we hand-roll the parser or depend on tinycss2? This document works through both questions and proposes a decision.*

## The questions

The existing package-design.md assumes pure Python 3.10+ with stdlib-only parsing. Two questions have come up since:

1. **Should umwelt's core be written in Rust with bindings (pyo3) for Python consumers?** A Rust core would be faster, memory-safer, and able to support non-Python consumers directly.

2. **If we stay Python, should the parser be hand-rolled or use tinycss2?** The existing vision says hand-rolled. A recent conversation pointed out that tinycss2 exists and is the right tool for this shape of parsing work.

These questions are related. A Rust core obviates the tinycss2 question (we'd use a Rust CSS parser like cssparser or lightningcss). A Python core raises it. I'll work through the Rust question first, then the parser question conditional on the answer.

## Question 1: Rust vs Python

### Where Rust genuinely wins

1. **Parsing and lexing speed.** A hand-rolled Rust parser processing a view file is ~10-100x faster than a Python equivalent. For small view files (the common case), this is negligible; for a hypothetical future where umwelt evaluates thousands of views per second, it matters.

2. **File system operations.** The workspace builder does a lot of glob walking, file reading, content hashing, and symlink/copy operations. Rust's std::fs and rayon for parallelism are significantly faster than Python's pathlib + hashlib for large workspaces.

3. **Cross-language bindings.** If umwelt ever needs to be called from Node.js, Go, Ruby, or a shell without Python installed, a Rust core with bindings (pyo3, napi, cgo) is the only path that avoids reimplementing the core in each language.

4. **Deterministic performance.** Rust has more predictable performance characteristics. On the critical path of every delegate invocation, that predictability has value.

5. **Memory safety at the sandbox-definition layer.** There's a philosophical argument that the code defining and enforcing sandboxes should itself be written in the most bulletproof language available. Rust notably wins here over Python's interpreted, garbage-collected model — not because Python is insecure, but because Rust's guarantees are stronger.

6. **Shipping as a standalone binary.** `umwelt` as a CLI that users can `cargo install` or download a static binary for is a much better distribution story than `pip install umwelt` for non-Python users.

### Where Rust costs more than it saves

1. **Development velocity.** Rust is ~2-3x slower to write than Python for the kind of work umwelt does (parsing, filesystem I/O, subprocess invocation, data transformation). For an experimental project whose design is still evolving, this is real cost. Every iteration on the grammar, every new compiler, every API shape change is more expensive.

2. **Contribution barrier.** The pool of developers who can contribute to a Rust+Python hybrid is much smaller than the pool who can contribute to pure Python. For a tool that wants adoption and ecosystem growth, this matters.

3. **Packaging and distribution.** Rust wheels require maturin or setuptools-rust, cross-platform builds (Linux x86_64, Linux aarch64, macOS x86_64, macOS arm64, Windows x86_64, plus musl variants), CI infrastructure per target, and careful handling of ABI compatibility. A pure Python package has none of this — one sdist and one universal wheel.

4. **The bottleneck isn't CPU.** For realistic workloads, umwelt's time is dominated by:
   - Subprocess spawning for hook dispatch (I/O)
   - File reads and writes for workspace construction (I/O)
   - Waiting for the delegate to finish (blocking on network or subprocess)
   - Parsing a single view file (~100 lines, trivial in any language)
   
   None of these are CPU-bound. Rust does not help with any of them. The parser speedup is real but in absolute terms it's the difference between 10ms and 0.1ms for a typical view file. We can't spend that time anywhere useful.

5. **tinycss2 is already fast enough.** A Python CSS parser backed by tinycss2 parses view files in single-digit milliseconds. The CPU cost of the parser is invisible in any realistic workflow.

6. **No concrete non-Python consumer.** The consumers we know about (lackpy, kibitzer, pluckit, Claude Code plugins) are all Python. Until someone actually wants to call umwelt from Node or Go, cross-language bindings are speculative complexity. YAGNI applies.

7. **Python is where the sandbox ecosystem already is.** nsjail-python, bwrap-python (if it existed), lackpy, pluckit, kibitzer — all Python. The integration work is with Python libraries and Python type systems. A Rust core would still need a Python wrapper for every concrete consumer, which means maintaining both.

8. **The complexity is in semantics, not computation.** The hardest parts of umwelt are:
   - Write-back semantics under concurrent modification (how to detect and handle conflicts)
   - Hook dispatch with timeout, cleanup, and error propagation
   - Compiler correctness for each enforcement target (getting nsjail textproto right, getting bwrap argv right, etc.)
   - The workspace lifecycle as a context manager with proper cleanup on exceptional exit
   
   None of these are easier in Rust. If anything, Python's exception handling and context manager idioms make the orchestration code simpler than Rust's Result-plumbing equivalent.

### The inversion test

Suppose umwelt existed as a Rust core with Python bindings. What would we lose?

- Every change to the core requires recompiling (minutes, not seconds) and rebuilding wheels for every target platform
- Contributors need to know Rust, pyo3's conventions, and Python packaging
- Any bug in the Rust-Python boundary (reference counting, lifetimes, exception translation) is harder to diagnose than a bug in pure Python
- Iterating on the compiler protocol or adding a new compiler target requires round-trips through FFI
- The README starts with "First, install a Rust toolchain" for anyone who wants to contribute

What would we gain?

- Faster parsing (invisible in practice)
- Faster filesystem ops (invisible in practice because the bottleneck is elsewhere)
- A distribution story for non-Python users (who don't currently exist)
- A memory-safety argument (marginal — Python is already memory-safe against the kinds of bugs that matter here; the unsafe surface is the subprocess boundary, which Rust doesn't help with)

The tradeoff is asymmetric: we'd pay certain, substantial development cost for speculative, mostly theoretical benefits.

### The design principle that matters more

The question of "Rust or Python" isn't as important as the principle underneath it: **umwelt's internal architecture should be decomposed cleanly enough that a later port to Rust — if ever needed — is mechanical rather than a rewrite.**

Concretely, this means:

- Parser is a pure function: `text → View AST`. No side effects. Testable in isolation. A Rust replacement swaps in behind the same interface.
- Compilers are pure functions: `View → native format`. No side effects. No dependencies on the runtime. A Rust replacement swaps in behind the same protocol.
- Workspace operations are I/O and should stay in whatever language the orchestration lives in. They're not a port candidate regardless.
- Hook dispatch is subprocess invocation. Same.

If the parser ever becomes a bottleneck (it won't, but hypothetically), we can port just the parser to Rust in v2 without touching anything else. The rest of the package stays Python forever.

### Recommendation

**Start in Python 3.10+. Keep the architecture port-ready at the parser and compiler layers. Revisit if and only if a concrete performance or cross-language requirement emerges.**

This is not "Rust is bad." Rust is excellent for the class of problems where its benefits dominate. It's that umwelt's bottleneck profile, current consumer set, and dev-velocity needs all point away from Rust for v1. The right time to consider Rust is when one of these is true:

- A measurable performance problem in the parser or compiler (not hypothesized; measured)
- A concrete non-Python consumer requesting bindings
- A security audit finding that depends on memory safety of the parser
- A distribution problem that requires a static binary

None of those are true today. They may be true in 18 months. If so, we port the parser + compilers to Rust in a v2 effort, while the orchestration layer stays Python.

## Question 2: Hand-rolled parser vs tinycss2

Conditional on the Python answer above, there's a sub-question: should the parser be hand-rolled (as the existing package-design.md specifies) or use tinycss2?

### What each choice gets us

**Hand-rolled:**
- Zero runtime dependencies beyond stdlib — the strongest form of "leaf dependency"
- Full control over error messages (line/column reporting, context-aware hints)
- Full control over behavior in edge cases
- Smaller wheel and install footprint
- ~400 lines of parser + lexer code to write, test, and maintain

**tinycss2:**
- Single small dependency (~2KB wheel, BSD-licensed, actively maintained by the WeasyPrint folks)
- CSS-3 tokenization including string escapes, numbers with units, comments, nested blocks — all the parts of CSS parsing that are easy to get subtly wrong
- At-rule prelude/block separation for free
- Well-tested over years of production use in WeasyPrint and other tools
- ~150 lines of glue code instead of ~400 lines of hand-rolled parser

### The tension

The existing package-design.md is emphatic about zero runtime dependencies:

> **Runtime (required):** Python 3.10+, stdlib only

That's a stance. It makes umwelt a strict leaf-dependency package. No supply-chain surface area beyond the Python interpreter. Users never hit "I wanted to install umwelt and it pulled in five other things."

But a recent conversation pushed the opposite direction:

> Why are we not using sitting_duck or tinycss?

The argument was that hand-rolling a CSS tokenizer reimplements something that's already done well, and the parts of CSS parsing we'd hand-roll (string escape handling, numeric unit tokenization, comment stripping) are precisely the parts where hand-rolled code accumulates bugs.

Both positions are legitimate. The question is which tradeoff we prefer: supply-chain purity vs. leveraging a well-tested library.

### Recommendation

I'd take tinycss2 as a required runtime dependency, for three reasons:

1. **It's a single, small, stable dependency.** tinycss2 has 25+ releases over a decade, a BSD-3 license, and a clean scope (it does CSS-3 tokenization, nothing more). Adding it is substantially different from adding "a dependency" in the abstract. It's not pulling in numpy.

2. **The parsing cliff edge is the most bug-prone part of the code.** String escape handling in CSS values, multi-character unit parsing, comment-in-declaration-value handling — all of these are places where hand-rolled parsers accumulate edge-case bugs. tinycss2 has already solved them.

3. **The "zero dependencies" goal is doing less work than it looks.** The existing package-design.md lists "stdlib only" but also specifies optional dependencies on `nsjail-python` and `pluckit`. Once any optional dependency exists, the "zero dependencies" purity argument weakens — users installing umwelt for nsjail integration are already pulling in non-stdlib code. Adding tinycss2 as a required dependency is a smaller delta than it looks.

**Counter-option:** If "stdlib only" is a principled commitment worth keeping, hand-roll the parser. It's not a small amount of work but it's bounded and the grammar is narrow enough to be tractable. The argument for purity is legitimate even if I think tinycss2 is the better tradeoff.

My recommendation is tinycss2, but this is a decision where the person maintaining the package should choose based on their own preference about dependency purity. Both options produce a working parser; the choice is about philosophy, not correctness.

### An important constraint regardless of the answer

**The parser must be isolated behind a narrow interface.** `umwelt.parser.parse(text: str) -> View` is the only public entry point. Nothing downstream of the parser imports tinycss2 (if we use it) or touches the tokenizer internals (if we hand-roll). This way, the decision can be revisited later without rippling through the codebase. Whichever choice we make in v1, we keep the escape hatch open.

## Summary of the recommendation

**Implementation language:** Python 3.10+. Keep the parser and compiler layers decomposed as pure functions so a future port to Rust (if needed) is scoped to those modules, not the whole package.

**Parser dependency:** tinycss2 as a required runtime dependency. One small, well-tested, stable library saves ~250 lines of bug-prone hand-rolled code and eliminates a class of edge cases we'd otherwise need to test for. If the "zero dependencies" commitment is non-negotiable, hand-roll the parser behind the same isolated interface.

**Rust port criteria:** defer unless one of these becomes true — measured parser performance problem, concrete non-Python consumer, security audit finding requiring memory-safe parsing, or a distribution problem requiring a static binary.

**What this means for v1:** the first commit proceeds in Python with tinycss2 (or hand-rolled, depending on the call). The architecture in package-design.md is otherwise unchanged. The "port-ready decomposition" principle doesn't add work — it just means we keep the parser and compilers as pure functions, which is already the design.

## Open follow-ups

1. **Is the "stdlib only" commitment in package-design.md a hard constraint, or was it a preference at time of writing?** If hard, ignore this doc's tinycss2 recommendation and hand-roll. If soft, the recommendation stands.

2. **Is there a known non-Python consumer on the roadmap?** If yes, the Rust question becomes more concrete. If no, the question stays theoretical.

3. **Does the "port-ready decomposition" principle belong in package-design.md as a design constraint?** It's not a big change — the existing architecture already satisfies it — but making it explicit would help future contributors understand why the parser and compilers are structured as pure functions.

4. **Should v2 planning include a "measure first, port second" rule?** I.e., before any Rust work, there must be a benchmarking artifact showing the current Python implementation is insufficient for a specific workload. This prevents speculative rewrites and keeps the decision anchored in evidence.
