"""Tests that the selector parser accepts complex of= attribute values.

These values contain '/', '#', and pseudo-class expressions because they
are world-entity selectors embedded as attribute strings. Locks in
parser behavior for the Task 4 UseMatcher.
"""
from __future__ import annotations

from umwelt.parser import parse
from umwelt.registry import registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary


def _install():
    """Register the sandbox vocabulary (including `use`) into the active scope."""
    register_sandbox_vocabulary()


def test_of_attr_with_slash_and_hash():
    with registry_scope():
        _install()
        view = parse('use[of="file#/src/auth.py"] { editable: true; }')
    assert len(view.rules) == 1
    rule = view.rules[0]
    assert len(rule.selectors) == 1
    sel = rule.selectors[0]
    attrs = sel.parts[-1].selector.attributes
    of_attr = next((a for a in attrs if a.name == "of"), None)
    assert of_attr is not None
    assert of_attr.value == "file#/src/auth.py"


def test_of_kind_attr():
    with registry_scope():
        _install()
        view = parse('use[of-kind="file"] { editable: false; }')
    sel = view.rules[0].selectors[0]
    attrs = sel.parts[-1].selector.attributes
    ok = next((a for a in attrs if a.name == "of-kind"), None)
    assert ok is not None
    assert ok.value == "file"


def test_of_like_attr():
    with registry_scope():
        _install()
        view = parse('use[of-like="file#/src"] { editable: true; }')
    sel = view.rules[0].selectors[0]
    attrs = sel.parts[-1].selector.attributes
    ol = next((a for a in attrs if a.name == "of-like"), None)
    assert ol is not None
    assert ol.value == "file#/src"


def test_of_attr_preserves_pseudo_class_syntax():
    """The parser should not mangle a pseudo-class expression inside of=."""
    with registry_scope():
        _install()
        view = parse("use[of=\"file:glob('src/**/*.py')\"] { editable: true; }")
    sel = view.rules[0].selectors[0]
    attrs = sel.parts[-1].selector.attributes
    of_attr = next((a for a in attrs if a.name == "of"), None)
    assert of_attr is not None
    # The parser should preserve the whole pseudo-class expression as a string.
    assert "glob" in of_attr.value


def test_of_attr_with_multiple_segments():
    with registry_scope():
        _install()
        view = parse('use[of="file#/a/b/c/d/e/f.py"] { editable: true; }')
    sel = view.rules[0].selectors[0]
    attrs = sel.parts[-1].selector.attributes
    of_attr = next((a for a in attrs if a.name == "of"), None)
    assert of_attr is not None
    assert of_attr.value == "file#/a/b/c/d/e/f.py"
