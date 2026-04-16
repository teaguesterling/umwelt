"""Cross-axis cascade specificity tests.

Verifies claims A2 (cascade is well-ordered — no cycles across the new
axis_count primacy) and A3 (cross-axis soundness: rules that join more
taxa-axes are more specific than rules naming fewer axes). See
docs/vision/evaluation-framework.md.
"""
from __future__ import annotations

import itertools

import pytest

from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import register_matcher, registry_scope
from umwelt.sandbox.actor_matcher import ActorMatcher
from umwelt.sandbox.capability_matcher import CapabilityMatcher
from umwelt.sandbox.entities import InferencerEntity, UseEntity
from umwelt.sandbox.state_matcher import StateMatcher
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.world_matcher import WorldMatcher


@pytest.fixture
def vocab_with_matchers(tmp_path):
    with registry_scope():
        register_sandbox_vocabulary()
        register_matcher(taxon="world", matcher=WorldMatcher(base_dir=tmp_path))
        register_matcher(taxon="capability", matcher=CapabilityMatcher())
        register_matcher(taxon="state", matcher=StateMatcher())
        # Include a live inferencer so condition_met can match it.
        register_matcher(
            taxon="actor",
            matcher=ActorMatcher(inferencers=[InferencerEntity(model="gpt-4o")]),
        )
        yield tmp_path


def _parse(text: str, tmp_path):
    p = tmp_path / "test.umw"
    p.write_text(text)
    return parse(p)


def _specs(view):
    return [sel.specificity for rule in view.rules for sel in rule.selectors]


def test_single_axis_specificity_has_axis_count_one(vocab_with_matchers):
    """A3: a single-axis selector has axis_count=1."""
    view = _parse('file[path="x"] { editable: true; }', vocab_with_matchers)
    spec = _specs(view)[0]
    assert len(spec) >= 2
    assert spec[0] == 1


def test_cross_axis_has_higher_axis_count(vocab_with_matchers):
    """A3: a two-axis selector has axis_count=2, strictly greater than 1."""
    one_axis = _specs(_parse('file[path="x"] { editable: true; }', vocab_with_matchers))[0]
    two_axis = _specs(_parse(
        'inferencer tool[name="Edit"] { allow: true; }', vocab_with_matchers,
    ))[0]
    assert two_axis[0] > one_axis[0]
    assert two_axis > one_axis


def test_three_axis_beats_two_axis(vocab_with_matchers):
    """A3: three-axis selector beats two-axis selector by tuple comparison."""
    two = _specs(_parse(
        'tool[name="Edit"] use[of="file#x"] { editable: true; }', vocab_with_matchers,
    ))[0]
    three = _specs(_parse(
        'inferencer tool[name="Edit"] use[of="file#x"] { editable: true; }',
        vocab_with_matchers,
    ))[0]
    assert three > two


def test_bare_selector_less_specific_than_attribute_selector(vocab_with_matchers):
    """A2: within a single axis, attribute filters beat bare selectors."""
    bare = _specs(_parse('use { editable: true; }', vocab_with_matchers))[0]
    attr = _specs(_parse('use[of="file#x"] { editable: true; }', vocab_with_matchers))[0]
    assert attr > bare


def test_id_beats_class_within_same_axis(vocab_with_matchers):
    """A2: standard CSS specificity preserved within an axis."""
    cls = _specs(_parse('file.foo { editable: true; }', vocab_with_matchers))[0]
    ide = _specs(_parse('file#foo { editable: true; }', vocab_with_matchers))[0]
    assert ide > cls


def test_cross_axis_rule_wins_over_single_axis_in_cascade(vocab_with_matchers):
    """A3: the cross-axis rule resolves to the winning value even when document order favors the single-axis rule."""
    # Single-axis rule comes first (lower document order), cross-axis rule second.
    # Cross-axis should win because axis_count=2 > axis_count=1.
    view = _parse('''
        use[of="file#/src/auth.py"] { editable: false; }
        inferencer use[of="file#/src/auth.py"] { editable: true; }
    ''', vocab_with_matchers)
    rv = resolve(view)
    uses = [(e, p) for e, p in rv.entries("operation") if isinstance(e, UseEntity)]
    specific = [p for e, p in uses if e.of == "file#/src/auth.py"]
    assert specific, "expected a use entity with of=file#/src/auth.py"
    assert any(p.get("editable") == "true" for p in specific), (
        "cross-axis rule should win over single-axis"
    )


def test_document_order_breaks_ties_within_same_specificity(vocab_with_matchers):
    """A2: identical specificity → later rule wins (document order tiebreaker)."""
    view = _parse('''
        use[of="file#x"] { editable: false; }
        use[of="file#x"] { editable: true; }
    ''', vocab_with_matchers)
    rv = resolve(view)
    uses = [(e, p) for e, p in rv.entries("operation") if isinstance(e, UseEntity)]
    specific = [p for e, p in uses if e.of == "file#x"]
    assert any(p.get("editable") == "true" for p in specific)


def test_specificity_tuple_is_well_ordered_no_cycles(vocab_with_matchers):
    """A2: tuple comparison never yields cycles. Sample ordering across common cases."""
    specs = [
        _specs(_parse('use { editable: true; }', vocab_with_matchers))[0],
        _specs(_parse('use[of-kind="file"] { editable: true; }', vocab_with_matchers))[0],
        _specs(_parse('use[of="file#x"] { editable: true; }', vocab_with_matchers))[0],
        _specs(_parse('tool use[of="file#x"] { editable: true; }', vocab_with_matchers))[0],
        _specs(_parse('inferencer tool use[of="file#x"] { editable: true; }', vocab_with_matchers))[0],
    ]
    # Strictly monotone by construction.
    for a, b in itertools.pairwise(specs):
        assert b >= a, f"expected non-decreasing specificity: {a} → {b}"
    assert specs[-1] > specs[0]
