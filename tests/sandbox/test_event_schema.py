"""Tests for shared event schema on the audit taxon's observation entity."""
from __future__ import annotations

from umwelt.registry import get_property, list_properties, registry_scope


def test_observation_has_event_properties():
    with registry_scope():
        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        register_sandbox_vocabulary()

        props = list_properties("audit", "observation")
        prop_names = {p.name for p in props}
        assert "type" in prop_names
        assert "timestamp" in prop_names
        assert "session_id" in prop_names
        assert "severity" in prop_names
        assert "tags" in prop_names
        assert "payload" in prop_names


def test_observation_event_property_types():
    with registry_scope():
        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        register_sandbox_vocabulary()

        assert get_property("audit", "observation", "type").value_type == str
        assert get_property("audit", "observation", "timestamp").value_type == str
        assert get_property("audit", "observation", "session_id").value_type == str
        assert get_property("audit", "observation", "severity").value_type == str
        assert get_property("audit", "observation", "tags").value_type == str
        assert get_property("audit", "observation", "payload").value_type == str
