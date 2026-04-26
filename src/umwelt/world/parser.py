"""YAML parser for .world.yml files.

Reads a world file, expands shorthand keys into ``DeclaredEntity`` instances,
merges shorthand-derived entities with explicit ``entities:`` block entries
(explicit wins on ``(type, id)`` collision), processes ``require``, ``include``,
and ``exclude`` composition directives, and stashes Phase 2-3 keys with
warnings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from umwelt.errors import WorldParseError
from umwelt.world.model import DeclaredEntity, Projection, Provenance, WorldFile, WorldWarning
from umwelt.world.shorthands import get_shorthand

_STRUCTURAL_KEYS = frozenset({
    "entities", "discover", "projections", "overrides", "fixed",
    "include", "exclude", "require",
})
_RESERVED_KEYS = frozenset({"vars", "when", "version"})
_PHASE2_KEYS = frozenset({"discover", "overrides"})


def load_world(path: str | Path, *, _seen: frozenset[str] | None = None) -> WorldFile:
    """Parse a .world.yml file and return a :class:`WorldFile`.

    Raises:
        FileNotFoundError: if *path* does not exist.
        WorldParseError: if the file has structural problems.
    """
    path = Path(path).resolve()
    if _seen is None:
        _seen = frozenset()

    text = path.read_text()  # raises FileNotFoundError naturally
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WorldParseError(f"invalid YAML: {exc}") from exc
    if data is None:
        data = {}

    warnings: list[WorldWarning] = []

    # 1. require: collections (idempotent)
    require_raw: tuple[str, ...] = ()
    if "require" in data:
        raw = data["require"]
        if isinstance(raw, list):
            require_raw = tuple(str(x) for x in raw)
            _process_requires(require_raw, warnings)

    # 2. include: files (ordered)
    include_raw: tuple[str, ...] = ()
    included_entities: list[DeclaredEntity] = []
    if "include" in data:
        raw = data["include"]
        if isinstance(raw, list):
            include_raw = tuple(str(x) for x in raw)
            included_entities, inc_warnings = _process_includes(
                include_raw, path.parent, _seen | {str(path)}
            )
            warnings.extend(inc_warnings)

    # 3. Expand shorthands
    shorthand_entities, sh_warnings = _expand_shorthands(data)
    warnings.extend(sh_warnings)

    # 4. Parse explicit entities
    explicit_entities: list[DeclaredEntity] = []
    if "entities" in data:
        raw = data["entities"]
        if isinstance(raw, list):
            for item in raw:
                explicit_entities.append(_parse_entity_dict(item))

    # 5. Merge: collection -> included -> shorthand -> explicit (later wins)
    from umwelt.registry.collections import get_collection_entities

    merged: dict[tuple[str, str], DeclaredEntity] = {}
    for e in get_collection_entities():
        merged[(e.type, e.id)] = e
    for e in included_entities:
        merged[(e.type, e.id)] = e
    for e in shorthand_entities:
        merged[(e.type, e.id)] = e
    for e in explicit_entities:
        merged[(e.type, e.id)] = e

    # 6. exclude: removals last
    exclude_raw: tuple[str, ...] = ()
    if "exclude" in data:
        raw = data["exclude"]
        if isinstance(raw, list):
            exclude_raw = tuple(str(x) for x in raw)
            merged = _apply_excludes(merged, exclude_raw, warnings)

    # Parse projections block
    projections: list[Projection] = []
    if "projections" in data:
        raw = data["projections"]
        if isinstance(raw, list):
            projections = _parse_projections(raw)

    # Phase 2-3 stubs
    discover_raw: tuple[dict[str, Any], ...] = ()
    overrides_raw: dict[str, Any] = {}
    fixed_raw: dict[str, Any] = {}

    for key in _PHASE2_KEYS:
        if key in data:
            warnings.append(WorldWarning(
                message=f"'{key}' is not yet implemented (Phase 2-3)",
                key=key,
            ))
            if key == "discover":
                discover_raw = tuple(data[key]) if isinstance(data[key], list) else ()
            elif key == "overrides":
                overrides_raw = data[key] if isinstance(data[key], dict) else {}

    # Fixed constraints are implemented -- capture without warning
    if "fixed" in data:
        fixed_raw = data["fixed"] if isinstance(data["fixed"], dict) else {}

    # Warn on reserved and unknown keys
    known_keys = _STRUCTURAL_KEYS | _RESERVED_KEYS
    for key in data:
        if key in _RESERVED_KEYS:
            warnings.append(WorldWarning(message=f"'{key}' is a reserved key", key=key))
        elif key not in known_keys and get_shorthand(key) is None:
            warnings.append(WorldWarning(message=f"unknown key '{key}'", key=key))

    return WorldFile(
        entities=tuple(merged.values()),
        projections=tuple(projections),
        warnings=tuple(warnings),
        source_path=str(path),
        discover_raw=discover_raw,
        overrides_raw=overrides_raw,
        fixed_raw=fixed_raw,
        include_raw=include_raw,
        exclude_raw=exclude_raw,
        require_raw=require_raw,
    )


def _process_requires(
    names: tuple[str, ...],
    warnings: list[WorldWarning],
) -> None:
    from umwelt.registry.collections import require_collection

    for name in names:
        try:
            require_collection(name)
        except KeyError:
            warnings.append(WorldWarning(
                message=f"unknown collection '{name}'", key="require",
            ))


def _process_includes(
    paths: tuple[str, ...],
    base_dir: Path,
    seen: frozenset[str],
) -> tuple[list[DeclaredEntity], list[WorldWarning]]:
    entities: list[DeclaredEntity] = []
    warnings: list[WorldWarning] = []
    for rel_path in paths:
        abs_path = (base_dir / rel_path).resolve()
        if str(abs_path) in seen:
            warnings.append(WorldWarning(
                message=f"skipping circular include: {rel_path}", key="include",
            ))
            continue
        try:
            included = load_world(abs_path, _seen=seen)
            for e in included.entities:
                entities.append(DeclaredEntity(
                    type=e.type,
                    id=e.id,
                    classes=e.classes,
                    attributes=e.attributes,
                    parent=e.parent,
                    provenance=Provenance.INCLUDED,
                ))
            warnings.extend(included.warnings)
        except FileNotFoundError:
            warnings.append(WorldWarning(
                message=f"included file not found: {rel_path}", key="include",
            ))
    return entities, warnings


def _apply_excludes(
    merged: dict[tuple[str, str], DeclaredEntity],
    selectors: tuple[str, ...],
    warnings: list[WorldWarning],
) -> dict[tuple[str, str], DeclaredEntity]:
    for sel_str in selectors:
        if "[" in sel_str:
            warnings.append(WorldWarning(
                message=f"attribute selectors in exclude not yet supported: {sel_str}",
                key="exclude",
            ))
            continue
        if "#" in sel_str:
            type_name, entity_id = sel_str.split("#", 1)
            merged.pop((type_name, entity_id), None)
        else:
            to_remove = [k for k in merged if k[0] == sel_str]
            for k in to_remove:
                del merged[k]
    return merged


def _parse_entity_dict(d: dict[str, Any]) -> DeclaredEntity:
    """Parse a single entity dict from the ``entities:`` block."""
    if "type" not in d:
        raise WorldParseError("entity missing required 'type' field")
    if "id" not in d:
        raise WorldParseError("entity missing required 'id' field")

    classes = d.get("classes", ())
    if isinstance(classes, list):
        classes = tuple(str(c) for c in classes)

    return DeclaredEntity(
        type=str(d["type"]),
        id=str(d["id"]),
        classes=classes,
        attributes=dict(d.get("attributes", {})),
        parent=str(d["parent"]) if d.get("parent") is not None else None,
        provenance=Provenance.EXPLICIT,
    )


def _expand_shorthands(
    data: dict[str, Any],
) -> tuple[list[DeclaredEntity], list[WorldWarning]]:
    """Expand all registered shorthand keys found in *data*."""
    entities: list[DeclaredEntity] = []
    warnings: list[WorldWarning] = []

    for key, value in data.items():
        if key in _STRUCTURAL_KEYS or key in _RESERVED_KEYS:
            continue
        shorthand = get_shorthand(key)
        if shorthand is None:
            continue  # unknown keys are flagged separately

        if shorthand.form == "list":
            if isinstance(value, list):
                for item in value:
                    entities.append(DeclaredEntity(
                        type=shorthand.entity_type,
                        id=str(item),
                        provenance=Provenance.EXPLICIT,
                    ))
        elif shorthand.form == "scalar":
            entities.append(DeclaredEntity(
                type=shorthand.entity_type,
                id=str(value),
                provenance=Provenance.EXPLICIT,
            ))
        elif shorthand.form == "block" and isinstance(value, dict):
            attrs = {str(k): str(v) for k, v in value.items()}
            entities.append(DeclaredEntity(
                type=shorthand.entity_type,
                id=shorthand.entity_type,
                attributes=attrs,
                provenance=Provenance.EXPLICIT,
            ))
        elif shorthand.form == "map" and isinstance(value, dict):
            for k, v in value.items():
                attrs_map: dict[str, Any] = {}
                if shorthand.attribute_key is not None:
                    attrs_map[shorthand.attribute_key] = str(v)
                entities.append(DeclaredEntity(
                    type=shorthand.entity_type,
                    id=str(k),
                    attributes=attrs_map,
                    provenance=Provenance.EXPLICIT,
                ))

    return entities, warnings


def _parse_projections(raw: list[dict[str, Any]]) -> list[Projection]:
    """Parse the ``projections:`` list into :class:`Projection` instances."""
    projections: list[Projection] = []
    for d in raw:
        projections.append(Projection(
            type=str(d.get("type", "")),
            id=str(d.get("id", "")),
            attributes=dict(d.get("attributes", {})),
        ))
    return projections
