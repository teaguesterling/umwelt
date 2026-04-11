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
from umwelt.registry import resolve_entity_type

# Placeholder taxon — kept for backward compat but no longer used in production path.
UNRESOLVED_TAXON = "__unresolved__"


def parse_selector_list(
    tokens: list[Any],
    source_path: Any = None,
    scope_taxon: str | None = None,
) -> tuple[ComplexSelector, ...]:
    """Parse a tinycss2 token list into a tuple of ComplexSelector.

    The token list is the `prelude` of a qualified rule. Commas separate
    selectors in a union; each resulting ComplexSelector is a union member.
    """
    groups = _split_on_commas(tokens)
    selectors: list[ComplexSelector] = []
    for group in groups:
        sel = _parse_complex(group, source_path, scope_taxon=scope_taxon)
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


def _parse_complex(
    tokens: list[Any], source_path: Any, scope_taxon: str | None = None
) -> ComplexSelector | None:
    """Parse a compound selector token list into a ComplexSelector."""
    tokens = _strip_whitespace(tokens)
    if not tokens:
        return None

    # Split on combinators into (combinator, simple-token-list) pairs.
    parts_raw: list[tuple[str, list[Any]]] = []
    current: list[Any] = []
    current_combinator: str = "root"
    pending_ws = False
    i = 0
    while i < len(tokens):
        t = tokens[i]
        ttype = getattr(t, "type", None)

        if ttype == "whitespace":
            # Whitespace might be a combinator (descendant) or just padding
            # around an explicit combinator. Record that we've seen whitespace
            # and let the next token decide.
            pending_ws = True
            i += 1
            continue

        if _is_literal(t, ">"):
            # Close the current part; start a new one with "child" combinator.
            if current:
                parts_raw.append((current_combinator, current))
            current = []
            current_combinator = "child"
            pending_ws = False
            i += 1
            continue

        if _is_literal(t, "+") or _is_literal(t, "~"):
            # Sibling combinators — parse but treat as "sibling"/"adjacent".
            # Not exercised in v0.1, but the grammar permits them.
            if current:
                parts_raw.append((current_combinator, current))
            current = []
            current_combinator = "adjacent" if _is_literal(t, "+") else "sibling"
            pending_ws = False
            i += 1
            continue

        if pending_ws and current:
            # Whitespace between tokens and we're mid-part, so the whitespace
            # is a descendant combinator. Close the current part.
            parts_raw.append((current_combinator, current))
            current = [t]
            current_combinator = "descendant"
            pending_ws = False
            i += 1
            continue

        current.append(t)
        pending_ws = False
        i += 1

    if current:
        parts_raw.append((current_combinator, current))

    if not parts_raw:
        return None

    parts: list[CompoundPart] = []
    for idx, (combinator, part_tokens) in enumerate(parts_raw):
        simple = _parse_simple(part_tokens, source_path, scope_taxon=scope_taxon)
        if simple is None:
            raise ViewParseError(
                "empty compound part in compound selector",
                line=1,
                col=1,
                source_path=source_path,
            )
        # First part always has combinator "root" regardless of what we
        # recorded (we seeded with "root" and never rewrite it).
        combinator_kind = "root" if idx == 0 else combinator
        parts.append(
            CompoundPart(
                selector=simple,
                combinator=combinator_kind,  # type: ignore[arg-type]
                mode="root" if idx == 0 else "structural",
            )
        )

    target_taxon = parts[-1].selector.taxon
    if target_taxon == "*":
        for p in reversed(parts):
            if p.selector.taxon != "*":
                target_taxon = p.selector.taxon
                break
    return ComplexSelector(
        parts=tuple(parts),
        target_taxon=target_taxon,
        specificity=(0, 0, 0),  # Task 16 computes this.
    )


def _parse_simple(
    tokens: list[Any],
    source_path: Any,
    scope_taxon: str | None = None,
) -> SimpleSelector | None:
    """Walk a token list for one simple selector.

    Recognizes (in order): type name, id (#...), classes (.a), attributes
    ([...]), pseudo-classes (:...).

    Note: dotted id values (e.g. #README.md) are handled by consuming
    literal(".") + ident tokens that immediately follow a hash token as
    part of the id value, since umwelt supports filename-style ids.
    """
    tokens = _strip_whitespace(tokens)
    if not tokens:
        return None

    explicit_taxon: str | None = None

    # Check for an ns|type prefix: IdentToken, LiteralToken("|"), IdentToken
    if (
        len(tokens) >= 3
        and getattr(tokens[0], "type", None) == "ident"
        and _is_literal(tokens[1], "|")
        and getattr(tokens[2], "type", None) == "ident"
    ):
        explicit_taxon = tokens[0].value
        tokens = tokens[2:]

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

    resolved_taxon = _resolve_taxon(
        type_name,
        tokens,
        source_path,
        explicit_taxon=explicit_taxon,
        scope_taxon=scope_taxon,
    )
    return SimpleSelector(
        type_name=type_name,
        taxon=resolved_taxon,
        id_value=id_value,
        classes=tuple(classes),
        attributes=tuple(attributes),
        pseudo_classes=tuple(pseudo_classes),
        span=span,
    )


def _resolve_taxon(
    type_name: str | None,
    tokens: list[Any],
    source_path: Any,
    explicit_taxon: str | None = None,
    scope_taxon: str | None = None,
) -> str:
    """Look up the entity type in the registry. Unique match wins.

    - None or "*": return the scope_taxon sentinel or "*".
    - explicit_taxon set: validate and return it.
    - Known, unique: return that taxon name.
    - Unknown: raise ViewParseError.
    - Ambiguous: use scope_taxon if set; otherwise raise.
    """
    from umwelt.errors import RegistryError
    from umwelt.registry import get_entity, get_taxon

    if type_name is None or type_name == "*":
        return scope_taxon or "*"

    if explicit_taxon is not None:
        # Verify the taxon exists.
        try:
            get_taxon(explicit_taxon)
        except RegistryError as exc:
            raise ViewParseError(
                f"unknown taxon {explicit_taxon!r}",
                line=1,
                col=1,
                source_path=source_path,
            ) from exc
        # Verify the entity exists inside that taxon.
        try:
            get_entity(explicit_taxon, type_name)
        except RegistryError as exc:
            raise ViewParseError(
                f"no entity {type_name!r} in taxon {explicit_taxon!r}",
                line=1,
                col=1,
                source_path=source_path,
            ) from exc
        return explicit_taxon

    taxa = resolve_entity_type(type_name)
    if not taxa:
        first_tok = next(
            (t for t in tokens if getattr(t, "type", None) != "whitespace"),
            None,
        )
        raise ViewParseError(
            f"unknown entity type {type_name!r}",
            line=int(getattr(first_tok, "source_line", 1) or 1) if first_tok else 1,
            col=int(getattr(first_tok, "source_column", 1) or 1) if first_tok else 1,
            source_path=source_path,
        )
    if len(taxa) == 1:
        return taxa[0]
    # Ambiguous. Check scope.
    if scope_taxon is not None and scope_taxon in taxa:
        return scope_taxon
    raise ViewParseError(
        f"ambiguous entity type {type_name!r}: registered in {sorted(taxa)}",
        line=1,
        col=1,
        source_path=source_path,
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
