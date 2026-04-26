"""Data model for the umwelt world state layer.

All types are frozen dataclasses with tuple-typed sequence fields so they are
safely shareable and hashable — consistent with the pattern in umwelt.ast.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DetailLevel(Enum):
    SUMMARY = "summary"
    OUTLINE = "outline"
    FULL = "full"


class Provenance(Enum):
    EXPLICIT = "explicit"
    DISCOVERED = "discovered"
    PROJECTED = "projected"
    INCLUDED = "included"
    REQUIRED = "required"


@dataclass(frozen=True)
class WorldWarning:
    message: str
    key: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class DeclaredEntity:
    type: str
    id: str
    classes: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)
    parent: str | None = None
    provenance: Provenance = Provenance.EXPLICIT


@dataclass(frozen=True)
class Projection:
    type: str
    id: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorldFile:
    entities: tuple[DeclaredEntity, ...]
    projections: tuple[Projection, ...]
    warnings: tuple[WorldWarning, ...]
    source_path: str | None = None
    discover_raw: tuple[dict[str, Any], ...] = ()
    overrides_raw: dict[str, Any] = field(default_factory=dict)
    fixed_raw: dict[str, Any] = field(default_factory=dict)
    include_raw: tuple[str, ...] = ()
    exclude_raw: tuple[str, ...] = ()
    require_raw: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaterializedMeta:
    source: str | None
    materialized_at: str
    detail_level: str
    entity_count: int
    type_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class MaterializedWorld:
    meta: MaterializedMeta
    entities: tuple[DeclaredEntity, ...]
    projections: tuple[Projection, ...]
    warnings: tuple[WorldWarning, ...]
