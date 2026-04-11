"""Tests for CSS3 specificity computation."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.parser import parse
from umwelt.registry import registry_scope


def _spec(view, rule_idx: int = 0, sel_idx: int = 0):
    return view.rules[rule_idx].selectors[sel_idx].specificity


def test_bare_type_is_0_0_1():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { }")
    assert _spec(view) == (0, 0, 1)


def test_universal_selector_is_0_0_0():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("* { }")
    assert _spec(view) == (0, 0, 0)


def test_id_selector_is_1_0_0():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing#alpha { }")
    assert _spec(view) == (1, 0, 1)


def test_attribute_selector_is_0_1_1():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color="red"] { }')
    assert _spec(view) == (0, 1, 1)


def test_class_selector_is_0_1_1():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing.highlighted { }")
    assert _spec(view) == (0, 1, 1)


def test_pseudo_class_is_0_1_1():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing:glob("*.py") { }')
    assert _spec(view) == (0, 1, 1)


def test_descendant_accumulates():
    # thing widget -> (0,0,1) + (0,0,1) = (0,0,2)
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing widget { }")
    assert _spec(view) == (0, 0, 2)


def test_complex_compound_specificity():
    # thing#alpha[color="red"] widget.highlighted
    # left: (1,1,1)
    # right: (0,1,1)
    # total: (1,2,2)
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing#alpha[color="red"] widget.highlighted { }')
    assert _spec(view) == (1, 2, 2)


def test_cross_taxon_compound_accumulates_same():
    # The mode classification doesn't affect specificity — both parts
    # contribute their tuples regardless.
    with registry_scope():
        install_toy_taxonomy()
        view = parse('actor[role="admin"] thing#beta { }')
    assert _spec(view) == (1, 1, 2)


def test_multiple_selectors_each_get_specificity():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing, thing#alpha { }")
    assert view.rules[0].selectors[0].specificity == (0, 0, 1)
    assert view.rules[0].selectors[1].specificity == (1, 0, 1)
