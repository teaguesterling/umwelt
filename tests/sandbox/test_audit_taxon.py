"""Tests for the audit taxon (S3*) and @audit at-rule.

Verifies claim G1 (VSM fidelity — audit is the S3* cross-cut observer
placed outside the world) and C1-scaffold (audit provides the structural
hook for future proof-tree traceability). See docs/vision/evaluation-framework.md.

Distinct from tests/test_audit.py which covers the `umwelt audit` CLI.
"""
from __future__ import annotations

import pytest
from umwelt.parser import parse
from umwelt.cascade.resolver import resolve
from umwelt.registry import registry_scope, register_matcher, get_taxon, get_entity
from umwelt.sandbox.audit_matcher import AuditMatcher
from umwelt.sandbox.entities import ManifestEntity, ObservationEntity
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.world_matcher import WorldMatcher


@pytest.fixture
def vocab_with_matchers(tmp_path):
    with registry_scope():
        register_sandbox_vocabulary()
        register_matcher(taxon="world", matcher=WorldMatcher(base_dir=tmp_path))
        register_matcher(taxon="audit", matcher=AuditMatcher())
        yield tmp_path


def _parse(text, tmp_path):
    p = tmp_path / "test.umw"
    p.write_text(text)
    return parse(p)


def test_audit_taxon_registered(vocab_with_matchers):
    """G1: audit is a standalone S3* taxon with observation + manifest entities."""
    assert get_taxon("audit") is not None
    assert get_entity(taxon="audit", name="observation") is not None
    assert get_entity(taxon="audit", name="manifest") is not None


def test_at_audit_parses_observation_rule(vocab_with_matchers):
    """G1: @audit { observation#X { source: Y; } } produces an observation entry."""
    view = _parse('''
        @audit {
            observation#coach { source: "kibitzer"; }
        }
    ''', vocab_with_matchers)
    rv = resolve(view)
    observations = [
        (e, p) for e, p in rv.entries("audit")
        if isinstance(e, ObservationEntity)
    ]
    assert observations
    entity, props = observations[0]
    assert entity.name == "coach"
    assert props.get("source") in ('"kibitzer"', "kibitzer")


def test_at_audit_parses_manifest_rule(vocab_with_matchers):
    """G1: @audit { manifest#X { path: ...; } } produces a manifest entry."""
    view = _parse('''
        @audit {
            manifest#current { path: ".umwelt/manifest.json"; }
        }
    ''', vocab_with_matchers)
    rv = resolve(view)
    manifests = [
        (e, p) for e, p in rv.entries("audit")
        if isinstance(e, ManifestEntity)
    ]
    assert manifests
    entity, props = manifests[0]
    assert entity.name == "current"


def test_multiple_audit_entries(vocab_with_matchers):
    """G1: multiple entries inside @audit all resolve."""
    view = _parse('''
        @audit {
            observation#coach { source: "kibitzer"; }
            observation#ratchet { source: "ratchet-detect"; }
            manifest#current { path: ".umwelt/manifest.json"; }
        }
    ''', vocab_with_matchers)
    rv = resolve(view)
    observations = [
        (e, p) for e, p in rv.entries("audit")
        if isinstance(e, ObservationEntity)
    ]
    manifests = [
        (e, p) for e, p in rv.entries("audit")
        if isinstance(e, ManifestEntity)
    ]
    assert {e.name for e, _ in observations} == {"coach", "ratchet"}
    assert {e.name for e, _ in manifests} == {"current"}


def test_audit_entries_not_affected_by_world_filter(vocab_with_matchers):
    """G1: @audit lives outside any world. world-scoped resolve still sees audit entries."""
    view = _parse('''
        world#dev file { editable: true; }
        @audit { observation#coach { source: "kibitzer"; } }
    ''', vocab_with_matchers)
    rv = resolve(view, world="dev")
    audit_entries = [
        (e, p) for e, p in rv.entries("audit")
        if isinstance(e, ObservationEntity)
    ]
    assert audit_entries, "world-scoped resolve should still surface audit entries"


def test_audit_taxon_not_an_alias(vocab_with_matchers):
    """G1: audit is a real standalone taxon, not an alias."""
    from umwelt.registry import resolve_taxon
    assert resolve_taxon("audit") == "audit"
