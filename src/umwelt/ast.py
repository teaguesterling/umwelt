"""AST dataclasses for parsed umwelt views.

Everything is a frozen dataclass with tuple-typed sequence fields so the
AST is safely shareable and hashable. No methods beyond dataclass defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Combinator = Literal["root", "descendant", "child", "sibling", "adjacent"]
CombinatorMode = Literal["structural", "context", "root"]
AttrOp = Literal["=", "^=", "$=", "*=", "~=", "|="]


@dataclass(frozen=True)
class SourceSpan:
    """Line and column of an AST node in the source text."""

    line: int
    col: int


@dataclass(frozen=True)
class AttrFilter:
    """An attribute selector filter: [name], [name=value], [name^=value], ..."""

    name: str
    op: AttrOp | None
    value: str | None


@dataclass(frozen=True)
class PseudoClass:
    """A pseudo-class selector: :not(...), :glob(...), :has(...)."""

    name: str
    argument: str | None


@dataclass(frozen=True)
class SimpleSelector:
    """A single element in a selector chain.

    `taxon` is resolved at parse time by looking up `type_name` in the
    plugin registry. Compound selectors use this to classify each combinator
    as structural (same taxon) or context (different taxa).
    """

    type_name: str | None
    taxon: str
    id_value: str | None
    classes: tuple[str, ...]
    attributes: tuple[AttrFilter, ...]
    pseudo_classes: tuple[PseudoClass, ...]
    span: SourceSpan


@dataclass(frozen=True)
class CompoundPart:
    """One part of a compound selector.

    `combinator` is the CSS-style relationship to the previous part
    ("root" for the first part, "descendant"/"child"/etc. for the rest).
    `mode` is set at parse time by comparing the taxa on either side of
    the combinator: "structural" when they match, "context" when they
    differ, "root" for the leading part.
    """

    selector: SimpleSelector
    combinator: Combinator
    mode: CombinatorMode


@dataclass(frozen=True)
class ComplexSelector:
    """A compound selector with taxon-resolved target and specificity."""

    parts: tuple[CompoundPart, ...]
    target_taxon: str
    specificity: tuple[int, int, int]


@dataclass(frozen=True)
class Declaration:
    """A property declaration: `name: value;` or `name: v1, v2, v3;`."""

    property_name: str
    values: tuple[str, ...]
    span: SourceSpan


@dataclass(frozen=True)
class RuleBlock:
    """A selector list + its declaration block.

    `nested_blocks` is reserved for future CSS-style nesting support and
    is always empty in v0.1.
    """

    selectors: tuple[ComplexSelector, ...]
    declarations: tuple[Declaration, ...]
    nested_blocks: tuple[RuleBlock, ...]
    span: SourceSpan


@dataclass(frozen=True)
class UnknownAtRule:
    """An @-rule the parser didn't recognize. Preserved for forward compat."""

    name: str
    prelude_text: str
    block_text: str
    span: SourceSpan


@dataclass(frozen=True)
class ParseWarning:
    """A soft parser warning, attached to the View rather than raised."""

    message: str
    span: SourceSpan


@dataclass(frozen=True)
class View:
    """A parsed view: top-level rule blocks plus preserved unknown at-rules."""

    rules: tuple[RuleBlock, ...]
    unknown_at_rules: tuple[UnknownAtRule, ...]
    warnings: tuple[ParseWarning, ...]
    source_text: str
    source_path: Path | None
