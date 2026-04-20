from __future__ import annotations

from umwelt.registry.entities import resolve_entity_type
from umwelt.world.model import DeclaredEntity, WorldFile, WorldWarning


def validate_world(world: WorldFile) -> WorldFile:
    """Validate entity types against the registered vocabulary.

    Returns a new WorldFile with validation warnings appended.
    Unknown entity types produce warnings, not errors (forward compat).
    """
    new_warnings: list[WorldWarning] = []
    for entity in world.entities:
        new_warnings.extend(_validate_entity(entity))
    return WorldFile(
        entities=world.entities,
        projections=world.projections,
        warnings=world.warnings + tuple(new_warnings),
        source_path=world.source_path,
        discover_raw=world.discover_raw,
        overrides_raw=world.overrides_raw,
        fixed_raw=world.fixed_raw,
        include_raw=world.include_raw,
        exclude_raw=world.exclude_raw,
    )


def _validate_entity(entity: DeclaredEntity) -> list[WorldWarning]:
    """Check one entity against the registry."""
    warnings: list[WorldWarning] = []
    taxa = resolve_entity_type(entity.type)
    if not taxa:
        warnings.append(WorldWarning(
            message=f"unknown entity type '{entity.type}' (not in registered vocabulary)",
            key=entity.type,
        ))
    return warnings
