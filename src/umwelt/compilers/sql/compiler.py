"""Compile umwelt CSS selectors to SQL WHERE clauses.

Walks umwelt's AST (ComplexSelector, SimpleSelector, CompoundPart) and
emits SQL fragments using dialect-specific helpers. The returned strings
are valid SQL expressions for use as: SELECT e.id FROM entities e WHERE <expr>

Entry points:
  compile_selector(selector, dialect) -> SQL WHERE clause string
  compile_view(con, view, dialect, source_file) -> populates cascade_candidates
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from umwelt.ast import ComplexSelector, SimpleSelector
    from umwelt.compilers.sql.dialects import Dialect


def compile_selector(selector: ComplexSelector, dialect: Dialect) -> str:
    """Compile a ComplexSelector to a SQL WHERE clause."""
    parts = selector.parts
    if not parts:
        return "FALSE"

    target = parts[-1]
    qualifiers = parts[:-1]

    target_sql = _compile_simple(target.selector, "e", dialect)

    qualifier_clauses = []
    for i, qual in enumerate(qualifiers):
        q_alias = f"q{i}"
        is_structural = (
            qual.selector.taxon == target.selector.taxon
            and qual.mode != "context"
        )
        if is_structural:
            qualifier_clauses.append(_compile_structural_ancestor(qual.selector, q_alias, dialect))
        else:
            qualifier_clauses.append(_compile_context_qualifier(qual.selector, q_alias, dialect))

    all_clauses = [target_sql] + qualifier_clauses
    return " AND ".join(all_clauses)


def _compile_simple(simple: SimpleSelector, alias: str, dialect: Dialect) -> str:
    """Compile a SimpleSelector to SQL WHERE fragments."""
    clauses: list[str] = []

    if simple.type_name and simple.type_name != "*":
        clauses.append(f"{alias}.type_name = '{simple.type_name}'")

    if simple.id_value is not None:
        safe_id = simple.id_value.replace("'", "''")
        clauses.append(f"{alias}.entity_id = '{safe_id}'")

    for cls in simple.classes:
        clauses.append(dialect.list_contains(alias, "classes", cls))

    for attr in simple.attributes:
        clauses.append(_compile_attr_filter(attr, alias, dialect))

    for pseudo in simple.pseudo_classes:
        clause = _compile_pseudo(pseudo, alias, dialect)
        if clause:
            clauses.append(clause)

    if not clauses:
        return "TRUE"
    return " AND ".join(clauses)


def _compile_attr_filter(attr, alias: str, dialect: Dialect) -> str:
    """Compile an AttrFilter to a SQL expression."""
    col = dialect.json_attr(alias, attr.name)
    if attr.op is None:
        return f"{col} IS NOT NULL"
    safe_val = (attr.value or "").replace("'", "''")
    if attr.op == "=":
        return f"{col} = '{safe_val}'"
    if attr.op == "^=":
        return f"{col} LIKE '{safe_val}%'"
    if attr.op == "$=":
        return f"{col} LIKE '%{safe_val}'"
    if attr.op == "*=":
        return f"{col} LIKE '%{safe_val}%'"
    if attr.op == "~=":
        return (
            f"EXISTS(SELECT 1 FROM json_each(json_extract({alias}.attributes, '$.{attr.name}')) "
            f"WHERE value = '{safe_val}')"
        )
    if attr.op == "|=":
        return f"({col} = '{safe_val}' OR {col} LIKE '{safe_val}-%')"
    return "TRUE"


def _compile_pseudo(pseudo, alias: str, dialect: Dialect) -> str | None:
    """Compile a pseudo-class to a SQL expression."""
    if pseudo.name == "glob":
        pattern = (pseudo.argument or "").strip().strip("'\"")
        sql_pattern = _glob_to_like(pattern)
        col = dialect.json_attr(alias, "path")
        return f"{col} LIKE '{sql_pattern}'"
    return None


def _glob_to_like(pattern: str) -> str:
    """Convert a glob pattern to a SQL LIKE pattern."""
    result = pattern.replace("**", "\x00")
    result = result.replace("*", "%")
    result = result.replace("?", "_")
    result = result.replace("\x00", "%")
    return result.replace("'", "''")


def _compile_context_qualifier(simple: SimpleSelector, alias: str, dialect: Dialect) -> str:
    """Compile a cross-axis context qualifier to an EXISTS subquery."""
    where = _compile_simple(simple, alias, dialect)
    return f"EXISTS (SELECT 1 FROM entities {alias} WHERE {where})"


def _compile_structural_ancestor(simple: SimpleSelector, alias: str, dialect: Dialect) -> str:
    """Compile a structural-descent qualifier to a closure-table EXISTS."""
    where = _compile_simple(simple, alias, dialect)
    return (
        f"EXISTS ("
        f"SELECT 1 FROM entities {alias} "
        f"JOIN entity_closure ec ON ec.ancestor_id = {alias}.id "
        f"WHERE ec.descendant_id = e.id AND ec.depth > 0 AND {where}"
        f")"
    )
