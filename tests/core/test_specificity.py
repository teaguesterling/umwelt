"""Tests for CSS3 specificity computation.

v0.5: the specificity tuple is now axis_count-first. These tests verify
the ordering invariants (A2: well-ordered) rather than exact tuple values,
since the internal encoding changed. The ordering must remain:
  universal < bare-type < class/attr < id.

For cross-taxon compound selectors, the axis_count component (spec[0])
must be > 1 when multiple distinct taxa are present.
"""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.parser import parse
from umwelt.registry import registry_scope


def _spec(view, rule_idx: int = 0, sel_idx: int = 0):
    return view.rules[rule_idx].selectors[sel_idx].specificity


def test_bare_type_is_less_specific_than_id():
    with registry_scope():
        install_toy_taxonomy()
        bare = _spec(parse("thing { }"))
        with_id = _spec(parse("thing#alpha { }"))
    assert with_id > bare


def test_universal_selector_is_0_0_0():
    with registry_scope():
        install_toy_taxonomy()
        universal = _spec(parse("* { }"))
        bare = _spec(parse("thing { }"))
    # Universal is less specific than any typed selector.
    assert bare > universal
    # axis_count for universal is 0 (no type_name).
    assert universal[0] == 0


def test_id_selector_beats_bare_type():
    with registry_scope():
        install_toy_taxonomy()
        bare = _spec(parse("thing { }"))
        with_id = _spec(parse("thing#alpha { }"))
    assert with_id > bare


def test_attribute_selector_beats_bare_type():
    with registry_scope():
        install_toy_taxonomy()
        bare = _spec(parse("thing { }"))
        with_attr = _spec(parse('thing[color="red"] { }'))
    assert with_attr > bare


def test_class_selector_beats_bare_type():
    with registry_scope():
        install_toy_taxonomy()
        bare = _spec(parse("thing { }"))
        with_cls = _spec(parse("thing.highlighted { }"))
    assert with_cls > bare


def test_pseudo_class_beats_bare_type():
    with registry_scope():
        install_toy_taxonomy()
        bare = _spec(parse("thing { }"))
        with_pseudo = _spec(parse('thing:glob("*.py") { }'))
    assert with_pseudo > bare


def test_descendant_accumulates():
    # thing widget has two typed parts, so it should be more specific than thing.
    with registry_scope():
        install_toy_taxonomy()
        single = _spec(parse("thing { }"))
        compound = _spec(parse("thing widget { }"))
    assert compound > single


def test_complex_compound_specificity():
    # thing#alpha[color="red"] widget.highlighted should beat thing#alpha.
    with registry_scope():
        install_toy_taxonomy()
        simple = _spec(parse("thing#alpha { }"))
        complex_ = _spec(parse('thing#alpha[color="red"] widget.highlighted { }'))
    assert complex_ > simple


def test_cross_taxon_compound_has_axis_count_two():
    # actor + thing spans two distinct taxa → axis_count == 2.
    with registry_scope():
        install_toy_taxonomy()
        spec = _spec(parse('actor[role="admin"] thing#beta { }'))
    assert spec[0] == 2


def test_cross_taxon_beats_single_taxon():
    with registry_scope():
        install_toy_taxonomy()
        single = _spec(parse("thing#beta { }"))
        cross = _spec(parse('actor[role="admin"] thing#beta { }'))
    assert cross > single


def test_multiple_selectors_each_get_specificity():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing, thing#alpha { }")
    spec0 = view.rules[0].selectors[0].specificity
    spec1 = view.rules[0].selectors[1].specificity
    # thing#alpha is more specific than thing.
    assert spec1 > spec0
