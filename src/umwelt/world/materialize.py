"""Materialization of a WorldFile into a detail-level-specific snapshot.

The three detail levels are:
  FULL    — all entities with all attributes
  OUTLINE — all entities, attributes stripped
  SUMMARY — no entities, only aggregate meta counts
"""

from __future__ import annotations

import datetime
from collections import Counter
from typing import Any

import yaml

from umwelt.world.model import (
    DeclaredEntity,
    DetailLevel,
    MaterializedMeta,
    MaterializedWorld,
    WorldFile,
)


def materialize(
    world: WorldFile,
    level: DetailLevel = DetailLevel.FULL,
) -> MaterializedWorld:
    """Return a MaterializedWorld from *world* at the requested *level*."""
    type_counts: dict[str, int] = dict(Counter(e.type for e in world.entities))

    if level == DetailLevel.FULL:
        entities = world.entities
    elif level == DetailLevel.OUTLINE:
        entities = tuple(
            DeclaredEntity(
                type=e.type,
                id=e.id,
                classes=e.classes,
                attributes={},
                parent=e.parent,
                provenance=e.provenance,
            )
            for e in world.entities
        )
    else:  # SUMMARY
        entities = ()

    meta = MaterializedMeta(
        source=world.source_path,
        materialized_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        detail_level=level.value,
        entity_count=len(world.entities),
        type_counts=type_counts,
    )

    return MaterializedWorld(
        meta=meta,
        entities=entities,
        projections=world.projections,
        warnings=world.warnings,
    )


# ---------------------------------------------------------------------------
# YAML rendering
# ---------------------------------------------------------------------------


def _entity_to_dict(entity: DeclaredEntity) -> dict[str, Any]:
    d: dict[str, Any] = {"type": entity.type, "id": entity.id}
    if entity.classes:
        d["classes"] = list(entity.classes)
    if entity.attributes:
        d["attributes"] = dict(entity.attributes)
    if entity.parent is not None:
        d["parent"] = entity.parent
    d["provenance"] = entity.provenance.value
    return d


def _projection_to_dict(proj: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"type": proj.type, "id": proj.id}
    if proj.attributes:
        d["attributes"] = dict(proj.attributes)
    return d


def render_yaml(materialized: MaterializedWorld) -> str:
    """Serialize *materialized* to a YAML string."""
    meta = materialized.meta
    meta_dict: dict[str, Any] = {
        "source": meta.source,
        "materialized_at": meta.materialized_at,
        "detail_level": meta.detail_level,
        "entity_count": meta.entity_count,
        "type_counts": dict(meta.type_counts),
    }

    data: dict[str, Any] = {"meta": meta_dict}

    if materialized.entities:
        data["entities"] = [_entity_to_dict(e) for e in materialized.entities]

    if materialized.projections:
        data["projections"] = [_projection_to_dict(p) for p in materialized.projections]

    return yaml.dump(data, default_flow_style=False, sort_keys=False)
