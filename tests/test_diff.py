"""Tests for the umwelt diff utility."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from umwelt.ast import (
    ComplexSelector,
    CompoundPart,
    Declaration,
    RuleBlock,
    SimpleSelector,
    SourceSpan,
    View,
)
from umwelt.diff_util import diff_views, format_diff

_FIXTURES = Path(__file__).resolve().parents[1] / "src" / "umwelt" / "_fixtures"


# ── AST construction helpers ────────────────────────────────────────────────

def _span(line: int = 1) -> SourceSpan:
    return SourceSpan(line=line, col=1)


def _simple(type_name: str, taxon: str) -> SimpleSelector:
    return SimpleSelector(
        type_name=type_name,
        taxon=taxon,
        id_value=None,
        classes=(),
        attributes=(),
        pseudo_classes=(),
        span=_span(),
    )


def _part(selector: SimpleSelector) -> CompoundPart:
    return CompoundPart(selector=selector, combinator="root", mode="root")


def _complex(type_name: str, taxon: str) -> ComplexSelector:
    return ComplexSelector(
        parts=(_part(_simple(type_name, taxon)),),
        target_taxon=taxon,
        specificity=(0, 0, 1),
    )


def _decl(name: str, *values: str) -> Declaration:
    return Declaration(property_name=name, values=tuple(values), span=_span())


def _rule(sel: ComplexSelector, declarations: list[Declaration]) -> RuleBlock:
    return RuleBlock(
        selectors=(sel,),
        declarations=tuple(declarations),
        nested_blocks=(),
        span=_span(),
    )


def _view(*rules: RuleBlock) -> View:
    return View(
        rules=tuple(rules),
        unknown_at_rules=(),
        warnings=(),
        source_text="",
        source_path=None,
    )


# ── Unit tests ───────────────────────────────────────────────────────────────

def test_identical_views_empty_diff() -> None:
    sel = _complex("tool", "capability")
    rule = _rule(sel, [_decl("allow", "true")])
    view_a = _view(rule)
    view_b = _view(rule)
    diff = diff_views(view_a, view_b)
    assert diff.added == []
    assert diff.removed == []
    assert diff.changed == []
    assert diff.unchanged == 1


def test_added_rule() -> None:
    sel_id_a = ComplexSelector(
        parts=(_part(SimpleSelector(
            type_name="tool", taxon="capability", id_value="read",
            classes=(), attributes=(), pseudo_classes=(), span=_span(),
        )),),
        target_taxon="capability",
        specificity=(1, 0, 1),
    )
    sel_id_b = ComplexSelector(
        parts=(_part(SimpleSelector(
            type_name="tool", taxon="capability", id_value="grep",
            classes=(), attributes=(), pseudo_classes=(), span=_span(),
        )),),
        target_taxon="capability",
        specificity=(1, 0, 1),
    )
    rule_read = _rule(sel_id_a, [_decl("allow", "true")])
    rule_grep = _rule(sel_id_b, [_decl("allow", "true")])
    view_a = _view(rule_read)
    view_b = _view(rule_read, rule_grep)
    diff = diff_views(view_a, view_b)
    assert len(diff.added) == 1
    assert diff.removed == []
    assert diff.changed == []


def test_removed_rule() -> None:
    sel_id_a = ComplexSelector(
        parts=(_part(SimpleSelector(
            type_name="tool", taxon="capability", id_value="read",
            classes=(), attributes=(), pseudo_classes=(), span=_span(),
        )),),
        target_taxon="capability",
        specificity=(1, 0, 1),
    )
    sel_id_b = ComplexSelector(
        parts=(_part(SimpleSelector(
            type_name="tool", taxon="capability", id_value="grep",
            classes=(), attributes=(), pseudo_classes=(), span=_span(),
        )),),
        target_taxon="capability",
        specificity=(1, 0, 1),
    )
    rule_read = _rule(sel_id_a, [_decl("allow", "true")])
    rule_grep = _rule(sel_id_b, [_decl("allow", "true")])
    view_a = _view(rule_read, rule_grep)
    view_b = _view(rule_read)
    diff = diff_views(view_a, view_b)
    assert diff.added == []
    assert len(diff.removed) == 1
    assert diff.changed == []


def test_changed_declaration() -> None:
    sel = _complex("tool", "capability")
    rule_a = _rule(sel, [_decl("allow", "true")])
    rule_b = _rule(sel, [_decl("allow", "false")])
    diff = diff_views(_view(rule_a), _view(rule_b))
    assert diff.added == []
    assert diff.removed == []
    assert len(diff.changed) == 1
    assert diff.unchanged == 0


def test_mixed_changes() -> None:
    sel_a = ComplexSelector(
        parts=(_part(SimpleSelector(
            type_name="tool", taxon="capability", id_value="bash",
            classes=(), attributes=(), pseudo_classes=(), span=_span(),
        )),),
        target_taxon="capability",
        specificity=(1, 0, 1),
    )
    sel_b = ComplexSelector(
        parts=(_part(SimpleSelector(
            type_name="tool", taxon="capability", id_value="grep",
            classes=(), attributes=(), pseudo_classes=(), span=_span(),
        )),),
        target_taxon="capability",
        specificity=(1, 0, 1),
    )
    sel_shared = _complex("tool", "capability")
    rule_bash = _rule(sel_a, [_decl("allow", "false")])
    rule_grep = _rule(sel_b, [_decl("allow", "true")])
    rule_shared = _rule(sel_shared, [_decl("allow", "true")])
    view_a = _view(rule_shared, rule_bash)
    view_b = _view(rule_shared, rule_grep)
    diff = diff_views(view_a, view_b)
    assert len(diff.added) == 1
    assert len(diff.removed) == 1
    assert diff.unchanged == 1


def test_format_diff_identical() -> None:
    sel = _complex("tool", "capability")
    rule = _rule(sel, [_decl("allow", "true")])
    diff = diff_views(_view(rule), _view(rule))
    output = format_diff(diff)
    assert "No differences" in output
    assert "1" in output


def test_format_diff_shows_added() -> None:
    sel_a = ComplexSelector(
        parts=(_part(SimpleSelector(
            type_name="tool", taxon="capability", id_value="read",
            classes=(), attributes=(), pseudo_classes=(), span=_span(),
        )),),
        target_taxon="capability",
        specificity=(1, 0, 1),
    )
    sel_b = ComplexSelector(
        parts=(_part(SimpleSelector(
            type_name="tool", taxon="capability", id_value="grep",
            classes=(), attributes=(), pseudo_classes=(), span=_span(),
        )),),
        target_taxon="capability",
        specificity=(1, 0, 1),
    )
    rule_a = _rule(sel_a, [_decl("allow", "true")])
    rule_b = _rule(sel_b, [_decl("allow", "true")])
    diff = diff_views(_view(rule_a), _view(rule_a, rule_b))
    output = format_diff(diff)
    assert "+1 added" in output


def test_format_diff_shows_removed() -> None:
    sel_a = ComplexSelector(
        parts=(_part(SimpleSelector(
            type_name="tool", taxon="capability", id_value="read",
            classes=(), attributes=(), pseudo_classes=(), span=_span(),
        )),),
        target_taxon="capability",
        specificity=(1, 0, 1),
    )
    sel_b = ComplexSelector(
        parts=(_part(SimpleSelector(
            type_name="tool", taxon="capability", id_value="grep",
            classes=(), attributes=(), pseudo_classes=(), span=_span(),
        )),),
        target_taxon="capability",
        specificity=(1, 0, 1),
    )
    rule_a = _rule(sel_a, [_decl("allow", "true")])
    rule_b = _rule(sel_b, [_decl("allow", "true")])
    diff = diff_views(_view(rule_a, rule_b), _view(rule_a))
    output = format_diff(diff)
    assert "-1 removed" in output


# ── CLI subprocess tests ─────────────────────────────────────────────────────

def test_cli_diff_identical(tmp_path: Path) -> None:
    # Use the existing fixture which the CLI can parse (sandbox vocab is auto-loaded)
    a = _FIXTURES / "minimal.umw"
    result = subprocess.run(
        [sys.executable, "-m", "umwelt.cli", "diff", str(a), str(a)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "No differences" in result.stdout


def test_cli_diff_with_changes(tmp_path: Path) -> None:
    # Create two minimal valid views (file entity is in core vocabulary)
    a = tmp_path / "a.umw"
    b = tmp_path / "b.umw"
    a.write_text('file[path^="src/"] { editable: false; }')
    b.write_text('file[path^="src/"] { editable: true; }')
    result = subprocess.run(
        [sys.executable, "-m", "umwelt.cli", "diff", str(a), str(b)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "changed" in result.stdout
