"""Tests for the top-level parser structure."""

from __future__ import annotations

import pytest

from tests.core.helpers.toy_taxonomy import install_toy_taxonomy
from umwelt.errors import ViewParseError
from umwelt.parser import parse
from umwelt.registry import registry_scope


def test_parse_empty_string():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("")
    assert view.rules == ()
    assert view.unknown_at_rules == ()
    assert view.warnings == ()


def test_parse_whitespace_only():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("   \n   \n")
    assert view.rules == ()


def test_parse_single_rule_block():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("thing { }")
    assert len(view.rules) == 1
    rule = view.rules[0]
    assert len(rule.selectors) == 1
    assert rule.declarations == ()


def test_parse_source_text_preserved():
    source = "thing { }"
    with registry_scope():
        install_toy_taxonomy()
        view = parse(source)
    assert view.source_text == source


def test_parse_from_path(tmp_path):
    path = tmp_path / "a.umw"
    path.write_text("thing { }\n")
    with registry_scope():
        install_toy_taxonomy()
        view = parse(path)
    assert view.source_path == path
    assert view.source_text == "thing { }\n"


def test_parse_unknown_at_rule_preserved():
    with registry_scope():
        install_toy_taxonomy()
        view = parse("@retrieval { context: last-3; }")
    assert len(view.unknown_at_rules) == 1
    at = view.unknown_at_rules[0]
    assert at.name == "retrieval"


def test_parse_syntax_error_raises():
    with registry_scope():
        install_toy_taxonomy()
        with pytest.raises(ViewParseError):
            # A prelude with no block — tinycss2 reaches EOF before finding
            # the `{}` and emits a qualified-rule parse error. tinycss2 is
            # extremely lenient (auto-closes unterminated braces, strings,
            # and comments at EOF), so this is one of the few inputs that
            # reliably surfaces through the parser error path.
            parse('"incomplete"')


def test_parse_accepts_string_or_path(tmp_path):
    path = tmp_path / "b.umw"
    path.write_text("thing { }")
    with registry_scope():
        install_toy_taxonomy()
        view_from_str = parse("thing { }")
        view_from_path = parse(path)
    assert view_from_str.source_path is None
    assert view_from_path.source_path == path
