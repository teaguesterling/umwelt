"""Tests for world file composition: require, include, exclude."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from umwelt.registry import registry_scope
from umwelt.registry.collections import (
    get_collection_entities,
    register_collection,
    require_collection,
)
from umwelt.world.model import DeclaredEntity, Provenance


def _tool_entity(name):
    return DeclaredEntity(type="tool", id=name, provenance=Provenance.REQUIRED)


def test_register_and_require_collection():
    with registry_scope():
        register_collection(
            name="executables",
            loader=lambda: [_tool_entity("Bash"), _tool_entity("Read")],
        )
        require_collection("executables")
        entities = get_collection_entities()
        ids = [e.id for e in entities]
        assert "Bash" in ids and "Read" in ids


def test_require_is_idempotent():
    with registry_scope():
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return [_tool_entity("Bash")]

        register_collection(name="executables", loader=loader)
        require_collection("executables")
        require_collection("executables")
        assert call_count == 1


def test_require_unknown_collection_raises():
    with registry_scope():
        with pytest.raises(KeyError, match="ghost"):
            require_collection("ghost")


def test_provenance_is_required():
    with registry_scope():
        register_collection(
            name="executables", loader=lambda: [_tool_entity("Bash")]
        )
        require_collection("executables")
        assert get_collection_entities()[0].provenance == Provenance.REQUIRED


def test_include_loads_entities_from_file(tmp_path):
    from umwelt.registry import register_entity, register_taxon
    from umwelt.registry.entities import AttrSchema
    from umwelt.world.parser import load_world

    base = tmp_path / "base.world.yml"
    base.write_text(
        yaml.dump({
            "entities": [
                {"type": "tool", "id": "Bash"},
                {"type": "tool", "id": "Read"},
            ]
        })
    )
    main = tmp_path / "main.world.yml"
    main.write_text(
        yaml.dump({
            "include": ["./base.world.yml"],
            "entities": [{"type": "tool", "id": "Edit"}],
        })
    )

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(
            taxon="capability",
            name="tool",
            attributes={"name": AttrSchema(type=str)},
            description="t",
        )
        world = load_world(main)
    ids = [e.id for e in world.entities]
    assert "Bash" in ids and "Read" in ids and "Edit" in ids


def test_include_later_overrides_earlier(tmp_path):
    from umwelt.registry import register_entity, register_taxon
    from umwelt.registry.entities import AttrSchema
    from umwelt.world.parser import load_world

    (tmp_path / "b1.world.yml").write_text(
        yaml.dump({
            "entities": [{"type": "tool", "id": "X", "attributes": {"v": "1"}}]
        })
    )
    (tmp_path / "b2.world.yml").write_text(
        yaml.dump({
            "entities": [{"type": "tool", "id": "X", "attributes": {"v": "2"}}]
        })
    )
    (tmp_path / "main.world.yml").write_text(
        yaml.dump({"include": ["./b1.world.yml", "./b2.world.yml"]})
    )

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(
            taxon="capability",
            name="tool",
            attributes={"name": AttrSchema(type=str)},
            description="t",
        )
        world = load_world(tmp_path / "main.world.yml")
    x = [e for e in world.entities if e.id == "X"][0]
    assert x.attributes.get("v") == "2"


def test_exclude_removes_entities(tmp_path):
    from umwelt.registry import register_entity, register_taxon
    from umwelt.registry.entities import AttrSchema
    from umwelt.world.parser import load_world

    (tmp_path / "main.world.yml").write_text(
        yaml.dump({
            "entities": [
                {"type": "tool", "id": "Bash"},
                {"type": "tool", "id": "Read"},
                {"type": "tool", "id": "Edit"},
            ],
            "exclude": ["tool#Bash"],
        })
    )

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(
            taxon="capability",
            name="tool",
            attributes={"name": AttrSchema(type=str)},
            description="t",
        )
        world = load_world(tmp_path / "main.world.yml")
    ids = [e.id for e in world.entities]
    assert "Bash" not in ids and "Read" in ids and "Edit" in ids


def test_include_cycle_detection(tmp_path):
    from umwelt.registry import register_entity, register_taxon
    from umwelt.registry.entities import AttrSchema
    from umwelt.world.parser import load_world

    (tmp_path / "a.world.yml").write_text(
        yaml.dump({
            "include": ["./b.world.yml"],
            "entities": [{"type": "tool", "id": "A"}],
        })
    )
    (tmp_path / "b.world.yml").write_text(
        yaml.dump({
            "include": ["./a.world.yml"],
            "entities": [{"type": "tool", "id": "B"}],
        })
    )

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(
            taxon="capability",
            name="tool",
            attributes={"name": AttrSchema(type=str)},
            description="t",
        )
        world = load_world(tmp_path / "a.world.yml")
    ids = [e.id for e in world.entities]
    assert "A" in ids and "B" in ids
    assert any(
        "skip" in w.message.lower() or "circular" in w.message.lower()
        for w in world.warnings
    )


def test_require_in_world_file(tmp_path):
    from umwelt.registry import register_entity, register_taxon
    from umwelt.registry.entities import AttrSchema
    from umwelt.world.parser import load_world

    (tmp_path / "main.world.yml").write_text(
        yaml.dump({
            "require": ["test_tools"],
            "entities": [{"type": "tool", "id": "Extra"}],
        })
    )

    with registry_scope():
        register_taxon(name="capability", description="cap")
        register_entity(
            taxon="capability",
            name="tool",
            attributes={"name": AttrSchema(type=str)},
            description="t",
        )
        register_collection(
            name="test_tools",
            loader=lambda: [_tool_entity("Bash"), _tool_entity("Read")],
        )
        world = load_world(tmp_path / "main.world.yml")
    ids = [e.id for e in world.entities]
    assert "Bash" in ids and "Read" in ids and "Extra" in ids
