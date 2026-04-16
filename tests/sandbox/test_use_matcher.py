"""Tests for use[of=...] matching and cascade.

Verifies claims A5 (property comparison semantics) and the integration
test for use entity resolution. See docs/vision/evaluation-framework.md.
"""
from __future__ import annotations

import pytest

from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import register_matcher, registry_scope
from umwelt.sandbox.capability_matcher import CapabilityMatcher
from umwelt.sandbox.entities import UseEntity
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary


@pytest.fixture
def vocab_with_matchers(tmp_path):
    with registry_scope():
        register_sandbox_vocabulary()
        register_matcher(taxon="capability", matcher=CapabilityMatcher())
        yield tmp_path


def _parse_view_text(text: str, tmp_path):
    path = tmp_path / "test.umw"
    path.write_text(text)
    return parse(path)


def test_use_with_of_exact(vocab_with_matchers):
    view = _parse_view_text(
        'use[of="file#/src/auth.py"] { editable: true; }',
        vocab_with_matchers,
    )
    rv = resolve(view)
    entries = list(rv.entries("operation"))
    uses = [(e, p) for e, p in entries if isinstance(e, UseEntity)]
    assert len(uses) == 1
    entity, props = uses[0]
    assert entity.of == "file#/src/auth.py"
    assert props.get("editable") == "true"


def test_use_with_of_kind(vocab_with_matchers):
    view = _parse_view_text(
        'use[of-kind="file"] { visible: true; }',
        vocab_with_matchers,
    )
    rv = resolve(view)
    uses = [(e, p) for e, p in rv.entries("operation") if isinstance(e, UseEntity)]
    assert len(uses) == 1
    assert uses[0][0].of_kind == "file"
    assert uses[0][1].get("visible") == "true"


def test_use_with_of_like(vocab_with_matchers):
    view = _parse_view_text(
        'use[of-like="file#/src"] { editable: true; }',
        vocab_with_matchers,
    )
    rv = resolve(view)
    uses = [(e, p) for e, p in rv.entries("operation") if isinstance(e, UseEntity)]
    assert len(uses) == 1
    assert uses[0][0].of_like == "file#/src"


def test_multiple_distinct_uses(vocab_with_matchers):
    view = _parse_view_text(
        '''
        use[of="file#/a.py"] { editable: true; }
        use[of="file#/b.py"] { editable: false; }
        ''',
        vocab_with_matchers,
    )
    rv = resolve(view)
    uses = [(e, p) for e, p in rv.entries("operation") if isinstance(e, UseEntity)]
    assert len(uses) == 2
    of_values = {e.of for e, _ in uses}
    assert of_values == {"file#/a.py", "file#/b.py"}


def test_use_bare_rule_creates_bare_entity(vocab_with_matchers):
    """A bare `use { ... }` rule creates a UseEntity with all fields None."""
    view = _parse_view_text('use { editable: false; }', vocab_with_matchers)
    rv = resolve(view)
    uses = [(e, p) for e, p in rv.entries("operation") if isinstance(e, UseEntity)]
    assert len(uses) >= 1
    bare = [(e, p) for e, p in uses if e.of is None and e.of_kind is None and e.of_like is None]
    assert bare
    _entity, props = bare[0]
    assert props.get("editable") == "false"
