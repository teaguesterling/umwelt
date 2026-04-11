"""Top-level view parser.

Uses `tinycss2` for CSS tokenization; walks its output into the umwelt AST.
Selector-string parsing lives in `umwelt.selector.parse`; this module is the
orchestrator that recognizes rule blocks vs. at-rules, extracts source
positions, and produces the final `View`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tinycss2

from umwelt.ast import (
    Declaration,
    ParseWarning,
    RuleBlock,
    SourceSpan,
    UnknownAtRule,
    View,
)
from umwelt.errors import RegistryError, ViewParseError
from umwelt.registry import get_taxon
from umwelt.selector.parse import parse_selector_list

# tinycss2's ParseError node doesn't expose a typed class we can isinstance-check
# cleanly across versions, so we sniff by attribute instead.


def parse(source: str | Path, *, validate: bool = True) -> View:
    """Parse a view from text or a file path into a `View` AST.

    Args:
        source: Either a string containing view text, or a `Path` to a view file.
        validate: Whether to run the registered validators after parsing. v0.1
            defers validator implementation to Task 18; the flag is plumbed now.

    Returns:
        A `View` with rules, preserved unknown at-rules, and warnings.

    Raises:
        ViewParseError: On any syntactic error, with line and column.
    """
    if isinstance(source, Path):
        text = source.read_text()
        source_path: Path | None = source
    else:
        text = source
        source_path = None

    nodes = tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True)

    rules: list[RuleBlock] = []
    unknown_at_rules: list[UnknownAtRule] = []
    warnings: list[ParseWarning] = []

    for node in nodes:
        if _is_parse_error(node):
            raise _parse_error_to_view_error(node, source_path)
        node_type = getattr(node, "type", None)
        if node_type == "qualified-rule":
            rule = _build_rule_block(node, warnings, source_path=source_path)
            if rule is not None:
                rules.append(rule)
        elif node_type == "at-rule":
            at_name: str = str(
                getattr(node, "lower_at_keyword", None)
                or getattr(node, "at_keyword", "")
                or ""
            )
            if _is_taxon_scope(at_name):
                rules.extend(
                    _expand_taxon_scope(node, warnings, source_path, at_name)
                )
            else:
                unknown_at_rules.append(_build_unknown_at_rule(node))
        # tinycss2 with skip_whitespace=True shouldn't yield bare whitespace here.

    view = View(
        rules=tuple(rules),
        unknown_at_rules=tuple(unknown_at_rules),
        warnings=tuple(warnings),
        source_text=text,
        source_path=source_path,
    )
    if validate:
        from umwelt.validate import validate as run_validators

        view = run_validators(view)
    return view


def _is_parse_error(node: Any) -> bool:
    return getattr(node, "type", None) == "error"


def _parse_error_to_view_error(
    node: Any, source_path: Path | None
) -> ViewParseError:
    message = getattr(node, "message", "parse error")
    line = int(getattr(node, "source_line", 1) or 1)
    col = int(getattr(node, "source_column", 1) or 1)
    return ViewParseError(
        message, line=line, col=col, source_path=source_path
    )


def _span(node: Any) -> SourceSpan:
    line = int(getattr(node, "source_line", 1) or 1)
    col = int(getattr(node, "source_column", 1) or 1)
    return SourceSpan(line=line, col=col)


def _build_rule_block(
    node: Any,
    warnings: list[ParseWarning],
    source_path: Path | None = None,
    scope_taxon: str | None = None,
) -> RuleBlock | None:
    prelude = list(getattr(node, "prelude", []) or [])
    content = list(getattr(node, "content", []) or [])
    selectors = parse_selector_list(
        prelude, source_path=source_path, scope_taxon=scope_taxon
    )
    declarations = _parse_declarations(content, source_path, warnings)
    return RuleBlock(
        selectors=selectors,
        declarations=declarations,
        nested_blocks=(),
        span=_span(node),
    )


def _is_taxon_scope(at_name: str) -> bool:
    try:
        get_taxon(at_name)
        return True
    except RegistryError:
        return False


def _expand_taxon_scope(
    node: Any,
    warnings: list[ParseWarning],
    source_path: Path | None,
    scope_taxon: str,
) -> list[RuleBlock]:
    """Parse the contents of an @<taxon> block as a fresh rule list.

    Inner selectors are parsed with `scope_taxon` set so bare entity names
    that are ambiguous across taxa resolve against the scope first.
    """
    inner_rules: list[RuleBlock] = []
    content = getattr(node, "content", None)
    if content is None:
        return inner_rules
    # Re-parse the block content as a stylesheet fragment.
    inner_nodes = tinycss2.parse_rule_list(
        list(content), skip_comments=True, skip_whitespace=True
    )
    for inner in inner_nodes:
        if _is_parse_error(inner):
            raise _parse_error_to_view_error(inner, source_path)
        if getattr(inner, "type", None) != "qualified-rule":
            continue
        rule = _build_rule_block(
            inner, warnings, source_path=source_path, scope_taxon=scope_taxon
        )
        if rule is not None:
            inner_rules.append(rule)
    return inner_rules


def _parse_declarations(
    content: list[Any],
    source_path: Path | None,
    warnings: list[ParseWarning],
) -> tuple[Declaration, ...]:
    """Parse the content of a qualified-rule block into Declaration tuples."""
    if not content:
        return ()
    decl_nodes = tinycss2.parse_declaration_list(
        content, skip_comments=True, skip_whitespace=True
    )
    out: list[Declaration] = []
    seen: dict[str, SourceSpan] = {}
    for node in decl_nodes:
        if _is_parse_error(node):
            raise _parse_error_to_view_error(node, source_path)
        node_type = getattr(node, "type", None)
        if node_type != "declaration":
            # At-rules inside declaration blocks are preserved as unknown
            # but v0.1 doesn't expose them through the RuleBlock; skip for now.
            continue
        name: str = str(getattr(node, "lower_name", None) or getattr(node, "name", ""))
        values = _split_declaration_values(
            list(getattr(node, "value", []) or [])
        )
        span = _span(node)
        if name in seen:
            warnings.append(
                ParseWarning(
                    message=f"duplicate declaration key {name!r}",
                    span=span,
                )
            )
        else:
            seen[name] = span
        out.append(
            Declaration(
                property_name=name,
                values=tuple(values),
                span=span,
            )
        )
    return tuple(out)


def _split_declaration_values(tokens: list[Any]) -> list[str]:
    """Split a declaration value token list on commas and serialize each part."""
    groups: list[list[Any]] = [[]]
    for t in tokens:
        if _is_literal(t, ","):
            groups.append([])
        else:
            groups[-1].append(t)
    result: list[str] = []
    for g in groups:
        text = str(tinycss2.serialize(g).strip())
        if text:
            result.append(_unquote(text))
    return result


def _unquote(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _is_literal(token: Any, value: str) -> bool:
    return (
        getattr(token, "type", None) == "literal"
        and getattr(token, "value", None) == value
    )


def _build_unknown_at_rule(node: Any) -> UnknownAtRule:
    name: str = str(
        getattr(node, "lower_at_keyword", None) or getattr(node, "at_keyword", "")
    )
    prelude = tinycss2.serialize(getattr(node, "prelude", []) or [])
    block = ""
    content = getattr(node, "content", None)
    if content is not None:
        block = tinycss2.serialize(content)
    return UnknownAtRule(
        name=name,
        prelude_text=prelude,
        block_text=block,
        span=_span(node),
    )
