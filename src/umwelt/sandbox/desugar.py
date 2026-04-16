"""At-rule sugar desugaring for the sandbox consumer.

Registers transformers for legacy at-rules with the core parser's
sugar registry. Each transformer takes a tinycss2 at-rule node and
returns a list of RuleBlock in entity-selector form.

Call register_sandbox_sugar() once per registry scope (or call it from
register_sandbox_vocabulary() so both happen together).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tinycss2

from umwelt.ast import ComplexSelector, Declaration, RuleBlock, SourceSpan
from umwelt.parser import register_sugar
from umwelt.selector.parse import parse_selector_list

_SPAN = SourceSpan(line=1, col=1)


def register_sandbox_sugar() -> None:
    """Register all sandbox at-rule transformers with the parser."""
    register_sugar("source", _desugar_source)
    register_sugar("tools", _desugar_tools)
    register_sugar("after-change", _desugar_after_change)
    register_sugar("network", _desugar_network)
    register_sugar("budget", _desugar_budget)
    register_sugar("env", _desugar_env)
    register_sugar("audit", _desugar_audit)


# ---------------------------------------------------------------------------
# @source("path") { * { editable: true; } }
# → file:glob("path") { editable: true; }   (if path has glob chars)
# → file[path^="path/"] { editable: true; } (if path is a plain prefix)
# ---------------------------------------------------------------------------

def _desugar_source(
    node: Any,
    warnings: list[Any],
    source_path: Path | None,
) -> list[RuleBlock]:
    path_str = _extract_source_path(node)
    if path_str is None:
        return []

    # Collect declarations from nested `* { ... }` blocks inside the at-rule.
    declarations = _collect_source_declarations(node, warnings, source_path)
    if not declarations:
        return []

    # Build selector text based on whether path contains glob chars.
    glob_chars = {"*", "?", "["}
    if any(c in path_str for c in glob_chars):
        sel_text = f'file:glob("{path_str}")'
    else:
        # Prefix match: add trailing slash if it looks like a directory.
        prefix = path_str.rstrip("/") + "/"
        sel_text = f'file[path^="{prefix}"]'

    selectors = _parse_sel(sel_text, source_path)
    return [RuleBlock(
        selectors=selectors,
        declarations=declarations,
        nested_blocks=(),
        span=_span(node),
    )]


def _extract_source_path(node: Any) -> str | None:
    """Extract the path string from @source(...) prelude."""
    prelude = list(getattr(node, "prelude", []) or [])
    for tok in prelude:
        # The path is inside a parentheses block.
        if getattr(tok, "type", None) == "() block":
            inner = _strip_ws(list(getattr(tok, "content", []) or []))
            if inner:
                first = inner[0]
                if getattr(first, "type", None) == "string":
                    return str(first.value)
                if getattr(first, "type", None) == "ident":
                    return str(first.value)
    return None


def _collect_source_declarations(
    node: Any,
    warnings: list[Any],
    source_path: Path | None,
) -> tuple[Declaration, ...]:
    """Walk the @source content for nested `* { ... }` rules and collect their declarations."""
    content = list(getattr(node, "content", []) or [])
    if not content:
        return ()

    # Re-parse content as a rule list to find qualified-rule nodes.
    inner_nodes = tinycss2.parse_rule_list(
        content, skip_comments=True, skip_whitespace=True
    )
    all_decls: list[Declaration] = []
    for inner in inner_nodes:
        if getattr(inner, "type", None) != "qualified-rule":
            continue
        # We accept any selector (typically `*`) — extract its declarations.
        block_content = list(getattr(inner, "content", []) or [])
        decl_nodes = tinycss2.parse_declaration_list(
            block_content, skip_comments=True, skip_whitespace=True
        )
        for d in decl_nodes:
            if getattr(d, "type", None) != "declaration":
                continue
            name = str(getattr(d, "lower_name", None) or getattr(d, "name", ""))
            values = _split_values(list(getattr(d, "value", []) or []))
            all_decls.append(Declaration(
                property_name=name,
                values=tuple(values),
                span=_span(d),
            ))
    return tuple(all_decls)


# ---------------------------------------------------------------------------
# @tools { allow: Read, Edit; deny: Bash; kit: python-dev; }
# → tool[name="Read"] { allow: true; }
# → tool[name="Edit"] { allow: true; }
# → tool[name="Bash"] { allow: false; }
# → kit[name="python-dev"] { allow: true; }
# ---------------------------------------------------------------------------

def _desugar_tools(
    node: Any,
    warnings: list[Any],
    source_path: Path | None,
) -> list[RuleBlock]:
    content = list(getattr(node, "content", []) or [])
    if not content:
        return []

    rules: list[RuleBlock] = []
    decl_nodes = tinycss2.parse_declaration_list(
        content, skip_comments=True, skip_whitespace=True
    )
    for d in decl_nodes:
        if getattr(d, "type", None) != "declaration":
            continue
        prop_name = str(getattr(d, "lower_name", None) or getattr(d, "name", ""))
        values = _split_values(list(getattr(d, "value", []) or []))

        if prop_name in ("allow", "deny"):
            allow_val = "true" if prop_name == "allow" else "false"
            for name in values:
                sel_text = f'tool[name="{name}"]'
                selectors = _parse_sel(sel_text, source_path)
                decl = Declaration(
                    property_name="allow",
                    values=(allow_val,),
                    span=_span(d),
                )
                rules.append(RuleBlock(
                    selectors=selectors,
                    declarations=(decl,),
                    nested_blocks=(),
                    span=_span(d),
                ))
        elif prop_name == "kit":
            for name in values:
                sel_text = f'kit[name="{name}"]'
                selectors = _parse_sel(sel_text, source_path)
                decl = Declaration(
                    property_name="allow",
                    values=("true",),
                    span=_span(d),
                )
                rules.append(RuleBlock(
                    selectors=selectors,
                    declarations=(decl,),
                    nested_blocks=(),
                    span=_span(d),
                ))
    return rules


# ---------------------------------------------------------------------------
# @after-change { test: pytest; lint: ruff; }
# → hook[event="after-change"] { run: "pytest"; run: "ruff"; }
# ---------------------------------------------------------------------------

def _desugar_after_change(
    node: Any,
    warnings: list[Any],
    source_path: Path | None,
) -> list[RuleBlock]:
    content = list(getattr(node, "content", []) or [])
    if not content:
        return []

    decl_nodes = tinycss2.parse_declaration_list(
        content, skip_comments=True, skip_whitespace=True
    )
    run_decls: list[Declaration] = []
    for d in decl_nodes:
        if getattr(d, "type", None) != "declaration":
            continue
        # Each declaration's value is the command to run.
        # `test: pytest tests/` → run: "pytest tests/"
        cmd = tinycss2.serialize(list(getattr(d, "value", []) or [])).strip()
        run_decls.append(Declaration(
            property_name="run",
            values=(cmd,),
            span=_span(d),
        ))

    if not run_decls:
        return []

    sel_text = 'hook[event="after-change"]'
    selectors = _parse_sel(sel_text, source_path)
    return [RuleBlock(
        selectors=selectors,
        declarations=tuple(run_decls),
        nested_blocks=(),
        span=_span(node),
    )]


# ---------------------------------------------------------------------------
# @network { deny: *; }
# → network { deny: "*"; }
# ---------------------------------------------------------------------------

def _desugar_network(
    node: Any,
    warnings: list[Any],
    source_path: Path | None,
) -> list[RuleBlock]:
    content = list(getattr(node, "content", []) or [])
    if not content:
        return []

    decl_nodes = tinycss2.parse_declaration_list(
        content, skip_comments=True, skip_whitespace=True
    )
    decls: list[Declaration] = []
    for d in decl_nodes:
        if getattr(d, "type", None) != "declaration":
            continue
        prop_name = str(getattr(d, "lower_name", None) or getattr(d, "name", ""))
        raw_val = tinycss2.serialize(list(getattr(d, "value", []) or [])).strip()
        decls.append(Declaration(
            property_name=prop_name,
            values=(raw_val,),
            span=_span(d),
        ))

    if not decls:
        return []

    selectors = _parse_sel("network", source_path)
    return [RuleBlock(
        selectors=selectors,
        declarations=tuple(decls),
        nested_blocks=(),
        span=_span(node),
    )]


# ---------------------------------------------------------------------------
# @budget { memory: 512MB; wall-time: 60s; }
# → resource[kind="memory"] { limit: 512MB; }
# → resource[kind="wall-time"] { limit: 60s; }
# ---------------------------------------------------------------------------

def _desugar_budget(
    node: Any,
    warnings: list[Any],
    source_path: Path | None,
) -> list[RuleBlock]:
    content = list(getattr(node, "content", []) or [])
    if not content:
        return []

    decl_nodes = tinycss2.parse_declaration_list(
        content, skip_comments=True, skip_whitespace=True
    )
    rules: list[RuleBlock] = []
    for d in decl_nodes:
        if getattr(d, "type", None) != "declaration":
            continue
        kind = str(getattr(d, "lower_name", None) or getattr(d, "name", ""))
        raw_val = tinycss2.serialize(list(getattr(d, "value", []) or [])).strip()

        sel_text = f'resource[kind="{kind}"]'
        selectors = _parse_sel(sel_text, source_path)
        decl = Declaration(
            property_name="limit",
            values=(raw_val,),
            span=_span(d),
        )
        rules.append(RuleBlock(
            selectors=selectors,
            declarations=(decl,),
            nested_blocks=(),
            span=_span(d),
        ))
    return rules


# ---------------------------------------------------------------------------
# @env { allow: CI, PYTHONPATH; deny: *; }
# → env[name="CI"] { allow: true; }
# → env[name="PYTHONPATH"] { allow: true; }
# → env { allow: false; }
# ---------------------------------------------------------------------------

def _desugar_env(
    node: Any,
    warnings: list[Any],
    source_path: Path | None,
) -> list[RuleBlock]:
    content = list(getattr(node, "content", []) or [])
    if not content:
        return []

    decl_nodes = tinycss2.parse_declaration_list(
        content, skip_comments=True, skip_whitespace=True
    )
    rules: list[RuleBlock] = []
    for d in decl_nodes:
        if getattr(d, "type", None) != "declaration":
            continue
        prop_name = str(getattr(d, "lower_name", None) or getattr(d, "name", ""))
        values = _split_values(list(getattr(d, "value", []) or []))

        if prop_name == "allow":
            for name in values:
                sel_text = f'env[name="{name}"]'
                selectors = _parse_sel(sel_text, source_path)
                decl = Declaration(
                    property_name="allow",
                    values=("true",),
                    span=_span(d),
                )
                rules.append(RuleBlock(
                    selectors=selectors,
                    declarations=(decl,),
                    nested_blocks=(),
                    span=_span(d),
                ))
        elif prop_name == "deny":
            # deny: * → env { allow: false; }  (broad deny without name attr)
            raw_val = tinycss2.serialize(list(getattr(d, "value", []) or [])).strip()
            if raw_val == "*":
                selectors = _parse_sel("env", source_path)
                decl = Declaration(
                    property_name="allow",
                    values=("false",),
                    span=_span(d),
                )
                rules.append(RuleBlock(
                    selectors=selectors,
                    declarations=(decl,),
                    nested_blocks=(),
                    span=_span(d),
                ))
    return rules


# ---------------------------------------------------------------------------
# @audit { observation#coach { source: "kibitzer"; } manifest#current { ... } }
# → the body's rules, passed through unchanged. Because observation and
# manifest entities are registered under the audit taxon, the selector
# parser automatically tags them with target_taxon="audit".
# ---------------------------------------------------------------------------

def _desugar_audit(
    node: Any,
    warnings: list[Any],
    source_path: Path | None,
) -> list[RuleBlock]:
    """Parse @audit body as regular rules; rules target the audit taxon automatically."""
    content = list(getattr(node, "content", []) or [])
    if not content:
        return []

    # Re-parse the @audit body as a rule list.
    inner_nodes = tinycss2.parse_rule_list(
        content, skip_comments=True, skip_whitespace=True
    )

    from umwelt.parser import _build_rule_block  # internal; same pattern as parser internals

    out: list[RuleBlock] = []
    for inner in inner_nodes:
        if getattr(inner, "type", None) != "qualified-rule":
            continue
        rb = _build_rule_block(inner, warnings, source_path=source_path)
        if rb is not None:
            out.append(rb)
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_sel(selector_text: str, source_path: Path | None) -> tuple[ComplexSelector, ...]:
    """Tokenize a selector text string and parse it into ComplexSelectors."""
    tokens = tinycss2.parse_component_value_list(selector_text)
    return parse_selector_list(tokens, source_path=source_path)


def _span(node: Any) -> SourceSpan:
    line = int(getattr(node, "source_line", 1) or 1)
    col = int(getattr(node, "source_column", 1) or 1)
    return SourceSpan(line=line, col=col)


def _strip_ws(tokens: list[Any]) -> list[Any]:
    out = list(tokens)
    while out and getattr(out[0], "type", None) == "whitespace":
        out.pop(0)
    while out and getattr(out[-1], "type", None) == "whitespace":
        out.pop()
    return out


def _split_values(tokens: list[Any]) -> list[str]:
    """Split declaration values on commas and strip whitespace."""
    groups: list[list[Any]] = [[]]
    for t in tokens:
        if getattr(t, "type", None) == "literal" and getattr(t, "value", None) == ",":
            groups.append([])
        else:
            groups[-1].append(t)
    result: list[str] = []
    for g in groups:
        text = tinycss2.serialize(g).strip()
        if text:
            result.append(text)
    return result
