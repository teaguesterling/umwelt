"""Populate the entities table from the matcher registry.

Bridges umwelt's Matcher protocol to SQL INSERT statements. Each
registered matcher is queried for entities, which are serialized
to JSON-column rows and inserted.
"""
from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from umwelt.registry.taxa import _current_state


def entity_to_row(taxon: str, type_name: str, entity: Any) -> dict[str, Any]:
    """Convert a matcher entity object to an insertable row dict."""
    entity_id = _extract_id(entity)
    classes = _extract_classes(entity)
    attributes = _extract_attributes(entity)

    return {
        "taxon": taxon,
        "type_name": type_name,
        "entity_id": entity_id,
        "classes": json.dumps(classes) if classes else None,
        "attributes": json.dumps(attributes) if attributes else None,
    }


def _extract_id(entity: Any) -> str | None:
    """Extract an identity value from an entity, trying common id fields."""
    for attr in ("path", "name", "kind", "id"):
        val = getattr(entity, attr, None)
        if val is not None:
            return str(val)
    return None


def _extract_classes(entity: Any) -> list[str]:
    """Extract CSS-like class labels from an entity."""
    classes = getattr(entity, "classes", None)
    if classes is not None:
        return list(classes)
    return []


def _extract_attributes(entity: Any) -> dict[str, str]:
    """Extract all dataclass fields as a flat string-valued dict.

    Skips abs_path (not serializable to JSON) and classes (stored
    in a dedicated column).
    """
    attrs: dict[str, str] = {}
    skip = {"abs_path", "classes"}
    try:
        for f in fields(entity):
            if f.name in skip:
                continue
            val = getattr(entity, f.name)
            if val is not None:
                attrs[f.name] = str(val)
    except TypeError:
        pass
    return attrs


def populate_entities(con: Any, base_dir: Path) -> None:
    """Query all registered matchers and INSERT their entities."""
    state = _current_state()

    for taxon, matcher in state.matchers.items():
        type_names = _get_type_names(taxon)
        for type_name in type_names:
            try:
                entities = matcher.match_type(type_name)
            except Exception:
                continue
            for entity in entities:
                row = entity_to_row(taxon, type_name, entity)
                con.execute(
                    "INSERT INTO entities (taxon, type_name, entity_id, classes, attributes, depth) "
                    "VALUES (?, ?, ?, ?, ?, 0)",
                    (row["taxon"], row["type_name"], row["entity_id"],
                     row["classes"], row["attributes"]),
                )

    con.commit()
    _rebuild_hierarchy(con, base_dir)
    _rebuild_closure(con)


def _get_type_names(taxon: str) -> list[str]:
    """Return the entity type names to query for a taxon."""
    state = _current_state()
    types = []
    for (t, name) in state.entities:
        if t == taxon:
            types.append(name)
    return types if types else ["*"]


def _rebuild_hierarchy(con: Any, base_dir: Path) -> None:
    """Set parent_id for file/dir entities based on filesystem paths."""
    dirs = con.execute(
        "SELECT id, entity_id FROM entities WHERE type_name = 'dir'"
    ).fetchall()
    dir_map = {path: eid for eid, path in dirs}

    files = con.execute(
        "SELECT id, entity_id FROM entities WHERE type_name IN ('file', 'dir') AND entity_id IS NOT NULL"
    ).fetchall()
    for file_id, file_path in files:
        if file_path is None:
            continue
        parent_path = str(Path(file_path).parent)
        if parent_path == ".":
            continue
        parent_id = dir_map.get(parent_path)
        if parent_id is not None:
            con.execute("UPDATE entities SET parent_id = ? WHERE id = ?", (parent_id, file_id))
    con.commit()


def _rebuild_closure(con: Any) -> None:
    """Rebuild the entity_closure table from parent_id relationships."""
    con.executescript("""
        DELETE FROM entity_closure;
        INSERT INTO entity_closure
        WITH RECURSIVE closure(ancestor_id, descendant_id, depth) AS (
            SELECT id, id, 0 FROM entities
            UNION ALL
            SELECT c.ancestor_id, e.id, c.depth + 1
            FROM closure c
            JOIN entities e ON e.parent_id = c.descendant_id
        )
        SELECT DISTINCT * FROM closure;
    """)


def populate_from_world(con: Any, world: Any) -> None:
    """Insert DeclaredEntity instances from a WorldFile into the entities table.

    World file entities win on (type_name, entity_id) collision with
    existing matcher-discovered entities.
    """
    for entity in world.entities:
        _upsert_declared_entity(con, entity)

    for proj in world.projections:
        _upsert_projection(con, proj)

    fixed_raw = getattr(world, "fixed_raw", {})
    if fixed_raw:
        _process_fixed_constraints(con, fixed_raw)

    con.commit()
    _rebuild_closure(con)


def _upsert_declared_entity(con: Any, entity: Any) -> None:
    classes_json = json.dumps(list(entity.classes)) if entity.classes else None
    attrs_json = json.dumps(entity.attributes) if entity.attributes else None

    existing = con.execute(
        "SELECT id FROM entities WHERE type_name = ? AND entity_id = ?",
        (entity.type, entity.id),
    ).fetchone()

    if existing:
        con.execute(
            "UPDATE entities SET classes = ?, attributes = ? WHERE id = ?",
            (classes_json, attrs_json, existing[0]),
        )
    else:
        taxon = _guess_taxon(entity.type)
        con.execute(
            "INSERT INTO entities (taxon, type_name, entity_id, classes, attributes, depth) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (taxon, entity.type, entity.id, classes_json, attrs_json),
        )


def _upsert_projection(con: Any, proj: Any) -> None:
    attrs_json = json.dumps(proj.attributes) if proj.attributes else None

    existing = con.execute(
        "SELECT id FROM entities WHERE type_name = ? AND entity_id = ?",
        (proj.type, proj.id),
    ).fetchone()

    if existing:
        con.execute(
            "UPDATE entities SET attributes = ? WHERE id = ?",
            (attrs_json, existing[0]),
        )
    else:
        taxon = _guess_taxon(proj.type)
        con.execute(
            "INSERT INTO entities (taxon, type_name, entity_id, attributes, depth) "
            "VALUES (?, ?, ?, ?, 0)",
            (taxon, proj.type, proj.id, attrs_json),
        )


def _process_fixed_constraints(con, fixed_raw):
    for selector_str, props in fixed_raw.items():
        if not isinstance(props, dict):
            continue
        matching_ids = _match_fixed_selector(con, selector_str)
        for entity_pk in matching_ids:
            for prop_name, prop_value in props.items():
                con.execute(
                    "INSERT INTO fixed_constraints (entity_id, property_name, property_value, selector) "
                    "VALUES (?, ?, ?, ?)",
                    (entity_pk, prop_name, str(prop_value), selector_str),
                )


def _match_fixed_selector(con, selector_str):
    if "#" in selector_str:
        type_name, entity_id = selector_str.split("#", 1)
        rows = con.execute(
            "SELECT id FROM entities WHERE type_name = ? AND entity_id = ?",
            (type_name, entity_id),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id FROM entities WHERE type_name = ?",
            (selector_str,),
        ).fetchall()
    return [r[0] for r in rows]


def _guess_taxon(type_name: str) -> str:
    try:
        from umwelt.registry.entities import resolve_entity_type
        taxa = resolve_entity_type(type_name)
        if taxa:
            return taxa[0]
    except Exception:
        pass
    return type_name
