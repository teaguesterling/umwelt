# src/umwelt/policy/queries.py
from __future__ import annotations

import json
import sqlite3

from umwelt.policy.engine import Candidate, TraceResult

_MODE_FILTER = "AND (mode_qualifier IS NULL OR mode_qualifier = ?)"

_RESOLVE_MODE_EXACT = """
SELECT property_name, property_value FROM (
    SELECT property_name, property_value, ROW_NUMBER() OVER (
        PARTITION BY property_name
        ORDER BY specificity DESC, rule_index DESC
    ) AS _rn
    FROM cascade_candidates
    WHERE entity_id = ? AND comparison = 'exact'
    {mode_clause}
) WHERE _rn = 1
"""

_RESOLVE_MODE_CAP = """
SELECT property_name, property_value FROM (
    SELECT property_name, property_value, ROW_NUMBER() OVER (
        PARTITION BY property_name
        ORDER BY CAST(property_value AS INTEGER) ASC, specificity DESC
    ) AS _rn
    FROM cascade_candidates
    WHERE entity_id = ? AND comparison = '<='
    {mode_clause}
) WHERE _rn = 1
"""

_RESOLVE_MODE_PATTERN = """
SELECT property_name, GROUP_CONCAT(DISTINCT property_value) AS property_value
FROM cascade_candidates
WHERE entity_id = ? AND comparison = 'pattern-in'
{mode_clause}
GROUP BY property_name
"""


def resolve_entity(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str,
    property: str | None = None,
    mode: str | None = None,
) -> str | dict[str, str] | None:
    entity_row = _find_entity(con, type=type, id=id)
    if entity_row is None:
        return None if property else {}

    entity_pk = entity_row[0]

    if mode is None:
        return _resolve_from_view(con, entity_pk, property)
    return _resolve_with_mode(con, entity_pk, property, mode)


def _resolve_from_view(
    con: sqlite3.Connection,
    entity_pk: int,
    property: str | None,
) -> str | dict[str, str] | None:
    if property is not None:
        row = con.execute(
            "SELECT effective_value FROM effective_properties "
            "WHERE entity_id = ? AND property_name = ?",
            (entity_pk, property),
        ).fetchone()
        return row[0] if row else None

    rows = con.execute(
        "SELECT property_name, effective_value FROM effective_properties WHERE entity_id = ?",
        (entity_pk,),
    ).fetchall()
    return {name: value for name, value in rows}


def _resolve_with_mode(
    con: sqlite3.Connection,
    entity_pk: int,
    property: str | None,
    mode: str,
) -> str | dict[str, str] | None:
    props: dict[str, str] = {}
    for sql_template in (_RESOLVE_MODE_EXACT, _RESOLVE_MODE_CAP, _RESOLVE_MODE_PATTERN):
        sql = sql_template.format(mode_clause=_MODE_FILTER)
        rows = con.execute(sql, (entity_pk, mode)).fetchall()
        for name, value in rows:
            props[name] = value

    if property is not None:
        return props.get(property)
    return props


def resolve_all_entities(
    con: sqlite3.Connection,
    *,
    type: str,
    mode: str | None = None,
) -> list[dict]:
    entities = con.execute(
        "SELECT id, entity_id, classes, attributes FROM entities WHERE type_name = ?",
        (type,),
    ).fetchall()

    results = []
    for eid, entity_id, classes_json, attrs_json in entities:
        if mode is None:
            props_rows = con.execute(
                "SELECT property_name, effective_value FROM effective_properties WHERE entity_id = ?",
                (eid,),
            ).fetchall()
            props = {name: value for name, value in props_rows}
        else:
            props = _resolve_with_mode(con, eid, None, mode) or {}

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
    mode: str | None = None,
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

    if mode is not None:
        result = _resolve_with_mode(con, entity_pk, property, mode)
        winning_value = result if isinstance(result, str) else None
    else:
        winner_row = con.execute(
            "SELECT effective_value FROM effective_properties "
            "WHERE entity_id = ? AND property_name = ?",
            (entity_pk, property),
        ).fetchone()
        winning_value = winner_row[0] if winner_row else None

    mode_clause = ""
    params: list = [entity_pk, property]
    if mode is not None:
        mode_clause = _MODE_FILTER
        params.append(mode)

    rows = con.execute(
        "SELECT property_value, specificity, rule_index, "
        "source_file, source_line "
        "FROM cascade_candidates "
        f"WHERE entity_id = ? AND property_name = ? {mode_clause} "
        "ORDER BY specificity DESC, rule_index DESC",
        params,
    ).fetchall()

    candidates = []
    winner_marked = False
    for value, spec, rule_idx, src_file, src_line in rows:
        is_winner = not winner_marked and value == winning_value
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
