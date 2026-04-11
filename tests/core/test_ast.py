"""Tests for the umwelt AST dataclasses."""

from __future__ import annotations

from pathlib import Path

import pytest

from umwelt.ast import (
    AttrFilter,
    ComplexSelector,
    CompoundPart,
    Declaration,
    ParseWarning,
    PseudoClass,
    SimpleSelector,
    SourceSpan,
    UnknownAtRule,
    View,
)


def test_source_span_is_frozen():
    span = SourceSpan(line=1, col=1)
    with pytest.raises((AttributeError, Exception)):  # dataclass frozen
        span.line = 2  # type: ignore[misc]


def test_simple_selector_basic():
    sel = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(AttrFilter(name="path", op="^=", value="src/"),),
        pseudo_classes=(),
        span=SourceSpan(line=1, col=1),
    )
    assert sel.type_name == "file"
    assert sel.taxon == "world"
    assert sel.attributes[0].name == "path"


def test_simple_selector_is_hashable():
    sel1 = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(),
        pseudo_classes=(),
        span=SourceSpan(line=1, col=1),
    )
    sel2 = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(),
        pseudo_classes=(),
        span=SourceSpan(line=1, col=1),
    )
    # Equality on frozen dataclasses is structural
    assert sel1 == sel2
    assert hash(sel1) == hash(sel2)
    # Can live in a set
    assert {sel1, sel2} == {sel1}


def test_compound_part_modes():
    simple = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(),
        pseudo_classes=(),
        span=SourceSpan(line=1, col=1),
    )
    part = CompoundPart(selector=simple, combinator="root", mode="root")
    assert part.mode == "root"
    assert part.combinator == "root"


def test_complex_selector_target_taxon_and_specificity():
    simple = SimpleSelector(
        type_name="file",
        taxon="world",
        id_value=None,
        classes=(),
        attributes=(AttrFilter(name="path", op="^=", value="src/"),),
        pseudo_classes=(),
        span=SourceSpan(line=1, col=1),
    )
    compound = ComplexSelector(
        parts=(CompoundPart(selector=simple, combinator="root", mode="root"),),
        target_taxon="world",
        specificity=(0, 1, 1),
    )
    assert compound.target_taxon == "world"
    assert compound.specificity == (0, 1, 1)


def test_declaration_multi_value():
    decl = Declaration(
        property_name="run",
        values=("pytest", "ruff check"),
        span=SourceSpan(line=3, col=5),
    )
    assert decl.property_name == "run"
    assert decl.values == ("pytest", "ruff check")


def test_view_construction():
    view = View(
        rules=(),
        unknown_at_rules=(),
        warnings=(),
        source_text="",
        source_path=None,
    )
    assert view.rules == ()
    assert view.source_path is None


def test_view_with_source_path():
    view = View(
        rules=(),
        unknown_at_rules=(),
        warnings=(),
        source_text="",
        source_path=Path("test.umw"),
    )
    assert view.source_path == Path("test.umw")


def test_unknown_at_rule_preserved():
    at = UnknownAtRule(
        name="retrieval",
        prelude_text="",
        block_text="context: last-3;",
        span=SourceSpan(line=1, col=1),
    )
    assert at.name == "retrieval"


def test_parse_warning():
    warn = ParseWarning(
        message="duplicate declaration key",
        span=SourceSpan(line=5, col=3),
    )
    assert "duplicate" in warn.message


def test_pseudo_class_with_argument():
    ps = PseudoClass(name="glob", argument="src/**/*.py")
    assert ps.name == "glob"
    assert ps.argument == "src/**/*.py"


def test_attr_filter_exists_form():
    # [path] — existence check, no op or value
    af = AttrFilter(name="path", op=None, value=None)
    assert af.name == "path"
    assert af.op is None
