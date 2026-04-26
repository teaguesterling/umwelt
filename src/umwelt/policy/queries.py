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

# ---------------------------------------------------------------------------
# Generic context qualifier types and SQL templates
# ---------------------------------------------------------------------------

ContextQualifier = tuple[str, str, str]  # (taxon, type_name, entity_id)

_CONTEXT_FILTER = """
AND NOT EXISTS (
    SELECT 1 FROM cascade_context_qualifiers ccq
    WHERE ccq.candidate_rowid = cascade_candidates.rowid
    AND NOT EXISTS (
        SELECT 1 FROM _active_context ac
        WHERE ac.taxon = ccq.taxon
          AND ac.type_name = ccq.type_name
          AND ac.entity_id = ccq.entity_id
    )
)
"""

_RESOLVE_CTX_EXACT = """
SELECT property_name, property_value FROM (
    SELECT property_name, property_value, ROW_NUMBER() OVER (
        PARTITION BY property_name
        ORDER BY specificity DESC, rule_index DESC
    ) AS _rn
    FROM cascade_candidates
    WHERE entity_id = ? AND comparison = 'exact'
    {context_clause}
) WHERE _rn = 1
"""

_RESOLVE_CTX_CAP = """
SELECT property_name, property_value FROM (
    SELECT property_name, property_value, ROW_NUMBER() OVER (
        PARTITION BY property_name
        ORDER BY CAST(property_value AS INTEGER) ASC, specificity DESC
    ) AS _rn
    FROM cascade_candidates
    WHERE entity_id = ? AND comparison = '<='
    {context_clause}
) WHERE _rn = 1
"""

_RESOLVE_CTX_PATTERN = """
SELECT property_name, GROUP_CONCAT(DISTINCT property_value) AS property_value
FROM cascade_candidates
WHERE entity_id = ? AND comparison = 'pattern-in'
{context_clause}
GROUP BY property_name
"""


# ---------------------------------------------------------------------------
# Context helper functions
# ---------------------------------------------------------------------------

def _setup_active_context(con: sqlite3.Connection, context: list[ContextQualifier]) -> None:
    con.execute("CREATE TEMP TABLE IF NOT EXISTS _active_context (taxon TEXT, type_name TEXT, entity_id TEXT)")
    con.execute("DELETE FROM _active_context")
    for taxon, type_name, entity_id in context:
        con.execute(
            "INSERT INTO _active_context (taxon, type_name, entity_id) VALUES (?, ?, ?)",
            (taxon, type_name, entity_id),
        )


def _teardown_active_context(con: sqlite3.Connection) -> None:
    con.execute("DROP TABLE IF EXISTS _active_context")


def _normalize_context(context) -> list[ContextQualifier] | None:
    if context is None:
        return None
    if isinstance(context, dict):
        from umwelt.registry.entities import resolve_entity_type
        result = []
        for type_name, entity_id in context.items():
            try:
                taxa = resolve_entity_type(type_name)
                taxon = taxa[0] if taxa else type_name
            except Exception:
                taxon = type_name
            result.append((taxon, type_name, entity_id))
        return result
    return list(context)


def _resolve_with_context(
    con: sqlite3.Connection,
    entity_pk: int,
    property: str | None,
    context: list[ContextQualifier],
) -> str | dict[str, str] | None:
    _setup_active_context(con, context)
    try:
        props: dict[str, str] = {}
        for sql_template in (_RESOLVE_CTX_EXACT, _RESOLVE_CTX_CAP, _RESOLVE_CTX_PATTERN):
            sql = sql_template.format(context_clause=_CONTEXT_FILTER)
            rows = con.execute(sql, (entity_pk,)).fetchall()
            for name, value in rows:
                props[name] = value

        try:
            fixed_rows = con.execute(
                "SELECT property_name, property_value FROM fixed_constraints WHERE entity_id = ?",
                (entity_pk,),
            ).fetchall()
            for name, value in fixed_rows:
                if name in props:
                    props[name] = value
        except sqlite3.OperationalError:
            pass

        if property is not None:
            return props.get(property)
        return props
    finally:
        _teardown_active_context(con)


def resolve_entity(
    con: sqlite3.Connection,
    *,
    type: str,
    id: str,
    property: str | None = None,
    mode: str | None = None,
    context: list[ContextQualifier] | dict | None = None,
) -> str | dict[str, str] | None:
    entity_row = _find_entity(con, type=type, id=id)
    if entity_row is None:
        return None if property else {}

    entity_pk = entity_row[0]

    resolved_context = _normalize_context(context)
    if resolved_context is None and mode is not None:
        resolved_context = [("state", "mode", mode)]

    if resolved_context is None:
        return _resolve_from_view(con, entity_pk, property)
    return _resolve_with_context(con, entity_pk, property, resolved_context)


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

    # Fixed constraints override cascade results regardless of mode
    try:
        fixed_rows = con.execute(
            "SELECT property_name, property_value FROM fixed_constraints WHERE entity_id = ?",
            (entity_pk,),
        ).fetchall()
        for name, value in fixed_rows:
            if name in props:
                props[name] = value
    except sqlite3.OperationalError:
        pass

    if property is not None:
        return props.get(property)
    return props


def resolve_all_entities(
    con: sqlite3.Connection,
    *,
    type: str,
    mode: str | None = None,
    context: list[ContextQualifier] | dict | None = None,
) -> list[dict]:
    resolved_context = _normalize_context(context)
    if resolved_context is None and mode is not None:
        resolved_context = [("state", "mode", mode)]

    entities = con.execute(
        "SELECT id, entity_id, classes, attributes FROM entities WHERE type_name = ?",
        (type,),
    ).fetchall()

    results = []
    for eid, entity_id, classes_json, attrs_json in entities:
        if resolved_context is None:
            props_rows = con.execute(
                "SELECT property_name, effective_value FROM effective_properties WHERE entity_id = ?",
                (eid,),
            ).fetchall()
            props = {name: value for name, value in props_rows}
        else:
            props = _resolve_with_context(con, eid, None, resolved_context) or {}

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
    context: list[ContextQualifier] | dict | None = None,
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

    resolved_context = _normalize_context(context)
    if resolved_context is None and mode is not None:
        resolved_context = [("state", "mode", mode)]

    if resolved_context is not None:
        result = _resolve_with_context(con, entity_pk, property, resolved_context)
        winning_value = result if isinstance(result, str) else None
    else:
        winner_row = con.execute(
            "SELECT effective_value FROM effective_properties "
            "WHERE entity_id = ? AND property_name = ?",
            (entity_pk, property),
        ).fetchone()
        winning_value = winner_row[0] if winner_row else None

    if resolved_context is not None:
        _setup_active_context(con, resolved_context)
        try:
            rows = con.execute(
                "SELECT property_value, specificity, rule_index, "
                "source_file, source_line "
                "FROM cascade_candidates "
                f"WHERE entity_id = ? AND property_name = ? {_CONTEXT_FILTER} "
                "ORDER BY specificity DESC, rule_index DESC",
                (entity_pk, property),
            ).fetchall()
        finally:
            _teardown_active_context(con)
    else:
        rows = con.execute(
            "SELECT property_value, specificity, rule_index, "
            "source_file, source_line "
            "FROM cascade_candidates "
            "WHERE entity_id = ? AND property_name = ? "
            "ORDER BY specificity DESC, rule_index DESC",
            (entity_pk, property),
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
