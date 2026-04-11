"""Tests for combinator mode classification."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.parser import parse
from umwelt.registry import registry_scope


def _parts(view):
    return view.rules[0].selectors[0].parts


def test_within_taxon_descendant_is_structural():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing widget { }")
    parts = _parts(view)
    assert parts[0].mode == "root"
    assert parts[1].mode == "structural"


def test_within_taxon_child_is_structural():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing > widget { }")
    parts = _parts(view)
    assert parts[1].mode == "structural"


def test_cross_taxon_descendant_is_context():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("actor thing { }")
    parts = _parts(view)
    assert parts[0].mode == "root"
    assert parts[1].mode == "context"


def test_three_level_mixed_modes():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("actor thing widget { }")
    parts = _parts(view)
    assert [p.mode for p in parts] == ["root", "context", "structural"]


def test_target_taxon_is_rightmost():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("actor thing { }")
    c = view.rules[0].selectors[0]
    assert c.target_taxon == "shapes"


def test_universal_on_right_inherits_taxon():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing * { }")
    c = view.rules[0].selectors[0]
    # The rightmost is *, so target_taxon falls back to the left part.
    assert c.target_taxon == "shapes"


def test_universal_on_left_is_structural_root():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("* widget { }")
    parts = _parts(view)
    # The leading * is always root mode regardless of taxon.
    assert parts[0].mode == "root"
    # The widget under * treats the previous part as matching any taxon;
    # we classify this as structural (no cross-taxon barrier).
    assert parts[1].mode == "structural"
