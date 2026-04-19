"""DDL generation for the policy database schema.

Generates CREATE TABLE/INDEX statements for the policy database.
The schema structure is dialect-agnostic; only column type names
and literal syntax differ between dialects.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from umwelt.compilers.sql.dialects import Dialect

EXPECTED_TABLES = [
    "taxa",
    "entity_types",
    "property_types",
    "entities",
    "entity_closure",
    "cascade_candidates",
]


def create_schema(dialect: Dialect) -> str:
    """Generate the full DDL for the policy database."""
    is_sqlite = dialect.name == "sqlite"
    text_type = "TEXT" if is_sqlite else "VARCHAR"
    int_type = "INTEGER"
    autoincrement = (
        "INTEGER PRIMARY KEY AUTOINCREMENT"
        if is_sqlite
        else "INTEGER PRIMARY KEY DEFAULT nextval('entity_seq')"
    )

    sections = []

    # -- Vocabulary tables
    sections.append(f"""
CREATE TABLE IF NOT EXISTS taxa (
    name            {text_type} PRIMARY KEY,
    canonical       {text_type},
    vsm_system      {text_type},
    description     {text_type}
);

CREATE TABLE IF NOT EXISTS entity_types (
    name            {text_type} NOT NULL,
    taxon           {text_type} NOT NULL REFERENCES taxa(name),
    parent_type     {text_type},
    category        {text_type},
    description     {text_type},
    PRIMARY KEY (taxon, name)
);

CREATE TABLE IF NOT EXISTS property_types (
    name            {text_type} NOT NULL,
    taxon           {text_type} NOT NULL,
    entity_type     {text_type} NOT NULL,
    value_type      {text_type} NOT NULL,
    comparison      {text_type} DEFAULT 'exact',
    description     {text_type},
    PRIMARY KEY (taxon, entity_type, name),
    FOREIGN KEY (taxon, entity_type) REFERENCES entity_types(taxon, name)
);""")

    # -- Entity tables
    sections.append(f"""
CREATE TABLE IF NOT EXISTS entities (
    id              {autoincrement},
    taxon           {text_type} NOT NULL,
    type_name       {text_type} NOT NULL,
    entity_id       {text_type},
    classes         {text_type},
    attributes      {text_type},
    parent_id       {int_type} REFERENCES entities(id),
    depth           {int_type} DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_entities_taxon ON entities(taxon);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type_name);
CREATE INDEX IF NOT EXISTS idx_entities_id ON entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_entities_parent ON entities(parent_id);""")

    # -- Closure table
    sections.append(f"""
CREATE TABLE IF NOT EXISTS entity_closure (
    ancestor_id     {int_type} NOT NULL REFERENCES entities(id),
    descendant_id   {int_type} NOT NULL REFERENCES entities(id),
    depth           {int_type} NOT NULL,
    PRIMARY KEY (ancestor_id, descendant_id)
);

CREATE INDEX IF NOT EXISTS idx_closure_ancestor ON entity_closure(ancestor_id);
CREATE INDEX IF NOT EXISTS idx_closure_descendant ON entity_closure(descendant_id);""")

    # -- Cascade candidates (materialized, not a view)
    sections.append(f"""
CREATE TABLE IF NOT EXISTS cascade_candidates (
    entity_id       {int_type} NOT NULL REFERENCES entities(id),
    property_name   {text_type} NOT NULL,
    property_value  {text_type} NOT NULL,
    comparison      {text_type} NOT NULL DEFAULT 'exact',
    specificity     {text_type} NOT NULL,
    rule_index      {int_type} NOT NULL,
    source_file     {text_type},
    source_line     {int_type}
);

CREATE INDEX IF NOT EXISTS idx_candidates_entity_prop ON cascade_candidates(entity_id, property_name);
CREATE INDEX IF NOT EXISTS idx_candidates_comparison ON cascade_candidates(comparison);""")

    return "\n".join(sections)
