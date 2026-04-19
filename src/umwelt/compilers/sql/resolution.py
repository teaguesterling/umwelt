"""Cascade resolution views for the policy database.

Creates SQL views that implement comparison-aware cascade resolution:
- exact: highest specificity wins (document order breaks ties)
- <=: tightest bound (MIN value) wins
- pattern-in: all values aggregate via set union
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

    from umwelt.compilers.sql.dialects import Dialect


def create_resolution_views(con: sqlite3.Connection, dialect: Dialect) -> str:
    """Create resolution views and return the DDL as SQL text.

    Also executes the DDL against `con` if provided.
    """
    ddl = _resolution_ddl(dialect)
    con.executescript(ddl)
    return ddl


def resolution_ddl(dialect: Dialect) -> str:
    """Return the resolution view DDL as SQL text without executing."""
    return _resolution_ddl(dialect)


def _resolution_ddl(dialect: Dialect) -> str:
    is_sqlite = dialect.name == "sqlite"

    if is_sqlite:
        exact_view = """
CREATE VIEW IF NOT EXISTS _resolved_exact AS
SELECT entity_id, property_name, property_value, comparison,
       specificity, rule_index, source_file, source_line
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY entity_id, property_name
        ORDER BY specificity DESC, rule_index DESC
    ) AS _rn
    FROM cascade_candidates WHERE comparison = 'exact'
) WHERE _rn = 1;"""
    else:
        exact_view = """
CREATE OR REPLACE VIEW _resolved_exact AS
SELECT DISTINCT ON (entity_id, property_name)
    entity_id, property_name, property_value, comparison,
    specificity, rule_index, source_file, source_line
FROM cascade_candidates
WHERE comparison = 'exact'
ORDER BY entity_id, property_name, specificity DESC, rule_index DESC;"""

    cap_view_body = """
WITH ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY entity_id, property_name
        ORDER BY CAST(property_value AS INTEGER) ASC, specificity DESC
    ) AS _rn
    FROM cascade_candidates WHERE comparison = '<='
)
SELECT entity_id, property_name, property_value, comparison,
       specificity, rule_index, source_file, source_line
FROM ranked WHERE _rn = 1"""

    if is_sqlite:
        cap_view = f"CREATE VIEW IF NOT EXISTS _resolved_cap AS\n{cap_view_body};"
    else:
        cap_view = f"CREATE OR REPLACE VIEW _resolved_cap AS\n{cap_view_body};"

    if is_sqlite:
        pattern_view = """
CREATE VIEW IF NOT EXISTS _resolved_pattern AS
WITH agg AS (
    SELECT entity_id, property_name,
        GROUP_CONCAT(DISTINCT property_value) AS property_value,
        'pattern-in' AS comparison,
        MAX(specificity) AS specificity,
        MAX(rule_index) AS rule_index
    FROM cascade_candidates WHERE comparison = 'pattern-in'
    GROUP BY entity_id, property_name
)
SELECT entity_id, property_name, property_value, comparison,
       specificity, rule_index,
       '' AS source_file, 0 AS source_line
FROM agg;"""
    else:
        pattern_view = """
CREATE OR REPLACE VIEW _resolved_pattern AS
WITH agg AS (
    SELECT entity_id, property_name,
        STRING_AGG(DISTINCT property_value, ', ' ORDER BY property_value) AS property_value,
        'pattern-in' AS comparison,
        MAX(specificity) AS specificity,
        MAX(rule_index) AS rule_index
    FROM cascade_candidates WHERE comparison = 'pattern-in'
    GROUP BY entity_id, property_name
)
SELECT entity_id, property_name, property_value, comparison,
       specificity, rule_index,
       '' AS source_file, 0 AS source_line
FROM agg;"""

    union_keyword = "UNION ALL"
    resolved_view_prefix = "CREATE VIEW IF NOT EXISTS" if is_sqlite else "CREATE OR REPLACE VIEW"

    resolved_view = f"""
{resolved_view_prefix} resolved_properties AS
SELECT * FROM _resolved_exact
{union_keyword} SELECT * FROM _resolved_cap
{union_keyword} SELECT * FROM _resolved_pattern;"""

    return "\n".join([exact_view, cap_view, pattern_view, resolved_view])
