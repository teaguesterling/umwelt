"""Tests for generic context qualifier mechanism."""
from __future__ import annotations

import sqlite3

import pytest

from umwelt.compilers.sql.dialects import SQLiteDialect
from umwelt.compilers.sql.schema import EXPECTED_TABLES, create_schema


def test_context_qualifiers_table_exists():
    dialect = SQLiteDialect()
    con = sqlite3.connect(":memory:")
    con.executescript(create_schema(dialect))
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "cascade_context_qualifiers" in tables


def test_context_qualifiers_in_expected_tables():
    assert "cascade_context_qualifiers" in EXPECTED_TABLES
