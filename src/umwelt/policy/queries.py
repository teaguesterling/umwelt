# src/umwelt/policy/queries.py
from __future__ import annotations

import json
import sqlite3

from umwelt.policy.engine import Candidate, TraceResult


def resolve_entity(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str,
    property: str | None = None,
) -> str | dict[str, str] | None:
    entity_row = _find_entity(con, type=type, id=id)
    if entity_row is None:
        return None if property else {}

    entity_pk = entity_row[0]

    if property is not None:
        row = con.execute(
            "SELECT property_value FROM resolved_properties "
            "WHERE entity_id = ? AND property_name = ?",
            (entity_pk, property),
        ).fetchone()
        return row[0] if row else None

    rows = con.execute(
        "SELECT property_name, property_value FROM resolved_properties WHERE entity_id = ?",
        (entity_pk,),
    ).fetchall()
    return {name: value for name, value in rows}


def resolve_all_entities(
    con: sqlite3.Connection,
    *,
    type: str,
) -> list[dict]:
    entities = con.execute(
        "SELECT id, entity_id, classes, attributes FROM entities WHERE type_name = ?",
        (type,),
    ).fetchall()

    results = []
    for eid, entity_id, classes_json, attrs_json in entities:
        props_rows = con.execute(
            "SELECT property_name, property_value FROM resolved_properties WHERE entity_id = ?",
            (eid,),
        ).fetchall()
        props = {name: value for name, value in props_rows}
        results.append({
            "entity_id": entity_id,
            "type_name": type,
            "classes": json.loads(classes_json) if classes_json else [],
            "attributes": json.loads(attrs_json) if attrs_json else {},
            "properties": props,
        })
    return results


def trace_entity(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str,
    property: str,
) -> TraceResult:
    entity_row = _find_entity(con, type=type, id=id)
    if entity_row is None:
        return TraceResult(
            entity=f"{type}#{id}",
            property=property,
            value=None,
            candidates=(),
        )

    entity_pk = entity_row[0]

    winner_row = con.execute(
        "SELECT property_value FROM resolved_properties "
        "WHERE entity_id = ? AND property_name = ?",
        (entity_pk, property),
    ).fetchone()
    winning_value = winner_row[0] if winner_row else None

    rows = con.execute(
        "SELECT property_value, specificity, rule_index, source_file, source_line "
        "FROM cascade_candidates "
        "WHERE entity_id = ? AND property_name = ? "
        "ORDER BY specificity DESC, rule_index DESC",
        (entity_pk, property),
    ).fetchall()

    candidates = []
    winner_marked = False
    for value, spec, rule_idx, src_file, src_line in rows:
        is_winner = (value == winning_value and not winner_marked)
        if is_winner:
            winner_marked = True
        candidates.append(Candidate(
            value=value,
            specificity=spec,
            rule_index=rule_idx,
            source_file=src_file or "",
            source_line=src_line or 0,
            won=is_winner,
        ))

    return TraceResult(
        entity=f"{type}#{id}",
        property=property,
        value=winning_value,
        candidates=tuple(candidates),
    )


def select_entities(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str | None = None,
    classes: list[str] | None = None,
) -> list[dict]:
    sql = "SELECT id, entity_id, type_name, classes, attributes FROM entities WHERE type_name = ?"
    params: list = [type]

    if id is not None:
        sql += " AND entity_id = ?"
        params.append(id)

    rows = con.execute(sql, params).fetchall()

    results = []
    for eid, entity_id, type_name, classes_json, attrs_json in rows:
        entity_classes = json.loads(classes_json) if classes_json else []
        if classes and not all(c in entity_classes for c in classes):
            continue
        results.append({
            "id": eid,
            "entity_id": entity_id,
            "type_name": type_name,
            "classes": entity_classes,
            "attributes": json.loads(attrs_json) if attrs_json else {},
        })
    return results


def _find_entity(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str,
) -> tuple | None:
    return con.execute(
        "SELECT id, entity_id, type_name, classes, attributes FROM entities "
        "WHERE type_name = ? AND entity_id = ?",
        (type, id),
    ).fetchone()
