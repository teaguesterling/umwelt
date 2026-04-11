"""Parse a tinycss2 prelude token list into a tuple of `ComplexSelector`.

Task 9 handles single-part compound selectors: type, id, class, attribute,
pseudo-class. Task 12 adds combinators (descendant, child, sibling).
"""

from __future__ import annotations

from typing import Any

from umwelt.ast import (
    AttrFilter,
    AttrOp,
    ComplexSelector,
    CompoundPart,
    PseudoClass,
    SimpleSelector,
    SourceSpan,
)
from umwelt.errors import ViewParseError

# Placeholder taxon — Task 15 resolves type names against the registry.
UNRESOLVED_TAXON = "__unresolved__"


def parse_selector_list(
    tokens: list[Any], source_path: Any = None
) -> tuple[ComplexSelector, ...]:
    """Parse a tinycss2 token list into a tuple of ComplexSelector.

    The token list is the `prelude` of a qualified rule. Commas separate
    selectors in a union; each resulting ComplexSelector is a union member.
    """
    groups = _split_on_commas(tokens)
    selectors: list[ComplexSelector] = []
    for group in groups:
        sel = _parse_complex(group, source_path)
        if sel is not None:
            selectors.append(sel)
    if not selectors:
        # An empty selector list is a syntactic error; require at least one.
        raise ViewParseError(
            "empty selector", line=1, col=1, source_path=source_path
        )
    return tuple(selectors)


def _split_on_commas(tokens: list[Any]) -> list[list[Any]]:
    groups: list[list[Any]] = [[]]
    for t in tokens:
        if _is_literal(t, ","):
            groups.append([])
        else:
            groups[-1].append(t)
    return [g for g in groups if _non_whitespace(g)]


def _non_whitespace(tokens: list[Any]) -> bool:
    return any(getattr(t, "type", None) != "whitespace" for t in tokens)


def _parse_complex(tokens: list[Any], source_path: Any) -> ComplexSelector | None:
    """Task 9 form: one compound part with no combinators."""
    compound = _parse_simple(tokens, source_path)
    if compound is None:
        return None
    part = CompoundPart(selector=compound, combinator="root", mode="root")
    return ComplexSelector(
        parts=(part,),
        target_taxon=compound.taxon,
        specificity=(0, 0, 0),  # Task 15 computes this properly.
    )


def _parse_simple(tokens: list[Any], source_path: Any) -> SimpleSelector | None:
    """Walk a token list for one simple selector.

    Recognizes (in order): type name, id (#...), classes (.a), attributes
    ([...]), pseudo-classes (:...). Stops at whitespace (Task 9 has no
    combinators).

    Note: dotted id values (e.g. #README.md) are handled by consuming
    literal(".") + ident tokens that immediately follow a hash token as
    part of the id value, since umwelt supports filename-style ids.
    """
    # Strip leading/trailing whitespace at the compound boundary.
    tokens = _strip_whitespace(tokens)
    if not tokens:
        return None

    type_name: str | None = None
    id_value: str | None = None
    classes: list[str] = []
    attributes: list[AttrFilter] = []
    pseudo_classes: list[PseudoClass] = []

    span = _first_span(tokens)
    i = 0
    while i < len(tokens):
        t = tokens[i]
        ttype = getattr(t, "type", None)

        if ttype == "whitespace":
            # In Task 9, interior whitespace terminates the compound. We'll
            # handle combinators in Task 12; for now, require no interior
            # whitespace.
            raise ViewParseError(
                "unexpected whitespace inside simple selector",
                line=int(getattr(t, "source_line", 1) or 1),
                col=int(getattr(t, "source_column", 1) or 1),
                source_path=source_path,
            )

        if ttype == "ident" and type_name is None and not classes and not attributes and not pseudo_classes and id_value is None:
            type_name = t.value
            i += 1
            continue

        if _is_literal(t, "*") and type_name is None:
            type_name = "*"
            i += 1
            continue

        if ttype == "hash":
            if id_value is not None:
                raise ViewParseError(
                    "selector already has an id",
                    line=int(getattr(t, "source_line", 1) or 1),
                    col=int(getattr(t, "source_column", 1) or 1),
                    source_path=source_path,
                )
            # Collect the base hash value.
            raw_id = t.value
            i += 1
            # Consume any immediately-following .ident pairs as part of the
            # id value — this supports filename-style ids like #README.md.
            while (
                i < len(tokens)
                and _is_literal(tokens[i], ".")
                and i + 1 < len(tokens)
                and getattr(tokens[i + 1], "type", None) == "ident"
            ):
                raw_id = raw_id + "." + tokens[i + 1].value
                i += 2
            id_value = raw_id
            continue

        if _is_literal(t, "."):
            # .class — the next token should be an ident
            if i + 1 >= len(tokens):
                raise ViewParseError(
                    "expected class name after '.'",
                    line=int(getattr(t, "source_line", 1) or 1),
                    col=int(getattr(t, "source_column", 1) or 1),
                    source_path=source_path,
                )
            nxt = tokens[i + 1]
            if getattr(nxt, "type", None) != "ident":
                raise ViewParseError(
                    "expected class name after '.'",
                    line=int(getattr(nxt, "source_line", 1) or 1),
                    col=int(getattr(nxt, "source_column", 1) or 1),
                    source_path=source_path,
                )
            classes.append(nxt.value)
            i += 2
            continue

        if ttype == "[] block":
            attributes.append(_parse_attribute_block(t, source_path))
            i += 1
            continue

        if _is_literal(t, ":"):
            # Pseudo-class; Task 12 expands the grammar. For Task 9, require
            # an ident after the colon and record the name (no arguments yet).
            if i + 1 >= len(tokens):
                raise ViewParseError(
                    "expected pseudo-class name after ':'",
                    line=int(getattr(t, "source_line", 1) or 1),
                    col=int(getattr(t, "source_column", 1) or 1),
                    source_path=source_path,
                )
            nxt = tokens[i + 1]
            if getattr(nxt, "type", None) == "function":
                pseudo_classes.append(
                    PseudoClass(name=nxt.lower_name, argument=_serialize_function_args(nxt))
                )
                i += 2
                continue
            if getattr(nxt, "type", None) == "ident":
                pseudo_classes.append(PseudoClass(name=nxt.value, argument=None))
                i += 2
                continue
            raise ViewParseError(
                "expected pseudo-class name",
                line=int(getattr(nxt, "source_line", 1) or 1),
                col=int(getattr(nxt, "source_column", 1) or 1),
                source_path=source_path,
            )

        raise ViewParseError(
            f"unexpected token in selector: {ttype!r}",
            line=int(getattr(t, "source_line", 1) or 1),
            col=int(getattr(t, "source_column", 1) or 1),
            source_path=source_path,
        )

    if type_name is None and id_value is None and not classes and not attributes and not pseudo_classes:
        return None

    return SimpleSelector(
        type_name=type_name,
        taxon=UNRESOLVED_TAXON,
        id_value=id_value,
        classes=tuple(classes),
        attributes=tuple(attributes),
        pseudo_classes=tuple(pseudo_classes),
        span=span,
    )


def _parse_attribute_block(block: Any, source_path: Any) -> AttrFilter:
    """Parse the contents of a tinycss2 `[...]` block."""
    inner = _strip_whitespace(list(getattr(block, "content", []) or []))
    if not inner:
        raise ViewParseError(
            "empty attribute selector",
            line=int(getattr(block, "source_line", 1) or 1),
            col=int(getattr(block, "source_column", 1) or 1),
            source_path=source_path,
        )

    name_tok = inner[0]
    if getattr(name_tok, "type", None) != "ident":
        raise ViewParseError(
            "attribute name must be an identifier",
            line=int(getattr(name_tok, "source_line", 1) or 1),
            col=int(getattr(name_tok, "source_column", 1) or 1),
            source_path=source_path,
        )
    name: str = name_tok.value

    # Just the name? Existence check.
    if len(inner) == 1:
        return AttrFilter(name=name, op=None, value=None)

    # Otherwise we expect an operator followed by a value.
    op_tokens = inner[1:]
    # tinycss2 emits compound operators like "^=" as a single "delim-like"
    # structure: a LiteralToken("^") followed by a LiteralToken("="). We
    # parse two-character ops manually.
    op, consumed = _parse_attr_op(op_tokens, source_path)
    value_tokens = op_tokens[consumed:]
    value = _parse_attr_value(value_tokens, source_path)
    return AttrFilter(name=name, op=op, value=value)


def _parse_attr_op(
    tokens: list[Any], source_path: Any
) -> tuple[AttrOp, int]:
    if not tokens:
        raise ViewParseError(
            "expected attribute operator",
            line=1,
            col=1,
            source_path=source_path,
        )
    first = tokens[0]
    # tinycss2 >= 1.2 emits compound operators as single LiteralTokens
    # (e.g. "^=" as one token with value "^=").
    val = getattr(first, "value", None)
    if val in ("=", "^=", "$=", "*=", "|=", "~=") and getattr(first, "type", None) == "literal":
        return (str(val), 1)  # type: ignore[return-value]
    # Fallback: two separate tokens (^, =) — older tinycss2 behaviour.
    if len(tokens) >= 2 and _is_literal(tokens[1], "="):
        if _is_literal(first, "^"):
            return ("^=", 2)
        if _is_literal(first, "$"):
            return ("$=", 2)
        if _is_literal(first, "*"):
            return ("*=", 2)
        if _is_literal(first, "|"):
            return ("|=", 2)
        if _is_literal(first, "~"):
            return ("~=", 2)
    raise ViewParseError(
        "unknown attribute operator",
        line=int(getattr(first, "source_line", 1) or 1),
        col=int(getattr(first, "source_column", 1) or 1),
        source_path=source_path,
    )


def _parse_attr_value(tokens: list[Any], source_path: Any) -> str:
    tokens = _strip_whitespace(tokens)
    if not tokens:
        raise ViewParseError(
            "expected attribute value",
            line=1,
            col=1,
            source_path=source_path,
        )
    t = tokens[0]
    ttype = getattr(t, "type", None)
    if ttype == "string":
        return str(t.value)
    if ttype == "ident":
        return str(t.value)
    raise ViewParseError(
        f"attribute value must be a string or identifier, got {ttype!r}",
        line=int(getattr(t, "source_line", 1) or 1),
        col=int(getattr(t, "source_column", 1) or 1),
        source_path=source_path,
    )


def _serialize_function_args(func: Any) -> str:
    """Serialize the arguments of a tinycss2 function token back to text."""
    import tinycss2

    return str(tinycss2.serialize(getattr(func, "arguments", []) or []).strip())


def _strip_whitespace(tokens: list[Any]) -> list[Any]:
    out = list(tokens)
    while out and getattr(out[0], "type", None) == "whitespace":
        out.pop(0)
    while out and getattr(out[-1], "type", None) == "whitespace":
        out.pop()
    return out


def _is_literal(token: Any, value: str) -> bool:
    return getattr(token, "type", None) == "literal" and getattr(token, "value", None) == value


def _first_span(tokens: list[Any]) -> SourceSpan:
    for t in tokens:
        if getattr(t, "type", None) != "whitespace":
            return SourceSpan(
                line=int(getattr(t, "source_line", 1) or 1),
                col=int(getattr(t, "source_column", 1) or 1),
            )
    return SourceSpan(line=1, col=1)
