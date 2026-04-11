"""Tests for selector parsing inside rule blocks."""

from __future__ import annotations

import pytest

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.ast import AttrFilter
from umwelt.errors import ViewParseError
from umwelt.parser import parse
from umwelt.registry import registry_scope


def _sole_simple(view) -> tuple:
    """Return the sole simple selector in the sole rule of a single-rule view."""
    assert len(view.rules) == 1
    rule = view.rules[0]
    assert len(rule.selectors) == 1
    complex_sel = rule.selectors[0]
    assert len(complex_sel.parts) == 1
    return complex_sel.parts[0].selector


def test_bare_type_selector():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { }")
    sel = _sole_simple(view)
    assert sel.type_name == "thing"
    assert sel.id_value is None
    assert sel.classes == ()
    assert sel.attributes == ()


def test_universal_selector():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("* { }")
    sel = _sole_simple(view)
    assert sel.type_name == "*"


def test_id_selector():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing#alpha { }")
    sel = _sole_simple(view)
    assert sel.type_name == "thing"
    assert sel.id_value == "alpha"


def test_id_selector_allows_dotted_value():
    # e.g. filename-as-id: file#README.md
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing#README.md { }")
    sel = _sole_simple(view)
    assert sel.id_value == "README.md"


def test_class_selector():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing.highlighted { }")
    sel = _sole_simple(view)
    assert sel.classes == ("highlighted",)


def test_multiple_classes():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing.a.b.c { }")
    sel = _sole_simple(view)
    assert sel.classes == ("a", "b", "c")


def test_attribute_exists():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing[color] { }")
    sel = _sole_simple(view)
    assert sel.attributes == (AttrFilter(name="color", op=None, value=None),)


def test_attribute_equals():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color="red"] { }')
    sel = _sole_simple(view)
    assert sel.attributes == (AttrFilter(name="color", op="=", value="red"),)


def test_attribute_prefix():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color^="re"] { }')
    sel = _sole_simple(view)
    assert sel.attributes == (AttrFilter(name="color", op="^=", value="re"),)


def test_attribute_suffix():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color$="ed"] { }')
    sel = _sole_simple(view)
    assert sel.attributes == (AttrFilter(name="color", op="$=", value="ed"),)


def test_attribute_substring():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color*="e"] { }')
    sel = _sole_simple(view)
    assert sel.attributes == (AttrFilter(name="color", op="*=", value="e"),)


def test_multiple_attributes():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color="red"][id^="alpha"] { }')
    sel = _sole_simple(view)
    assert len(sel.attributes) == 2
    assert sel.attributes[0] == AttrFilter(name="color", op="=", value="red")
    assert sel.attributes[1] == AttrFilter(name="id", op="^=", value="alpha")


def test_comma_separated_selector_list():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing, widget { }")
    assert len(view.rules) == 1
    rule = view.rules[0]
    assert len(rule.selectors) == 2
    assert rule.selectors[0].parts[0].selector.type_name == "thing"
    assert rule.selectors[1].parts[0].selector.type_name == "widget"


def test_malformed_selector_raises():
    with registry_scope():
        install_toy_taxonomy()
        with pytest.raises(ViewParseError):
            # Unterminated attribute bracket
            parse("thing[color { }")
