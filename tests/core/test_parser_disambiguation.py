"""Tests for ambiguous type names and disambiguation syntax."""

from __future__ import annotations

import pytest

from tests.core.helpers.toy_taxonomy import install_doubled_taxonomy
from umwelt.errors import ViewParseError
from umwelt.parser import parse
from umwelt.registry import registry_scope


def _first_simple(view):
    return view.rules[0].selectors[0].parts[0].selector


def test_bare_ambiguous_type_raises():
    with registry_scope():
        install_doubled_taxonomy()
        with pytest.raises(ViewParseError, match="ambiguous"):
            parse("thing { }")


def test_namespace_prefix_shapes():
    with registry_scope():
        install_doubled_taxonomy()
        view = parse("shapes|thing { }")
    sel = _first_simple(view)
    assert sel.type_name == "thing"
    assert sel.taxon == "shapes"


def test_namespace_prefix_shadows():
    with registry_scope():
        install_doubled_taxonomy()
        view = parse("shadows|thing { }")
    sel = _first_simple(view)
    assert sel.taxon == "shadows"


def test_namespace_prefix_unknown_taxon_raises():
    with registry_scope():
        install_doubled_taxonomy()
        with pytest.raises(ViewParseError, match="unknown taxon 'ghost'"):
            parse("ghost|thing { }")


def test_namespace_prefix_unknown_type_in_taxon_raises():
    with registry_scope():
        install_doubled_taxonomy()
        with pytest.raises(ViewParseError, match="no entity 'widget' in taxon 'shapes'"):
            parse("shapes|widget { }")


def test_at_rule_scope_disambiguates():
    with registry_scope():
        install_doubled_taxonomy()
        view = parse("@shapes { thing { } }")
    # The rule inside @shapes is lifted into the top-level rules with
    # thing resolved to shapes.
    assert len(view.rules) == 1
    sel = _first_simple(view)
    assert sel.taxon == "shapes"


def test_at_rule_scope_with_multiple_rules():
    with registry_scope():
        install_doubled_taxonomy()
        view = parse("@shadows { thing { } thing#beta { } }")
    assert len(view.rules) == 2
    for r in view.rules:
        assert r.selectors[0].parts[0].selector.taxon == "shadows"


def test_at_rule_scope_does_not_affect_outside():
    with registry_scope():
        install_doubled_taxonomy()
        view = parse("@shapes { thing { } } shadows|thing { }")
    assert len(view.rules) == 2
    assert view.rules[0].selectors[0].parts[0].selector.taxon == "shapes"
    assert view.rules[1].selectors[0].parts[0].selector.taxon == "shadows"


def test_unknown_scope_at_rule_is_unknown_at_rule():
    with registry_scope():
        install_doubled_taxonomy()
        # @retrieval isn't a taxon scope — it's an unknown at-rule.
        view = parse("@retrieval { thing { } }")
    assert len(view.unknown_at_rules) == 1
    # Inner rules are not lifted.
    assert view.rules == ()
