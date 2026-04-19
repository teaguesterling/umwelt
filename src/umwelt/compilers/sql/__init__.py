"""SQL policy compiler — translates .umw views to SQL databases.

Public API:
  compile_to_sql(view, dialect, base_dir, source_file) -> SQL text
  compile_to_db(con, view, dialect, base_dir, source_file) -> None (mutates db)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path
    from umwelt.ast import View
    from umwelt.compilers.sql.dialects import Dialect


def compile_to_db(
    con: sqlite3.Connection,
    view: View,
    dialect: Dialect,
    base_dir: Path | None = None,
    source_file: str = "",
) -> None:
    """Compile a view into an existing database connection."""
    from umwelt.compilers.sql.compiler import compile_view
    from umwelt.compilers.sql.populate import populate_entities
    from umwelt.compilers.sql.schema import create_schema

    con.executescript(create_schema(dialect))
    if base_dir is not None:
        populate_entities(con, base_dir)
    compile_view(con, view, dialect, source_file=source_file)


def compile_to_sql(
    view: View,
    dialect: Dialect,
    base_dir: Path | None = None,
    source_file: str = "",
) -> str:
    """Compile a view to SQL text (schema + inserts + resolution views)."""
    import sqlite3 as _sqlite3
    from umwelt.compilers.sql.resolution import resolution_ddl
    from umwelt.compilers.sql.schema import create_schema

    parts = [create_schema(dialect)]
    parts.append(resolution_ddl(dialect))
    return "\n\n".join(parts)
