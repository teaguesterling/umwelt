"""SQL dialect abstraction for the policy compiler.

Each dialect provides expression helpers that abstract database-specific
syntax: JSON access, array operations, specificity encoding, and literal
formatting. The compiler builds SQL using these helpers rather than
hardcoding any dialect's syntax.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod


class Dialect(ABC):
    """Base class for SQL dialect-specific expression helpers."""

    name: str

    @abstractmethod
    def json_attr(self, alias: str, key: str) -> str:
        """Access a key from a JSON/MAP attributes column."""
        ...

    @abstractmethod
    def list_contains(self, alias: str, column: str, value: str) -> str:
        """Check if a JSON array / list column contains a value."""
        ...

    @abstractmethod
    def format_specificity(self, spec: tuple[int, ...]) -> str:
        """Format a specificity tuple as a storable/sortable literal."""
        ...

    @abstractmethod
    def array_literal(self, values: list[str]) -> str:
        """Format a list of strings as an array literal."""
        ...

    @abstractmethod
    def map_literal(self, mapping: dict[str, str]) -> str:
        """Format a dict as a MAP/JSON literal."""
        ...

    @abstractmethod
    def json_attr_list_contains(self, alias: str, key: str, value: str) -> str:
        """Check if a JSON attribute's array value contains an element."""
        ...



class SQLiteDialect(Dialect):
    name = "sqlite"

    def json_attr(self, alias: str, key: str) -> str:
        safe_key = key.replace("'", "''")
        return f"json_extract({alias}.attributes, '$.{safe_key}')"

    def list_contains(self, alias: str, column: str, value: str) -> str:
        safe_val = value.replace("'", "''")
        return (
            f"EXISTS(SELECT 1 FROM json_each({alias}.{column}) "
            f"WHERE value = '{safe_val}')"
        )

    def format_specificity(self, spec: tuple[int, ...]) -> str:
        padded = [f"{v:05d}" for v in spec]
        return json.dumps(padded, separators=(",", ":"))

    def array_literal(self, values: list[str]) -> str:
        return json.dumps(values, separators=(",", ":"))

    def map_literal(self, mapping: dict[str, str]) -> str:
        return json.dumps(mapping, separators=(",", ":"))

    def json_attr_list_contains(self, alias: str, key: str, value: str) -> str:
        safe_key = key.replace("'", "''")
        safe_val = value.replace("'", "''")
        return (
            f"EXISTS(SELECT 1 FROM json_each(json_extract({alias}.attributes, '$.{safe_key}')) "
            f"WHERE value = '{safe_val}')"
        )


class DuckDBDialect(Dialect):
    name = "duckdb"

    def json_attr(self, alias: str, key: str) -> str:
        safe_key = key.replace("'", "''")
        return f"{alias}.attributes['{safe_key}']"

    def list_contains(self, alias: str, column: str, value: str) -> str:
        safe_val = value.replace("'", "''")
        return f"list_contains({alias}.{column}, '{safe_val}')"

    def format_specificity(self, spec: tuple[int, ...]) -> str:
        return f"[{','.join(str(s) for s in spec)}]::INTEGER[]"

    def array_literal(self, values: list[str]) -> str:
        inner = ",".join(f"'{v.replace(chr(39), chr(39)*2)}'" for v in values)
        return f"[{inner}]"

    def map_literal(self, mapping: dict[str, str]) -> str:
        pairs = ",".join(
            f"'{k.replace(chr(39), chr(39)*2)}':'{v.replace(chr(39), chr(39)*2)}'"
            for k, v in mapping.items()
        )
        return f"MAP{{{pairs}}}"

    def json_attr_list_contains(self, alias: str, key: str, value: str) -> str:
        safe_key = key.replace("'", "''")
        safe_val = value.replace("'", "''")
        return f"list_contains({alias}.attributes['{safe_key}'], '{safe_val}')"


_DIALECTS: dict[str, type[Dialect]] = {
    "sqlite": SQLiteDialect,
    "duckdb": DuckDBDialect,
}


def get_dialect(name: str) -> Dialect:
    """Look up a dialect by name."""
    cls = _DIALECTS.get(name)
    if cls is None:
        available = ", ".join(sorted(_DIALECTS))
        raise ValueError(f"unknown SQL dialect {name!r}; available: {available}")
    return cls()


def register_dialect(name: str, cls: type[Dialect]) -> None:
    """Register a custom dialect."""
    _DIALECTS[name] = cls
