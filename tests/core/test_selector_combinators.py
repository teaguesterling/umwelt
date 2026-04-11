"""Tests for compound selectors with combinators and pseudo-classes."""

from __future__ import annotations

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.parser import parse
from umwelt.registry import registry_scope


def _complex(view, idx: int = 0):
    return view.rules[0].selectors[idx]


def test_descendant_two_parts():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing widget { }")
    c = _complex(view)
    assert len(c.parts) == 2
    assert c.parts[0].selector.type_name == "thing"
    assert c.parts[0].combinator == "root"
    assert c.parts[1].selector.type_name == "widget"
    assert c.parts[1].combinator == "descendant"


def test_descendant_three_parts():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing widget thing { }")
    c = _complex(view)
    assert len(c.parts) == 3
    assert [p.selector.type_name for p in c.parts] == ["thing", "widget", "thing"]
    assert [p.combinator for p in c.parts] == ["root", "descendant", "descendant"]


def test_child_combinator():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing > widget { }")
    c = _complex(view)
    assert len(c.parts) == 2
    assert c.parts[1].combinator == "child"


def test_mixed_combinators():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing > widget thing { }")
    c = _complex(view)
    assert [p.combinator for p in c.parts] == ["root", "child", "descendant"]


def test_descendant_with_attributes():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing[color="red"] widget[color^="bl"] { }')
    c = _complex(view)
    assert len(c.parts) == 2
    first = c.parts[0].selector
    second = c.parts[1].selector
    assert first.attributes[0].value == "red"
    assert second.attributes[0].value == "bl"


def test_not_pseudo_class():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing:not([color="red"]) { }')
    sel = view.rules[0].selectors[0].parts[0].selector
    assert len(sel.pseudo_classes) == 1
    assert sel.pseudo_classes[0].name == "not"
    assert "color" in (sel.pseudo_classes[0].argument or "")


def test_glob_pseudo_class():
    with registry_scope():
        install_toy_taxonomy()
        view = parse('thing:glob("*.py") { }')
    sel = view.rules[0].selectors[0].parts[0].selector
    assert sel.pseudo_classes[0].name == "glob"
    assert sel.pseudo_classes[0].argument == '"*.py"'


def test_pseudo_class_plus_descendant():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing:glob(\"*.py\") widget { }")
    c = _complex(view)
    assert len(c.parts) == 2
    assert c.parts[0].selector.pseudo_classes[0].name == "glob"
    assert c.parts[1].selector.type_name == "widget"
