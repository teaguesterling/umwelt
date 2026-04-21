# src/umwelt/policy/projections.py
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def create_projection_views(con: sqlite3.Connection) -> None:
    _create_resolved_entities_view(con)
    type_props = _get_type_properties(con)
    for entity_type, props in type_props.items():
        _create_typed_view(con, entity_type, props)


def create_compilation_meta(
    con: sqlite3.Connection,
    *,
    source_world: str | None = None,
    source_stylesheet: str | None = None,
) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS compilation_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    entity_count = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    resolved_count_row = con.execute("SELECT COUNT(*) FROM resolved_properties").fetchone()
    resolved_count = resolved_count_row[0] if resolved_count_row else 0

    meta = {
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": str(entity_count),
        "resolved_count": str(resolved_count),
        "dialect": "sqlite",
    }
    if source_world:
        meta["source_world"] = source_world
    if source_stylesheet:
        meta["source_stylesheet"] = source_stylesheet

    for key, value in meta.items():
        con.execute(
            "INSERT OR REPLACE INTO compilation_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
    con.commit()


def _get_type_properties(con: sqlite3.Connection) -> dict[str, list[str]]:
    rows = con.execute(
        "SELECT entity_type, name FROM property_types ORDER BY entity_type, name"
    ).fetchall()
    result: dict[str, list[str]] = {}
    for entity_type, prop_name in rows:
        result.setdefault(entity_type, []).append(prop_name)
    return result


def _create_typed_view(
    con: sqlite3.Connection,
    entity_type: str,
    properties: list[str],
) -> None:
    view_name = entity_type + "s"
    safe_view = view_name.replace('"', '""')

    pivot_cols = []
    for prop in properties:
        col_name = prop.replace("-", "_")
        safe_col = col_name.replace('"', '""')
        safe_prop = prop.replace("'", "''")
        pivot_cols.append(
            f'    MAX(CASE WHEN rp.property_name = \'{safe_prop}\' '
            f'THEN rp.property_value END) AS "{safe_col}"'
        )

    pivot_sql = ",\n".join(pivot_cols)
    safe_type = entity_type.replace("'", "''")

    ddl = f"""
CREATE VIEW IF NOT EXISTS "{safe_view}" AS
SELECT e.entity_id AS name, e.classes, e.attributes,
{pivot_sql}
FROM entities e
LEFT JOIN resolved_properties rp ON e.id = rp.entity_id
WHERE e.type_name = '{safe_type}'
GROUP BY e.id, e.entity_id, e.classes, e.attributes;
"""
    con.executescript(ddl)


def _create_resolved_entities_view(con: sqlite3.Connection) -> None:
    con.executescript("""
CREATE VIEW IF NOT EXISTS resolved_entities AS
SELECT e.id, e.taxon, e.type_name, e.entity_id, e.classes, e.attributes,
    json_group_object(rp.property_name, rp.property_value) AS properties
FROM entities e
LEFT JOIN resolved_properties rp ON e.id = rp.entity_id
GROUP BY e.id, e.taxon, e.type_name, e.entity_id, e.classes, e.attributes;
""")
