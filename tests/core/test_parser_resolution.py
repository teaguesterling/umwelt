"""Tests for entity-type resolution against the registry during parsing."""

from __future__ import annotations

import pytest

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.errors import ViewParseError
from umwelt.parser import parse
from umwelt.registry import registry_scope


def _first_simple(view):
    return view.rules[0].selectors[0].parts[0].selector


def test_resolves_unique_type():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { }")
    sel = _first_simple(view)
    assert sel.type_name == "thing"
    assert sel.taxon == "shapes"


def test_resolves_cross_taxon_type():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("actor { }")
    sel = _first_simple(view)
    assert sel.type_name == "actor"
    assert sel.taxon == "actors"


def test_resolves_widget_under_shapes():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("widget { }")
    sel = _first_simple(view)
    assert sel.taxon == "shapes"


def test_universal_selector_is_wildcard_taxon():
    # `*` doesn't refer to any specific entity type; resolution leaves the
    # taxon field as "*" (sentinel) until the selector engine decides how
    # to interpret universal matching.
    with registry_scope():
        install_toy_taxonomy()
        view = parse("* { }")
    sel = _first_simple(view)
    assert sel.type_name == "*"
    assert sel.taxon == "*"


def test_unknown_type_raises():
    with registry_scope():
        install_toy_taxonomy()
        with pytest.raises(ViewParseError, match="unknown entity type 'ghost'"):
            parse("ghost { }")


def test_resolution_in_compound_parts():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing widget { }")
    c = view.rules[0].selectors[0]
    assert c.parts[0].selector.taxon == "shapes"
    assert c.parts[1].selector.taxon == "shapes"
    # target_taxon comes from the rightmost part.
    assert c.target_taxon == "shapes"
