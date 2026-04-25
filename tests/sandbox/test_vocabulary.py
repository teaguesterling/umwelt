"""Tests for sandbox vocabulary registration."""

from __future__ import annotations

from umwelt.registry import (
    get_entity,
    get_property,
    get_taxon,
    registry_scope,
)
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary


def _register_sandbox() -> None:
    """Register sandbox vocabulary in the current registry scope."""
    register_sandbox_vocabulary()


def test_world_taxon_registered():
    with registry_scope():
        _register_sandbox()
        taxon = get_taxon("world")
        assert taxon.name == "world"
        assert taxon.ma_concept == "world_coupling_axis"


def test_capability_taxon_registered():
    with registry_scope():
        _register_sandbox()
        taxon = get_taxon("capability")
        assert taxon.name == "capability"


def test_state_taxon_registered():
    with registry_scope():
        _register_sandbox()
        taxon = get_taxon("state")
        assert taxon.name == "state"


def test_world_file_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "file")
        assert entity.name == "file"
        assert entity.parent == "dir"
        assert "path" in entity.attributes
        assert entity.attributes["path"].required is True


def test_world_dir_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "dir")
        assert entity.parent is None
        assert "path" in entity.attributes


def test_world_resource_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "resource")
        assert "name" in entity.attributes


def test_world_network_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "network")
        assert entity.name == "network"


def test_world_env_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "env")
        assert "name" in entity.attributes


def test_capability_tool_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("capability", "tool")
        assert "name" in entity.attributes
        assert "level" in entity.attributes


def test_capability_kit_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("capability", "kit")
        assert entity.name == "kit"


def test_state_hook_entity():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("state", "hook")
        assert "event" in entity.attributes


def test_file_editable_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "file", "editable")
        assert prop.value_type is bool
        assert prop.comparison == "exact"


def test_tool_max_level_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("capability", "tool", "max-level")
        assert prop.comparison == "<="
        assert prop.value_attribute == "level"


def test_tool_allow_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("capability", "tool", "allow")
        assert prop.value_type is bool


def test_tool_allow_pattern_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("capability", "tool", "allow-pattern")
        assert prop.comparison == "pattern-in"


def test_hook_run_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("state", "hook", "run")
        assert prop.name == "run"


def test_resource_properties():
    with registry_scope():
        _register_sandbox()
        for name in ("memory", "wall-time", "cpu", "max-fds"):
            prop = get_property("world", "resource", name)
            assert prop.name == name
            assert prop.restrictive_direction == "min"


def test_network_deny_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "network", "deny")
        assert prop.name == "deny"


def test_env_allow_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "env", "allow")
        assert prop.name == "allow"


# ---------------------------------------------------------------------------
# world-as-root entity
# ---------------------------------------------------------------------------


def test_world_entity_registered():
    """world entity is the root of the world taxon."""
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "world")
        assert entity.name == "world"
        assert entity.taxon == "world"
        assert "name" in entity.attributes
        assert entity.attributes["name"].type is str


def test_world_entity_has_no_parent():
    """world entity is the root — no parent."""
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "world")
        assert entity.parent is None


def test_mount_entity_has_parent_world():
    """mount is a child of world."""
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "mount")
        assert entity.parent == "world"


def test_mount_entity_attributes():
    """mount entity has path, source, type attributes."""
    with registry_scope():
        _register_sandbox()
        entity = get_entity("world", "mount")
        assert "path" in entity.attributes
        assert entity.attributes["path"].required is True
        assert "source" in entity.attributes
        assert "type" in entity.attributes


def test_mount_has_size_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "mount", "size")
        assert prop.value_type is str


def test_mount_has_source_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "mount", "source")
        assert prop.value_type is str


def test_mount_has_readonly_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "mount", "readonly")
        assert prop.value_type is bool


def test_mount_has_type_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("world", "mount", "type")
        assert prop.value_type is str


# ---------------------------------------------------------------------------
# actor taxon
# ---------------------------------------------------------------------------


def test_actor_taxon_registered():
    with registry_scope():
        _register_sandbox()
        taxon = get_taxon("actor")
        assert taxon.name == "actor"
        assert taxon.ma_concept == "four_actor_taxonomy"


def test_inferencer_entity_registered():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("actor", "inferencer")
        assert entity.name == "inferencer"
        assert "model" in entity.attributes
        assert "kit" in entity.attributes
        assert "temperature" in entity.attributes


def test_executor_entity_registered():
    with registry_scope():
        _register_sandbox()
        entity = get_entity("actor", "executor")
        assert entity.name == "executor"
        assert "tool_name" in entity.attributes
        assert "altitude" in entity.attributes


def test_inferencer_model_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("actor", "inferencer", "model")
        assert prop.value_type is str


def test_inferencer_temperature_property():
    with registry_scope():
        _register_sandbox()
        prop = get_property("actor", "inferencer", "temperature")
        assert prop.value_type is float


# ---------------------------------------------------------------------------
# WorldMatcher handles world entity type
# ---------------------------------------------------------------------------


def test_world_matcher_returns_world_entity():
    """WorldMatcher.match_type('world') returns a WorldEntity."""
    import tempfile
    from pathlib import Path

    from umwelt.sandbox.entities import WorldEntity
    from umwelt.sandbox.world_matcher import WorldMatcher

    with tempfile.TemporaryDirectory() as td:
        matcher = WorldMatcher(base_dir=Path(td), world_name="dev")
        results = matcher.match_type("world")
        assert len(results) == 1
        assert isinstance(results[0], WorldEntity)
        assert results[0].name == "dev"


def test_world_matcher_default_world_name():
    """WorldMatcher defaults world_name to 'default'."""
    import tempfile
    from pathlib import Path

    from umwelt.sandbox.world_matcher import WorldMatcher

    with tempfile.TemporaryDirectory() as td:
        matcher = WorldMatcher(base_dir=Path(td))
        results = matcher.match_type("world")
        assert results[0].name == "default"


def test_world_matcher_get_id_world_entity():
    """WorldMatcher.get_id returns the world name for WorldEntity."""
    import tempfile
    from pathlib import Path

    from umwelt.sandbox.entities import WorldEntity
    from umwelt.sandbox.world_matcher import WorldMatcher

    with tempfile.TemporaryDirectory() as td:
        matcher = WorldMatcher(base_dir=Path(td), world_name="ci")
        entity = WorldEntity(name="ci")
        assert matcher.get_id(entity) == "ci"


# ---------------------------------------------------------------------------
# ActorMatcher
# ---------------------------------------------------------------------------


def test_actor_matcher_returns_inferencer():
    from umwelt.sandbox.actor_matcher import ActorMatcher
    from umwelt.sandbox.entities import InferencerEntity

    matcher = ActorMatcher(inferencers=[InferencerEntity(model="claude-sonnet-4-6")])
    results = matcher.match_type("inferencer")
    assert len(results) == 1
    assert results[0].model == "claude-sonnet-4-6"


def test_actor_matcher_returns_executor():
    from umwelt.sandbox.actor_matcher import ActorMatcher
    from umwelt.sandbox.entities import ExecutorEntity

    matcher = ActorMatcher(executors=[ExecutorEntity(tool_name="Bash", altitude="os")])
    results = matcher.match_type("executor")
    assert len(results) == 1
    assert results[0].tool_name == "Bash"


def test_actor_matcher_condition_met_always_false():
    from umwelt.sandbox.actor_matcher import ActorMatcher

    matcher = ActorMatcher()
    assert matcher.condition_met(None) is False


def test_actor_matcher_get_id_inferencer():
    from umwelt.sandbox.actor_matcher import ActorMatcher
    from umwelt.sandbox.entities import InferencerEntity

    matcher = ActorMatcher()
    entity = InferencerEntity(model="claude-sonnet-4-6")
    assert matcher.get_id(entity) == "claude-sonnet-4-6"


def test_actor_matcher_get_id_executor():
    from umwelt.sandbox.actor_matcher import ActorMatcher
    from umwelt.sandbox.entities import ExecutorEntity

    matcher = ActorMatcher()
    entity = ExecutorEntity(tool_name="Bash")
    assert matcher.get_id(entity) == "Bash"


# ---------------------------------------------------------------------------
# Parse-level smoke tests
# ---------------------------------------------------------------------------


def test_world_entity_parses_in_view():
    """world#dev file { editable: true; } parses — world type resolves."""
    from umwelt.parser import parse

    with registry_scope():
        _register_sandbox()
        view = parse("world#dev file { editable: true; }")
        assert view is not None


def test_world_entity_cross_taxon_parses():
    """world#dev tool[name=\"Bash\"] { allow: false; } parses as cross-taxon."""
    from umwelt.parser import parse

    with registry_scope():
        _register_sandbox()
        view = parse('world#dev tool[name="Bash"] { allow: false; }')
        assert view is not None
