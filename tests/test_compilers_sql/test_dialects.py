"""Tests for SQL dialect abstraction layer."""
from __future__ import annotations

import pytest
from umwelt.compilers.sql.dialects import SQLiteDialect, DuckDBDialect


class TestSQLiteDialect:
    def setup_method(self):
        self.d = SQLiteDialect()

    def test_json_attr(self):
        result = self.d.json_attr("e", "path")
        assert result == "json_extract(e.attributes, '$.path')"

    def test_list_contains(self):
        result = self.d.list_contains("e", "classes", "implement")
        assert "json_each" in result
        assert "implement" in result

    def test_format_specificity(self):
        spec = (2, 0, 10100, 0, 0, 100, 0, 0)
        result = self.d.format_specificity(spec)
        assert result == '["00002","00000","10100","00000","00000","00100","00000","00000"]'

    def test_specificity_ordering(self):
        """Higher specificity sorts after lower when compared as strings."""
        high = self.d.format_specificity((2, 0, 10100, 0, 0, 100, 0, 0))
        low = self.d.format_specificity((1, 0, 0, 0, 0, 100, 0, 0))
        assert high > low

    def test_array_literal(self):
        result = self.d.array_literal(["implement", "tdd"])
        assert result == '["implement","tdd"]'

    def test_map_literal(self):
        result = self.d.map_literal({"path": "src/auth.py", "language": "python"})
        assert '"path":"src/auth.py"' in result
        assert '"language":"python"' in result


class TestDuckDBDialect:
    def setup_method(self):
        self.d = DuckDBDialect()

    def test_json_attr(self):
        result = self.d.json_attr("e", "path")
        assert result == "e.attributes['path']"

    def test_list_contains(self):
        result = self.d.list_contains("e", "classes", "implement")
        assert result == "list_contains(e.classes, 'implement')"

    def test_format_specificity(self):
        spec = (2, 0, 10100, 0, 0, 100, 0, 0)
        result = self.d.format_specificity(spec)
        assert result == "[2,0,10100,0,0,100,0,0]::INTEGER[]"

    def test_array_literal(self):
        result = self.d.array_literal(["implement", "tdd"])
        assert result == "['implement','tdd']"

    def test_map_literal(self):
        result = self.d.map_literal({"path": "src/auth.py"})
        assert result == "MAP{'path':'src/auth.py'}"
