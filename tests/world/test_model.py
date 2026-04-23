from __future__ import annotations

import pytest

from umwelt.world.model import (
    DeclaredEntity,
    DetailLevel,
    MaterializedMeta,
    MaterializedWorld,
    Projection,
    Provenance,
    WorldFile,
    WorldWarning,
)


def test_declared_entity_defaults():
    e = DeclaredEntity(type="tool", id="Read")
    assert e.classes == ()
    assert e.attributes == {}
    assert e.parent is None
    assert e.provenance == Provenance.EXPLICIT


def test_declared_entity_frozen():
    e = DeclaredEntity(type="tool", id="Read")
    with pytest.raises(AttributeError):
        e.type = "mode"


def test_declared_entity_with_all_fields():
    e = DeclaredEntity(
        type="tool",
        id="Bash",
        classes=("dangerous",),
        attributes={"description": "shell"},
        parent="tools",
        provenance=Provenance.EXPLICIT,
    )
    assert e.classes == ("dangerous",)
    assert e.attributes["description"] == "shell"


def test_projection_construction():
    p = Projection(type="dir", id="node_modules", attributes={"path": "node_modules/"})
    assert p.type == "dir"


def test_world_file_defaults():
    wf = WorldFile(entities=(), projections=(), warnings=())
    assert wf.source_path is None
    assert wf.discover_raw == ()
    assert wf.include_raw == ()


def test_detail_level_values():
    assert DetailLevel.SUMMARY.value == "summary"
    assert DetailLevel.OUTLINE.value == "outline"
    assert DetailLevel.FULL.value == "full"


def test_provenance_values():
    assert Provenance.EXPLICIT.value == "explicit"
    assert Provenance.PROJECTED.value == "projected"


def test_materialized_world_construction():
    meta = MaterializedMeta(
        source="test.world.yml",
        materialized_at="2026-04-19T00:00:00Z",
        detail_level="full",
        entity_count=0,
        type_counts={},
    )
    mw = MaterializedWorld(meta=meta, entities=(), projections=(), warnings=())
    assert mw.meta.entity_count == 0


def test_world_warning():
    w = WorldWarning(message="unknown key", key="foo")
    assert w.line is None
