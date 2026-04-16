"""Verifies claim A1 (resolver determinism): resolving the same view twice
produces identical ResolvedView.

Tier 0 — foundational. See docs/vision/evaluation-framework.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import register_matcher, registry_scope
from umwelt.sandbox.actor_matcher import ActorMatcher
from umwelt.sandbox.capability_matcher import CapabilityMatcher
from umwelt.sandbox.state_matcher import StateMatcher
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.world_matcher import WorldMatcher

FIXTURE_DIR = Path(__file__).parent.parent.parent / "src" / "umwelt" / "_fixtures"


@pytest.fixture(autouse=True)
def vocab_scope():
    with registry_scope():
        register_sandbox_vocabulary()
        register_matcher(taxon="world", matcher=WorldMatcher(base_dir=FIXTURE_DIR))
        register_matcher(taxon="capability", matcher=CapabilityMatcher())
        register_matcher(taxon="state", matcher=StateMatcher())
        register_matcher(taxon="actor", matcher=ActorMatcher())
        yield


def _resolved_signature(rv):
    """A stable, hashable signature of a ResolvedView for comparison."""
    sig = []
    for taxon in sorted(rv.taxa()):
        for entity, props in rv.entries(taxon):
            sig.append((taxon, type(entity).__name__, tuple(sorted(props.items()))))
    return tuple(sig)


@pytest.mark.parametrize(
    "fixture",
    sorted(FIXTURE_DIR.glob("*.umw")),
    ids=lambda p: p.name,
)
def test_resolve_is_deterministic(fixture):
    """A1: resolving the same view twice yields the same ResolvedView."""
    view = parse(fixture)
    rv1 = resolve(view)
    rv2 = resolve(view)
    assert _resolved_signature(rv1) == _resolved_signature(rv2)


def test_resolve_deterministic_across_many_runs():
    """A1: 50 runs of the same fixture all produce identical signatures."""
    fixtures = sorted(FIXTURE_DIR.glob("*.umw"))
    if not fixtures:
        pytest.skip("no fixtures to test")
    fixture = fixtures[0]
    view = parse(fixture)
    signatures = {_resolved_signature(resolve(view)) for _ in range(50)}
    assert len(signatures) == 1, f"resolver non-deterministic: {len(signatures)} distinct results"
